"""
Socket.IO server for realtime chat (typing, new messages, read receipts).
JWT in handshake auth matches REST: Authorization: Bearer <token> semantics.

Uses AsyncServer with async_mode='asgi' (required for Uvicorn/ASGI). The sync
socketio.Server class does not support async_mode='asgi'.
"""
import socketio
from jose import jwt, JWTError

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models.user import User


def _chat_room(chat_type: str, chat_id: str) -> str:
    return f"{chat_type}:{chat_id}"


def _parse_socket_token(token: str):
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    email = payload.get("sub")
    if not email:
        raise JWTError("Missing sub in token")
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            raise JWTError("User not found or inactive")
        db.expunge(user)
    return user


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ, auth):
    if not isinstance(auth, dict):
        return False
    token = auth.get("token")
    if not token:
        return False
    try:
        user = _parse_socket_token(token)
    except JWTError:
        return False
    await sio.save_session(sid, {"user_id": user.user_id, "email": user.email})
    return True


@sio.event
async def disconnect(sid):
    return


@sio.on("chat:join")
async def chat_join(sid, data):
    session = await sio.get_session(sid)
    if not session:
        return {"ok": False, "error": "Not authenticated"}
    chat_type = data.get("chat_type")
    chat_id = str(data.get("chat_id", ""))
    if chat_type not in ("group", "private"):
        return {"ok": False, "error": "Invalid chat_type"}
    room = _chat_room(chat_type, chat_id)
    await sio.enter_room(sid, room)
    return {"ok": True, "room": room}


@sio.on("chat:typing")
async def chat_typing_socket(sid, data):
    session = await sio.get_session(sid)
    if not session:
        return
    chat_type = data.get("chat_type")
    chat_id = str(data.get("chat_id", ""))
    if chat_type not in ("group", "private"):
        return
    room = _chat_room(chat_type, chat_id)
    await sio.emit(
        "chat:typing",
        {
            "user_id": session["user_id"],
            "chat_type": chat_type,
            "chat_id": chat_id,
            "is_typing": bool(data.get("is_typing")),
        },
        room=room,
    )


async def emit_chat_new_message(chat_type: str, chat_id: str, msg: dict) -> None:
    room = _chat_room(chat_type, chat_id)
    await sio.emit("chat:new_message", msg, room=room)


async def emit_chat_typing(chat_type: str, chat_id: str, user_id: int, is_typing: bool) -> None:
    room = _chat_room(chat_type, chat_id)
    await sio.emit(
        "chat:typing",
        {
            "user_id": user_id,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "is_typing": is_typing,
        },
        room=room,
    )


async def emit_chat_read_receipt(chat_type: str, chat_id: str, msg_id: str, read_by: list) -> None:
    room = _chat_room(chat_type, chat_id)
    await sio.emit(
        "chat:read_receipt",
        {"msg_id": msg_id, "read_by": read_by},
        room=room,
    )


async def emit_chat_message_edited(chat_type: str, chat_id: str, msg_id: str, content: str) -> None:
    room = _chat_room(chat_type, chat_id)
    await sio.emit(
        "chat:message_edited",
        {"id": msg_id, "content": content},
        room=room,
    )


async def emit_chat_message_deleted(chat_type: str, chat_id: str, msg_id: str) -> None:
    room = _chat_room(chat_type, chat_id)
    await sio.emit("chat:message_deleted", {"id": msg_id}, room=room)


socket_app = socketio.ASGIApp(sio, socketio_path="socket.io")
