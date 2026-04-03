from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.dependencies import get_current_user, require_roles
from app.db.database import get_db, SessionLocal
from app.db.models.user import User
from app.db.models.chat import ChatSession, ChatMember, ChatMessage
from app.schemas.chat_schema import (
    ChatUserSchema,
    MessageSchema,
    CreateGroupPayload,
    AddRemoveMemberPayload,
    CreateMessagePayload,
    TypingStatusPayload,
    ChatSessionSchema,
    ChangeGroupNamePayload,
    BulkMembersPayload,
    EditMessagePayload,
)
from app.services.chat_service import conversation_id
from app.realtime.socketio_app import (
    emit_chat_new_message,
    emit_chat_typing,
    emit_chat_read_receipt,
    emit_chat_message_edited,
    emit_chat_message_deleted,
)
from app.enums import RoleEnum, ChatMemberRoleEnum
from app.utils.timezone import now_ist
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/chats", tags=["Chat"])

CHAT_UPLOAD_DIR = Path("static/chat_documents")
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_CHAT_CONTENT_BYTES = 100_000
BASE64_DATA_URL_PATTERN = re.compile(r"^\s*data:[^;]+;base64,", re.IGNORECASE)


def validate_chat_content(content: Optional[str]) -> str:
    if content is None:
        return ""
    if BASE64_DATA_URL_PATTERN.match(content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content appears to be base64 data. Upload files using multipart file upload.",
        )
    content_bytes = len(content.encode("utf-8"))
    if content_bytes > MAX_CHAT_CONTENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Message content exceeds {MAX_CHAT_CONTENT_BYTES} bytes. Send large data as file attachment.",
        )
    return content


def save_chat_document(user_id: int, chat_id: str, document: UploadFile):
    if not document:
        return None, None, None, None
    timestamp = now_ist().strftime("%Y%m%d_%H%M%S")
    file_extension = Path(document.filename).suffix if document.filename else ""
    safe_chat_id = str(chat_id).replace("/", "_")
    unique_filename = f"chat_{safe_chat_id}_user_{user_id}_{timestamp}{file_extension}"
    file_path = CHAT_UPLOAD_DIR / unique_filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(document.file, buffer)
    file_url = f"/static/chat_documents/{unique_filename}"
    file_name = document.filename
    file_type = document.content_type
    file_size = file_path.stat().st_size
    return file_url, file_name, file_type, file_size


def _is_chat_member(db: Session, chat_id: str, user_id: int) -> bool:
    return (
        db.query(ChatMember)
        .filter(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        .first()
        is not None
    )


def _assert_chat_member(db: Session, chat_id: str, user_id: int) -> None:
    if not _is_chat_member(db, chat_id, user_id):
        # FastAPI/starlette uses HTTP_403_FORBIDDEN (there is no HTTP_403 constant)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this chat")


def _message_to_dict(m: ChatMessage) -> dict:
    # Store timestamp as UTC datetime in DB, but the API/Frontend expects unix-epoch seconds
    # in `timestamp` for backwards compatibility.
    time_ist = ""
    timestamp_epoch = 0.0
    try:
        if isinstance(m.timestamp, (int, float)):
            # Backward compatibility if any old rows still have float timestamps
            ts_utc = datetime.fromtimestamp(float(m.timestamp), tz=ZoneInfo("UTC"))
        else:
            # MySQL DATETIME comes back as naive datetime; treat as UTC.
            ts = m.timestamp
            if getattr(ts, "tzinfo", None) is None:
                ts_utc = ts.replace(tzinfo=ZoneInfo("UTC"))
            else:
                ts_utc = ts.astimezone(ZoneInfo("UTC"))

        ts_ist = ts_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        time_ist = ts_ist.strftime("%H:%M:%S")
        timestamp_epoch = ts_utc.timestamp()
    except Exception:
        time_ist = ""
        timestamp_epoch = 0.0

    d = {
        "id": m.msg_id,
        "sender_id": m.sender_id,
        "content": m.content or "",
        "timestamp": timestamp_epoch,
        "read_by": list(m.read_by) if m.read_by is not None else [],
        "time_ist": time_ist,
    }
    if m.file_url:
        d["file_url"] = m.file_url
        d["file_name"] = m.file_name
        d["file_type"] = m.file_type
        d["file_size"] = m.file_size
    return d


@router.get("/users", response_model=List[ChatUserSchema])
def list_chat_eligible_users(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    users = db.query(User).filter(User.user_id != current.user_id).all()
    return [
        ChatUserSchema(
            user_id=u.user_id,
            name=u.name,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
        )
        for u in users
    ]


@router.post("/private/{user_id}")
def create_or_get_private_conversation(
    user_id: int,
    current: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        target_user = db.query(User).filter(User.user_id == user_id).first()
        if not target_user:
            raise HTTPException(404, "Target user not found")

    conv_id = conversation_id(current.user_id, user_id)

    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == conv_id).first()
        if not session_obj:
            member_ids = {current.user_id, user_id}
            session_obj = ChatSession(
                chat_id=conv_id,
                chat_type="private",
                created_by_id=current.user_id,
                member_count=len(member_ids),
            )
            db.add(session_obj)
            for uid in member_ids:
                db.add(
                    ChatMember(
                        chat_id=conv_id,
                        user_id=uid,
                        role=ChatMemberRoleEnum.MEMBER,
                    )
                )
            db.commit()

    return {"chat_id": conv_id}


@router.post("/group", status_code=201)
def create_group_chat(
    payload: CreateGroupPayload,
    current: User = Depends(
        require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER)
    ),
):
    if current.user_id not in payload.member_ids:
        payload.member_ids.append(current.user_id)
    member_ids = list(set(payload.member_ids))
    group_id = str(uuid.uuid4())

    with SessionLocal() as db:
        try:
            session_obj = ChatSession(
                chat_id=group_id,
                chat_type="group",
                name=payload.name,
                created_by_id=current.user_id,
                member_count=len(member_ids),
            )
            db.add(session_obj)
            for uid in member_ids:
                role = (
                    ChatMemberRoleEnum.ADMIN
                    if uid == current.user_id
                    else ChatMemberRoleEnum.MEMBER
                )
                db.add(
                    ChatMember(
                        chat_id=group_id,
                        user_id=uid,
                        role=role,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create group chat",
            )

    return {"group_id": group_id}


@router.post("/group/{group_id}/members/add")
def add_group_member(
    group_id: str,
    payload: AddRemoveMemberPayload,
    current: User = Depends(
        require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER)
    ),
):
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id).first()
        if not session_obj:
            raise HTTPException(404, "Group not found")
        data_members = [
            r[0]
            for r in db.query(ChatMember.user_id)
            .filter(ChatMember.chat_id == group_id)
            .all()
        ]
        if payload.user_id in data_members:
            return {"members": data_members}
        db.add(
            ChatMember(
                chat_id=group_id,
                user_id=payload.user_id,
                role=ChatMemberRoleEnum.MEMBER,
            )
        )
        if session_obj.member_count is None:
            session_obj.member_count = 0
        session_obj.member_count += 1
        db.commit()
        data_members = [
            r[0]
            for r in db.query(ChatMember.user_id)
            .filter(ChatMember.chat_id == group_id)
            .all()
        ]
    return {"members": data_members}


@router.post("/group/{group_id}/members/remove")
def remove_group_member(
    group_id: str,
    payload: AddRemoveMemberPayload,
    current: User = Depends(
        require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER)
    ),
):
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id).first()
        if not session_obj:
            raise HTTPException(404, "Group not found")
        member = (
            db.query(ChatMember)
            .filter(
                ChatMember.chat_id == group_id,
                ChatMember.user_id == payload.user_id,
            )
            .first()
        )
        if member:
            db.delete(member)
            if session_obj.member_count is not None:
                session_obj.member_count = max(0, session_obj.member_count - 1)
            db.commit()
        data_members = [m.user_id for m in db.query(ChatMember).filter(ChatMember.chat_id == group_id).all()]
    return {"members": data_members}


@router.post("/{chat_type}/{chat_id}/messages")
async def send_message(
    chat_type: str,
    chat_id: str,
    payload: CreateMessagePayload,
    current: User = Depends(get_current_user),
):
    validated_content = validate_chat_content(payload.content)
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        msg_id = str(uuid.uuid4())
        ts = datetime.utcnow()  # UTC naive datetime
        row = ChatMessage(
            msg_id=msg_id,
            chat_id=chat_id,
            sender_id=current.user_id,
            content=validated_content,
            timestamp=ts,
            read_by=[current.user_id],
        )
        db.add(row)
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
        if session_obj:
            session_obj.last_message_at = now_ist()
        db.commit()
        msg = _message_to_dict(row)

    await emit_chat_new_message(chat_type, chat_id, msg)
    return msg


@router.post("/{chat_type}/{chat_id}/messages/with-file")
async def send_message_with_file(
    chat_type: str,
    chat_id: str,
    content: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    validated_content = validate_chat_content(content)
    if not validated_content and not file:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Either content or file must be provided",
        )
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        file_url, file_name, file_type, file_size = save_chat_document(
            user_id=current.user_id,
            chat_id=chat_id,
            document=file,
        )
        msg_id = str(uuid.uuid4())
        ts = datetime.utcnow()  # UTC naive datetime
        row = ChatMessage(
            msg_id=msg_id,
            chat_id=chat_id,
            sender_id=current.user_id,
            content=validated_content,
            timestamp=ts,
            read_by=[current.user_id],
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
        )
        db.add(row)
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
        if session_obj:
            session_obj.last_message_at = now_ist()
        db.commit()
        msg = _message_to_dict(row)

    await emit_chat_new_message(chat_type, chat_id, msg)
    return msg


@router.get("/{chat_type}/{chat_id}/messages", response_model=List[MessageSchema])
def fetch_messages(
    chat_type: str,
    chat_id: str,
    limit: int = Query(20, ge=1, le=100),
    before: Optional[float] = Query(None),
    current: User = Depends(get_current_user),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        q = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.timestamp.desc())
        )
        if before is not None:
            # `before` is epoch seconds; convert to UTC naive datetime
            before_dt = datetime.utcfromtimestamp(before)
            q = q.filter(ChatMessage.timestamp < before_dt)
        rows = q.limit(limit).all()

    return [_message_to_dict(m) for m in rows]


@router.post("/{chat_type}/{chat_id}/messages/{msg_id}/read")
async def mark_message_read(
    chat_type: str,
    chat_id: str,
    msg_id: str,
    current: User = Depends(get_current_user),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id, ChatMessage.msg_id == msg_id)
            .first()
        )
        if not msg:
            raise HTTPException(404, "Message not found")
        read_by = list(msg.read_by) if msg.read_by else []
        if current.user_id not in read_by:
            read_by.append(current.user_id)
            msg.read_by = read_by
            flag_modified(msg, "read_by")
            db.commit()
        else:
            read_by = list(msg.read_by) if msg.read_by else []

    await emit_chat_read_receipt(chat_type, chat_id, msg_id, read_by)
    return {"read_by": read_by}


@router.post("/{chat_type}/{chat_id}/typing")
async def typing_indicator(
    chat_type: str,
    chat_id: str,
    payload: TypingStatusPayload,
    current: User = Depends(get_current_user),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
    await emit_chat_typing(chat_type, chat_id, current.user_id, payload.is_typing)
    return {"ok": True}


@router.put("/group/{group_id}/name", status_code=200)
def change_group_name(
    group_id: str,
    payload: ChangeGroupNamePayload,
    current: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group")
            .first()
        )
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        member = (
            db.query(ChatMember)
            .filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id)
            .first()
        )
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can change name")
        session_obj.name = payload.name
        db.commit()
    return {"group_id": group_id, "name": payload.name}


@router.delete("/group/{group_id}", status_code=200)
def soft_delete_group(
    group_id: str,
    current: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group")
            .first()
        )
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        member = (
            db.query(ChatMember)
            .filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id)
            .first()
        )
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can delete the group")
        session_obj.is_deleted = True
        db.commit()
    return {"group_id": group_id, "deleted": True}


