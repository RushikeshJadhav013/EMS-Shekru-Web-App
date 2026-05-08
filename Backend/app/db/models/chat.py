from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, Enum, Text, JSON
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.timezone import now_ist
from app.enums import ChatMemberRoleEnum


def get_now_ist():
    """Get current time in IST (naive) for database storage."""
    return now_ist()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    # Private: sorted user ids joined by "_"; group: UUID string
    chat_id = Column(String(255), primary_key=True, index=True)

    # Tenant scope (Option 1): company (+ optional branch)
    # NOTE: kept nullable for backward compatibility; enforced in API layer.
    company_id = Column(
        Integer,
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("company_branches.branch_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 'private' or 'group'
    chat_type = Column(String(20), nullable=False, index=True)

    # Optional display name (mainly for groups)
    name = Column(String(255), nullable=True)

    # Creator of the chat
    created_by_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime, default=get_now_ist)

    # Denormalised metadata for fast listing/sorting
    member_count = Column(Integer, nullable=True)
    last_message_at = Column(DateTime, nullable=True)

    is_deleted = Column(Boolean, default=False)

    created_by = relationship("User", back_populates="created_chat_sessions")
    members = relationship(
        "ChatMember",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages = relationship(
        "ChatMessage",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)

    chat_id = Column(
        String(255),
        ForeignKey("chat_sessions.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'member', 'admin', etc. – stored as enum
    role = Column(Enum(ChatMemberRoleEnum), nullable=False, default=ChatMemberRoleEnum.MEMBER)
    joined_at = Column(DateTime, default=get_now_ist)

    chat_session = relationship("ChatSession", back_populates="members")
    user = relationship("User", back_populates="chat_memberships")

    __table_args__ = (
        # Prevent duplicate membership rows
        Index("ix_chat_members_chat_id_user_id", "chat_id", "user_id", unique=True),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    msg_id = Column(String(36), primary_key=True)
    chat_id = Column(
        String(255),
        ForeignKey("chat_sessions.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False, default="")
    # Stored as UTC naive datetime for correct ordering and precision
    timestamp = Column(DateTime, nullable=False)
    read_by = Column(JSON, nullable=False)
    file_url = Column(String(1024), nullable=True)
    file_name = Column(String(512), nullable=True)
    file_type = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)

    chat_session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_chat_messages_chat_id_timestamp", "chat_id", "timestamp"),
    )


