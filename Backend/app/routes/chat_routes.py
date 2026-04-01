from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, UploadFile, File, Form
from typing import List, Optional
from firebase_admin import firestore
from app.dependencies import get_current_user, require_roles
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.db.models.user import User
from app.db.models.chat import ChatSession, ChatMember
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
from app.services.chat_service import (
    conversation_id,
    get_private_chat_ref,
    get_group_ref,
    get_message_collection,
    db,
)
from app.enums import RoleEnum, ChatMemberRoleEnum
from app.utils.timezone import now_ist
import uuid
import os
import shutil
import re
from pathlib import Path
from google.api_core.exceptions import GoogleAPICallError, RetryError, DeadlineExceeded

router = APIRouter(prefix="/chats", tags=["Chat"])


CHAT_UPLOAD_DIR = Path("static/chat_documents")
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_CHAT_CONTENT_BYTES = 100_000
BASE64_DATA_URL_PATTERN = re.compile(r"^\s*data:[^;]+;base64,", re.IGNORECASE)
FIRESTORE_TIMEOUT_SECONDS = 8


def _fs_get(doc_ref):
    try:
        return doc_ref.get(timeout=FIRESTORE_TIMEOUT_SECONDS)
    except (RetryError, DeadlineExceeded, GoogleAPICallError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service temporarily unavailable (Firestore): {e}",
        )


def _fs_set(doc_ref, payload: dict):
    try:
        doc_ref.set(payload, timeout=FIRESTORE_TIMEOUT_SECONDS)
    except (RetryError, DeadlineExceeded, GoogleAPICallError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service temporarily unavailable (Firestore): {e}",
        )


def _fs_update(doc_ref, payload: dict):
    try:
        doc_ref.update(payload, timeout=FIRESTORE_TIMEOUT_SECONDS)
    except (RetryError, DeadlineExceeded, GoogleAPICallError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service temporarily unavailable (Firestore): {e}",
        )


def _fs_delete(doc_ref):
    try:
        doc_ref.delete(timeout=FIRESTORE_TIMEOUT_SECONDS)
    except (RetryError, DeadlineExceeded, GoogleAPICallError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service temporarily unavailable (Firestore): {e}",
        )


