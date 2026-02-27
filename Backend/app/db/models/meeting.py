from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.timezone import now_ist


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    meeting_url = Column(String(1024), nullable=False)

    # Optional: project-linked meeting (used by /projects/{project_id}/meetings endpoints)
    project_id = Column(
        Integer,
        ForeignKey("projects.project_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(DateTime, default=now_ist, nullable=False)

    created_by = relationship("User", back_populates="created_meetings")
    project = relationship("Project", back_populates="meetings")
    participants = relationship(
        "MeetingParticipant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User", back_populates="meeting_participations")

    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_user"),
    )

