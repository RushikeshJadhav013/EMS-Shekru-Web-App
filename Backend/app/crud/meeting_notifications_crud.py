from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.notification import MeetingNotification
from app.db.models.user import User


def _get_meeting_participants(
    db: Session, *, meeting_id: int, exclude_user_id: Optional[int]
) -> List[User]:
    q = (
        db.query(User)
        .join(MeetingParticipant, MeetingParticipant.user_id == User.user_id)
        .filter(
            MeetingParticipant.meeting_id == meeting_id,
            User.is_active.is_(True),
        )
    )
    if exclude_user_id is not None:
        q = q.filter(User.user_id != exclude_user_id)
    return q.all()


def create_meeting_notifications(
    db: Session,
    *,
    meeting: Meeting,
    actor: User,
    notification_type: str,
    title: str,
    message: str,
    store_meeting_id: Optional[int] = None,
) -> List[MeetingNotification]:
    """
    Create notifications for all meeting participants except the actor.

    `store_meeting_id` is used for deletions where we want notifications to persist
    even after the meeting row is removed (set to None in that case).
    """
    meeting_id_to_query = meeting.id
    recipients = _get_meeting_participants(
        db, meeting_id=meeting_id_to_query, exclude_user_id=actor.user_id
    )
    if not recipients:
        return []

    notifications: List[MeetingNotification] = []
    for recipient in recipients:
        notification = MeetingNotification(
            user_id=recipient.user_id,
            meeting_id=store_meeting_id,
            notification_type=notification_type,
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    db.commit()
    for notification in notifications:
        db.refresh(notification)

    return notifications


def list_meeting_notifications(db: Session, user_id: int) -> List[MeetingNotification]:
    return (
        db.query(MeetingNotification)
        .filter(MeetingNotification.user_id == user_id)
        .order_by(MeetingNotification.created_at.desc())
        .all()
    )


def mark_meeting_notification_as_read(
    db: Session, *, notification_id: int, user_id: int
) -> Optional[MeetingNotification]:
    notification = (
        db.query(MeetingNotification)
        .filter(
            MeetingNotification.notification_id == notification_id,
            MeetingNotification.user_id == user_id,
        )
        .first()
    )
    if not notification:
        return None
    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification

