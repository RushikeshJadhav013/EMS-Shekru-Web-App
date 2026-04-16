from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.project import Project
from app.db.models.project_member import ProjectMember
from app.db.models.user import User
from app.dependencies import get_current_user
from app.enums import RoleEnum
from app.utils.timezone import now_ist
from app.schemas.meeting_schema import (
    MeetingCreate,
    MeetingOut,
    MeetingParticipantOut,
    MeetingUpdate,
)
from app.crud.meeting_notifications_crud import create_meeting_notifications


router = APIRouter(
    prefix="/projects/{project_id}/meetings",
    tags=["Project Meetings"],
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


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _ensure_project_access(db: Session, project_id: int, current_user: User) -> None:
    if current_user.role in (RoleEnum.ADMIN, RoleEnum.HR):
        return
    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.user_id,
            ProjectMember.is_active.is_(True),
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an active member of this project to access project meetings",
        )


def _is_invited_to_project_meeting(db: Session, project_id: int, meeting_id: int, user_id: int) -> bool:
    row = (
        db.query(MeetingParticipant.id)
        .join(Meeting, MeetingParticipant.meeting_id == Meeting.id)
        .filter(
            Meeting.id == meeting_id,
            Meeting.project_id == project_id,
            MeetingParticipant.user_id == user_id,
        )
        .first()
    )
    return bool(row)


def _ensure_project_or_invited_access(
    db: Session, project_id: int, meeting_id: Optional[int], current_user: User
) -> None:
    """
    Access rule for project meetings:
    - Admin/HR: always allowed
    - Project active member: allowed
    - Otherwise: allowed only if user is invited to the specific meeting (meeting_id required)
    """
    if current_user.role in (RoleEnum.ADMIN, RoleEnum.HR):
        return

    member = (
        db.query(ProjectMember.id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.user_id,
            ProjectMember.is_active.is_(True),
        )
        .first()
    )
    if member:
        return

    if meeting_id is not None and _is_invited_to_project_meeting(
        db, project_id, meeting_id, current_user.user_id
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You must be an active project member or invited to this meeting",
    )


def _get_project_meeting_or_404(db: Session, project_id: int, meeting_id: int) -> Meeting:
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.project_id == project_id)
        .first()
    )
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project meeting not found",
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
def create_project_meeting(
    project_id: int,
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a meeting linked to a project.

    If `participant_ids` is empty, it defaults to all active project members (+ creator).
    """
    _get_project_or_404(db, project_id)
    _ensure_project_access(db, project_id, current_user)

    _validate_meeting_times(payload.start_time, payload.end_time)
    meeting = Meeting(
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        meeting_url=str(payload.meeting_url),
        created_by_id=current_user.user_id,
        project_id=project_id,
    )
    db.add(meeting)
    db.flush()

    if payload.participant_ids:
        participant_ids = list({uid for uid in payload.participant_ids if uid is not None})
    else:
        participant_ids = [
            uid
            for (uid,) in (
                db.query(ProjectMember.user_id)
                .filter(ProjectMember.project_id == project_id, ProjectMember.is_active.is_(True))
                .all()
            )
        ]

    # Always include creator
    participant_ids = list({*participant_ids, current_user.user_id})

    if participant_ids:
        users = (
            db.query(User)
            .filter(User.user_id.in_(participant_ids), User.is_active.is_(True))
            .all()
        )
        found_ids = {u.user_id for u in users}
        missing = [uid for uid in participant_ids if uid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User(s) not found or inactive: {missing}",
            )

        for uid in participant_ids:
            db.add(MeetingParticipant(meeting_id=meeting.id, user_id=uid))

    db.commit()
    db.refresh(meeting)
    start_iso = meeting.start_time.isoformat() if meeting.start_time else ""
    end_iso = meeting.end_time.isoformat() if meeting.end_time else ""
    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Project Meeting Scheduled",
        title="Meeting Scheduled",
        message=f"Project meeting '{meeting.title}' is scheduled {start_iso} - {end_iso}.",
        store_meeting_id=meeting.id,
    )
    return _serialize_meeting(db, meeting)


@router.get("/", response_model=List[MeetingOut])
def list_project_meetings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(db, project_id)
    _ensure_project_access(db, project_id, current_user)

    meetings = (
        db.query(Meeting)
        .filter(Meeting.project_id == project_id)
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return [_serialize_meeting(db, m) for m in meetings]


@router.get("/invited", response_model=List[MeetingOut])
def list_project_invited_meetings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List meetings within a project where the current user is invited (participant)
    but is NOT the creator.
    """
    _get_project_or_404(db, project_id)

    meetings = (
        db.query(Meeting)
        .join(MeetingParticipant, Meeting.id == MeetingParticipant.meeting_id)
        .filter(
            Meeting.project_id == project_id,
            MeetingParticipant.user_id == current_user.user_id,
            Meeting.created_by_id != current_user.user_id,
        )
        .order_by(Meeting.created_at.desc())
        .all()
    )

    return [_serialize_meeting(db, m) for m in meetings]


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_project_meeting(
    project_id: int,
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(db, project_id)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id)
    _ensure_project_or_invited_access(db, project_id, meeting_id, current_user)
    return _serialize_meeting(db, meeting)


@router.put("/{meeting_id}", response_model=MeetingOut)
def update_project_meeting(
    project_id: int,
    meeting_id: int,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(db, project_id)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id)
    _ensure_project_or_invited_access(db, project_id, meeting_id, current_user)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can update this project meeting",
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
        db.query(MeetingParticipant).filter(MeetingParticipant.meeting_id == meeting.id).delete()

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
    start_iso = meeting.start_time.isoformat() if meeting.start_time else ""
    end_iso = meeting.end_time.isoformat() if meeting.end_time else ""
    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Project Meeting Updated",
        title="Meeting Updated",
        message=f"Project meeting '{meeting.title}' was updated {start_iso} - {end_iso}.",
        store_meeting_id=meeting.id,
    )
    return _serialize_meeting(db, meeting)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_meeting(
    project_id: int,
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(db, project_id)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id)
    _ensure_project_or_invited_access(db, project_id, meeting_id, current_user)

    if meeting.created_by_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting creator can delete this project meeting",
        )

    create_meeting_notifications(
        db,
        meeting=meeting,
        actor=current_user,
        notification_type="Project Meeting Cancelled",
        title="Meeting Cancelled",
        message=f"Project meeting '{meeting.title}' was cancelled.",
        store_meeting_id=None,
    )
    db.delete(meeting)
    db.commit()
    return None


@router.get("/{meeting_id}/participants", response_model=List[MeetingParticipantOut])
def list_project_meeting_participants(
    project_id: int,
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_project_or_404(db, project_id)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id)
    _ensure_project_or_invited_access(db, project_id, meeting_id, current_user)

    rows = (
        db.query(MeetingParticipant, User)
        .join(User, MeetingParticipant.user_id == User.user_id)
        .filter(MeetingParticipant.meeting_id == meeting.id)
        .order_by(User.name.asc())
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

