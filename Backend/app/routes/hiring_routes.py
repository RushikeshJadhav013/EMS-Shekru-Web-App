from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from app.schemas.hiring_schema import (
    VacancyCreate,
    VacancyUpdate,
    VacancyOut,
    CandidateCreate,
    CandidateUpdate,
    CandidateOut,
    CandidateOutNoInterview,
    SocialMediaPost,
    CandidateShortlist,
    CandidateStatusUpdate,
)
from app.db.database import get_db
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.enums import RoleEnum
from app.db.models.hiring import Vacancy, Candidate
from app.db.models.interview import Interview
from app.db.models.user import User
from app.schemas.interview_schema import InterviewCreate
from datetime import datetime, timedelta
import json
import os

router = APIRouter(
    prefix="/hiring",
    tags=["Hiring Management"],
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))]
)


def _vacancy_scope_query(db: Session, scope: dict):
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    q = db.query(Vacancy).join(User, User.user_id == Vacancy.created_by)
    q = q.filter(User.company_id == company_id)
    if branch_id is not None:
        q = q.filter(User.branch_id == branch_id)
    return q


def _candidate_scope_query(db: Session, scope: dict):
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    q = (
        db.query(Candidate)
        .join(Vacancy, Vacancy.vacancy_id == Candidate.vacancy_id)
        .join(User, User.user_id == Vacancy.created_by)
        .filter(User.company_id == company_id)
    )
    if branch_id is not None:
        q = q.filter(User.branch_id == branch_id)
    return q


def _interview_scope_query(db: Session, scope: dict):
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    q = (
        db.query(Interview)
        .join(Vacancy, Vacancy.vacancy_id == Interview.vacancy_id)
        .join(User, User.user_id == Vacancy.created_by)
        .filter(User.company_id == company_id)
    )
    if branch_id is not None:
        q = q.filter(User.branch_id == branch_id)
    return q


# Interview records that count toward offer/hire (excludes cancelled / no_show-only paths).
_QUALIFYING_INTERVIEW_STATUSES = ("scheduled", "rescheduled", "completed")


def _candidate_has_qualifying_interview(db: Session, scope: dict, candidate_id: int) -> bool:
    return (
        _interview_scope_query(db, scope)
        .filter(
            Interview.candidate_id == candidate_id,
            Interview.status.in_(_QUALIFYING_INTERVIEW_STATUSES),
        )
        .first()
        is not None
    )


# Vacancy Routes

@router.post("/vacancies", response_model=VacancyOut, status_code=status.HTTP_201_CREATED)
def create_vacancy(
    vacancy: VacancyCreate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Create a new vacancy."""
    
    db_vacancy = Vacancy(
        **vacancy.model_dump(),
        created_by=current_user.user_id
    )
    db.add(db_vacancy)
    db.commit()
    db.refresh(db_vacancy)
    
    # Get candidates count
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == db_vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(
        db_vacancy,
        context={"skip_closing_date_validation": True},
    )
    result.candidates_count = candidates_count
    return result

@router.get("/vacancies", response_model=List[VacancyOut])
def get_vacancies(
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all vacancies."""
    query = _vacancy_scope_query(db, scope)
    
    if department:
        query = query.filter(Vacancy.department == department)
    
    if status_filter:
        query = query.filter(Vacancy.status == status_filter)
    
    vacancies = query.order_by(Vacancy.created_at.desc()).all()
    
    result = []
    for vacancy in vacancies:
        candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
            Candidate.vacancy_id == vacancy.vacancy_id
        ).scalar() or 0
        
        vacancy_out = VacancyOut.model_validate(
            vacancy,
            context={"skip_closing_date_validation": True},
        )
        vacancy_out.candidates_count = candidates_count
        result.append(vacancy_out)
    
    return result

@router.get("/vacancies/{vacancy_id}", response_model=VacancyOut)
def get_vacancy(
    vacancy_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get a specific vacancy."""
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(
        vacancy,
        context={"skip_closing_date_validation": True},
    )
    result.candidates_count = candidates_count
    return result

@router.put("/vacancies/{vacancy_id}", response_model=VacancyOut)
def update_vacancy(
    vacancy_id: int,
    vacancy_update: VacancyUpdate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update a vacancy."""
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    update_data = vacancy_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vacancy, field, value)
    
    vacancy.updated_at = datetime.now()
    db.commit()
    db.refresh(vacancy)
    
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(
        vacancy,
        context={"skip_closing_date_validation": True},
    )
    result.candidates_count = candidates_count
    return result

@router.delete("/vacancies/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vacancy(
    vacancy_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Delete a vacancy."""
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    db.delete(vacancy)
    db.commit()
    return None

@router.post("/vacancies/{vacancy_id}/post-social", response_model=VacancyOut)
def post_to_social_media(
    vacancy_id: int,
    post_data: SocialMediaPost,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Post vacancy to social media platforms."""
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Update posting status
    if "linkedin" in post_data.platforms:
        vacancy.posted_on_linkedin = True
    if "naukri" in post_data.platforms:
        vacancy.posted_on_naukri = True
    if "indeed" in post_data.platforms:
        vacancy.posted_on_indeed = True
    if "other" in post_data.platforms:
        vacancy.posted_on_other = True
    
    # Store links
    if post_data.links:
        existing_links = {}
        if vacancy.social_media_links:
            try:
                existing_links = json.loads(vacancy.social_media_links)
            except:
                pass
        existing_links.update(post_data.links)
        vacancy.social_media_links = json.dumps(existing_links)
    
    vacancy.updated_at = datetime.now()
    db.commit()
    db.refresh(vacancy)
    
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(
        vacancy,
        context={"skip_closing_date_validation": True},
    )
    result.candidates_count = candidates_count
    return result

# Candidate Routes

@router.post("/candidates", response_model=CandidateOutNoInterview, status_code=status.HTTP_201_CREATED)
def create_candidate(
    vacancy_id: int = Form(..., description="Vacancy ID"),
    name: str = Form(..., description="Candidate name"),
    email: str = Form(..., description="Candidate email"),
    phone: Optional[str] = Form(None, description="Phone number"),
    cover_letter: Optional[str] = Form(None, description="Cover letter"),
    experience_years: Optional[int] = Form(None, description="Years of experience"),
    current_company: Optional[str] = Form(None, description="Current company"),
    current_position: Optional[str] = Form(None, description="Current position"),
    expected_salary: Optional[str] = Form(None, description="Expected salary"),
    notice_period: Optional[str] = Form(None, description="Notice period"),
    source: Optional[str] = Form(None, description="Application source"),
    resume_url: Optional[str] = Form(None, description="Resume URL (if already hosted)"),
    resume: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Create a new candidate application."""
    # Build data dict and validate using CandidateCreate to reuse all schema rules
    candidate_data = {
        "vacancy_id": vacancy_id,
        "name": name,
        "email": email,
        "phone": phone,
        "cover_letter": cover_letter,
        "experience_years": experience_years,
        "current_company": current_company,
        "current_position": current_position,
        "expected_salary": expected_salary,
        "notice_period": notice_period,
        "source": source,
        "resume_url": resume_url,
    }

    try:
        candidate_obj = CandidateCreate(**candidate_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid candidate data: {str(e)}"
        )
    
    # Enforce unique phone number (if provided)
    if candidate_obj.phone:
        existing_phone = (
            db.query(Candidate)
            .filter(Candidate.phone == candidate_obj.phone)
            .first()
        )
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A candidate with this phone number already exists"
            )

    # Enforce unique email
    existing_email = (
        db.query(Candidate)
        .filter(Candidate.email == candidate_obj.email)
        .first()
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A candidate with this email already exists"
        )
    
    # Verify vacancy exists
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == candidate_obj.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Handle resume upload
    final_resume_url = candidate_obj.resume_url
    if resume:
        # Save resume file (simplified - in production, use proper file storage)
        upload_dir = "uploads/resumes"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = f"{upload_dir}/{candidate_obj.vacancy_id}_{candidate_obj.email}_{resume.filename}"
        with open(file_path, "wb") as buffer:
            content = resume.file.read()
            buffer.write(content)
        final_resume_url = f"/{file_path}"
    
    db_candidate = Candidate(
        **candidate_obj.model_dump(exclude={"resume_url"}),
        resume_url=final_resume_url,
        status="applied"
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    result = CandidateOutNoInterview.model_validate(db_candidate)
    result.vacancy_title = vacancy.title
    result.vacancy_department = vacancy.department
    return result

@router.get("/candidates", response_model=List[CandidateOutNoInterview])
def get_candidates(
    vacancy_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all candidates."""
    query = _candidate_scope_query(db, scope)
    
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    if status_filter:
        query = query.filter(Candidate.status == status_filter)
    
    candidates = query.order_by(Candidate.applied_at.desc()).all()
    
    result = []
    for candidate in candidates:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        candidate_out = CandidateOutNoInterview.model_validate(candidate)
        
        if vacancy:
            candidate_out.vacancy_title = vacancy.title
            candidate_out.vacancy_department = vacancy.department
        
        result.append(candidate_out)
    
    return result

@router.get("/candidates/shortlisted", response_model=List[CandidateOut])
def get_shortlisted_candidates(
    vacancy_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get all shortlisted candidates (status='interview'). Optionally filter by vacancy_id."""
    query = _candidate_scope_query(db, scope).filter(Candidate.status == 'interview')
    
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    # Get candidates and their next upcoming interview
    candidates = query.order_by(Candidate.applied_at.desc()).all()
    
    result = []
    for candidate in candidates:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        
        # Get next upcoming interview for this candidate
        next_interview = db.query(Interview).filter(
            and_(
                Interview.candidate_id == candidate.candidate_id,
                Interview.status.in_(['scheduled', 'rescheduled'])
            )
        ).order_by(Interview.start_time.asc()).first()
        
        candidate_out = CandidateOut.model_validate(candidate)
        if vacancy:
            candidate_out.vacancy_title = vacancy.title
            candidate_out.vacancy_department = vacancy.department
        
        # Set interview_date from interviews table if available (for backward compatibility)
        if next_interview:
            candidate_out.interview_date = next_interview.start_time
        
        result.append(candidate_out)
    
    # Sort by next interview date (upcoming first)
    result.sort(key=lambda x: (x.interview_date is None, x.interview_date or datetime.max))
    
    return result

@router.get("/candidates/{candidate_id}", response_model=CandidateOutNoInterview)
def get_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Get a specific candidate."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    result = CandidateOutNoInterview.model_validate(candidate)
    
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result


@router.get("/candidates/{candidate_id}/resume")
def get_candidate_resume(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Download/view the resume file for a specific candidate."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if not candidate.resume_url:
        raise HTTPException(status_code=404, detail="Resume not available for this candidate")

    # If resume_url is an external URL, just return it
    if candidate.resume_url.startswith("http://") or candidate.resume_url.startswith("https://"):
        return {"resume_url": candidate.resume_url}

    # Otherwise treat it as a local file path (as saved by create_candidate)
    relative_path = candidate.resume_url.lstrip("/")  # stored like "/uploads/resumes/..."
    file_path = os.path.join(os.getcwd(), relative_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume file not found on server")

    return FileResponse(path=file_path, media_type="application/pdf", filename=os.path.basename(file_path))


@router.put("/candidates/{candidate_id}/resume", response_model=CandidateOutNoInterview)
def update_candidate_resume(
    candidate_id: int,
    resume: Optional[UploadFile] = File(None),
    resume_url: Optional[str] = Form(None, description="External resume URL"),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update a candidate's resume, either via file upload or external URL."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()

    # Ensure exactly one of resume or resume_url is provided
    if (resume is None and not resume_url) or (resume is not None and resume_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of 'resume' file or 'resume_url'"
        )

    final_resume_url = resume_url

    # Handle resume file upload if provided
    if resume is not None:
        upload_dir = "uploads/resumes"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = f"{upload_dir}/{candidate.vacancy_id}_{candidate.email}_{resume.filename}"
        with open(file_path, "wb") as buffer:
            content = resume.file.read()
            buffer.write(content)
        final_resume_url = f"/{file_path}"

    candidate.resume_url = final_resume_url
    candidate.updated_at = datetime.now()
    db.commit()
    db.refresh(candidate)

    result = CandidateOutNoInterview.model_validate(candidate)
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result

# @router.post("/candidates/{candidate_id}/shortlist", response_model=CandidateOut)
# def shortlist_candidate(
#     candidate_id: int,
#     shortlist_data: CandidateShortlist,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """Shortlist a candidate for an interview. Creates an interview record and updates status to 'interview'."""
#     candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
#     if not candidate:
#         raise HTTPException(status_code=404, detail="Candidate not found")
#     vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    
#     # Check if candidate is already rejected or hired
#     if candidate.status in ['rejected', 'hired', 'withdrawn']:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Cannot shortlist candidate with status '{candidate.status}'"
#         )
    
#     # Check for overlapping interviews
#     # Simple overlap check: if new interview starts before existing ends and ends after existing starts
#     overlapping = db.query(Interview).filter(
#         and_(
#             Interview.candidate_id == candidate_id,
#             Interview.status.in_(['scheduled', 'rescheduled']),
#             Interview.start_time <= shortlist_data.interview_date,
#             or_(
#                 Interview.end_time > shortlist_data.interview_date,
#                 Interview.end_time.is_(None)  # If no end_time, assume 1 hour duration
#             )
#         )
#     ).first()
    # Check for overlapping interviews
    # Simple overlap check: if new interview starts before existing ends and ends after existing starts
    # overlapping = _interview_scope_query(db, scope).filter(
    #     and_(
    #         Interview.candidate_id == candidate_id,
    #         Interview.status.in_(['scheduled', 'rescheduled']),
    #         Interview.start_time <= shortlist_data.interview_date,
    #         or_(
    #             Interview.end_time > shortlist_data.interview_date,
    #             Interview.end_time.is_(None)  # If no end_time, assume 1 hour duration
    #         )
    #     )
    # ).first()
    
    # # Also check reverse overlap
    # if not overlapping:
    #     overlapping = db.query(Interview).filter(
    #         and_(
    #             Interview.candidate_id == candidate_id,
    #             Interview.status.in_(['scheduled', 'rescheduled']),
    #             Interview.start_time >= shortlist_data.interview_date,
    #             Interview.start_time < shortlist_data.interview_date + timedelta(hours=1)  # Default 1 hour duration
    #         )
    #     ).first()
    
#     if overlapping:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Candidate already has an interview scheduled at this time (Interview ID: {overlapping.interview_id})"
#         )
    
#     # Create interview record
#     interview_data = InterviewCreate(
#         candidate_id=candidate_id,
#         vacancy_id=candidate.vacancy_id,
#         start_time=shortlist_data.interview_date,
#         end_time=None,  # Can be set later
#         round_type="HR"  # Default to HR round for shortlisting
#     )
    
#     db_interview = Interview(
#         candidate_id=interview_data.candidate_id,
#         vacancy_id=interview_data.vacancy_id,
#         scheduled_by=current_user.user_id,
#         start_time=interview_data.start_time,
#         end_time=interview_data.end_time,
#         round_type=interview_data.round_type,
#         status="scheduled"
#     )
    
#     # Store interview notes in feedback_summary (can be updated later with proper feedback)
#     if shortlist_data.interview_notes:
#         db_interview.feedback_summary = shortlist_data.interview_notes
    
#     db.add(db_interview)
    
#     # Update candidate status to 'interview'
#     candidate.status = 'interview'
#     candidate.updated_at = datetime.now()
    
#     db.commit()
#     db.refresh(candidate)
#     db.refresh(db_interview)
    
#     result = CandidateOut.model_validate(candidate)
#     if vacancy:
#         result.vacancy_title = vacancy.title
#         result.vacancy_department = vacancy.department
    
#     # Set interview_date from the created interview (for backward compatibility)
#     result.interview_date = db_interview.start_time
    
#     return result

@router.put("/candidates/{candidate_id}/status", response_model=CandidateOutNoInterview)
def update_candidate_status(
    candidate_id: int,
    status_update: CandidateStatusUpdate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update a candidate's status with proper validation."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    
    # Validate status transitions
    current_status = candidate.status
    new_status = status_update.status
    
    # Terminal statuses cannot be changed to other statuses
    terminal_statuses = ['rejected', 'hired', 'withdrawn']
    if current_status in terminal_statuses and new_status != current_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status from '{current_status}' to '{new_status}'. Terminal statuses cannot be changed."
        )
    
    # Cannot change to terminal status from another terminal status (except same status)
    if new_status in terminal_statuses and current_status in terminal_statuses and new_status != current_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status from '{current_status}' to '{new_status}'."
        )

    # Pipeline: interview -> offered -> hired (rejected/withdrawn allowed without interview)
    if new_status == "offered":
        if current_status != "interview":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot move to 'offered' from '{current_status}'. "
                    "Candidate must be in 'interview' status first."
                ),
            )
        if not _candidate_has_qualifying_interview(db, scope, candidate_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot move to 'offered' without a scheduled interview. "
                    "Shortlist the candidate or set status to 'interview' with interview_date first."
                ),
            )

    if new_status == "hired":
        if current_status != "offered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot move to 'hired' from '{current_status}'. "
                    "Candidate must be in 'offered' status first."
                ),
            )

    # Business logic validation: when setting status to 'interview', 
    # there should be at least one scheduled interview
    if new_status == 'interview':
        existing_interview = _interview_scope_query(db, scope).filter(
            and_(
                Interview.candidate_id == candidate_id,
                Interview.status.in_(['scheduled', 'rescheduled'])
            )
        ).first()
        
        if not existing_interview and not status_update.interview_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No scheduled interview found. Please schedule an interview first or provide interview_date to create one."
            )
        
        # If interview_date is provided, create an interview record
        if status_update.interview_date:
            interview_data = InterviewCreate(
                candidate_id=candidate_id,
                vacancy_id=candidate.vacancy_id,
                start_time=status_update.interview_date,
                end_time=None,
                round_type="HR"
            )
            
            db_interview = Interview(
                candidate_id=interview_data.candidate_id,
                vacancy_id=interview_data.vacancy_id,
                scheduled_by=current_user.user_id,
                start_time=interview_data.start_time,
                end_time=interview_data.end_time,
                round_type=interview_data.round_type,
                status="scheduled"
            )
            
            if status_update.interview_notes:
                db_interview.feedback_summary = status_update.interview_notes
            
            db.add(db_interview)
    
    # Update status
    candidate.status = new_status
    
    candidate.updated_at = datetime.now()
    db.commit()
    db.refresh(candidate)
    
    result = CandidateOutNoInterview.model_validate(candidate)
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result

@router.put("/candidates/{candidate_id}", response_model=CandidateOutNoInterview)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Update a candidate."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.model_dump(exclude_unset=True)

    # Validate status transitions if status is being updated
    new_status = update_data.get("status")
    if new_status is not None:
        current_status = candidate.status
        
        # Terminal statuses cannot be changed to other statuses
        terminal_statuses = ['rejected', 'hired', 'withdrawn']
        if current_status in terminal_statuses and new_status != current_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status from '{current_status}' to '{new_status}'. Terminal statuses cannot be changed."
            )
        
        # Cannot change to terminal status from another terminal status (except same status)
        if new_status in terminal_statuses and current_status in terminal_statuses and new_status != current_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status from '{current_status}' to '{new_status}'."
            )
        
        # Business logic validation: when setting status to 'interview', 
        # there should be at least one scheduled interview
        if new_status == 'interview':
            existing_interview = db.query(Interview).filter(
                and_(
                    Interview.candidate_id == candidate_id,
                    Interview.status.in_(['scheduled', 'rescheduled'])
                )
            ).first()
            
            if not existing_interview:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No scheduled interview found. Please schedule an interview first or use status update API."
                )

        # Business logic validation: when setting status to 'hired',
        # there should be at least one scheduled, rescheduled, or completed interview
        if new_status == 'hired':
            existing_interview = db.query(Interview).filter(
                and_(
                    Interview.candidate_id == candidate_id,
                    Interview.status.in_(['scheduled', 'rescheduled', 'completed'])
                )
            ).first()
            
            if not existing_interview:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot hire candidate without scheduling an interview first."
                )

    # Enforce unique phone number on update (if phone is being changed)
    new_phone = update_data.get("phone")
    if new_phone:
        existing_phone = (
            db.query(Candidate)
            .filter(
                Candidate.phone == new_phone,
                Candidate.candidate_id != candidate_id,
            )
            .first()
        )
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A candidate with this phone number already exists"
            )

    # Enforce unique email on update (if email is being changed)
    new_email = update_data.get("email")
    if new_email:
        existing_email = (
            db.query(Candidate)
            .filter(
                Candidate.email == new_email,
                Candidate.candidate_id != candidate_id,
            )
            .first()
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A candidate with this email already exists"
            )

    for field, value in update_data.items():
        setattr(candidate, field, value)
    
    candidate.updated_at = datetime.now()
    db.commit()
    db.refresh(candidate)
    
    vacancy = _vacancy_scope_query(db, scope).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    result = CandidateOutNoInterview.model_validate(candidate)
    
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    
    return result

@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db)
):
    """Delete a candidate."""
    candidate = _candidate_scope_query(db, scope).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db.delete(candidate)
    db.commit()
    return None