def validate_chat_content(content: Optional[str]) -> str:
    """
    Keep message text small and block accidental base64 payloads in content.
    """
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
    """
    Save an uploaded chat document and return (file_url, file_name, file_type, file_size).
    """
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

    # Firestore: ensure private chat document exists
    chat_ref = get_private_chat_ref(conv_id)
    conv = _fs_get(chat_ref)
    if not conv.exists:
        _fs_set(chat_ref, {
                "members": [current.user_id, user_id],
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    # MySQL: ensure chat session & membership metadata exist (best-effort)
    with SessionLocal() as db:
        try:
            session_obj = (
                db.query(ChatSession).filter(ChatSession.chat_id == conv_id).first()
            )
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
                    # Ignore duplicate (chat_id, user_id) via unique index at DB level
                    db.add(
                        ChatMember(
                            chat_id=conv_id,
                            user_id=uid,
                            role=ChatMemberRoleEnum.MEMBER,
                        )
                    )
            db.commit()
        except Exception:
            db.rollback()
            # Firestore remains source of truth; do not fail the request on metadata issues

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

    # First create group document in Firestore
    _fs_set(get_group_ref(group_id), {
            "id": group_id,
            "name": payload.name,
            "members": member_ids,
            "created_by": current.user_id,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )

    # Then create metadata in MySQL (chat_sessions + chat_members)
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
            # Best-effort rollback of Firestore group document
            try:
                _fs_delete(get_group_ref(group_id))
            except Exception:
                pass
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
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group not found")

    data = group.to_dict()
    if payload.user_id not in data["members"]:
        data["members"].append(payload.user_id)
        _fs_update(group_ref, {"members": data["members"]})

        # Update MySQL metadata (best-effort)
        with SessionLocal() as db:
            try:
                session_obj = (
                    db.query(ChatSession)
                    .filter(ChatSession.chat_id == group_id)
                    .first()
                )
                if session_obj:
                    existing_member = (
                        db.query(ChatMember)
                        .filter(
                            ChatMember.chat_id == group_id,
                            ChatMember.user_id == payload.user_id,
                        )
                        .first()
                    )
                    if not existing_member:
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
            except Exception:
                db.rollback()

    return {"members": data["members"]}


@router.post("/group/{group_id}/members/remove")
def remove_group_member(
    group_id: str,
    payload: AddRemoveMemberPayload,
    current: User = Depends(
        require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER)
    ),
):
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group not found")

    data = group.to_dict()
    if payload.user_id in data["members"]:
        data["members"].remove(payload.user_id)
        _fs_update(group_ref, {"members": data["members"]})

        # Update MySQL metadata (best-effort)
        with SessionLocal() as db:
            try:
                session_obj = (
                    db.query(ChatSession)
                    .filter(ChatSession.chat_id == group_id)
                    .first()
                )
                if session_obj:
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
                            session_obj.member_count = max(
                                0, session_obj.member_count - 1
                            )
                    db.commit()
            except Exception:
                db.rollback()

    return {"members": data["members"]}


@router.post("/{chat_type}/{chat_id}/messages")
def send_message(
    chat_type: str,
    chat_id: str,
    payload: CreateMessagePayload,
    current: User = Depends(get_current_user),
):
    validated_content = validate_chat_content(payload.content)
    is_group = chat_type == "group"
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": current.user_id,
        "content": validated_content,
        "timestamp": datetime.utcnow().timestamp(),
        "read_by": [current.user_id]
    }
    col = get_message_collection(is_group, chat_id)
    if is_group:
        group = _fs_get(get_group_ref(chat_id))
        if not group.exists or current.user_id not in group.to_dict()["members"]:
            raise HTTPException(403, "Not a group member")
    else:
        priv = _fs_get(get_private_chat_ref(chat_id))
        if not priv.exists or current.user_id not in priv.to_dict()["members"]:
            raise HTTPException(403, "Not a chat member")

    # Persist message only in Firestore
    _fs_set(col.document(msg["id"]), msg)

    # Update last_message_at in MySQL metadata (best-effort, stored in IST)
    with SessionLocal() as db:
        try:
            session_obj = (
                db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
            )
            if session_obj:
                session_obj.last_message_at = now_ist()
                db.commit()
        except Exception:
            db.rollback()

    return msg


@router.post("/{chat_type}/{chat_id}/messages/with-file")
async def send_message_with_file(
    chat_type: str,
    chat_id: str,
    content: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    """
    Send a chat message with a document attachment.
    The document is stored on the server and referenced from the Firestore message.
    """
    validated_content = validate_chat_content(content)

    if not validated_content and not file:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Either content or file must be provided",
        )

    is_group = chat_type == "group"

    # Permission checks (reuse logic from send_message)
    if is_group:
        group = _fs_get(get_group_ref(chat_id))
        if not group.exists or current.user_id not in group.to_dict().get("members", []):
            raise HTTPException(403, "Not a group member")
    else:
        priv = _fs_get(get_private_chat_ref(chat_id))
        if not priv.exists or current.user_id not in priv.to_dict().get("members", []):
            raise HTTPException(403, "Not a chat member")

    # Save file to local storage
    file_url, file_name, file_type, file_size = save_chat_document(
        user_id=current.user_id,
        chat_id=chat_id,
        document=file,
    )

    col = get_message_collection(is_group, chat_id)
    msg_id = str(uuid.uuid4())
    msg = {
        "id": msg_id,
        "sender_id": current.user_id,
        "content": validated_content,
        "timestamp": datetime.utcnow().timestamp(),
        "read_by": [current.user_id],
        "file_url": file_url,
        "file_name": file_name,
        "file_type": file_type,
        "file_size": file_size,
    }

    # Persist message only in Firestore
    _fs_set(col.document(msg_id), msg)

    # Update last_message_at in MySQL metadata (best-effort, stored in IST)
    with SessionLocal() as db:
        try:
            session_obj = (
                db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
            )
            if session_obj:
                session_obj.last_message_at = now_ist()
                db.commit()
        except Exception:
            db.rollback()

    return msg

@router.get("/{chat_type}/{chat_id}/messages", response_model=List[MessageSchema])
def fetch_messages(chat_type: str, chat_id: str, limit: int = Query(20, ge=1, le=100), before: Optional[float] = Query(None), current: User = Depends(get_current_user)):
    is_group = chat_type == "group"
    col = get_message_collection(is_group, chat_id)
    q = col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
    if before:
        q = q.where("timestamp", "<", before)
    docs = q.stream()
    msgs = [doc.to_dict() for doc in docs]
    if is_group:
        group = get_group_ref(chat_id).get()
        if not group.exists or current.user_id not in group.to_dict()["members"]:
            raise HTTPException(403, "Not a group member")
    else:
        priv = get_private_chat_ref(chat_id).get()
        if not priv.exists or current.user_id not in priv.to_dict()["members"]:
            raise HTTPException(403, "Not a chat member")
    return msgs

@router.post("/{chat_type}/{chat_id}/messages/{msg_id}/read")
def mark_message_read(chat_type: str, chat_id: str, msg_id: str, current: User = Depends(get_current_user)):
    is_group = chat_type == "group"
    col = get_message_collection(is_group, chat_id)
    msg_ref = col.document(msg_id)
    msg = msg_ref.get()
    if msg.exists:
        data = msg.to_dict()
        if current.user_id not in data["read_by"]:
            data["read_by"].append(current.user_id)
            msg_ref.update({"read_by": data["read_by"]})
        return {"read_by": data["read_by"]}
    else:
        raise HTTPException(404, "Message not found")

@router.post("/{chat_type}/{chat_id}/typing")
def typing_indicator(
    chat_type: str,
    chat_id: str,
    payload: TypingStatusPayload,
    current: User = Depends(get_current_user),
):
    is_group = chat_type == "group"
    typing_collection = (
        db.collection("groups").document(chat_id).collection("typing")
        if is_group
        else db.collection("private_chats").document(chat_id).collection("typing")
    )
    typing_collection.document(str(current.user_id)).set(
        {
            "user_id": current.user_id,
            "is_typing": payload.is_typing,
            "timestamp": datetime.utcnow().timestamp(),
        }
    )
    return {"ok": True}


@router.put("/group/{group_id}/name", status_code=200)
def change_group_name(
    group_id: str,
    payload: ChangeGroupNamePayload,
    current: User = Depends(get_current_user),
):
    """
    Change the name of a group chat. Only group admin can perform this action.
    """
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group").first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")

        member = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id).first()
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can change name")

    # Update Firestore without holding MySQL connection.
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group chat (Firestore) not found")
    _fs_update(group_ref, {"name": payload.name})

    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group").first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")

        session_obj.name = payload.name
        db.commit()

    return {"group_id": group_id, "name": payload.name}

