from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional, List

from app.db.models.leave_calendar import CompanyHoliday, DeptWeekOffRule
from app.db.models.leave_config import LeaveAllocationConfig
from app.db.models.leave import Leave
from app.db.models.user import User
from sqlalchemy import and_, func
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


def list_holidays(db: Session, start: Optional[date] = None, end: Optional[date] = None, department: Optional[str] = None) -> List[CompanyHoliday]:
    q = db.query(CompanyHoliday)
    if start:
        q = q.filter(CompanyHoliday.date >= start)
    if end:
        q = q.filter(CompanyHoliday.date <= end)
    return q.order_by(CompanyHoliday.date.asc()).all()


def delete_holiday(db: Session, holiday_id: int) -> bool:
    h = db.query(CompanyHoliday).filter(CompanyHoliday.id == holiday_id).first()
    if not h:
        return False
    db.delete(h)
    db.commit()
    return True


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


def list_weekoff_rules(db: Session, department: Optional[str] = None):
    q = db.query(DeptWeekOffRule).filter(DeptWeekOffRule.is_active == True)
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
    if not cfg:
        cfg = LeaveAllocationConfig(
            total_annual_leave=total,
            sick_leave_allocation=sick,
            casual_leave_allocation=casual,
            other_leave_allocation=other,
            updated_by=updated_by
        )
        db.add(cfg)
    else:
        cfg.total_annual_leave = total
        cfg.sick_leave_allocation = sick
        cfg.casual_leave_allocation = casual
        cfg.other_leave_allocation = other
        cfg.updated_by = updated_by
        cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg


def get_calendar_events(db: Session, start: date, end: date, department: Optional[str] = None):
    events = []
    # Holidays
    qh = db.query(CompanyHoliday).filter(CompanyHoliday.date >= start, CompanyHoliday.date <= end)
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


