from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, date
from app.schemas.interview_schema import (
    InterviewCreate,
    InterviewUpdate,
    InterviewOut,
    InterviewOutBasic,
    InterviewStatusOnlyUpdate,
)
from app.db.database import get_db
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.db.models.interview import Interview
from app.db.models.hiring import Vacancy, Candidate
from app.db.models.user import User
import json

router = APIRouter(
    prefix="/interviews",
    tags=["Interview Management"],
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))]
)

# Allowed status transitions (target statuses from each source status).
_INTERVIEW_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"completed", "cancelled", "no_show"},
    "rescheduled": {"completed", "cancelled", "no_show"},
    "cancelled": {"rescheduled"},
    "no_show": {"rescheduled"},
    "completed": set(),
}


def _validate_interview_status_transition(current_status: str, new_status: str) -> None:
    """Raise HTTP 400 when a status change is not permitted."""
    if current_status == new_status:
        return
    allowed = _INTERVIEW_STATUS_TRANSITIONS.get(current_status)
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown interview status '{current_status}'.",
        )
    if new_status not in allowed:
        if current_status == "completed":
            detail = "Cannot change status of a completed interview."
        elif current_status == "scheduled" and new_status == "rescheduled":
            detail = (
                "Cannot change status from 'scheduled' to 'rescheduled'. "
                "Update interview times instead, or cancel and create a new interview."
            )
        elif current_status in ("cancelled", "no_show"):
            detail = (
                f"Cannot change status from '{current_status}' to '{new_status}'. "
                f"'{current_status}' interviews can only be rescheduled."
            )
        elif current_status == "rescheduled":
            detail = (
                f"Cannot change status from 'rescheduled' to '{new_status}'. "
                "Allowed targets: completed, cancelled, no_show."
            )
        else:
            allowed_list = ", ".join(sorted(allowed)) if allowed else "none"
            detail = (
                f"Cannot change status from '{current_status}' to '{new_status}'. "
                f"Allowed targets: {allowed_list}."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _interview_scope_query(db: Session, scope: dict):
    q = (
        db.query(Interview)
        .join(Vacancy, Vacancy.vacancy_id == Interview.vacancy_id)
        .filter(Vacancy.company_id == int(scope["company_id"]))
    )
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        q = q.join(User, User.user_id == Vacancy.created_by).filter(
            User.branch_id == int(branch_id)
        )
    return q


def _candidate_in_scope(db: Session, scope: dict, candidate_id: int) -> Candidate | None:
    q = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id,
        Candidate.company_id == int(scope["company_id"]),
    )
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        q = (
            q.join(Vacancy, Vacancy.vacancy_id == Candidate.vacancy_id)
            .join(User, User.user_id == Vacancy.created_by)
            .filter(User.branch_id == int(branch_id))
        )
    return q.first()


def _vacancy_in_scope(db: Session, scope: dict, vacancy_id: int) -> Vacancy | None:
    q = db.query(Vacancy).filter(
        Vacancy.vacancy_id == vacancy_id,
        Vacancy.company_id == int(scope["company_id"]),
    )
    branch_id = scope.get("branch_id")
    if branch_id is not None:
        q = q.join(User, User.user_id == Vacancy.created_by).filter(
            User.branch_id == int(branch_id)
        )
    return q.first()


@router.post("/", response_model=InterviewOutBasic, status_code=status.HTTP_201_CREATED)
def schedule_interview(
    interview_data: InterviewCreate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Schedule a new interview for a candidate."""
    # Verify candidate exists
    candidate = _candidate_in_scope(db, scope, interview_data.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Verify vacancy exists
    vacancy = _vacancy_in_scope(db, scope, interview_data.vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Verify candidate belongs to the vacancy
    if candidate.vacancy_id != interview_data.vacancy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate does not belong to the specified vacancy"
        )
    
    # Validate end_time is after start_time if both provided
    if interview_data.end_time and interview_data.start_time:
        if interview_data.end_time <= interview_data.start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be after start time"
            )
    
    # Optional: Check for overlapping interviews for the same candidate
    overlapping = _interview_scope_query(db, scope).filter(
        and_(
            Interview.candidate_id == interview_data.candidate_id,
            Interview.status != 'cancelled',
            or_(
                and_(
                    Interview.start_time <= interview_data.start_time,
                    Interview.end_time > interview_data.start_time
                ),
                and_(
                    Interview.start_time < interview_data.end_time if interview_data.end_time else datetime.max,
                    Interview.start_time >= interview_data.start_time
                )
            )
        )
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate already has an interview scheduled at this time (Interview ID: {overlapping.interview_id})"
        )
    
    # Serialize panel_members to JSON string
    panel_members_json = None
    if interview_data.panel_members:
        panel_members_json = json.dumps(interview_data.panel_members)
    
    # Create interview
    db_interview = Interview(
        candidate_id=interview_data.candidate_id,
        vacancy_id=interview_data.vacancy_id,
        scheduled_by=current_user.user_id,
        start_time=interview_data.start_time,
        end_time=interview_data.end_time,
        mode=interview_data.mode,
        location=interview_data.location,
        round_type=interview_data.round_type,
        panel_members=panel_members_json,
        status="scheduled"
    )
    
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    
    # Build response with denormalized data
    result = InterviewOutBasic.model_validate(db_interview)
    result.candidate_name = candidate.name
    result.vacancy_title = vacancy.title
    result.vacancy_department = vacancy.department
    
    return result


@router.get("/", response_model=List[InterviewOutBasic])
def get_interviews(
    candidate_id: Optional[int] = None,
    vacancy_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all interviews with optional filters."""
    query = _interview_scope_query(db, scope)
    
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    
    if vacancy_id:
        query = query.filter(Interview.vacancy_id == vacancy_id)
    
    if status_filter:
        query = query.filter(Interview.status == status_filter)
    
    if from_date:
        query = query.filter(func.date(Interview.start_time) >= from_date)
    
    if to_date:
        query = query.filter(func.date(Interview.start_time) <= to_date)
    
    # Order by start_time ascending (upcoming first)
    interviews = query.order_by(Interview.start_time.asc()).all()
    
    result = []
    for interview in interviews:
        candidate = db.query(Candidate).filter(Candidate.candidate_id == interview.candidate_id).first()
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == interview.vacancy_id).first()
        
        interview_out = InterviewOutBasic.model_validate(interview)
        if candidate:
            interview_out.candidate_name = candidate.name
        if vacancy:
            interview_out.vacancy_title = vacancy.title
            interview_out.vacancy_department = vacancy.department
        
        result.append(interview_out)
    
    return result


@router.get("/{interview_id}", response_model=InterviewOutBasic)
def get_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get a specific interview by ID."""
    interview = _interview_scope_query(db, scope).filter(Interview.interview_id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    candidate = _candidate_in_scope(db, scope, interview.candidate_id)
    vacancy = _vacancy_in_scope(db, scope, interview.vacancy_id)
    
    result = InterviewOutBasic.model_validate(interview)
    if candidate:
        result.candidate_name = candidate.name
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result


@router.put("/{interview_id}", response_model=InterviewOut)
def update_interview(
    interview_id: int,
    interview_update: InterviewUpdate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update interview details (reschedule, change location, etc.)."""
    interview = _interview_scope_query(db, scope).filter(Interview.interview_id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Prevent updating cancelled or completed interviews (unless changing status)
    if interview.status in ['cancelled', 'completed'] and not interview_update.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update interview with status '{interview.status}'. Use status update endpoint to change status."
        )
    
    # Validate end_time is after start_time if both are being updated
    start_time = interview_update.start_time if interview_update.start_time else interview.start_time
    end_time = interview_update.end_time if interview_update.end_time else interview.end_time
    
    if end_time and start_time:
        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be after start time"
            )
    
    # Update fields
    update_data = interview_update.model_dump(exclude_unset=True)

    if "status" in update_data:
        _validate_interview_status_transition(interview.status, update_data["status"])
    
    # Handle panel_members serialization
    if 'panel_members' in update_data and update_data['panel_members'] is not None:
        update_data['panel_members'] = json.dumps(update_data['panel_members'])
    
    for field, value in update_data.items():
        setattr(interview, field, value)
    
    interview.updated_at = datetime.now()
    db.commit()
    db.refresh(interview)
    
    candidate = _candidate_in_scope(db, scope, interview.candidate_id)
    vacancy = _vacancy_in_scope(db, scope, interview.vacancy_id)
    
    result = InterviewOut.model_validate(interview)
    if candidate:
        result.candidate_name = candidate.name
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result


@router.put("/{interview_id}/status", response_model=InterviewOut)
def update_interview_status(
    interview_id: int,
    status_update: InterviewStatusOnlyUpdate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update interview status with feedback and rating."""
    interview = _interview_scope_query(db, scope).filter(Interview.interview_id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    _validate_interview_status_transition(interview.status, status_update.status)

    # Update status only
    interview.status = status_update.status
    
    interview.updated_at = datetime.now()
    db.commit()
    db.refresh(interview)
    
    candidate = _candidate_in_scope(db, scope, interview.candidate_id)
    vacancy = _vacancy_in_scope(db, scope, interview.vacancy_id)
    
    result = InterviewOut.model_validate(interview)
    if candidate:
        result.candidate_name = candidate.name
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Delete an interview."""
    interview = _interview_scope_query(db, scope).filter(Interview.interview_id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    db.delete(interview)
    db.commit()
    return None


# Additional convenience endpoints

@router.get("/candidates/{candidate_id}/interviews", response_model=List[InterviewOut])
def get_candidate_interviews(
    candidate_id: int,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all interviews for a specific candidate."""
    candidate = _candidate_in_scope(db, scope, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    query = _interview_scope_query(db, scope).filter(Interview.candidate_id == candidate_id)
    
    if status_filter:
        query = query.filter(Interview.status == status_filter)
    
    interviews = query.order_by(Interview.start_time.asc()).all()
    
    result = []
    vacancy = _vacancy_in_scope(db, scope, candidate.vacancy_id)
    
    for interview in interviews:
        interview_out = InterviewOut.model_validate(interview)
        interview_out.candidate_name = candidate.name
        if vacancy:
            interview_out.vacancy_title = vacancy.title
            interview_out.vacancy_department = vacancy.department
        result.append(interview_out)
    
    return result


@router.get("/vacancies/{vacancy_id}/interviews", response_model=List[InterviewOut])
def get_vacancy_interviews(
    vacancy_id: int,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all interviews for a specific vacancy."""
    vacancy = _vacancy_in_scope(db, scope, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    query = _interview_scope_query(db, scope).filter(Interview.vacancy_id == vacancy_id)
    
    if status_filter:
        query = query.filter(Interview.status == status_filter)
    
    interviews = query.order_by(Interview.start_time.asc()).all()
    
    result = []
    for interview in interviews:
        candidate = _candidate_in_scope(db, scope, interview.candidate_id)
        
        interview_out = InterviewOut.model_validate(interview)
        if candidate:
            interview_out.candidate_name = candidate.name
        interview_out.vacancy_title = vacancy.title
        interview_out.vacancy_department = vacancy.department
        result.append(interview_out)
    
    return result
