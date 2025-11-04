from sqlalchemy.orm import Session
from datetime import datetime
from app.db.models.leave import Leave

def apply_leave(db: Session, user_id: int, start_date: datetime, end_date: datetime, reason: str):
    leave = Leave(user_id=user_id, start_date=start_date, end_date=end_date, reason=reason)
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

def approve_leave(db: Session, leave_id: int):
    leave = db.query(Leave).filter(Leave.leave_id == leave_id).first()
    if leave:
        leave.status = "Approved"
        db.commit()
        db.refresh(leave)
    return leave

def list_leave(db: Session, user_id: int):
    return db.query(Leave).filter(Leave.user_id == user_id).all()