@router.delete("/group/{group_id}", status_code=200)
def soft_delete_group(
    group_id: str,
    current: User = Depends(get_current_user),
):
    """
    Soft-delete a group chat (set is_deleted=True in MySQL, mark deleted in Firestore). Only group admin can do this.
    """
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group").first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")

        member = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id).first()
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can delete the group")

    # Firestore soft-delete (mark a deleted flag in doc) without DB session held.
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group chat (Firestore) not found")
    _fs_update(group_ref, {"is_deleted": True})

    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group").first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")

        session_obj.is_deleted = True
        db.commit()

    return {"group_id": group_id, "deleted": True}

@router.post("/group/{group_id}/members/bulk_add", status_code=200)
def bulk_add_group_members(
    group_id: str,
    payload: BulkMembersPayload,
    current: User = Depends(get_current_user),
):
    """
    Add multiple members to a chat group. Only group admin can perform this action.
    """
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group", ChatSession.is_deleted == False).first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        # Check admin
        member = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id).first()
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can add members")
    members_to_add = set(payload.user_ids)
    # Sync to Firestore first
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group not found (Firestore)")
    data = group.to_dict()
    members_firestore = set(data.get("members", []))
    new_members_firestore = list(members_firestore.union(members_to_add))
    try:
        _fs_update(group_ref, {"members": new_members_firestore})
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to add members in Firestore: {e}")
    # Sync to MySQL
    with SessionLocal() as db:
        try:
            session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group", ChatSession.is_deleted == False).first()
            if not session_obj:
                raise HTTPException(404, "Group chat not found")
            added_count = 0
            for uid in members_to_add:
                existing = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == uid).first()
                if not existing:
                    db.add(ChatMember(chat_id=group_id, user_id=uid, role=ChatMemberRoleEnum.MEMBER))
                    added_count += 1
            session_obj.member_count = (session_obj.member_count or 0) + added_count
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to add members in MySQL: {e}")
    return {"group_id": group_id, "added_count": added_count, "members": new_members_firestore}

