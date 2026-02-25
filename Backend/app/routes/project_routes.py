from typing import List, Optional
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.project import Project
from app.db.models.task import Task
from app.db.models.project_member import ProjectMember
from app.db.models.user import User
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from app.schemas.project_schema import ProjectCreate, ProjectUpdate, ProjectOut, ProjectStatusUpdate
from app.schemas.project_member_schema import ProjectMemberAdd, ProjectMemberOut, ProjectMembersBulkAdd
from app.utils.timezone import now_ist


router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    dependencies=[Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))],
)


def _validate_project_dates(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Ensure project dates are not in the past and end_date is not before start_date."""
    today = date.today()

    if start_date is not None and start_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be in the past.",
        )

    if end_date is not None and end_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be in the past.",
        )

    if start_date is not None and end_date is not None and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be before start_date.",
        )


def _ensure_project_exists(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new project.

    Person in charge (PIC) is always Admin/HR (current user).
    """
    _validate_project_dates(payload.start_date, payload.end_date)

    project = Project(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="planned",
        person_in_charge_id=current_user.user_id,
        created_by=current_user.user_id,
        is_active=True,
    )

    db.add(project)
    db.flush()

    # Add PIC as project member with role 'pic'
    member = ProjectMember(
        project_id=project.project_id,
        user_id=current_user.user_id,
        role="pic",
        added_by=current_user.user_id,
    )
    db.add(member)

    db.commit()
    db.refresh(project)

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=db.query(ProjectMember).filter(
            ProjectMember.project_id == project.project_id,
            ProjectMember.is_active.is_(True),
        ).count(),
        task_count=task_count,
    )


@router.get("/", response_model=List[ProjectOut])
def list_projects(
    status_filter: Optional[str] = Query(None, description="Filter by project status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all projects.

    Only Admin/HR can access this endpoint (PICs by definition).
    """
    query = db.query(Project)

    if status_filter:
        query = query.filter(Project.status == status_filter)

    projects = query.order_by(Project.created_at.desc()).all()

    results: List[ProjectOut] = []
    for project in projects:
        member_count = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
            .count()
        )
        task_count = (
            db.query(Task)
            .filter(Task.project_id == project.project_id)
            .count()
        )
        results.append(
            ProjectOut(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                start_date=project.start_date,
                end_date=project.end_date,
                status=project.status,
                is_active=project.is_active,
                person_in_charge_id=project.person_in_charge_id,
                person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
                created_by=project.created_by,
                created_at=project.created_at,
                updated_at=project.updated_at,
                member_count=member_count,
                task_count=task_count,
            )
        )

    return results


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific project by ID."""
    project = _ensure_project_exists(db, project_id)

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a project.

    Only Admin/HR (PIC roles) can update projects.
    """
    project = _ensure_project_exists(db, project_id)

    # Determine the effective dates after update for validation
    new_start_date = payload.start_date if payload.start_date is not None else project.start_date
    new_end_date = payload.end_date if payload.end_date is not None else project.end_date
    _validate_project_dates(new_start_date, new_end_date)

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.put("/{project_id}/status", response_model=ProjectOut)
def update_project_status(
    project_id: int,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activate/deactivate a project (is_active flag).

    Only Admin/HR can toggle project active status.
    """
    project = _ensure_project_exists(db, project_id)

    project.is_active = payload.is_active
    db.commit()
    db.refresh(project)

    member_count = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.is_active.is_(True))
        .count()
    )

    task_count = (
        db.query(Task)
        .filter(Task.project_id == project.project_id)
        .count()
    )

    return ProjectOut(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        is_active=project.is_active,
        person_in_charge_id=project.person_in_charge_id,
        person_in_charge_name=project.person_in_charge.name if project.person_in_charge else None,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        task_count=task_count,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project.

    Only Admin/HR can delete projects.
    """
    project = _ensure_project_exists(db, project_id)

    db.delete(project)
    db.commit()

    return None


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: int,
    payload: ProjectMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a member to a project.

    Only Admin/HR (PIC roles) can manage members.
    """
    project = _ensure_project_exists(db, project_id)

    user = db.query(User).filter(User.user_id == payload.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.user_id == payload.user_id)
        .first()
    )

    if member:
        # Reactivate + update role
        member.is_active = True
        member.removed_at = None
        member.role = payload.role
    else:
        member = ProjectMember(
            project_id=project.project_id,
            user_id=payload.user_id,
            role=payload.role,
            added_by=current_user.user_id,
        )
        db.add(member)

    db.commit()
    db.refresh(member)

    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        user_name=user.name,
        user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        project_role=member.role,
        is_active=member.is_active,
        added_at=member.added_at,
    )


@router.get("/{project_id}/members", response_model=List[ProjectMemberOut])
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active members for a project."""
    _ensure_project_exists(db, project_id)

    members = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.user_id)
        .filter(ProjectMember.project_id == project_id, ProjectMember.is_active.is_(True))
        .order_by(User.name.asc())
        .all()
    )

    results: List[ProjectMemberOut] = []
    for member, user in members:
        results.append(
            ProjectMemberOut(
                id=member.id,
                project_id=member.project_id,
                user_id=member.user_id,
                user_name=user.name,
                user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
                project_role=member.role,
                is_active=member.is_active,
                added_at=member.added_at,
            )
        )

    return results


@router.post("/{project_id}/members/bulk", response_model=List[ProjectMemberOut], status_code=status.HTTP_201_CREATED)
def add_project_members_bulk(
    project_id: int,
    payload: ProjectMembersBulkAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk add members to a project.

    - Reactivates existing members (updates role).
    - Creates new members where needed.
    - Single role applied to all provided user IDs.
    """
    project = _ensure_project_exists(db, project_id)

    # Deduplicate IDs
    user_ids = list({uid for uid in payload.user_ids if uid is not None})

    # Load users and validate they exist and are active
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
            detail=f"User(s) not found or inactive for user_id(s): {missing}",
        )

    # Preload existing member records
    existing_members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.project_id, ProjectMember.user_id.in_(user_ids))
        .all()
    )
    members_by_user_id = {m.user_id: m for m in existing_members}

    created_or_updated: list[ProjectMember] = []

    for user in users:
        member = members_by_user_id.get(user.user_id)
        if member:
            # Reactivate and update role
            member.is_active = True
            member.removed_at = None
            member.role = payload.role
        else:
            member = ProjectMember(
                project_id=project.project_id,
                user_id=user.user_id,
                role=payload.role,
                added_by=current_user.user_id,
            )
            db.add(member)
        created_or_updated.append((member, user))

    db.commit()

    # Refresh members
    for member, _ in created_or_updated:
        db.refresh(member)

    return [
        ProjectMemberOut(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            user_name=user.name,
            user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            project_role=member.role,
            is_active=member.is_active,
            added_at=member.added_at,
        )
        for member, user in created_or_updated
    ]

@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove (deactivate) a project member.

    Only Admin/HR (PIC roles) can manage members.
    """
    _ensure_project_exists(db, project_id)

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.is_active.is_(True))
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found")

    # Do not allow removing the PIC record via this endpoint
    if member.role == "pic":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the PIC from the project. Change PIC or archive project instead.",
        )

    member.is_active = False
    member.removed_at = now_ist()

    db.commit()
    return None