@router.post("/group/{group_id}/members/bulk_add", status_code=200)
def bulk_add_group_members(
    group_id: str,
    payload: BulkMembersPayload,
    current: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.chat_id == group_id,
                ChatSession.chat_type == "group",
                ChatSession.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        member = (
            db.query(ChatMember)
            .filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id)
            .first()
        )
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can add members")

        members_to_add = set(payload.user_ids)
        added_count = 0
        for uid in members_to_add:
            existing = (
                db.query(ChatMember)
                .filter(ChatMember.chat_id == group_id, ChatMember.user_id == uid)
                .first()
            )
            if not existing:
                db.add(ChatMember(chat_id=group_id, user_id=uid, role=ChatMemberRoleEnum.MEMBER))
                added_count += 1
        session_obj.member_count = (session_obj.member_count or 0) + added_count
        db.commit()
        new_members = [m.user_id for m in db.query(ChatMember).filter(ChatMember.chat_id == group_id).all()]
    return {"group_id": group_id, "added_count": added_count, "members": new_members}


@router.post("/group/{group_id}/members/bulk_remove", status_code=200)
def bulk_remove_group_members(
    group_id: str,
    payload: BulkMembersPayload,
    current: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.chat_id == group_id,
                ChatSession.chat_type == "group",
                ChatSession.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        member = (
            db.query(ChatMember)
            .filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id)
            .first()
        )
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can remove members")

        members_to_remove = set(payload.user_ids)
        removed_count = 0
        for uid in members_to_remove:
            cm = (
                db.query(ChatMember)
                .filter(ChatMember.chat_id == group_id, ChatMember.user_id == uid)
                .first()
            )
            if cm:
                db.delete(cm)
                removed_count += 1
        session_obj.member_count = max(0, (session_obj.member_count or 0) - removed_count)
        db.commit()
        new_members = [m.user_id for m in db.query(ChatMember).filter(ChatMember.chat_id == group_id).all()]
    return {"group_id": group_id, "removed_count": removed_count, "members": new_members}


@router.put("/{chat_type}/{chat_id}/messages/{msg_id}/edit", status_code=200)
async def edit_message(
    chat_type: str,
    chat_id: str,
    msg_id: str,
    payload: EditMessagePayload,
    current: User = Depends(get_current_user),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id, ChatMessage.msg_id == msg_id)
            .first()
        )
        if not msg:
            raise HTTPException(404, "Message not found")
        now_ts = datetime.utcnow()
        if msg.sender_id != current.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only edit your own messages")
        if (now_ts - msg.timestamp).total_seconds() > 120:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Cannot edit messages after 2 minutes of sending",
            )
        msg.content = payload.content
        db.commit()
    await emit_chat_message_edited(chat_type, chat_id, msg_id, payload.content)
    return {"msg_id": msg_id, "edited": True}


@router.delete("/{chat_type}/{chat_id}/messages/{msg_id}/delete", status_code=200)
async def delete_message(
    chat_type: str,
    chat_id: str,
    msg_id: str,
    current: User = Depends(get_current_user),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member(db, chat_id, current.user_id)
        msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_id == chat_id, ChatMessage.msg_id == msg_id)
            .first()
        )
        if not msg:
            raise HTTPException(404, "Message not found")
        now_ts = datetime.utcnow()
        if msg.sender_id != current.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own messages")
        if (now_ts - msg.timestamp).total_seconds() > 300:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Cannot delete messages after 5 minutes of sending",
            )
        db.delete(msg)
        db.commit()
    await emit_chat_message_deleted(chat_type, chat_id, msg_id)
    return {"msg_id": msg_id, "deleted": True}


@router.get("/sessions", response_model=List[ChatSessionSchema])
def list_user_chat_sessions(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .join(ChatMember, ChatMember.chat_id == ChatSession.chat_id)
        .filter(
            ChatMember.user_id == current.user_id,
            ChatSession.is_deleted == False,  # noqa: E712
        )
        .order_by(
            ChatSession.last_message_at.desc(),
            ChatSession.created_at.desc(),
        )
        .all()
    )
    return sessions