@router.post("/group/{group_id}/members/bulk_remove", status_code=200)
def bulk_remove_group_members(
    group_id: str,
    payload: BulkMembersPayload,
    current: User = Depends(get_current_user),
):
    """
    Remove multiple members from a chat group. Only group admin can perform this action.
    """
    with SessionLocal() as db:
        session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group", ChatSession.is_deleted == False).first()
        if not session_obj:
            raise HTTPException(404, "Group chat not found")
        # Check admin
        member = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == current.user_id).first()
        if not member or member.role != ChatMemberRoleEnum.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only group admin can remove members")
    members_to_remove = set(payload.user_ids)
    # Sync to Firestore first
    group_ref = get_group_ref(group_id)
    group = _fs_get(group_ref)
    if not group.exists:
        raise HTTPException(404, "Group not found (Firestore)")
    data = group.to_dict()
    members_firestore = set(data.get("members", []))
    new_members_firestore = list(members_firestore - members_to_remove)
    try:
        _fs_update(group_ref, {"members": new_members_firestore})
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to remove members in Firestore: {e}")
    # Sync to MySQL
    with SessionLocal() as db:
        try:
            session_obj = db.query(ChatSession).filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group", ChatSession.is_deleted == False).first()
            if not session_obj:
                raise HTTPException(404, "Group chat not found")
            removed_count = 0
            for uid in members_to_remove:
                cm = db.query(ChatMember).filter(ChatMember.chat_id == group_id, ChatMember.user_id == uid).first()
                if cm:
                    db.delete(cm)
                    removed_count += 1
            session_obj.member_count = max(0, (session_obj.member_count or 0) - removed_count)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to remove members in MySQL: {e}")
    return {"group_id": group_id, "removed_count": removed_count, "members": new_members_firestore}

from datetime import datetime, timedelta

@router.put("/{chat_type}/{chat_id}/messages/{msg_id}/edit", status_code=200)
def edit_message(
    chat_type: str,
    chat_id: str,
    msg_id: str,
    payload: EditMessagePayload,
    current: User = Depends(get_current_user),
):
    """
    Edit a chat message. Only sender can edit, and only within 2 minutes of sending.
    """
    is_group = chat_type == "group"
    col = get_message_collection(is_group, chat_id)
    msg_ref = col.document(msg_id)
    msg = _fs_get(msg_ref)
    if not msg.exists:
        raise HTTPException(404, "Message not found")
    data = msg.to_dict()
    now_ts = datetime.utcnow().timestamp()
    if data.get("sender_id") != current.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only edit your own messages")
    if now_ts - float(data.get("timestamp", 0)) > 120:  # 120 seconds = 2 minutes
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit messages after 2 minutes of sending")
    try:
        _fs_update(msg_ref, {"content": payload.content})
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to edit message: {e}")
    return {"msg_id": msg_id, "edited": True}


@router.delete("/{chat_type}/{chat_id}/messages/{msg_id}/delete", status_code=200)
def delete_message(
    chat_type: str,
    chat_id: str,
    msg_id: str,
    current: User = Depends(get_current_user),
):
    """
    Delete a chat message. Only sender can delete, and only within 5 minutes of sending.
    """
    is_group = chat_type == "group"
    col = get_message_collection(is_group, chat_id)
    msg_ref = col.document(msg_id)
    msg = _fs_get(msg_ref)
    if not msg.exists:
        raise HTTPException(404, "Message not found")
    data = msg.to_dict()
    now_ts = datetime.utcnow().timestamp()
    if data.get("sender_id") != current.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own messages")
    if now_ts - float(data.get("timestamp", 0)) > 300:  # 5 minutes = 300 seconds
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete messages after 5 minutes of sending")
    try:
        _fs_delete(msg_ref)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to delete message: {e}")
    return {"msg_id": msg_id, "deleted": True}

@router.get("/sessions", response_model=List[ChatSessionSchema])
def list_user_chat_sessions(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List chat sessions for the current user using MySQL metadata.
    Messages remain stored only in Firestore.
    """
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

