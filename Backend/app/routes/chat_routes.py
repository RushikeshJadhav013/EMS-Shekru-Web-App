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
from sqlalchemy import and_, or_, exists, select

from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.db.database import get_db, SessionLocal
from app.db.models.user import User
from app.db.models.company_admin_assignment import CompanyAdminAssignment
from app.db.models.branch_admin_assignment import BranchAdminAssignment
from app.db.models.chat import ChatSession, ChatMember, ChatMessage
from app.db.models.notification import ChatNotification
from app.schemas.chat_schema import (
    ChatUserSchema,
    GroupChatMemberOut,
    MessageSchema,
    CreateGroupPayload,
    AddRemoveMemberPayload,
    CreateMessagePayload,
    TypingStatusPayload,
    ChatSessionSchema,
    ChatNotificationOut,
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
from app.utils.team_lead_scope import (
    employee_can_chat_with_user,
    get_employee_project_peer_employee_ids,
    get_employee_project_team_lead_ids,
    get_team_lead_managed_employee_ids,
    team_lead_can_chat_with_user,
)
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


def _user_scope_filters(scope: dict, user_alias=User) -> list:
    """
    Tenant scope for chat: users on company/branch rows, plus admins linked via
    company_admin_assignments / branch_admin_assignments (often company_id NULL).
    """
    company_id = int(scope["company_id"])
    branch_id = scope.get("branch_id")

    direct_parts = [user_alias.company_id == company_id]
    if branch_id is not None:
        direct_parts.append(user_alias.branch_id == int(branch_id))
    direct_clause = and_(*direct_parts)

    company_admin_clause = exists(
        select(CompanyAdminAssignment.assignment_id).where(
            CompanyAdminAssignment.admin_user_id == user_alias.user_id,
            CompanyAdminAssignment.company_id == company_id,
            CompanyAdminAssignment.is_active.is_(True),
        )
    )

    scope_clauses = [direct_clause, company_admin_clause]
    if branch_id is not None:
        branch_admin_clause = exists(
            select(BranchAdminAssignment.assignment_id).where(
                BranchAdminAssignment.admin_user_id == user_alias.user_id,
                BranchAdminAssignment.branch_id == int(branch_id),
                BranchAdminAssignment.is_active.is_(True),
            )
        )
        scope_clauses.append(branch_admin_clause)

    return [or_(*scope_clauses)]


def _get_user_in_scope(db: Session, *, user_id: int, scope: dict) -> User | None:
    return (
        db.query(User)
        .filter(User.user_id == user_id, User.is_active.is_(True), *_user_scope_filters(scope))
        .first()
    )


def _assert_current_in_scope(db: Session, *, current: User, scope: dict) -> None:
    # For ADMIN users, tenant scope is assignment-based (validated inside get_tenant_scope).
    # Admin rows may not have company_id/branch_id populated, so don't enforce via users table.
    if getattr(current, "role", None) == RoleEnum.ADMIN:
        return

    if _get_user_in_scope(db, user_id=int(current.user_id), scope=scope) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is outside selected tenant scope",
        )


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


def _chat_session_scope_filters(scope: dict) -> list:
    clauses = [ChatSession.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(ChatSession.branch_id == branch_id)
    return clauses


def _assert_chat_in_scope(db: Session, *, chat_id: str, scope: dict) -> None:
    exists_in_scope = (
        db.query(ChatSession.chat_id)
        .filter(ChatSession.chat_id == chat_id, ChatSession.is_deleted == False)  # noqa: E712
        .filter(*_chat_session_scope_filters(scope))
        .first()
        is not None
    )
    if not exists_in_scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found in selected tenant scope",
        )


def _assert_chat_member_in_scope(db: Session, *, chat_id: str, current: User, scope: dict) -> None:
    _assert_current_in_scope(db, current=current, scope=scope)
    _assert_chat_member(db, chat_id, int(current.user_id))
    _assert_chat_in_scope(db, chat_id=chat_id, scope=scope)



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


