from pydantic import BaseModel, Field, constr
from typing import List, Optional
from datetime import datetime

class ChatUserSchema(BaseModel):
    user_id: int
    name: str
    email: str
    role: str

class MessageSchema(BaseModel):
    id: str
    sender_id: int
    content: str
    timestamp: float
    read_by: Optional[List[int]] = []

class CreateMessagePayload(BaseModel):
    content: constr(strip_whitespace=True, min_length=1)

class CreateGroupPayload(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    member_ids: List[int]

class AddRemoveMemberPayload(BaseModel):
    user_id: int

class TypingStatusPayload(BaseModel):
    is_typing: bool

