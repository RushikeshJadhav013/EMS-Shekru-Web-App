from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional, List

from app.db.models.leave_calendar import CompanyHoliday, DeptWeekOffRule
from app.db.models.notification import CompanyHolidayNotification
from app.db.models.leave_config import LeaveAllocationConfig
from app.db.models.leave import Leave
from app.db.models.user import User
from sqlalchemy import and_, func, or_
from datetime import timedelta


def create_holiday(db: Session, holiday_date: date, name: str, description: Optional[str], created_by: Optional[int], is_recurring: bool = False) -> CompanyHoliday:
    # Prevent duplicate holidays on same date (unless explicit override planned elsewhere)
    existing = db.query(CompanyHoliday).filter(CompanyHoliday.date == holiday_date, CompanyHoliday.name == name.strip()).first()
    if existing:
        return existing

    # If recurring, ensure no duplicate recurring holiday for same month/day
    if is_recurring:
        month = holiday_date.month
        day = holiday_date.day
        dup = db.query(CompanyHoliday).filter(
            CompanyHoliday.is_recurring == True,
            func.extract('month', CompanyHoliday.date) == month,
            func.extract('day', CompanyHoliday.date) == day,
            CompanyHoliday.name == name.strip()
        ).first()
        if dup:
            return dup

    h = CompanyHoliday(date=holiday_date, name=name.strip(), description=description, created_by=created_by, is_recurring=is_recurring)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def list_holidays(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
    department: Optional[str] = None,
    company_id: int | None = None,
    branch_id: int | None = None,
    include_global: bool = True,
) -> List[CompanyHoliday]:
    """
    List holidays within an optional date range.

    Behaviour for recurring holidays:
    - When both start and end are provided, recurring holidays are projected into
      every year spanned by the range.
      Example: a recurring holiday stored as 2024-01-01 with is_recurring=True
      will appear as 2025-01-01 when the requested range covers that date.
    - When start/end are not both provided, fall back to returning stored rows only.
    """
    def apply_tenant_filter(q):
        if company_id is None and branch_id is None:
            return q
        # Treat holidays created_by=NULL as "global" optionally.
        q = q.outerjoin(User, User.user_id == CompanyHoliday.created_by)
        clauses = []
        if company_id is not None:
            clauses.append(User.company_id == company_id)
        if branch_id is not None:
            clauses.append(User.branch_id == branch_id)
        if include_global:
            return q.filter(or_(CompanyHoliday.created_by.is_(None), and_(*clauses)))
        return q.filter(and_(*clauses))

    # If no explicit range, preserve simple behaviour (no projection).
    if not start and not end:
        q = apply_tenant_filter(db.query(CompanyHoliday))
        return q.order_by(CompanyHoliday.date.asc()).all()

    # Load all holidays once (scoped); table is expected to be small.
    holidays = apply_tenant_filter(db.query(CompanyHoliday)).all()

    results: List[CompanyHoliday] = []

    for h in holidays:
        if not h.is_recurring:
            # Non-recurring: simple range filter on stored date
            if start and h.date < start:
                continue
            if end and h.date > end:
                continue
            results.append(h)
            continue

        # Recurring holiday
        if not (start and end):
            # If we don't have a full range, apply simple filter on stored date
            if start and h.date < start:
                continue
            if end and h.date > end:
                continue
            results.append(h)
            continue

        # Project recurring holiday into each year within [start.year, end.year]
        month = h.date.month
        day = h.date.day
        for year in range(start.year, end.year + 1):
            try:
                projected = date(year, month, day)
            except ValueError:
                # Skip invalid dates (e.g. Feb 29 on non-leap years)
                continue

            if projected < start or projected > end:
                continue

            # Create an in-memory instance with the projected date.
            # Keep the same ID so delete operations still target the base record.
            projected_holiday = CompanyHoliday(
                id=h.id,
                date=projected,
                name=h.name,
                description=h.description,
                created_by=h.created_by,
                is_recurring=h.is_recurring,
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            results.append(projected_holiday)

    # Sort by date (then name for stable ordering)
    results.sort(key=lambda x: (x.date, x.name))
    return results


def delete_holiday(
    db: Session,
    holiday_id: int,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
    include_global: bool = True,
) -> bool:
    q = db.query(CompanyHoliday).filter(CompanyHoliday.id == holiday_id)
    if company_id is not None or branch_id is not None:
        q = q.outerjoin(User, User.user_id == CompanyHoliday.created_by)
        clauses = []
        if company_id is not None:
            clauses.append(User.company_id == company_id)
        if branch_id is not None:
            clauses.append(User.branch_id == branch_id)
        if include_global:
            q = q.filter(or_(CompanyHoliday.created_by.is_(None), and_(*clauses)))
        else:
            q = q.filter(and_(*clauses))

    h = q.first()
    if not h:
        return False
    db.delete(h)
    db.commit()
    return True


def create_holiday_notifications(
    db: Session,
    *,
    holiday: CompanyHoliday,
    actor_user_id: Optional[int],
    action: str,
    company_id: int | None = None,
    branch_id: int | None = None,
) -> int:
    users_q = db.query(User).filter(User.is_active.is_(True))
    if company_id is not None:
        users_q = users_q.filter(User.company_id == company_id)
    if branch_id is not None:
        users_q = users_q.filter(User.branch_id == branch_id)
    users = users_q.all()
    if not users:
        return 0

    holiday_date = holiday.date.strftime("%d %b %Y")
    action_key = action.strip().lower()
    if action_key == "created":
        notification_type = "holiday_created"
        title = "New Company Holiday Announced"
        message = f"{holiday.name} is marked as a company holiday on {holiday_date}."
    elif action_key == "deleted":
        notification_type = "holiday_deleted"
        title = "Company Holiday Removed"
        message = f"{holiday.name} holiday scheduled for {holiday_date} has been removed."
    else:
        notification_type = "holiday_update"
        title = "Company Holiday Updated"
        message = f"{holiday.name} holiday details for {holiday_date} have been updated."

    notifications: list[CompanyHolidayNotification] = []
    for user in users:
        if actor_user_id is not None and user.user_id == actor_user_id:
            continue
        notification = CompanyHolidayNotification(
            user_id=user.user_id,
            holiday_id=holiday.id if action_key == "created" else None,
            notification_type=notification_type,
            title=title,
            message=message,
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)

    if not notifications:
        return 0

    db.commit()
    return len(notifications)


def list_holiday_notifications(db: Session, user_id: int) -> list[CompanyHolidayNotification]:
    return (
        db.query(CompanyHolidayNotification)
        .filter(CompanyHolidayNotification.user_id == user_id)
        .order_by(CompanyHolidayNotification.created_at.desc())
        .all()
    )


def mark_holiday_notification_as_read(
    db: Session,
    notification_id: int,
    user_id: int,
) -> Optional[CompanyHolidayNotification]:
    notification = (
        db.query(CompanyHolidayNotification)
        .filter(
            CompanyHolidayNotification.notification_id == notification_id,
            CompanyHolidayNotification.user_id == user_id,
        )
        .first()
    )
    if not notification:
        return None

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)

    return notification


def upsert_weekoff_rule(db: Session, department: str, days: List[str], created_by: Optional[int]) -> DeptWeekOffRule:
    rule = db.query(DeptWeekOffRule).filter(DeptWeekOffRule.department == department).first()
    days_str = ",".join([d.strip() for d in days])
    if rule:
        rule.days = days_str
        rule.updated_at = datetime.utcnow()
        rule.created_by = created_by
    else:
        rule = DeptWeekOffRule(department=department, days=days_str, created_by=created_by)
        db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_weekoff_rules(
    db: Session,
    department: Optional[str] = None,
    company_id: int | None = None,
    branch_id: int | None = None,
    include_global: bool = True,
):
    q = db.query(DeptWeekOffRule).filter(DeptWeekOffRule.is_active == True)
    if company_id is not None or branch_id is not None:
        q = q.outerjoin(User, User.user_id == DeptWeekOffRule.created_by)
        clauses = []
        if company_id is not None:
            clauses.append(User.company_id == company_id)
        if branch_id is not None:
            clauses.append(User.branch_id == branch_id)
        if include_global:
            q = q.filter(or_(DeptWeekOffRule.created_by.is_(None), and_(*clauses)))
        else:
            q = q.filter(and_(*clauses))
    if department:
        q = q.filter(DeptWeekOffRule.department == department)
    return q.order_by(DeptWeekOffRule.department.asc()).all()


def delete_weekoff_rule(db: Session, rule_id: int) -> bool:
    r = db.query(DeptWeekOffRule).filter(DeptWeekOffRule.id == rule_id).first()
    if not r:
        return False
    db.delete(r)
    db.commit()
    return True


def get_leave_allocation(db: Session) -> LeaveAllocationConfig:
    cfg = db.query(LeaveAllocationConfig).order_by(LeaveAllocationConfig.id.desc()).first()
    return cfg


def update_leave_allocation(db: Session, total: int, sick: int, casual: int, other: int, updated_by: Optional[int]) -> LeaveAllocationConfig:
    cfg = db.query(LeaveAllocationConfig).order_by(LeaveAllocationConfig.id.desc()).first()
    # Enforce: annual bucket = sick + casual (ignore provided total)
    derived_total = (sick or 0) + (casual or 0)
    if not cfg:
        cfg = LeaveAllocationConfig(
            total_annual_leave=derived_total,
            sick_leave_allocation=sick,
            casual_leave_allocation=casual,
            other_leave_allocation=other,
            updated_by=updated_by
        )
        db.add(cfg)
    else:
        cfg.total_annual_leave = derived_total
        cfg.sick_leave_allocation = sick
        cfg.casual_leave_allocation = casual
        cfg.other_leave_allocation = other
        cfg.updated_by = updated_by
        cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg


def get_calendar_events(
    db: Session,
    start: date,
    end: date,
    department: Optional[str] = None,
    *,
    company_id: int | None = None,
    branch_id: int | None = None,
    include_global: bool = True,
):
    events = []
    # Holidays
    qh = db.query(CompanyHoliday).filter(CompanyHoliday.date >= start, CompanyHoliday.date <= end)
    if company_id is not None or branch_id is not None:
        qh = qh.outerjoin(User, User.user_id == CompanyHoliday.created_by)
        clauses = []
        if company_id is not None:
            clauses.append(User.company_id == company_id)
        if branch_id is not None:
            clauses.append(User.branch_id == branch_id)
        if include_global:
            qh = qh.filter(or_(CompanyHoliday.created_by.is_(None), and_(*clauses)))
        else:
            qh = qh.filter(and_(*clauses))
    for h in qh.all():
        events.append({
            "id": f"holiday-{h.id}",
            "title": h.name,
            "start": h.date.isoformat(),
            "end": h.date.isoformat(),
            "type": "holiday",
            "department": None
        })

    # Leaves
    # Include leaves that overlap the requested range (start <= end AND end >= start)
    ql = db.query(Leave, User.department, User.name).join(User, Leave.user_id == User.user_id)
    if company_id is not None:
        ql = ql.filter(User.company_id == company_id)
    if branch_id is not None:
        ql = ql.filter(User.branch_id == branch_id)
    if department:
        ql = ql.filter(User.department == department)
    ql = ql.filter(and_(Leave.start_date <= end, Leave.end_date >= start))
    for leave, dept, name in ql.all():
        events.append({
            "id": f"leave-{leave.leave_id}",
            "title": f"{name} - {leave.leave_type}",
            "start": leave.start_date.strftime("%Y-%m-%d"),
            "end": leave.end_date.strftime("%Y-%m-%d") if leave.end_date else leave.start_date.strftime("%Y-%m-%d"),
            "type": "leave",
            "department": dept,
            "user_id": leave.user_id
        })

    # Weekoffs
    qw = db.query(DeptWeekOffRule).filter(DeptWeekOffRule.is_active == True)
    if company_id is not None or branch_id is not None:
        qw = qw.outerjoin(User, User.user_id == DeptWeekOffRule.created_by)
        clauses = []
        if company_id is not None:
            clauses.append(User.company_id == company_id)
        if branch_id is not None:
            clauses.append(User.branch_id == branch_id)
        if include_global:
            qw = qw.filter(or_(DeptWeekOffRule.created_by.is_(None), and_(*clauses)))
        else:
            qw = qw.filter(and_(*clauses))
    if department:
        qw = qw.filter(DeptWeekOffRule.department == department)
    for rule in qw.all():
        # Expand weekoff rule into events between start and end
        days = [d.strip().lower() for d in rule.days.split(",") if d.strip()]
        cur = start
        while cur <= end:
            if cur.strftime("%A").lower() in days:
                events.append({
                    "id": f"weekoff-{rule.id}-{cur.isoformat()}",
                    "title": f"{rule.department} Week-off",
                    "start": cur.isoformat(),
                    "end": cur.isoformat(),
                    "type": "weekoff",
                    "department": rule.department
                })
            cur = cur + timedelta(days=1)

    return events


