from pydantic import BaseModel, Field, constr, field_validator
from typing import List, Optional
from datetime import datetime

class ChatUserSchema(BaseModel):
    user_id: int
    name: str
    role: str

class MessageSchema(BaseModel):
    id: str
    sender_id: int
    content: str
    timestamp: float
    read_by: Optional[List[int]] = []

class CreateMessagePayload(BaseModel):
    content: constr(strip_whitespace=True, min_length=1)

class EditMessagePayload(BaseModel):
    content: constr(strip_whitespace=True, min_length=1)

class CreateGroupPayload(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    member_ids: List[int]

class AddRemoveMemberPayload(BaseModel):
    user_id: int

class BulkMembersPayload(BaseModel):
    user_ids: List[int]

class TypingStatusPayload(BaseModel):
    is_typing: bool

class ChatMemberSchema(BaseModel):
    user_id: int
    role: str
    joined_at: Optional[datetime] = None

    @field_validator("role", mode="before")
    def _coerce_role(cls, v):
        # Accept enum or plain string; return its string value
        if hasattr(v, "value"):
            return v.value
        return str(v)

    class Config:
        from_attributes = True

class ChatSessionSchema(BaseModel):
    chat_id: str
    chat_type: str
    name: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    member_count: Optional[int] = None
    last_message_at: Optional[datetime] = None
    members: List[ChatMemberSchema] = []

    class Config:
        from_attributes = True

class ChangeGroupNamePayload(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
