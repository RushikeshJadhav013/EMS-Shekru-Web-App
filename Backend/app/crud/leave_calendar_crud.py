from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional, List

from app.db.models.leave_calendar import CompanyHoliday, DeptWeekOffRule
from app.db.models.notification import CompanyHolidayNotification
from app.db.models.notification import CompanyHolidayNotification
from app.db.models.leave_config import LeaveAllocationConfig
from app.db.models.leave import Leave
from app.db.models.user import User
from sqlalchemy import and_, func
from datetime import timedelta


def create_holiday(
    db: Session,
    company_id: int,
    holiday_date: date,
    name: str,
    description: Optional[str],
    created_by: Optional[int],
    is_recurring: bool = False,
) -> CompanyHoliday:
    company_id = int(company_id)
    name = name.strip()

    existing = (
        db.query(CompanyHoliday)
        .filter(
            CompanyHoliday.company_id == company_id,
            CompanyHoliday.date == holiday_date,
            CompanyHoliday.name == name,
        )
        .first()
    )
    if existing:
        return existing

    if is_recurring:
        month = holiday_date.month
        day = holiday_date.day
        dup = (
            db.query(CompanyHoliday)
            .filter(
                CompanyHoliday.company_id == company_id,
                CompanyHoliday.is_recurring.is_(True),
                func.extract("month", CompanyHoliday.date) == month,
                func.extract("day", CompanyHoliday.date) == day,
                CompanyHoliday.name == name,
            )
            .first()
        )
        if dup:
            return dup

    h = CompanyHoliday(
        company_id=company_id,
        date=holiday_date,
        name=name,
        description=description,
        created_by=created_by,
        is_recurring=is_recurring,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def list_holidays(
    db: Session,
    company_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    department: Optional[str] = None,
    branch_id: int | None = None,
) -> List[CompanyHoliday]:
    """
    List holidays within an optional date range for a company.

    Behaviour for recurring holidays:
    - When both start and end are provided, recurring holidays are projected into
      every year spanned by the range.
    """
    _ = department, branch_id  # reserved for future branch-specific holiday rules
    company_id = int(company_id)

    if not start and not end:
        return (
            db.query(CompanyHoliday)
            .filter(CompanyHoliday.company_id == company_id)
            .order_by(CompanyHoliday.date.asc())
            .all()
        )

    holidays = db.query(CompanyHoliday).filter(CompanyHoliday.company_id == company_id).all()

    results: List[CompanyHoliday] = []

    for h in holidays:
        if not h.is_recurring:
            if start and h.date < start:
                continue
            if end and h.date > end:
                continue
            results.append(h)
            continue

        if not (start and end):
            if start and h.date < start:
                continue
            if end and h.date > end:
                continue
            results.append(h)
            continue

        month = h.date.month
        day = h.date.day
        for year in range(start.year, end.year + 1):
            try:
                projected = date(year, month, day)
            except ValueError:
                continue

            if projected < start or projected > end:
                continue

            projected_holiday = CompanyHoliday(
                id=h.id,
                company_id=h.company_id,
                date=projected,
                name=h.name,
                description=h.description,
                created_by=h.created_by,
                is_recurring=h.is_recurring,
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            results.append(projected_holiday)

    results.sort(key=lambda x: (x.date, x.name))
    return results


def delete_holiday(
    db: Session,
    holiday_id: int,
    *,
    company_id: int,
) -> bool:
    h = (
        db.query(CompanyHoliday)
        .filter(
            CompanyHoliday.id == holiday_id,
            CompanyHoliday.company_id == int(company_id),
        )
        .first()
    )
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


def upsert_weekoff_rule(
    db: Session,
    company_id: int,
    department: str,
    days: List[str],
    created_by: Optional[int],
) -> DeptWeekOffRule:
    company_id = int(company_id)
    department = department.strip()
    rule = (
        db.query(DeptWeekOffRule)
        .filter(
            DeptWeekOffRule.company_id == company_id,
            DeptWeekOffRule.department == department,
        )
        .first()
    )
    days_str = ",".join([d.strip() for d in days])
    if rule:
        rule.days = days_str
        rule.updated_at = datetime.utcnow()
        rule.created_by = created_by
        rule.is_active = True
    else:
        rule = DeptWeekOffRule(
            company_id=company_id,
            department=department,
            days=days_str,
            created_by=created_by,
        )
        db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_weekoff_rules(
    db: Session,
    company_id: int,
    department: Optional[str] = None,
    branch_id: int | None = None,
):
    _ = branch_id
    q = db.query(DeptWeekOffRule).filter(
        DeptWeekOffRule.company_id == int(company_id),
        DeptWeekOffRule.is_active.is_(True),
    )
    if department:
        q = q.filter(DeptWeekOffRule.department == department)
    return q.order_by(DeptWeekOffRule.department.asc()).all()


def delete_weekoff_rule(db: Session, rule_id: int, company_id: int) -> bool:
    r = (
        db.query(DeptWeekOffRule)
        .filter(
            DeptWeekOffRule.id == rule_id,
            DeptWeekOffRule.company_id == int(company_id),
        )
        .first()
    )
    if not r:
        return False
    db.delete(r)
    db.commit()
    return True


def get_leave_allocation(db: Session, company_id: int) -> Optional[LeaveAllocationConfig]:
    return (
        db.query(LeaveAllocationConfig)
        .filter(
            LeaveAllocationConfig.company_id == int(company_id),
            LeaveAllocationConfig.is_active.is_(True),
        )
        .order_by(LeaveAllocationConfig.updated_at.desc())
        .first()
    )


def update_leave_allocation(
    db: Session,
    company_id: int,
    total: int,
    sick: int,
    casual: int,
    other: int,
    updated_by: Optional[int],
) -> LeaveAllocationConfig:
    derived_total = (sick or 0) + (casual or 0)
    cfg = get_leave_allocation(db, company_id)
    if not cfg:
        db.query(LeaveAllocationConfig).filter(
            LeaveAllocationConfig.company_id == int(company_id),
        ).update({"is_active": False})
        cfg = LeaveAllocationConfig(
            company_id=int(company_id),
            total_annual_leave=derived_total,
            sick_leave_allocation=sick,
            casual_leave_allocation=casual,
            other_leave_allocation=other,
            is_active=True,
            updated_by=updated_by,
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
):
    events = []
    if company_id is None:
        return events

    company_id = int(company_id)

    qh = db.query(CompanyHoliday).filter(
        CompanyHoliday.company_id == company_id,
        CompanyHoliday.date >= start,
        CompanyHoliday.date <= end,
    )
    for h in qh.all():
        events.append({
            "id": f"holiday-{h.id}",
            "title": h.name,
            "start": h.date.isoformat(),
            "end": h.date.isoformat(),
            "type": "holiday",
            "department": None,
        })

    ql = db.query(Leave, User.department, User.name).join(User, Leave.user_id == User.user_id)
    ql = ql.filter(Leave.company_id == company_id)
    if branch_id is not None:
        ql = ql.filter(User.branch_id == branch_id)
    if department:
        ql = ql.filter(User.department == department)
    ql = ql.filter(and_(Leave.start_date <= end, Leave.end_date >= start))
    from app.utils.leave_validation import unpaid_leave_display_suffix, _duration_days_value

    for leave, dept, name in ql.all():
        type_label = (leave.leave_type or "leave").replace("_", " ").title()
        suffix = unpaid_leave_display_suffix(
            leave.leave_type or "",
            _duration_days_value(leave),
            leave.leave_session,
        )
        events.append({
            "id": f"leave-{leave.leave_id}",
            "title": f"{name} - {type_label}{suffix}",
            "start": leave.start_date.strftime("%Y-%m-%d"),
            "end": leave.end_date.strftime("%Y-%m-%d") if leave.end_date else leave.start_date.strftime("%Y-%m-%d"),
            "type": "leave",
            "department": dept,
            "user_id": leave.user_id,
        })

    qw = db.query(DeptWeekOffRule).filter(
        DeptWeekOffRule.company_id == company_id,
        DeptWeekOffRule.is_active.is_(True),
    )
    if department:
        qw = qw.filter(DeptWeekOffRule.department == department)
    for rule in qw.all():
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
                    "department": rule.department,
                })
            cur = cur + timedelta(days=1)

    return events
