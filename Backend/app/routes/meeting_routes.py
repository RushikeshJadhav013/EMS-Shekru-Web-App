from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.notification import MeetingNotification
from app.db.models.user import User
from app.dependencies import get_current_user
from app.utils.timezone import now_ist
from app.schemas.meeting_schema import (
    MeetingCreate,
    MeetingOut,
    MeetingParticipantOut,
    MeetingUpdate,
    MeetingParticipantsAdd,
    MeetingNotificationOut,
)
from app.crud.meeting_notifications_crud import (
    create_meeting_notifications,
    list_meeting_notifications,
    mark_meeting_notification_as_read as mark_meeting_notification_as_read_crud,
)


router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
)

def _normalize_for_compare(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def _validate_meeting_times(start_time, end_time) -> None:
    """
    Business rules:
    - start_time cannot be in the past
    - end_time cannot be earlier than start_time
    """
    normalized_start_time = _normalize_for_compare(start_time)
    normalized_end_time = _normalize_for_compare(end_time)

    if normalized_start_time is not None and normalized_start_time < now_ist():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time cannot be a backdated date/time",
        )
    if (
        normalized_start_time is not None
        and normalized_end_time is not None
        and normalized_end_time < normalized_start_time
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time cannot be earlier than start_time",
        )


def _get_meeting_or_404(db: Session, meeting_id: int) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    return meeting


def _serialize_meeting(db: Session, meeting: Meeting) -> MeetingOut:
    rows = (
        db.query(MeetingParticipant, User)
        .join(User, MeetingParticipant.user_id == User.user_id)
        .filter(MeetingParticipant.meeting_id == meeting.id)
        .all()
    )

    participants: List[MeetingParticipantOut] = []
    for mp, user in rows:
        participants.append(
            MeetingParticipantOut(
                id=mp.id,
                user_id=mp.user_id,
                user_name=user.name,
            )
        )

    return MeetingOut(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        meeting_url=meeting.meeting_url,
        created_by_id=meeting.created_by_id,
        created_by_name=meeting.created_by.name if meeting.created_by else None,
        created_at=meeting.created_at,
        participants=participants,
    )


