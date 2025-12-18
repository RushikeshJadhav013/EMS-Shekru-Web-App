from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from typing import List, Optional
from firebase_admin import firestore
from app.dependencies import get_current_user, require_roles
from sqlalchemy.orm import Session
from app.db.database import get_db
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
import datetime

router = APIRouter(prefix="/chats", tags=["Chat"])


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
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
        )
        for u in users
    ]


@router.post("/private/{user_id}")
def create_or_get_private_conversation(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(404, "Target user not found")

    conv_id = conversation_id(current.user_id, user_id)

    # Firestore: ensure private chat document exists
    chat_ref = get_private_chat_ref(conv_id)
    conv = chat_ref.get()
    if not conv.exists:
        chat_ref.set(
            {
                "members": [current.user_id, user_id],
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    # MySQL: ensure chat session & membership metadata exist (best-effort)
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
    db: Session = Depends(get_db),
):
    if current.user_id not in payload.member_ids:
        payload.member_ids.append(current.user_id)

    member_ids = list(set(payload.member_ids))
    group_id = str(uuid.uuid4())

    # First create group document in Firestore
    get_group_ref(group_id).set(
        {
            "id": group_id,
            "name": payload.name,
            "members": member_ids,
            "created_by": current.user_id,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )

    # Then create metadata in MySQL (chat_sessions + chat_members)
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
            get_group_ref(group_id).delete()
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
    db: Session = Depends(get_db),
):
    group_ref = get_group_ref(group_id)
    group = group_ref.get()
    if not group.exists:
        raise HTTPException(404, "Group not found")

    data = group.to_dict()
    if payload.user_id not in data["members"]:
        data["members"].append(payload.user_id)
        group_ref.update({"members": data["members"]})

        # Update MySQL metadata (best-effort)
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
    db: Session = Depends(get_db),
):
    group_ref = get_group_ref(group_id)
    group = group_ref.get()
    if not group.exists:
        raise HTTPException(404, "Group not found")

    data = group.to_dict()
    if payload.user_id in data["members"]:
        data["members"].remove(payload.user_id)
        group_ref.update({"members": data["members"]})

        # Update MySQL metadata (best-effort)
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
    db: Session = Depends(get_db),
):
    is_group = chat_type == "group"
    msg = {
        "id": str(uuid.uuid4()),
        "sender_id": current.user_id,
        "content": payload.content,
        "timestamp": datetime.datetime.utcnow().timestamp(),
        "read_by": [current.user_id]
    }
    col = get_message_collection(is_group, chat_id)
    if is_group:
        group = get_group_ref(chat_id).get()
        if not group.exists or current.user_id not in group.to_dict()["members"]:
            raise HTTPException(403, "Not a group member")
    else:
        priv = get_private_chat_ref(chat_id).get()
        if not priv.exists or current.user_id not in priv.to_dict()["members"]:
            raise HTTPException(403, "Not a chat member")

    # Persist message only in Firestore
    col.document(msg["id"]).set(msg)

    # Update last_message_at in MySQL metadata (best-effort, stored in IST)
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
            "timestamp": datetime.datetime.utcnow().timestamp(),
        }
    )
    return {"ok": True}


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

