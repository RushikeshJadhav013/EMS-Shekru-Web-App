from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.meeting import Meeting, MeetingParticipant
from app.db.models.project import Project
from app.db.models.project_member import ProjectMember
from app.db.models.user import User
from app.dependencies import get_current_user
from app.enums import RoleEnum
from app.schemas.meeting_schema import MeetingCreate, MeetingOut, MeetingParticipantOut


router = APIRouter(
    prefix="/projects/{project_id}/meetings",
    tags=["Project Meetings"],
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