def _create_chat_notifications(
    db: Session,
    *,
    chat_id: str,
    sender_id: int,
    msg_id: str,
    content: str,
    has_attachment: bool = False,
    scope: dict | None = None,
) -> None:
    if scope is not None:
        _assert_chat_in_scope(db, chat_id=chat_id, scope=scope)
    members = (
        db.query(ChatMember.user_id)
        .filter(ChatMember.chat_id == chat_id, ChatMember.user_id != sender_id)
        .all()
    )
    if not members:
        return

    sender_q = db.query(User).filter(User.user_id == sender_id)
    if scope is not None:
        sender_q = sender_q.filter(User.is_active.is_(True), *_user_scope_filters(scope))
    sender = sender_q.first()
    sender_name = sender.name if sender else "Someone"
    text_preview = (content or "").strip()
    if has_attachment and not text_preview:
        text_preview = "sent an attachment."
    elif text_preview:
        text_preview = text_preview[:117] + "..." if len(text_preview) > 120 else text_preview
    else:
        text_preview = "sent a message."

    notification_type = "new_file_message" if has_attachment else "new_message"
    title = f"New message from {sender_name}"
    message = text_preview

    for row in members:
        db.add(
            ChatNotification(
                user_id=row[0],
                chat_id=chat_id,
                msg_id=msg_id,
                sender_id=sender_id,
                notification_type=notification_type,
                title=title,
                message=message,
                is_read=False,
            )
        )


@router.get("/users", response_model=List[ChatUserSchema])
def list_chat_eligible_users(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current=current, scope=scope)
    if getattr(current, "role", None) == RoleEnum.TEAM_LEAD:
        managed_ids = get_team_lead_managed_employee_ids(
            db,
            current,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )
        team_lead_filters = [
            User.is_active.is_(True),
            User.user_id != current.user_id,
            *_user_scope_filters(scope),
        ]
        elevated_roles = [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]
        if managed_ids:
            team_lead_filters.append(
                or_(
                    User.role.in_(elevated_roles),
                    User.user_id.in_(managed_ids),
                )
            )
        else:
            team_lead_filters.append(User.role.in_(elevated_roles))
        users = db.query(User).filter(*team_lead_filters).all()
    elif getattr(current, "role", None) == RoleEnum.EMPLOYEE:
        peer_employee_ids = get_employee_project_peer_employee_ids(
            db,
            current,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )
        project_team_lead_ids = get_employee_project_team_lead_ids(
            db,
            current,
            company_id=int(scope["company_id"]),
            branch_id=scope.get("branch_id"),
        )
        allowed_clauses = [
            User.role.in_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]),
        ]
        if peer_employee_ids:
            allowed_clauses.append(
                and_(
                    User.role == RoleEnum.EMPLOYEE,
                    User.user_id.in_(peer_employee_ids),
                )
            )
        if project_team_lead_ids:
            allowed_clauses.append(
                and_(
                    User.role == RoleEnum.TEAM_LEAD,
                    User.user_id.in_(project_team_lead_ids),
                )
            )
        users = (
            db.query(User)
            .filter(
                User.is_active.is_(True),
                User.user_id != current.user_id,
                *_user_scope_filters(scope),
                or_(*allowed_clauses),
            )
            .all()
        )
    else:
        users = (
            db.query(User)
            .filter(
                User.is_active.is_(True),
                User.user_id != current.user_id,
                *_user_scope_filters(scope),
            )
            .all()
        )
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
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        target_user = _get_user_in_scope(db, user_id=int(user_id), scope=scope)
        if not target_user:
            raise HTTPException(404, "Target user not found")
        if getattr(current, "role", None) == RoleEnum.TEAM_LEAD:
            if not team_lead_can_chat_with_user(
                db,
                current,
                target_user,
                company_id=int(scope["company_id"]),
                branch_id=scope.get("branch_id"),
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You can only start chats with Admin, HR, Manager, or employees "
                        "in your department and a shared active project."
                    ),
                )
        elif getattr(current, "role", None) == RoleEnum.EMPLOYEE:
            if not employee_can_chat_with_user(
                db,
                current,
                target_user,
                company_id=int(scope["company_id"]),
                branch_id=scope.get("branch_id"),
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You can only start chats with Admin, HR, Manager, employees, "
                        "and TeamLeads on your shared active projects."
                    ),
                )

    conv_id = conversation_id(current.user_id, user_id)

    with SessionLocal() as db:
        # Enforce tenant uniqueness: if chat_id exists in a different tenant, fail fast.
        existing_any = db.query(ChatSession).filter(ChatSession.chat_id == conv_id).first()
        if existing_any and existing_any.company_id != scope["company_id"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A private chat with this id exists in a different company scope.",
            )

        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == conv_id)
            .filter(*_chat_session_scope_filters(scope))
            .first()
        )
        if not session_obj:
            member_ids = {current.user_id, user_id}
            session_obj = ChatSession(
                chat_id=conv_id,
                company_id=scope["company_id"],
                branch_id=scope.get("branch_id"),
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
    scope: dict = Depends(get_tenant_scope),
):
    if current.user_id not in payload.member_ids:
        payload.member_ids.append(current.user_id)
    member_ids = list(set(payload.member_ids))
    group_id = str(uuid.uuid4())

    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        # All members must be in tenant scope
        ids_to_check = set(member_ids)
        # Admin users can be in scope via assignments even if users.company_id/branch_id is NULL.
        # get_tenant_scope already validated the selected scope for ADMIN, so don't block on users table.
        if getattr(current, "role", None) == RoleEnum.ADMIN:
            ids_to_check.discard(int(current.user_id))

        scoped_user_ids = {
            uid
            for (uid,) in (
                db.query(User.user_id)
                .filter(User.user_id.in_(list(ids_to_check)), User.is_active.is_(True), *_user_scope_filters(scope))
                .all()
            )
        }
        if getattr(current, "role", None) == RoleEnum.ADMIN:
            scoped_user_ids.add(int(current.user_id))
        missing = [uid for uid in member_ids if uid not in scoped_user_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Some members are outside selected tenant scope: {missing}",
            )
        try:
            session_obj = ChatSession(
                chat_id=group_id,
                company_id=scope["company_id"],
                branch_id=scope.get("branch_id"),
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


@router.get("/group/{group_id}/members", response_model=List[GroupChatMemberOut])
def list_group_chat_members(
    group_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List all members of a group chat with display names.

    Any member of the group may call this (including Team Lead and Employee).
    Access is based on group membership only, not private-chat or employee-directory rules.
    """
    _assert_current_in_scope(db, current=current, scope=scope)
    session_obj = (
        db.query(ChatSession)
        .filter(
            ChatSession.chat_id == group_id,
            ChatSession.chat_type == "group",
            ChatSession.is_deleted == False,  # noqa: E712
        )
        .filter(*_chat_session_scope_filters(scope))
        .first()
    )
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group chat not found")
    _assert_chat_member(db, group_id, int(current.user_id))

    rows = (
        db.query(ChatMember, User)
        .join(User, User.user_id == ChatMember.user_id)
        .filter(ChatMember.chat_id == group_id)
        .order_by(User.name.asc())
        .all()
    )
    return [
        GroupChatMemberOut(
            user_id=user.user_id,
            name=user.name or "",
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            group_role=member.role,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.post("/group/{group_id}/members/add")
def add_group_member(
    group_id: str,
    payload: AddRemoveMemberPayload,
    current: User = Depends(
        require_roles(RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER)
    ),
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id)
            .filter(*_chat_session_scope_filters(scope))
            .first()
        )
        if not session_obj:
            raise HTTPException(404, "Group not found")
        # Only allow adding users in scope
        if _get_user_in_scope(db, user_id=int(payload.user_id), scope=scope) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is outside selected tenant scope")
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
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id)
            .filter(*_chat_session_scope_filters(scope))
            .first()
        )
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
    scope: dict = Depends(get_tenant_scope),
):
    validated_content = validate_chat_content(payload.content)
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
        # Ensure parent message row exists before child chat_notifications inserts.
        db.flush()
        _create_chat_notifications(
            db,
            chat_id=chat_id,
            sender_id=current.user_id,
            msg_id=msg_id,
            content=validated_content,
            has_attachment=False,
            scope=scope,
        )
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
    scope: dict = Depends(get_tenant_scope),
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
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
        # Ensure parent message row exists before child chat_notifications inserts.
        db.flush()
        _create_chat_notifications(
            db,
            chat_id=chat_id,
            sender_id=current.user_id,
            msg_id=msg_id,
            content=validated_content,
            has_attachment=True,
            scope=scope,
        )
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
    scope: dict = Depends(get_tenant_scope),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
    scope: dict = Depends(get_tenant_scope),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")

    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
    scope: dict = Depends(get_tenant_scope),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
    await emit_chat_typing(chat_type, chat_id, current.user_id, payload.is_typing)
    return {"ok": True}


@router.put("/group/{group_id}/name", status_code=200)
def change_group_name(
    group_id: str,
    payload: ChangeGroupNamePayload,
    current: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group")
            .filter(*_chat_session_scope_filters(scope))
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
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(ChatSession.chat_id == group_id, ChatSession.chat_type == "group")
            .filter(*_chat_session_scope_filters(scope))
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
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.chat_id == group_id,
                ChatSession.chat_type == "group",
                ChatSession.is_deleted == False,  # noqa: E712
            )
            .filter(*_chat_session_scope_filters(scope))
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
        # Restrict additions to tenant-scoped users only
        scoped_add_ids = {
            uid
            for (uid,) in db.query(User.user_id)
            .filter(User.user_id.in_(members_to_add), User.is_active.is_(True), *_user_scope_filters(scope))
            .all()
        }
        missing = [uid for uid in members_to_add if uid not in scoped_add_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Some members are outside selected tenant scope: {missing}",
            )
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
    scope: dict = Depends(get_tenant_scope),
):
    with SessionLocal() as db:
        _assert_current_in_scope(db, current=current, scope=scope)
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.chat_id == group_id,
                ChatSession.chat_type == "group",
                ChatSession.is_deleted == False,  # noqa: E712
            )
            .filter(*_chat_session_scope_filters(scope))
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
    scope: dict = Depends(get_tenant_scope),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
    scope: dict = Depends(get_tenant_scope),
):
    if chat_type not in ("group", "private"):
        raise HTTPException(400, "Invalid chat_type")
    with SessionLocal() as db:
        _assert_chat_member_in_scope(db, chat_id=chat_id, current=current, scope=scope)
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
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current=current, scope=scope)
    sessions = (
        db.query(ChatSession)
        .join(ChatMember, ChatMember.chat_id == ChatSession.chat_id)
        .filter(
            ChatMember.user_id == current.user_id,
            ChatSession.is_deleted == False,  # noqa: E712
        )
        .filter(*_chat_session_scope_filters(scope))
        .order_by(
            ChatSession.last_message_at.desc(),
            ChatSession.created_at.desc(),
        )
        .all()
    )
    return sessions


@router.get("/notifications", response_model=List[ChatNotificationOut])
def list_chat_notifications(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current=current, scope=scope)
    return (
        db.query(ChatNotification)
        .filter(ChatNotification.user_id == current.user_id)
        .join(ChatSession, ChatSession.chat_id == ChatNotification.chat_id)
        .filter(ChatSession.is_deleted == False)  # noqa: E712
        .filter(*_chat_session_scope_filters(scope))
        .order_by(ChatNotification.created_at.desc())
        .all()
    )


@router.put("/notifications/{notification_id}/read", response_model=ChatNotificationOut)
def mark_chat_notification_read(
    notification_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current=current, scope=scope)
    notification = (
        db.query(ChatNotification)
        .filter(
            ChatNotification.notification_id == notification_id,
            ChatNotification.user_id == current.user_id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)

    return notification
