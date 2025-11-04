# app/routes/leave_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.crud.leave_crud import apply_leave, approve_leave as approve_leave_db, list_leave
from app.dependencies import get_current_user, require_roles
from app.schemas.leave_schema import LeaveCreate, LeaveOut

router = APIRouter(prefix="/leave", tags=["Leave"])

# Employee applies for leave
@router.post("/", response_model=LeaveOut)
def request_leave(
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return apply_leave(db, user.user_id, leave.start_date, leave.end_date, leave.reason)


# Manager/Admin can approve leave
@router.put("/{leave_id}/approve", response_model=LeaveOut)
def approve_leave_request(
    leave_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("Manager", "Admin"))
):
    leave = approve_leave_db(db, leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave


# View logged-in user's leave requests
@router.get("/", response_model=list[LeaveOut])
def view_my_leave(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return list_leave(db, user.user_id)
