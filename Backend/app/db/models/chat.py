from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, Enum
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.timezone import now_ist
from app.enums import ChatMemberRoleEnum


def get_now_ist():
    """Get current time in IST (naive) for database storage."""
    return now_ist()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    # Use Firestore conversation/group ID as primary key
    chat_id = Column(String(255), primary_key=True, index=True)

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

    # Soft-delete flag for hiding chats without removing Firestore data
    is_deleted = Column(Boolean, default=False)

    created_by = relationship("User", back_populates="created_chat_sessions")
    members = relationship(
        "ChatMember",
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


