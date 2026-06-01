from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Optional
from enum import Enum
from app.db.database import get_db
from app.crud.shift_crud import (
    create_shift,
    get_shift,
    get_shifts_by_department,
    get_shifts_for_department_tokens,
    update_shift,
    delete_shift,
    assign_shift,
    bulk_assign_shift,
    get_shift_assignment,
    get_user_shift_assignments,
    get_department_shift_schedule,
    get_department_shift_schedule_range,
    update_shift_assignment,
    delete_shift_assignment,
    create_shift_notification,
    get_shift_notifications,
    mark_notification_as_read,
)
from app.utils.department_utils import department_tokens_lower
from app.dependencies import get_current_user, get_tenant_scope, require_roles
from app.schemas.shift_schema import (
    ShiftCreate,
    ShiftUpdate,
    ShiftOut,
    ShiftAssignmentCreate,
    ShiftAssignmentBulkCreate,
    ShiftAssignmentUpdate,
    ShiftAssignmentOut,
    ShiftNotificationOut,
    DepartmentShiftSchedule,
    DepartmentShiftScheduleRange,
    UserShiftSchedule,
    UserBasicInfo,
)
from app.db.models.user import User
from app.enums import RoleEnum

router = APIRouter(prefix="/shift", tags=["Shift Management"])


def _user_scope_filters(scope: dict):
    company_id = scope.get("company_id")
    branch_id = scope.get("branch_id")
    filters = [User.company_id == company_id]
    if branch_id is not None:
        filters.append(User.branch_id == branch_id)
    return filters


def _scoped_company_id(scope: dict) -> int:
    return int(scope["company_id"])


def _tenant_departments(db: Session, scope: dict) -> list[str]:
    rows = (
        db.query(User.department)
        .filter(*_user_scope_filters(scope), User.is_active.is_(True), User.department.isnot(None))
        .distinct()
        .all()
    )
    return [r[0] for r in rows if r and r[0]]


def _tenant_department_tokens(db: Session, scope: dict) -> set[str]:
    tokens: set[str] = set()
    for raw in _tenant_departments(db, scope):
        tokens.update(department_tokens_lower(raw))
    return tokens


def _departments_overlap(a: Optional[str], b: Optional[str]) -> bool:
    ta = set(department_tokens_lower(a))
    tb = set(department_tokens_lower(b))
    return bool(ta & tb) if ta and tb else False


def _shift_in_tenant(shift_department: Optional[str], tenant_tokens: set[str]) -> bool:
    if not shift_department:
        return True
    return bool(set(department_tokens_lower(shift_department)) & tenant_tokens)


def _manager_can_access_department(manager: User, department: Optional[str]) -> bool:
    if not department:
        return True
    return _departments_overlap(manager.department, department)


def _first_department_label(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p and p.strip()]
    return parts[0] if parts else None


def _resolve_schedule_department(
    current_user: User,
    department_query: Optional[str],
    db: Session,
    scope: dict,
) -> str:
    """Resolve a single department token for schedule views."""
    if current_user.role == RoleEnum.ADMIN:
        if not department_query:
            raise HTTPException(status_code=400, detail="Department must be specified for Admin")
        dept = department_query.strip()
        token = dept.lower()
        if token not in _tenant_department_tokens(db, scope) and dept not in set(_tenant_departments(db, scope)):
            raise HTTPException(status_code=403, detail="Department not in tenant scope")
        return dept

    if not current_user.department:
        raise HTTPException(status_code=403, detail="User must belong to a department")

    user_tokens = department_tokens_lower(current_user.department)

    if department_query:
        req = department_query.strip()
        if req.lower() not in user_tokens:
            raise HTTPException(status_code=403, detail="Department not in your assigned departments")
        return req

    if len(user_tokens) == 1:
        label = _first_department_label(current_user.department)
        if not label:
            raise HTTPException(status_code=403, detail="User must belong to a department")
        return label

    if current_user.role == RoleEnum.MANAGER:
        raise HTTPException(
            status_code=400,
            detail="department query parameter is required when you manage multiple departments",
        )

    return _first_department_label(current_user.department) or current_user.department


# Shift CRUD Operations (Manager only)
@router.post("/", response_model=ShiftOut)
def create_new_shift(
    shift: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Create a new shift (Manager/Admin only)"""
    try:
        if not current_user.department and current_user.role != RoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager must belong to a department to create shifts"
            )
        
        department = shift.department
        if current_user.role == RoleEnum.MANAGER:
            manager_tokens = department_tokens_lower(current_user.department)
            if not manager_tokens:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Manager must belong to a department to create shifts",
                )
            if not department:
                if len(manager_tokens) > 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="department is required when creating shifts for multiple departments",
                    )
                department = _first_department_label(current_user.department)
            elif not _manager_can_access_department(current_user, department):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only create shifts for your assigned departments",
                )
        else:
            tenant_tokens = _tenant_department_tokens(db, scope)
            if department and not _shift_in_tenant(department, tenant_tokens):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department not in tenant scope")
        
        new_shift = create_shift(
            db,
            name=shift.name,
            start_time=shift.start_time,
            end_time=shift.end_time,
            company_id=_scoped_company_id(scope),
            department=department,
            description=shift.description,
            is_active=shift.is_active,
        )
        return new_shift
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error creating shift: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create shift: {str(e)}"
        )


@router.get("/", response_model=List[ShiftOut])
def list_shifts(
    department: Optional[str] = Query(None, description="Filter by department"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get shifts for a department or all shifts (Admin)"""
    company_id = _scoped_company_id(scope)
    if current_user.role == RoleEnum.ADMIN:
        tenant_tokens = _tenant_department_tokens(db, scope)
        if department and department.strip().lower() not in tenant_tokens:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department not in tenant scope")
        shifts = get_shifts_by_department(
            db, department, company_id=company_id, allowed_departments=_tenant_departments(db, scope)
        )
    elif current_user.role == RoleEnum.MANAGER:
        if not current_user.department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager must belong to a department",
            )
        manager_tokens = department_tokens_lower(current_user.department)
        if department:
            if department.strip().lower() not in manager_tokens:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department not in your assigned departments")
            shifts = get_shifts_by_department(db, department.strip(), company_id=company_id)
        else:
            shifts = get_shifts_for_department_tokens(db, manager_tokens, company_id=company_id)
    else:
        if not current_user.department:
            return []
        user_tokens = department_tokens_lower(current_user.department)
        if department:
            if department.strip().lower() not in user_tokens:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department not in your assigned departments")
            shifts = get_shifts_by_department(db, department.strip(), company_id=company_id)
        elif len(user_tokens) == 1:
            shifts = get_shifts_by_department(
                db, _first_department_label(current_user.department), company_id=company_id
            )
        else:
            shifts = get_shifts_for_department_tokens(db, user_tokens, company_id=company_id)
    
    return shifts


@router.get("/notifications")
def get_my_shift_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get current user's shift notifications"""
    try:
        notifications = get_shift_notifications(
            db,
            current_user.user_id,
            company_id=scope.get("company_id"),
            branch_id=scope.get("branch_id"),
        )
        # Convert to plain dictionaries to avoid Pydantic validation issues
        result = []
        for notification in notifications:
            try:
                # Convert datetime to ISO format string
                created_at_str = None
                if notification.created_at:
                    if hasattr(notification.created_at, 'isoformat'):
                        created_at_str = notification.created_at.isoformat()
                    else:
                        created_at_str = str(notification.created_at)
                
                notification_dict = {
                    "notification_id": int(notification.notification_id),
                    "user_id": int(notification.user_id),
                    "shift_assignment_id": int(notification.shift_assignment_id),
                    "notification_type": str(notification.notification_type),
                    "title": str(notification.title),
                    "message": str(notification.message),
                    "is_read": bool(notification.is_read),
                    "created_at": created_at_str,
                }
                result.append(notification_dict)
            except Exception as e:
                # Skip invalid notifications
                import logging
                logging.warning(f"Skipping notification {getattr(notification, 'notification_id', 'unknown')}: {str(e)}")
                continue
        
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        import logging
        logging.error(f"Error fetching shift notifications: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return JSONResponse(
            content={"detail": f"Error fetching notifications: {str(e)}"},
            status_code=500
        )


@router.get("/{shift_id}", response_model=ShiftOut)
def get_shift_by_id(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get a specific shift by ID"""
    shift = get_shift(db, shift_id, company_id=_scoped_company_id(scope))
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    tenant_tokens = _tenant_department_tokens(db, scope)
    if shift.department and not _shift_in_tenant(shift.department, tenant_tokens):
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role == RoleEnum.MANAGER:
        if shift.department and not _manager_can_access_department(current_user, shift.department):
            raise HTTPException(status_code=403, detail="Access denied")
    
    return shift


@router.put("/{shift_id}", response_model=ShiftOut)
def update_shift_by_id(
    shift_id: int,
    shift_update: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Update a shift (Manager/Admin only)"""
    shift = get_shift(db, shift_id, company_id=_scoped_company_id(scope))
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    tenant_tokens = _tenant_department_tokens(db, scope)
    if shift.department and not _shift_in_tenant(shift.department, tenant_tokens):
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role == RoleEnum.MANAGER:
        if shift.department and not _manager_can_access_department(current_user, shift.department):
            raise HTTPException(status_code=403, detail="Access denied")
    
    updated_shift = update_shift(
        db,
        shift_id,
        name=shift_update.name,
        start_time=shift_update.start_time,
        end_time=shift_update.end_time,
        description=shift_update.description,
        is_active=shift_update.is_active,
    )
    
    if not updated_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    return updated_shift


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift_by_id(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Delete a shift (soft delete) (Manager/Admin only)"""
    shift = get_shift(db, shift_id, company_id=_scoped_company_id(scope))
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    tenant_tokens = _tenant_department_tokens(db, scope)
    if shift.department and not _shift_in_tenant(shift.department, tenant_tokens):
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role == RoleEnum.MANAGER:
        if shift.department and not _manager_can_access_department(current_user, shift.department):
            raise HTTPException(status_code=403, detail="Access denied")
    
    success = delete_shift(db, shift_id)
    if not success:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    return None


# Shift Assignment Operations
@router.post("/assignment", response_model=ShiftAssignmentOut)
def assign_user_to_shift(
    assignment: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Assign a user to a shift (Manager/Admin only)"""
    # Verify shift exists in tenant
    shift = get_shift(db, assignment.shift_id, company_id=_scoped_company_id(scope))
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Verify user exists
    user = db.query(User).filter(User.user_id == assignment.user_id, *_user_scope_filters(scope)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tenant_tokens = _tenant_department_tokens(db, scope)
    if shift.department and not _shift_in_tenant(shift.department, tenant_tokens):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user.role == RoleEnum.MANAGER:
        if not current_user.department:
            raise HTTPException(status_code=403, detail="Manager must belong to a department")
        if not _manager_can_access_department(current_user, user.department):
            raise HTTPException(status_code=403, detail="Can only assign shifts to users in your department")
        if shift.department and not _manager_can_access_department(current_user, shift.department):
            raise HTTPException(status_code=403, detail="Can only assign shifts from your department")
        if shift.department and user.department and not _departments_overlap(shift.department, user.department):
            raise HTTPException(
                status_code=403,
                detail="Shift department must overlap with the user's department",
            )
    
    # Create assignment
    new_assignment = assign_shift(
        db,
        user_id=assignment.user_id,
        shift_id=assignment.shift_id,
        assignment_date=assignment.assignment_date,
        assigned_by=current_user.user_id,
        notes=assignment.notes,
    )
    
    # Create notification with manager details
    shift_name = shift.name
    date_str = assignment.assignment_date.strftime("%d %b %Y")
    manager_name = current_user.name
    # Get role display name
    manager_role = current_user.role.value if isinstance(current_user.role, Enum) else str(current_user.role)
    title = "Shift Assignment"
    message = f"{manager_name} ({manager_role}) has assigned you to {shift_name} on {date_str}."
    if assignment.notes:
        message += f" Notes: {assignment.notes}"
    
    create_shift_notification(
        db,
        user_id=assignment.user_id,
        shift_assignment_id=new_assignment.assignment_id,
        notification_type="shift_assigned",
        title=title,
        message=message,
    )
    
    return new_assignment


@router.post("/assignment/bulk", response_model=List[ShiftAssignmentOut])
def bulk_assign_users_to_shift(
    assignment: ShiftAssignmentBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Bulk assign multiple users to a shift (Manager/Admin only)"""
    # Verify shift exists in tenant
    shift = get_shift(db, assignment.shift_id, company_id=_scoped_company_id(scope))
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    tenant_tokens = _tenant_department_tokens(db, scope)
    if shift.department and not _shift_in_tenant(shift.department, tenant_tokens):
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role == RoleEnum.MANAGER:
        if not current_user.department:
            raise HTTPException(status_code=403, detail="Manager must belong to a department")
        if shift.department and not _manager_can_access_department(current_user, shift.department):
            raise HTTPException(status_code=403, detail="Can only assign shifts from your department")

        users = db.query(User).filter(User.user_id.in_(assignment.user_ids), *_user_scope_filters(scope)).all()
        for user in users:
            if not _manager_can_access_department(current_user, user.department):
                raise HTTPException(
                    status_code=403,
                    detail=f"Can only assign shifts to users in your department. User {user.name} is in {user.department}",
                )
            if shift.department and user.department and not _departments_overlap(shift.department, user.department):
                raise HTTPException(
                    status_code=403,
                    detail=f"Shift department must overlap with user {user.name}'s department",
                )
    else:
        # Admin: ensure all target users are within tenant scope
        tenant_user_ids = {
            int(u[0])
            for u in db.query(User.user_id).filter(User.user_id.in_(assignment.user_ids), *_user_scope_filters(scope)).all()
        }
        missing = [uid for uid in assignment.user_ids if int(uid) not in tenant_user_ids]
        if missing:
            raise HTTPException(status_code=403, detail="One or more users are outside tenant scope")
    
    # Create assignments
    assignments = bulk_assign_shift(
        db,
        user_ids=assignment.user_ids,
        shift_id=assignment.shift_id,
        assignment_date=assignment.assignment_date,
        assigned_by=current_user.user_id,
        notes=assignment.notes,
    )
    
    # Create notifications for each user with manager details
    shift_name = shift.name
    date_str = assignment.assignment_date.strftime("%d %b %Y")
    manager_name = current_user.name
    # Get role display name
    manager_role = current_user.role.value if isinstance(current_user.role, Enum) else str(current_user.role)
    title = "Shift Assignment"
    message = f"{manager_name} ({manager_role}) has assigned you to {shift_name} on {date_str}."
    if assignment.notes:
        message += f" Notes: {assignment.notes}"
    
    for assignment_obj in assignments:
        create_shift_notification(
            db,
            user_id=assignment_obj.user_id,
            shift_assignment_id=assignment_obj.assignment_id,
            notification_type="shift_assigned",
            title=title,
            message=message,
        )
    
    return assignments


@router.get("/schedule/department", response_model=DepartmentShiftSchedule)
def get_department_schedule(
    schedule_date: date = Query(..., description="Date for the schedule"),
    department: Optional[str] = Query(None, description="Department token (required for Admin and multi-dept managers)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get shift schedule for a department on a specific date"""
    dept = _resolve_schedule_department(current_user, department, db, scope)
    
    schedule = get_department_shift_schedule(
        db,
        dept,
        schedule_date,
        company_id=scope.get("company_id"),
        branch_id=scope.get("branch_id"),
    )
    
    # Convert to response model
    from app.schemas.shift_schema import ShiftScheduleView
    
    shift_views = []
    for shift_data in schedule["shifts"]:
        shift_views.append(ShiftScheduleView(
            shift=ShiftOut.model_validate(shift_data["shift"]),
            assignments=[ShiftAssignmentOut.model_validate(a) for a in shift_data["assignments"]],
            total_assigned=shift_data["total_assigned"],
        ))
    
    return DepartmentShiftSchedule(
        department=schedule["department"],
        date=schedule["date"],
        shifts=shift_views,
        users_on_leave=[UserBasicInfo.model_validate(u) for u in schedule["users_on_leave"]],
        unassigned_users=[UserBasicInfo.model_validate(u) for u in schedule["unassigned_users"]],
    )


@router.get("/schedule/department/week", response_model=DepartmentShiftScheduleRange)
def get_department_schedule_week(
    start_date: date = Query(..., description="Start date for the weekly schedule"),
    end_date: Optional[date] = Query(None, description="End date for the weekly schedule (defaults to 6 days after start)"),
    department: Optional[str] = Query(None, description="Department token (required for Admin and multi-dept managers)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get weekly shift schedule for a department"""
    if not end_date:
        end_date = start_date + timedelta(days=6)
    
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    
    if (end_date - start_date).days > 31:
        raise HTTPException(status_code=400, detail="Date range too large (max 31 days)")
    
    dept = _resolve_schedule_department(current_user, department, db, scope)
    
    try:
        schedule = get_department_shift_schedule_range(
            db,
            dept,
            start_date,
            end_date,
            company_id=scope.get("company_id"),
            branch_id=scope.get("branch_id"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    from app.schemas.shift_schema import ShiftScheduleView
    
    days = []
    for day in schedule["days"]:
        shift_views = []
        for shift_data in day["shifts"]:
            shift_views.append(ShiftScheduleView(
                shift=ShiftOut.model_validate(shift_data["shift"]),
                assignments=[ShiftAssignmentOut.model_validate(a) for a in shift_data["assignments"]],
                total_assigned=shift_data["total_assigned"],
            ))
        
        days.append(DepartmentShiftSchedule(
            department=day["department"],
            date=day["date"],
            shifts=shift_views,
            users_on_leave=[UserBasicInfo.model_validate(u) for u in day["users_on_leave"]],
            unassigned_users=[UserBasicInfo.model_validate(u) for u in day["unassigned_users"]],
        ))
    
    return DepartmentShiftScheduleRange(
        department=schedule["department"],
        start_date=schedule["start_date"],
        end_date=schedule["end_date"],
        days=days,
    )


@router.get("/schedule/my", response_model=UserShiftSchedule)
def get_my_shift_schedule(
    start_date: Optional[date] = Query(None, description="Start date (default: today)"),
    end_date: Optional[date] = Query(None, description="End date (default: 30 days from start)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Get current user's shift schedule"""
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=30)
    
    assignments = get_user_shift_assignments(db, current_user.user_id, start_date, end_date)
    
    today = date.today()
    upcoming = [a for a in assignments if a.assignment_date >= today]
    past = [a for a in assignments if a.assignment_date < today]
    
    return UserShiftSchedule(
        user=UserBasicInfo.model_validate(current_user),
        assignments=[ShiftAssignmentOut.model_validate(a) for a in assignments],
        upcoming_shifts=[ShiftAssignmentOut.model_validate(a) for a in upcoming],
        past_shifts=[ShiftAssignmentOut.model_validate(a) for a in past],
    )


@router.put("/assignment/{assignment_id}", response_model=ShiftAssignmentOut)
def update_shift_assignment_by_id(
    assignment_id: int,
    assignment_update: ShiftAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Update a shift assignment (Manager/Admin only)"""
    assignment = get_shift_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check permissions
    if current_user.role == RoleEnum.MANAGER:
        user = db.query(User).filter(User.user_id == assignment.user_id, *_user_scope_filters(scope)).first()
        if not user or not _manager_can_access_department(current_user, user.department):
            raise HTTPException(status_code=403, detail="Access denied")
        if assignment_update.shift_id:
            new_shift = get_shift(
                db, assignment_update.shift_id, company_id=_scoped_company_id(scope)
            )
            if new_shift and new_shift.department and not _manager_can_access_department(current_user, new_shift.department):
                raise HTTPException(status_code=403, detail="Access denied")
    else:
        in_scope = (
            db.query(User.user_id)
            .filter(User.user_id == assignment.user_id, *_user_scope_filters(scope))
            .first()
        )
        if not in_scope:
            raise HTTPException(status_code=403, detail="Access denied")
    
    updated_assignment = update_shift_assignment(
        db,
        assignment_id,
        shift_id=assignment_update.shift_id,
        assignment_date=assignment_update.assignment_date,
        notes=assignment_update.notes,
    )
    
    if not updated_assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Create notification if shift changed
    if assignment_update.shift_id and assignment_update.shift_id != assignment.shift_id:
        shift = get_shift(db, assignment_update.shift_id, company_id=_scoped_company_id(scope))
        if shift:
            date_str = (assignment_update.assignment_date or assignment.assignment_date).strftime("%d %b %Y")
            title = "Shift Updated"
            message = f"Your shift assignment has been updated to {shift.name} on {date_str}."
            create_shift_notification(
                db,
                user_id=assignment.user_id,
                shift_assignment_id=assignment_id,
                notification_type="shift_updated",
                title=title,
                message=message,
            )
    
    return updated_assignment


@router.delete("/assignment/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift_assignment_by_id(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.MANAGER, RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    """Delete a shift assignment (Manager/Admin only)"""
    # Validate assignment_id
    if not assignment_id or assignment_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid assignment ID")
    
    assignment = get_shift_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=404, 
            detail=f"Assignment not found with ID: {assignment_id}"
        )
    
    # Check permissions
    if current_user.role == RoleEnum.MANAGER:
        user = db.query(User).filter(User.user_id == assignment.user_id, *_user_scope_filters(scope)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found for this assignment")
        if not _manager_can_access_department(current_user, user.department):
            raise HTTPException(status_code=403, detail="Access denied: Can only delete assignments for users in your department")
    else:
        in_scope = (
            db.query(User.user_id)
            .filter(User.user_id == assignment.user_id, *_user_scope_filters(scope))
            .first()
        )
        if not in_scope:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete the assignment
    try:
        db.delete(assignment)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete assignment: {str(e)}"
        )
    
    return None


@router.put("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_shift_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    """Mark a shift notification as read"""
    success = mark_notification_as_read(
        db,
        notification_id,
        current_user.user_id,
        company_id=scope.get("company_id"),
        branch_id=scope.get("branch_id"),
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None

