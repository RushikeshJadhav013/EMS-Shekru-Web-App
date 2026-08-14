from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.project import Project
from app.db.models.project_member import ProjectMember
from app.db.models.user import User
from app.dependencies import get_current_user, get_tenant_scope
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


def _user_scope_filters(scope: dict, user_alias=User) -> list:
    clauses = [user_alias.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(user_alias.branch_id == branch_id)
    return clauses


def _assert_current_in_scope(db: Session, current_user: User, scope: dict) -> None:
    if current_user.role == RoleEnum.ADMIN:
        # Admin tenant access is assignment-based and validated by get_tenant_scope.
        return
    current = (
        db.query(User.user_id)
        .filter(User.user_id == current_user.user_id, User.is_active.is_(True), *_user_scope_filters(scope))
        .first()
    )
    if not current:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user is outside selected tenant scope",
        )


def _project_in_scope_clause(scope: dict):
    clauses = [Project.company_id == scope["company_id"]]
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        clauses.append(Project.branch_id == branch_id)
    return clauses

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


def _get_project_or_404(db: Session, project_id: int, *, scope: dict) -> Project:
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id)
        .filter(*_project_in_scope_clause(scope))
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _ensure_project_access(db: Session, project_id: int, current_user: User) -> None:
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


def _validate_project_member_participants(
    db: Session, project_id: int, user_ids: list[int]
) -> None:
    if not user_ids:
        return
    rows = (
        db.query(ProjectMember.user_id)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id.in_(user_ids),
            ProjectMember.is_active.is_(True),
        )
        .all()
    )
    allowed = {uid for (uid,) in rows}
    invalid = [uid for uid in user_ids if uid not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User(s) are not active members of this project: {invalid}",
        )


def _validate_project_meeting_participants(
    db: Session,
    project_id: int,
    user_ids: list[int],
    scope: dict,
    current_user: User,
) -> None:
    if not user_ids:
        return
    _validate_project_member_participants(db, project_id, user_ids)
    users = (
        db.query(User)
        .filter(User.user_id.in_(user_ids), User.is_active.is_(True), *_user_scope_filters(scope))
        .all()
    )
    found_ids = {u.user_id for u in users}
    if current_user.role == RoleEnum.ADMIN and current_user.user_id in user_ids:
        found_ids.add(current_user.user_id)
    missing = [uid for uid in user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User(s) not found or inactive: {missing}",
        )


def _meeting_scope_filters(scope: dict) -> list:
    clauses = [Meeting.company_id == scope["company_id"]]
    if scope.get("branch_id") is not None:
        clauses.append(Meeting.branch_id == scope["branch_id"])
    return clauses


def _get_project_meeting_or_404(db: Session, project_id: int, meeting_id: int, *, scope: dict) -> Meeting:
    meeting = (
        db.query(Meeting)
        .filter(
            Meeting.id == meeting_id,
            Meeting.project_id == project_id,
            *_meeting_scope_filters(scope),
        )
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
    scope: dict = Depends(get_tenant_scope),
):
    """
    Create a meeting linked to a project.

    Requires the creator to be an active project member (all roles).
    If `participant_ids` is empty, it defaults to all active project members.
    Explicit participants must also be active project members.
    """
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
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
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
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

    # Always include creator (must be a project member via _ensure_project_access)
    participant_ids = list({*participant_ids, current_user.user_id})
    _validate_project_meeting_participants(
        db, project_id, participant_ids, scope, current_user
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
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    return _serialize_meeting(db, meeting)


@router.get("/", response_model=List[MeetingOut])
def list_project_meetings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)

    meetings = (
        db.query(Meeting)
        .filter(Meeting.project_id == project_id, *_meeting_scope_filters(scope))
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return [_serialize_meeting(db, m) for m in meetings]


@router.get("/invited", response_model=List[MeetingOut])
def list_project_invited_meetings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """
    List meetings within a project where the current user is invited (participant)
    but is NOT the creator.
    """
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)

    meetings = (
        db.query(Meeting)
        .join(MeetingParticipant, Meeting.id == MeetingParticipant.meeting_id)
        .filter(
            Meeting.project_id == project_id,
            *_meeting_scope_filters(scope),
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
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)
    return _serialize_meeting(db, meeting)


@router.put("/{meeting_id}", response_model=MeetingOut)
def update_project_meeting(
    project_id: int,
    meeting_id: int,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)

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
            _validate_project_meeting_participants(
                db, project_id, user_ids, scope, current_user
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
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    return _serialize_meeting(db, meeting)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_meeting(
    project_id: int,
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)

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
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
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
    scope: dict = Depends(get_tenant_scope),
):
    _assert_current_in_scope(db, current_user, scope)
    _get_project_or_404(db, project_id, scope=scope)
    meeting = _get_project_meeting_or_404(db, project_id, meeting_id, scope=scope)
    _ensure_project_access(db, project_id, current_user)

    rows = (
        db.query(MeetingParticipant, User)
        .join(User, MeetingParticipant.user_id == User.user_id)
        .filter(MeetingParticipant.meeting_id == meeting.id, *_user_scope_filters(scope))
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

