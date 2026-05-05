from datetime import datetime
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.interview import Interview
from app.db.models.interview_feedback import InterviewFeedback
from app.db.models.user import User
from app.db.models.hiring import Vacancy
from app.dependencies import get_current_user, get_tenant_scope
from app.enums import RoleEnum
from app.schemas.interview_feedback_schema import (
    InterviewFeedbackCreate,
    InterviewFeedbackUpdate,
    InterviewFeedbackOut,
)


router = APIRouter(
    prefix="/interviews",
    tags=["Interview Feedback Management"],
)


def _interview_in_scope(db: Session, scope: dict, interview_id: int) -> Interview | None:
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    q = (
        db.query(Interview)
        .join(Vacancy, Vacancy.vacancy_id == Interview.vacancy_id)
        .join(User, User.user_id == Vacancy.created_by)
        .filter(Interview.interview_id == interview_id, User.company_id == company_id)
    )
    if branch_id is not None:
        q = q.filter(User.branch_id == branch_id)
    return q.first()


def _feedback_in_scope(db: Session, scope: dict, interview_id: int, feedback_id: int) -> InterviewFeedback | None:
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    q = (
        db.query(InterviewFeedback)
        .join(Interview, Interview.interview_id == InterviewFeedback.interview_id)
        .join(Vacancy, Vacancy.vacancy_id == Interview.vacancy_id)
        .join(User, User.user_id == Vacancy.created_by)
        .filter(
            InterviewFeedback.id == feedback_id,
            InterviewFeedback.interview_id == interview_id,
            User.company_id == company_id,
        )
    )
    if branch_id is not None:
        q = q.filter(User.branch_id == branch_id)
    return q.first()


def _user_can_access_feedback(current_user: User, interview: Interview) -> bool:
    """Check if user can view feedback for a given interview."""
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
        return True

    # Allow panel members to access their interviews
    panel_members: list[int] = []
    if interview.panel_members:
        try:
            loaded = json.loads(interview.panel_members)
            if isinstance(loaded, list):
                panel_members = [int(x) for x in loaded]
        except (ValueError, TypeError):
            panel_members = []

    return current_user.user_id in panel_members or current_user.user_id == interview.scheduled_by


def _user_can_modify_feedback(current_user: User, feedback: InterviewFeedback) -> bool:
    """Check if user can update/delete a feedback entry."""
    if current_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
        return True
    return current_user.user_id == feedback.panel_member_id


@router.post("/{interview_id}/feedback", response_model=InterviewFeedbackOut, status_code=status.HTTP_201_CREATED)
def create_interview_feedback(
    interview_id: int,
    feedback_in: InterviewFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Submit feedback for an interview (panel member or HR/Admin)."""
    interview = _interview_in_scope(db, scope, interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    if not _user_can_access_feedback(current_user, interview):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to submit feedback for this interview",
        )

    # Optional: prevent duplicate feedback from same user for same interview
    existing = (
        db.query(InterviewFeedback)
        .filter(
            InterviewFeedback.interview_id == interview_id,
            InterviewFeedback.panel_member_id == current_user.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback already submitted for this interview by the current user",
        )

    feedback = InterviewFeedback(
        interview_id=interview_id,
        panel_member_id=current_user.user_id,
        feedback_summary=feedback_in.feedback_summary,
        rating=feedback_in.rating,
        strengths=feedback_in.strengths,
        weaknesses=feedback_in.weaknesses,
        recommendation=feedback_in.recommendation,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Build response with denormalized panel member info
    out = InterviewFeedbackOut.model_validate(feedback)
    out.panel_member_name = current_user.name
    out.panel_member_role = current_user.role

    return out


@router.get("/{interview_id}/feedback", response_model=List[InterviewFeedbackOut])
def list_interview_feedback(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get all feedback entries for an interview."""
    interview = _interview_in_scope(db, scope, interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    if not _user_can_access_feedback(current_user, interview):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view feedback for this interview",
        )

    q = (
        db.query(InterviewFeedback)
        .join(Interview, Interview.interview_id == InterviewFeedback.interview_id)
        .join(Vacancy, Vacancy.vacancy_id == Interview.vacancy_id)
        .join(User, User.user_id == Vacancy.created_by)
        .filter(
            InterviewFeedback.interview_id == interview_id,
            User.company_id == scope.get("company_id"),
        )
        .order_by(InterviewFeedback.created_at.asc())
    )
    if scope.get("branch_id") is not None:
        q = q.filter(User.branch_id == scope.get("branch_id"))
    feedback_list = q.all()

    # Preload panel member info to avoid repeated queries
    user_ids = {fb.panel_member_id for fb in feedback_list}
    users = (
        db.query(User)
        .filter(User.user_id.in_(user_ids))
        .all()
    )
    user_by_id = {u.user_id: u for u in users}

    results: List[InterviewFeedbackOut] = []
    for fb in feedback_list:
        out = InterviewFeedbackOut.model_validate(fb)
        user = user_by_id.get(fb.panel_member_id)
        if user:
            out.panel_member_name = user.name
            out.panel_member_role = user.role
        results.append(out)

    return results


@router.get("/{interview_id}/feedback/{feedback_id}", response_model=InterviewFeedbackOut)
def get_interview_feedback(
    interview_id: int,
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get a single feedback entry for an interview."""
    feedback = _feedback_in_scope(db, scope, interview_id, feedback_id)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    interview = _interview_in_scope(db, scope, interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    if not _user_can_access_feedback(current_user, interview):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this feedback",
        )

    out = InterviewFeedbackOut.model_validate(feedback)
    user = db.query(User).filter(User.user_id == feedback.panel_member_id).first()
    if user:
        out.panel_member_name = user.name
        out.panel_member_role = user.role

    return out


@router.put("/{interview_id}/feedback/{feedback_id}", response_model=InterviewFeedbackOut)
def update_interview_feedback(
    interview_id: int,
    feedback_id: int,
    feedback_in: InterviewFeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Update an existing feedback entry."""
    feedback = _feedback_in_scope(db, scope, interview_id, feedback_id)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    if not _user_can_modify_feedback(current_user, feedback):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to modify this feedback",
        )

    update_data = feedback_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feedback, field, value)

    db.commit()
    db.refresh(feedback)

    out = InterviewFeedbackOut.model_validate(feedback)
    user = db.query(User).filter(User.user_id == feedback.panel_member_id).first()
    if user:
        out.panel_member_name = user.name
        out.panel_member_role = user.role

    return out


@router.delete("/{interview_id}/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview_feedback(
    interview_id: int,
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Delete a feedback entry."""
    feedback = _feedback_in_scope(db, scope, interview_id, feedback_id)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    if not _user_can_modify_feedback(current_user, feedback):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this feedback",
        )

    db.delete(feedback)
    db.commit()

    return None

