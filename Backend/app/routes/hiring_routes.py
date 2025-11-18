from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.schemas.hiring_schema import VacancyCreate, VacancyUpdate, VacancyOut, CandidateCreate, CandidateUpdate, CandidateOut, SocialMediaPost
from app.db.database import get_db
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.db.models.hiring import Vacancy, Candidate
from app.db.models.user import User
from datetime import datetime
import json
import os

router = APIRouter(
    prefix="/hiring",
    tags=["Hiring Management"]
)

# Vacancy Routes

@router.post("/vacancies", response_model=VacancyOut, status_code=status.HTTP_201_CREATED)
def create_vacancy(
    vacancy: VacancyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new vacancy. Admin can create for any department, HR only for their department."""
    # Check permissions
    if current_user.role == RoleEnum.HR:
        if vacancy.department != current_user.department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR can only create vacancies for their own department"
            )
    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and HR can create vacancies"
        )
    
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
    
    result = VacancyOut.model_validate(db_vacancy)
    result.candidates_count = candidates_count
    return result

@router.get("/vacancies", response_model=List[VacancyOut])
def get_vacancies(
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all vacancies. HR sees only their department's vacancies."""
    query = db.query(Vacancy)
    
    # Filter by department for HR
    if current_user.role == RoleEnum.HR:
        query = query.filter(Vacancy.department == current_user.department)
    elif department:
        query = query.filter(Vacancy.department == department)
    
    if status_filter:
        query = query.filter(Vacancy.status == status_filter)
    
    vacancies = query.order_by(Vacancy.created_at.desc()).all()
    
    result = []
    for vacancy in vacancies:
        candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
            Candidate.vacancy_id == vacancy.vacancy_id
        ).scalar() or 0
        
        vacancy_out = VacancyOut.model_validate(vacancy)
        vacancy_out.candidates_count = candidates_count
        result.append(vacancy_out)
    
    return result

@router.get("/vacancies/{vacancy_id}", response_model=VacancyOut)
def get_vacancy(
    vacancy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific vacancy."""
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Check permissions for HR
    if current_user.role == RoleEnum.HR and vacancy.department != current_user.department:
        raise HTTPException(status_code=403, detail="Access denied")
    
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(vacancy)
    result.candidates_count = candidates_count
    return result

@router.put("/vacancies/{vacancy_id}", response_model=VacancyOut)
def update_vacancy(
    vacancy_id: int,
    vacancy_update: VacancyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a vacancy."""
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Check permissions
    if current_user.role == RoleEnum.HR:
        if vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
        # HR cannot change department
        if vacancy_update.department and vacancy_update.department != vacancy.department:
            raise HTTPException(status_code=403, detail="HR cannot change department")
    
    update_data = vacancy_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vacancy, field, value)
    
    vacancy.updated_at = datetime.now()
    db.commit()
    db.refresh(vacancy)
    
    candidates_count = db.query(func.count(Candidate.candidate_id)).filter(
        Candidate.vacancy_id == vacancy.vacancy_id
    ).scalar() or 0
    
    result = VacancyOut.model_validate(vacancy)
    result.candidates_count = candidates_count
    return result

@router.delete("/vacancies/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vacancy(
    vacancy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a vacancy."""
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Check permissions
    if current_user.role == RoleEnum.HR:
        if vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(vacancy)
    db.commit()
    return None

@router.post("/vacancies/{vacancy_id}/post-social", response_model=VacancyOut)
def post_to_social_media(
    vacancy_id: int,
    post_data: SocialMediaPost,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Post vacancy to social media platforms."""
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Check permissions
    if current_user.role == RoleEnum.HR:
        if vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    
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
    
    result = VacancyOut.model_validate(vacancy)
    result.candidates_count = candidates_count
    return result

# Candidate Routes

@router.post("/candidates", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate: CandidateCreate,
    resume: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new candidate application."""
    # Verify vacancy exists
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    # Check permissions
    if current_user.role == RoleEnum.HR:
        if vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Handle resume upload
    resume_url = candidate.resume_url
    if resume:
        # Save resume file (simplified - in production, use proper file storage)
        upload_dir = "uploads/resumes"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = f"{upload_dir}/{candidate.vacancy_id}_{candidate.email}_{resume.filename}"
        with open(file_path, "wb") as buffer:
            content = resume.file.read()
            buffer.write(content)
        resume_url = f"/{file_path}"
    
    db_candidate = Candidate(
        **candidate.model_dump(exclude={"resume_url"}),
        resume_url=resume_url,
        status="applied"
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    result = CandidateOut.model_validate(db_candidate)
    result.vacancy_title = vacancy.title
    result.vacancy_department = vacancy.department
    return result

@router.get("/candidates", response_model=List[CandidateOut])
def get_candidates(
    vacancy_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all candidates. HR sees only candidates for their department's vacancies."""
    query = db.query(Candidate)
    
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
        # Check permissions for HR
        if current_user.role == RoleEnum.HR:
            vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == vacancy_id).first()
            if vacancy and vacancy.department != current_user.department:
                raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == RoleEnum.HR:
        # Filter by HR's department
        department_vacancies = db.query(Vacancy.vacancy_id).filter(
            Vacancy.department == current_user.department
        ).subquery()
        query = query.filter(Candidate.vacancy_id.in_(department_vacancies))
    
    if status_filter:
        query = query.filter(Candidate.status == status_filter)
    
    candidates = query.order_by(Candidate.applied_at.desc()).all()
    
    result = []
    for candidate in candidates:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        candidate_out = CandidateOut.model_validate(candidate)
        if vacancy:
            candidate_out.vacancy_title = vacancy.title
            candidate_out.vacancy_department = vacancy.department
        result.append(candidate_out)
    
    return result

@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific candidate."""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check permissions for HR
    if current_user.role == RoleEnum.HR:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        if vacancy and vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    result = CandidateOut.model_validate(candidate)
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    return result

@router.put("/candidates/{candidate_id}", response_model=CandidateOut)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a candidate."""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check permissions for HR
    if current_user.role == RoleEnum.HR:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        if vacancy and vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    
    update_data = candidate_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)
    
    candidate.updated_at = datetime.now()
    db.commit()
    db.refresh(candidate)
    
    vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
    result = CandidateOut.model_validate(candidate)
    if vacancy:
        result.vacancy_title = vacancy.title
        result.vacancy_department = vacancy.department
    return result

@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a candidate."""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check permissions
    if current_user.role == RoleEnum.HR:
        vacancy = db.query(Vacancy).filter(Vacancy.vacancy_id == candidate.vacancy_id).first()
        if vacancy and vacancy.department != current_user.department:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(candidate)
    db.commit()
    return None