@router.post("/", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a meeting with an existing Google Meet / Zoom URL."""
    _validate_meeting_times(payload.start_time, payload.end_time)
    meeting = Meeting(
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        meeting_url=str(payload.meeting_url),
        created_by_id=current_user.user_id,
    )
    db.add(meeting)
    db.flush()

    if payload.participant_ids:
        user_ids = list({uid for uid in payload.participant_ids if uid is not None})
        users = (
            db.query(User)
            .filter(User.user_id.in_(user_ids), User.is_active.is_(True))
            .all()
        )
        found_ids = {u.user_id for u in users}
        missing = [uid for uid in user_ids if uid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User(s) not found or inactive: {missing}",
            )

        for uid in user_ids:
            db.add(MeetingParticipant(meeting_id=meeting.id, user_id=uid))

    db.commit()
    db.refresh(meeting)
    start_iso = meeting.start_time.isoformat() if meeting.start_time else ""
    end_iso = meeting.end_time.isoformat() if meeting.end_time else ""
    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Meeting Scheduled",
        title="Meeting Scheduled",
        message=f"Meeting '{meeting.title}' is scheduled {start_iso} - {end_iso}.",
        store_meeting_id=meeting.id,
    )
    return _serialize_meeting(db, meeting)


@router.get("/", response_model=List[MeetingOut])
def list_my_meetings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    as_creator: bool = Query(
        True,
        description=(
            "If true, list meetings I created; "
            "if false, list meetings where I'm a participant."
        ),
    ),
):
    if as_creator:
        meetings = (
            db.query(Meeting)
            .filter(Meeting.created_by_id == current_user.user_id)
            .order_by(Meeting.created_at.desc())
            .all()
        )
    else:
        meetings = (
            db.query(Meeting)
            .join(MeetingParticipant, Meeting.id == MeetingParticipant.meeting_id)
            .filter(MeetingParticipant.user_id == current_user.user_id)
            .order_by(Meeting.created_at.desc())
            .all()
        )

    return [_serialize_meeting(db, m) for m in meetings]


@router.get("/{meeting_id:int}", response_model=MeetingOut)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)
    return _serialize_meeting(db, meeting)


@router.put("/{meeting_id:int}", response_model=MeetingOut)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can update this meeting",
        )

    data = payload.model_dump(exclude_unset=True)
    participant_ids = data.pop("participant_ids", None)

    effective_start_time = data.get("start_time", meeting.start_time)
    effective_end_time = data.get("end_time", meeting.end_time)
    _validate_meeting_times(effective_start_time, effective_end_time)

    for field, value in data.items():
        if field == "meeting_url" and value is not None:
            setattr(meeting, field, str(value))
        else:
            setattr(meeting, field, value)

    if participant_ids is not None:
        db.query(MeetingParticipant).filter(
            MeetingParticipant.meeting_id == meeting.id
        ).delete()

        user_ids = list({uid for uid in participant_ids if uid is not None})
        if user_ids:
            users = (
                db.query(User)
                .filter(User.user_id.in_(user_ids), User.is_active.is_(True))
                .all()
            )
            found_ids = {u.user_id for u in users}
            missing = [uid for uid in user_ids if uid not in found_ids]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User(s) not found or inactive: {missing}",
                )
            for uid in user_ids:
                db.add(MeetingParticipant(meeting_id=meeting.id, user_id=uid))

    db.commit()
    db.refresh(meeting)
    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Meeting Updated",
        title="Meeting Updated",
        message=f"Meeting '{meeting.title}' was updated.",
        store_meeting_id=meeting.id,
    )
    return _serialize_meeting(db, meeting)


@router.post(
    "/{meeting_id}/participants",
    response_model=List[MeetingParticipantOut],
    status_code=status.HTTP_201_CREATED,
)
def add_meeting_participants(
    meeting_id: int,
    payload: MeetingParticipantsAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can add participants",
        )

    user_ids = list({uid for uid in payload.user_ids if uid is not None})
    if not user_ids:
        return []

    users = (
        db.query(User)
        .filter(User.user_id.in_(user_ids), User.is_active.is_(True))
        .all()
    )
    found_ids = {u.user_id for u in users}
    missing = [uid for uid in user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User(s) not found or inactive: {missing}",
        )

    existing = (
        db.query(MeetingParticipant)
        .filter(
            MeetingParticipant.meeting_id == meeting.id,
            MeetingParticipant.user_id.in_(user_ids),
        )
        .all()
    )
    existing_ids = {mp.user_id for mp in existing}

    for uid in user_ids:
        if uid in existing_ids:
            continue
        db.add(MeetingParticipant(meeting_id=meeting.id, user_id=uid))

    db.commit()

    new_user_ids = [uid for uid in user_ids if uid not in existing_ids and uid != current_user.user_id]
    if new_user_ids:
        start_iso = meeting.start_time.isoformat() if meeting.start_time else ""
        end_iso = meeting.end_time.isoformat() if meeting.end_time else ""
        message = (
            f"You were added to meeting '{meeting.title}'"
            + (f" ({start_iso} - {end_iso})" if start_iso or end_iso else "")
            + "."
        )
        for uid in new_user_ids:
            db.add(
                MeetingNotification(
                    user_id=uid,
                    meeting_id=meeting.id,
                    notification_type="Meeting Participant Added",
                    title="Added To Meeting",
                    message=message,
                    is_read=False,
                )
            )
        db.commit()

    rows = (
        db.query(MeetingParticipant, User)
        .join(User, MeetingParticipant.user_id == User.user_id)
        .filter(MeetingParticipant.meeting_id == meeting.id)
        .all()
    )
    return [
        MeetingParticipantOut(
            id=mp.id,
            user_id=mp.user_id,
            user_name=user.name,
        )
        for mp, user in rows
    ]


@router.delete(
    "/{meeting_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_meeting_participant(
    meeting_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can remove participants",
        )

    mp = (
        db.query(MeetingParticipant)
        .filter(
            MeetingParticipant.meeting_id == meeting.id,
            MeetingParticipant.user_id == user_id,
        )
        .first()
    )
    if not mp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found for this meeting",
        )

    db.delete(mp)
    db.commit()
    if user_id != current_user.user_id:
        start_iso = meeting.start_time.isoformat() if meeting.start_time else ""
        end_iso = meeting.end_time.isoformat() if meeting.end_time else ""
        message = (
            f"You were removed from meeting '{meeting.title}'"
            + (f" ({start_iso} - {end_iso})" if start_iso or end_iso else "")
            + "."
        )
        db.add(
            MeetingNotification(
                user_id=user_id,
                meeting_id=meeting.id,
                notification_type="Meeting Participant Removed",
                title="Removed From Meeting",
                message=message,
                is_read=False,
            )
        )
        db.commit()
    return None


@router.delete("/{meeting_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can delete this meeting",
        )

    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Meeting Cancelled",
        title="Meeting Cancelled",
        message=f"Meeting '{meeting.title}' was cancelled.",
        store_meeting_id=None,
    )
    db.delete(meeting)
    db.commit()
    return None


@router.get("/notifications", response_model=List[MeetingNotificationOut])
def get_meeting_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_meeting_notifications(db, current_user.user_id)


@router.put("/notifications/{notification_id}/read", response_model=MeetingNotificationOut)
def mark_meeting_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = mark_meeting_notification_as_read_crud(
        db,
        notification_id=notification_id,
        user_id=current_user.user_id,
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification

