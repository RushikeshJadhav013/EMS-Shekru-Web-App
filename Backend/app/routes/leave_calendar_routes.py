from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.dependencies import get_current_user, require_roles, get_tenant_scope
from app.db.models.user import User
from app.enums import RoleEnum

from app.schemas.leave_calendar_schema import (
    CompanyHolidayCreate, CompanyHolidayOut,
    DeptWeekOffRuleCreate, DeptWeekOffRuleOut,
    LeaveAllocationUpdate, CalendarEvent, CompanyHolidayNotificationOut
)
from app.crud.leave_calendar_crud import (
    create_holiday, list_holidays, delete_holiday,
    upsert_weekoff_rule, list_weekoff_rules,
    get_leave_allocation, update_leave_allocation,
    get_calendar_events, create_holiday_notifications,
    list_holiday_notifications, mark_holiday_notification_as_read
)
from app.db.models.leave_calendar import CompanyHoliday

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.post("/holidays", response_model=CompanyHolidayOut)
def add_holiday(
    payload: CompanyHolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    try:
        h = create_holiday(db, holiday_date=payload.date, name=payload.name, description=payload.description, created_by=current_user.user_id, is_recurring=payload.is_recurring)
        create_holiday_notifications(
            db,
            holiday=h,
            actor_user_id=current_user.user_id,
            action="created",
            company_id=scope["company_id"],
            branch_id=scope.get("branch_id"),
        )
        return h
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/holidays", response_model=list[CompanyHolidayOut])
def get_holidays(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    start = None
    end = None
    try:
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    return list_holidays(
        db,
        start=start,
        end=end,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )


@router.delete("/holidays/{holiday_id}")
def remove_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    holiday = db.query(CompanyHoliday).filter(CompanyHoliday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    ok = delete_holiday(
        db,
        holiday_id,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Holiday not found")
    create_holiday_notifications(
        db,
        holiday=holiday,
        actor_user_id=current_user.user_id,
        action="deleted",
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    return {"message": "Holiday deleted"}


@router.post("/weekoffs", response_model=DeptWeekOffRuleOut)
def set_weekoff_rule(
    payload: DeptWeekOffRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    scope: dict = Depends(get_tenant_scope),
):
    rule = upsert_weekoff_rule(db, department=payload.department, days=payload.days, created_by=current_user.user_id)
    # Convert days string to list for response model
    rule_out = DeptWeekOffRuleOut(
        id=rule.id,
        department=rule.department,
        days=[d.strip() for d in rule.days.split(",") if d.strip()],
        is_active=rule.is_active,
        created_at=rule.created_at
    )
    return rule_out


@router.get("/weekoffs", response_model=list[DeptWeekOffRuleOut])
def get_weekoff_rules(
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    rules = list_weekoff_rules(
        db,
        department=department,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    out = []
    for r in rules:
        out.append(DeptWeekOffRuleOut(id=r.id, department=r.department, days=[d.strip() for d in r.days.split(",") if d.strip()], is_active=r.is_active, created_at=r.created_at))
    return out


@router.delete("/weekoffs/{rule_id}")
def delete_weekoff(rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))):
    from app.crud.leave_calendar_crud import delete_weekoff_rule
    ok = delete_weekoff_rule(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Week-off rule not found")
    return {"message": "Week-off rule deleted"}


@router.get("/allocation")
def get_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    cfg = get_leave_allocation(db)
    if not cfg:
        return {}
    # Calculate annual as sick + casual
    annual_calculated = cfg.sick_leave_allocation + cfg.casual_leave_allocation
    return {
        "total_annual_leave": annual_calculated,  # Calculated as sick + casual
        "sick_leave_allocation": cfg.sick_leave_allocation,
        "casual_leave_allocation": cfg.casual_leave_allocation,
        "other_leave_allocation": cfg.other_leave_allocation,
        "updated_at": cfg.updated_at
    }


@router.put("/allocation")
def update_allocation(
    payload: LeaveAllocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN)),
    scope: dict = Depends(get_tenant_scope),
):
    cfg = update_leave_allocation(db, total=payload.total_annual_leave, sick=payload.sick_leave_allocation, casual=payload.casual_leave_allocation, other=payload.other_leave_allocation, updated_by=current_user.user_id)
    # Calculate annual as sick + casual
    annual_calculated = cfg.sick_leave_allocation + cfg.casual_leave_allocation
    return {
        "total_annual_leave": annual_calculated,  # Calculated as sick + casual
        "sick_leave_allocation": cfg.sick_leave_allocation,
        "casual_leave_allocation": cfg.casual_leave_allocation,
        "other_leave_allocation": cfg.other_leave_allocation,
        "updated_at": cfg.updated_at
    }


@router.get("/calendar", response_model=list[CalendarEvent])
def read_calendar(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    try:
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start = datetime.utcnow().date()
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end = start
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format.")

    events = get_calendar_events(
        db,
        start=start,
        end=end,
        department=department,
        company_id=scope["company_id"],
        branch_id=scope.get("branch_id"),
    )
    return events


@router.get("/notifications", response_model=list[CompanyHolidayNotificationOut])
def get_holiday_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    return list_holiday_notifications(db, current_user.user_id)


@router.put("/notifications/{notification_id}/read", response_model=CompanyHolidayNotificationOut)
def mark_holiday_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
):
    notification = mark_holiday_notification_as_read(db, notification_id, current_user.user_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


