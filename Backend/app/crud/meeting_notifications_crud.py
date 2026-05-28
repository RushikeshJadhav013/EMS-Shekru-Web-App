from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.notification import MeetingNotification
from app.db.models.user import User
from app.enums import RoleEnum


def _user_scope_filters(*, company_id: int | None, branch_id: int | None, user_alias=User) -> list:
    clauses = []
    if company_id is not None:
        clauses.append(user_alias.company_id == company_id)
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _meeting_row_scope_clauses(MeetingAlias, scope: dict) -> list:
    clauses = [MeetingAlias.company_id == scope["company_id"]]
    if scope.get("branch_id") is not None:
        clauses.append(MeetingAlias.branch_id == scope["branch_id"])
    return clauses


def _get_meeting_participants(
    db: Session,
    *,
    meeting_id: int,
    exclude_user_id: Optional[int],
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[User]:
    q = (
        db.query(User)
        .join(MeetingParticipant, MeetingParticipant.user_id == User.user_id)
        .filter(
            MeetingParticipant.meeting_id == meeting_id,
            User.is_active.is_(True),
        )
    )
    if company_id is not None or branch_id is not None:
        q = q.filter(
            or_(
                User.role == RoleEnum.ADMIN,
                *_user_scope_filters(company_id=company_id, branch_id=branch_id),
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
    company_id: int | None = None,
    branch_id: int | None = None,
) -> List[MeetingNotification]:
    """
    Create notifications for all meeting participants except the actor.

    `store_meeting_id` is used for deletions where we want notifications to persist
    even after the meeting row is removed (set to None in that case).
    """
    meeting_id_to_query = meeting.id
    recipients = _get_meeting_participants(
        db,
        meeting_id=meeting_id_to_query,
        exclude_user_id=actor.user_id,
        company_id=company_id,
        branch_id=branch_id,
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


def list_meeting_notifications(
    db: Session, user_id: int, *, scope: dict | None = None
) -> List[MeetingNotification]:
    q = db.query(MeetingNotification).filter(MeetingNotification.user_id == user_id)
    if scope is not None:
        Mt = aliased(Meeting)
        q = q.outerjoin(Mt, MeetingNotification.meeting_id == Mt.id).filter(
            or_(
                MeetingNotification.meeting_id.is_(None),
                and_(Mt.id.isnot(None), *_meeting_row_scope_clauses(Mt, scope)),
            )
        )
    return q.order_by(MeetingNotification.created_at.desc()).all()


def mark_meeting_notification_as_read(
    db: Session,
    *,
    notification_id: int,
    user_id: int,
    scope: dict | None = None,
) -> Optional[MeetingNotification]:
    q = db.query(MeetingNotification).filter(
        MeetingNotification.notification_id == notification_id,
        MeetingNotification.user_id == user_id,
    )
    if scope is not None:
        Mt = aliased(Meeting)
        q = q.outerjoin(Mt, MeetingNotification.meeting_id == Mt.id).filter(
            or_(
                MeetingNotification.meeting_id.is_(None),
                and_(Mt.id.isnot(None), *_meeting_row_scope_clauses(Mt, scope)),
            )
        )
    notification = q.first()
    if not notification:
        return None
    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification
