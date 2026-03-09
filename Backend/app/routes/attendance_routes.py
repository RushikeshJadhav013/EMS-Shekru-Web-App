import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, or_
from datetime import datetime, timedelta, time, date
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from app.db.models.office_timing import OfficeTiming
from app.schemas.attendance_schema import AttendanceOut, LocationData
from fastapi.responses import StreamingResponse, JSONResponse
from app.dependencies import get_current_user, require_roles
from app.enums import RoleEnum
from typing import Optional, List, Dict, Any, Union, Tuple, Literal
from decimal import Decimal
from pydantic import BaseModel, ValidationError
import base64
import os
import shutil
from io import BytesIO
import logging
import json
from ..utils.geolocation import location_service
from app.schemas.office_timing_schema import OfficeTimingOut, OfficeTimingCreate
from app.utils.timezone import now_ist, get_today_bounds_ist, get_date_bounds_ist
from app.crud.attendance_grid_export import export_monthly_grid_pdf, export_monthly_grid_csv
from app.utils.department_utils import department_tokens_lower, department_token_regex_pattern




router = APIRouter(prefix="/attendance", tags=["Attendance"])

# Logout endpoint that handles pause/resume functionality
class LogoutPayload(BaseModel):
    user_id: int
    logout_timestamp: str

# @router.post("/logout")
# async def logout_with_pause(
#     payload: LogoutPayload,
#     db: Session = Depends(get_db),
#     current_user=Depends(get_current_user)
# ):
#     """
#     Logout endpoint that treats logout as a pause in online status.
#     Records logout timestamp to pause Online time and start Offline time tracking.
#     """
#     try:
#         from app.db.models.online_status import OnlineStatus
        
#         # Verify user matches current user
#         if current_user.user_id != payload.user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Cannot logout for another user"
#             )
        
#         # Find today's active attendance record
#         today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
#         today_end = today_start + timedelta(days=1)
        
#         attendance = db.query(Attendance).filter(
#             Attendance.user_id == payload.user_id,
#             Attendance.check_in >= today_start,
#             Attendance.check_in < today_end,
#             Attendance.check_out.is_(None)  # Only active attendance
#         ).first()
        
#         if attendance:
#             # Get current online status
#             latest_status = db.query(OnlineStatus).filter(
#                 OnlineStatus.user_id == payload.user_id,
#                 OnlineStatus.timestamp >= today_start,
#                 OnlineStatus.timestamp < today_end
#             ).order_by(OnlineStatus.timestamp.desc()).first()
            
#             # If user is currently online, record logout as going offline
#             current_online_status = True if not latest_status else latest_status.is_online
            
#             if current_online_status:
#                 # Use server-side IST timestamp to avoid timezone and client clock issues
#                 logout_timestamp = now_ist()
                
#                 # Create offline status entry for logout
#                 offline_status = OnlineStatus(
#                     attendance_id=attendance.attendance_id,
#                     user_id=payload.user_id,
#                     is_online=False,
#                     reason="Logout - session paused",
#                     timestamp=logout_timestamp
#                 )
#                 db.add(offline_status)
#                 db.commit()
                
#                 logger.info(f"User {payload.user_id} logged out - status set to offline for pause/resume")
            
#         return {"message": "Logout successful - session paused", "user_id": current_user.user_id}
        
#     except Exception as e:
#         logger.error(f"Logout error for user {current_user.user_id}: {e}")
#         # Always allow logout even if pause recording fails
#         return {"message": "Logout successful", "user_id": current_user.user_id}


# Login resume endpoint to handle resume functionality
class LoginResumePayload(BaseModel):
    user_id: int
    login_timestamp: str

# @router.post("/login-resume")
# async def login_resume(
#     payload: LoginResumePayload,
#     db: Session = Depends(get_db),
#     current_user=Depends(get_current_user)
# ):
#     """
#     Login resume endpoint that treats login as resuming from a pause.
#     Records login timestamp to resume Online time and add offline duration to Offline time.
#     """
#     try:
#         from app.db.models.online_status import OnlineStatus
        
#         # Verify user matches current user
#         if current_user.user_id != payload.user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Cannot resume for another user"
#             )
        
#         # Find today's active attendance record
#         today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
#         today_end = today_start + timedelta(days=1)
        
#         attendance = db.query(Attendance).filter(
#             Attendance.user_id == payload.user_id,
#             Attendance.check_in >= today_start,
#             Attendance.check_in < today_end,
#             Attendance.check_out.is_(None)  # Only active attendance
#         ).first()
        
#         if attendance:
#             # Get current online status
#             latest_status = db.query(OnlineStatus).filter(
#                 OnlineStatus.user_id == payload.user_id,
#                 OnlineStatus.timestamp >= today_start,
#                 OnlineStatus.timestamp < today_end
#             ).order_by(OnlineStatus.timestamp.desc()).first()
            
#             # If user is currently offline (from logout), record login as going online
#             current_online_status = True if not latest_status else latest_status.is_online
            
#             if not current_online_status and latest_status:
#                 # Use server-side IST timestamp to avoid timezone and client clock issues
#                 login_timestamp = now_ist()
                
#                 # Calculate offline duration between last offline log and this login
#                 offline_duration = login_timestamp - latest_status.timestamp
#                 offline_seconds = offline_duration.total_seconds()
                
#                 # Create online status entry for login resume
#                 online_status = OnlineStatus(
#                     attendance_id=attendance.attendance_id,
#                     user_id=payload.user_id,
#                     is_online=True,
#                     reason=f"Login - session resumed (was offline for {int(offline_seconds)}s)",
#                     timestamp=login_timestamp
#                 )
#                 db.add(online_status)
#                 db.commit()
                
#                 logger.info(f"User {payload.user_id} logged in - status resumed to online after {int(offline_seconds)}s offline")
                
#                 return {
#                     "message": "Login successful - session resumed", 
#                     "user_id": current_user.user_id,
#                     "offline_duration_seconds": int(offline_seconds)
#                 }
            
#         return {"message": "Login successful", "user_id": current_user.user_id}
        
#     except Exception as e:
#         logger.error(f"Login resume error for user {current_user.user_id}: {e}")
#         return {"message": "Login successful", "user_id": current_user.user_id}


class AttendanceJSONPayload(BaseModel):
    user_id: int
    gps_location: Optional[Dict[str, Any]] = None
    selfie: Optional[str] = None  # base64 data URL or raw base64
    location_data: Optional[Dict[str, Any]] = None
    work_summary: Optional[str] = None
    work_report: Optional[str] = None  # base64 data URL or raw base64
    work_location: Optional[Literal['office', 'work_from_home']] = 'office'  # Work location type
    task_deadline_reason: Optional[str] = None  # Reason for incomplete tasks on deadline

# ---------------------------------
# Helper functions for Attendance
# ---------------------------------
logger = logging.getLogger(__name__)


def _ensure_location_dict(location_input: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """Normalize incoming location payloads to a dictionary."""
    if not location_input:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location data is required for check-in/out",
        )

    if isinstance(location_input, dict):
        return location_input

    if isinstance(location_input, str):
        try:
            return json.loads(location_input)
        except json.JSONDecodeError as exc:  # pragma: no cover - detailed error path
            logger.error("Failed to decode location string: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid location data format. Must be valid JSON.",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported location data type",
    )


def _format_location_label(details: Dict[str, Any]) -> str:
    """Convert processed location details to a concise string for storage."""
    if not details:
        return "Location not available"

    address = details.get("address") or ""
    if address and len(address) > 180:
        address = address[:177] + "..."

    lat = details.get("latitude")
    lon = details.get("longitude")
    coord_text = None
    try:
        if lat is not None and lon is not None:
            coord_text = f"({float(lat):.6f}, {float(lon):.6f})"
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        coord_text = None

    parts: list[str] = []
    if address:
        parts.append(address)
    if coord_text:
        parts.append(coord_text)

    return " ".join(parts) if parts else "Location available"


def _compose_location_entry(existing: Optional[str], entry_type: str, details: Dict[str, Any]) -> str:
    """Append or replace location information with a labelled entry."""
    label = _format_location_label(details)
    new_entry = f"{entry_type}: {label}"
    new_entry = _sanitize_text(new_entry, max_length=240) or new_entry

    if not existing:
        return new_entry

    segments = [segment.strip() for segment in existing.split("|") if segment.strip()]
    filtered = [segment for segment in segments if not segment.lower().startswith(entry_type.lower())]
    filtered.append(new_entry)
    combined = " | ".join(filtered)
    return _sanitize_text(combined, max_length=250) or combined


def _split_location_labels(label: Optional[str]) -> Dict[str, Optional[str]]:
    sections = {"check_in": None, "check_out": None}
    if not label:
        return sections

    for segment in label.split("|"):
        part = segment.strip()
        if not part:
            continue
        lower = part.lower()
        if lower.startswith("check-in"):  # format: "Check-in: ..."
            value = part.split(":", 1)[1].strip() if ":" in part else part
            sections["check_in"] = value or None
        elif lower.startswith("check-out"):
            value = part.split(":", 1)[1].strip() if ":" in part else part
            sections["check_out"] = value or None
    return sections


def _load_selfie_data(serialized: Optional[str]) -> Dict[str, Optional[str]]:
    if not serialized:
        return {}

    if isinstance(serialized, str):
        try:
            data = json.loads(serialized)
            if isinstance(data, dict):
                return {
                    "check_in": data.get("check_in"),
                    "check_out": data.get("check_out"),
                }
        except json.JSONDecodeError:
            if serialized.strip():
                return {"check_in": serialized.strip()}

    return {}


def _dump_selfie_data(
    existing: Optional[str],
    *,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
) -> Optional[str]:
    data = _load_selfie_data(existing)
    if check_in:
        data["check_in"] = check_in
    if check_out:
        data["check_out"] = check_out

    if not data:
        return None

    return json.dumps(data)


def _make_selfie_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    normalized = path.lstrip("/")
    full_path = os.path.join(os.getcwd(), normalized)
    
    # Check if file exists before returning URL
    if not os.path.exists(full_path):
        print(f"Warning: Selfie file not found: {full_path}")
        return None
    
    return f"/{normalized}"


def _cleanup_broken_selfie_urls(db: Session) -> None:
    """Clean up broken selfie references in the database"""
    try:
        attendances = db.query(Attendance).filter(Attendance.selfie.isnot(None)).all()
        cleaned_count = 0
        
        for attendance in attendances:
            if attendance.selfie:
                selfie_data = _load_selfie_data(attendance.selfie)
                updated = False
                
                # Check check-in selfie
                if selfie_data.get("check_in"):
                    check_in_path = os.path.join(os.getcwd(), selfie_data["check_in"].lstrip("/"))
                    if not os.path.exists(check_in_path):
                        selfie_data["check_in"] = None
                        updated = True
                
                # Check check-out selfie
                if selfie_data.get("check_out"):
                    check_out_path = os.path.join(os.getcwd(), selfie_data["check_out"].lstrip("/"))
                    if not os.path.exists(check_out_path):
                        selfie_data["check_out"] = None
                        updated = True
                
                # Update database if changes were made
                if updated:
                    attendance.selfie = _dump_selfie_data(
                        selfie_data.get("check_in"),
                        check_out=selfie_data.get("check_out")
                    )
                    cleaned_count += 1
        
        if cleaned_count > 0:
            db.commit()
            print(f"Cleaned up {cleaned_count} broken selfie references")
            
    except Exception as e:
        print(f"Error cleaning up selfie references: {e}")
        db.rollback()


def _sanitize_text(value: Optional[str], *, max_length: int = 250) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


# ---------------------------------
# Office timing helpers & endpoints
# ---------------------------------

def _normalize_department_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _serialize_office_timing(timing: OfficeTiming) -> OfficeTimingOut:
    return OfficeTimingOut(
        id=timing.id,
        department=_normalize_department_value(timing.department),
        start_time=timing.start_time.strftime("%H:%M"),
        end_time=timing.end_time.strftime("%H:%M"),
        check_in_grace_minutes=timing.check_in_grace_minutes or 0,
        check_out_grace_minutes=timing.check_out_grace_minutes or 0,
    )


def _build_office_timing_cache(db: Session) -> Tuple[Optional[OfficeTiming], Dict[str, OfficeTiming]]:
    records = (
        db.query(OfficeTiming)
        .filter(OfficeTiming.is_active.is_(True))
        .order_by(OfficeTiming.updated_at.desc())
        .all()
    )

    global_entry: Optional[OfficeTiming] = None
    department_entries: Dict[str, OfficeTiming] = {}

    for entry in records:
        dept_key = _normalize_department_value(entry.department)
        if dept_key is None:
            if global_entry is None:
                global_entry = entry
            else:
                if entry.updated_at and (global_entry.updated_at is None or entry.updated_at > global_entry.updated_at):
                    global_entry = entry
        else:
            existing = department_entries.get(dept_key)
            if existing is None or (
                entry.updated_at and (existing.updated_at is None or entry.updated_at > existing.updated_at)
            ):
                department_entries[dept_key] = entry

    return global_entry, department_entries


def _resolve_office_timing(
    db: Session,
    department: Optional[str],
    cache: Optional[Tuple[Optional[OfficeTiming], Dict[str, OfficeTiming]]] = None,
) -> Optional[OfficeTiming]:
    if cache is None:
        cache = _build_office_timing_cache(db)
    global_entry, department_entries = cache
    dept_key = _normalize_department_value(department)
    if dept_key and dept_key in department_entries:
        return department_entries[dept_key]
    return global_entry


def _to_local_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    return dt


def _evaluate_attendance_status(
    check_in: Optional[datetime],
    check_out: Optional[datetime],
    timing: Optional[OfficeTiming],
) -> Dict[str, Any]:
    local_check_in = _to_local_timezone(check_in)
    local_check_out = _to_local_timezone(check_out)

    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    if timing:
        scheduled_start = timing.start_time.strftime("%H:%M")
        scheduled_end = timing.end_time.strftime("%H:%M")

    if not local_check_in:
        return {
            "status": "absent",
            "check_in_status": "absent",
            "check_out_status": "absent",
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
        }

    late = False
    early = False
    check_in_status = "on_time"
    check_out_status = "pending"

    if timing:
        start_dt = datetime.combine(local_check_in.date(), timing.start_time)
        if timing.check_in_grace_minutes:
            start_dt += timedelta(minutes=timing.check_in_grace_minutes)
        if local_check_in > start_dt:
            late = True
            check_in_status = "late"

    if local_check_out:
        check_out_status = "on_time"
        if timing:
            end_reference_date = local_check_out.date() if local_check_out else local_check_in.date()
            end_dt = datetime.combine(end_reference_date, timing.end_time)
            if timing.check_out_grace_minutes:
                end_dt -= timedelta(minutes=timing.check_out_grace_minutes)
            if local_check_out < end_dt:
                early = True
                check_out_status = "early"
    else:
        check_out_status = "pending"

    if not timing:
        check_in_status = "on_time"
        check_out_status = "on_time" if local_check_out else "pending"

    status = "present"
    if late:
        status = "late"

    return {
        "status": status,
        "check_in_status": check_in_status,
        "check_out_status": check_out_status,
        "scheduled_start": scheduled_start,
        "scheduled_end": scheduled_end,
    }


def _format_hours_to_hhmm(total_hours: float) -> str:
    """Format decimal hours to HH:MM format (e.g., 2.58 → '2:35')"""
    if total_hours is None:
        return "0:00"
    hours = int(total_hours)
    minutes = int(round((total_hours - hours) * 60))
    return f"{hours}:{minutes:02d}"


def _prepare_attendance_payload(attendance: Attendance) -> Dict[str, Any]:
    selfie_data = _load_selfie_data(getattr(attendance, "selfie", None))
    location_sections = _split_location_labels(getattr(attendance, "gps_location", None))
    check_in_selfie_path = _make_selfie_url(selfie_data.get("check_in"))
    check_out_selfie_path = _make_selfie_url(selfie_data.get("check_out"))
    work_report_url = _make_selfie_url(getattr(attendance, "work_report", None))
    location_label = location_sections.get("check_in") or getattr(attendance, "gps_location", None)
    total_hours_value = getattr(attendance, "total_hours", None)
    if isinstance(total_hours_value, Decimal):
        total_hours_value = float(total_hours_value)

    return {
        "attendance_id": attendance.attendance_id,
        "user_id": attendance.user_id,
        "employee_id": getattr(attendance, "employee_id", None),
        "name": getattr(attendance, "name", None),
        "department": getattr(attendance, "department", None),
        "check_in": attendance.check_in,
        "check_out": attendance.check_out,
        "total_hours": total_hours_value,
        "total_hours_formatted": _format_hours_to_hhmm(total_hours_value or 0),
        # "totalHoursFormatted": _format_hours_to_hhmm(total_hours_value or 0),
        "gps_location": location_label,
        # "locationLabel": location_label,
        "checkInLocationLabel": location_sections.get("check_in"),
        "checkOutLocationLabel": location_sections.get("check_out"),
        # "selfie": check_in_selfie_path,
        "checkInSelfie": check_in_selfie_path,
        "checkOutSelfie": check_out_selfie_path,
        "work_summary": getattr(attendance, "work_summary", None),
        # "workSummary": getattr(attendance, "work_summary", None),
        "work_report": work_report_url,
        # "workReport": work_report_url,
        "work_location": getattr(attendance, "work_location", "office"),
        # "workLocation": getattr(attendance, "work_location", "office"),
        "task_deadline_reason": getattr(attendance, "task_deadline_reason", None),
        # "taskDeadlineReason": getattr(attendance, "task_deadline_reason", None),
    }

def get_attendance_summary(db: Session, current_user: User) -> Dict[str, Any]:
    """Compute today's summary (role-scoped) using configured office timings."""
    try:
        today = now_ist().date()

        # Build role-scoped population query
        pop_query = db.query(User).filter(User.is_active.is_(True))

        user_role = current_user.role
        if user_role == RoleEnum.ADMIN:
            # Admin should not consider self and other admins
            pop_query = pop_query.filter(
                User.user_id != current_user.user_id,
                User.role != RoleEnum.ADMIN,
            )
        elif user_role == RoleEnum.HR:
            # HR should not consider self, other HRs, and admins
            pop_query = pop_query.filter(
                User.user_id != current_user.user_id,
                ~User.role.in_([RoleEnum.ADMIN, RoleEnum.HR]),
            )
        elif user_role == RoleEnum.MANAGER:
            # Manager can only see their department(s) TeamLeads and Employees
            dept_tokens = department_tokens_lower(getattr(current_user, "department", None))
            if not dept_tokens:
                return {
                    "total_employees": 0,
                    "present_today": 0,
                    "absent_today": 0,
                    "late_arrivals": 0,
                    "early_departures": 0,
                    "average_work_hours": 0.0,
                    "date": today.isoformat(),
                }
            patterns = [department_token_regex_pattern(d) for d in dept_tokens]
            dept_filters = [User.department.op("RLIKE")(pat) for pat in patterns]
            pop_query = pop_query.filter(
                User.role.in_([RoleEnum.TEAM_LEAD, RoleEnum.EMPLOYEE]),
                User.department.isnot(None),
                or_(*dept_filters),
            )
        else:
            # TeamLead/Employee (and any other roles): only see own summary
            pop_query = pop_query.filter(User.user_id == current_user.user_id)

        total_employees = pop_query.count()
        if total_employees == 0:
            return {
                "total_employees": 0,
                "present_today": 0,
                "absent_today": 0,
                "late_arrivals": 0,
                "early_departures": 0,
                "average_work_hours": 0.0,
                "date": today.isoformat(),
            }

        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        allowed_user_ids = [uid for (uid,) in pop_query.with_entities(User.user_id).all()]
        if not allowed_user_ids:
            return {
                "total_employees": 0,
                "present_today": 0,
                "absent_today": 0,
                "late_arrivals": 0,
                "early_departures": 0,
                "average_work_hours": 0.0,
                "date": today.isoformat(),
            }

        records = (
            db.query(Attendance, User)
            .join(User, Attendance.user_id == User.user_id)
            .filter(
                Attendance.check_in >= today_start,
                Attendance.check_in <= today_end,
                User.is_active.is_(True),
                User.user_id.in_(allowed_user_ids),
            )
            .all()
        )

        global_timing, dept_cache = _build_office_timing_cache(db)

        present_user_ids = set()
        late_arrivals = 0
        early_departures = 0
        work_durations: list[float] = []

        for attendance, user in records:
            present_user_ids.add(user.user_id)
            effective_timing = _resolve_office_timing(db, user.department, (global_timing, dept_cache))
            evaluation = _evaluate_attendance_status(attendance.check_in, attendance.check_out, effective_timing)

            if evaluation["check_in_status"] == "late":
                late_arrivals += 1
            if evaluation["check_out_status"] == "early":
                early_departures += 1
                
            if attendance.check_in and attendance.check_out:
                duration = attendance.check_out - attendance.check_in
                work_durations.append(duration.total_seconds() / 3600.0)
        
        present_today = len(present_user_ids)
        absent_today = max(total_employees - present_today, 0)
        average_work_hours = sum(work_durations) / len(work_durations) if work_durations else 0.0

        return {
            "total_employees": total_employees,
            "present_today": present_today,
            "absent_today": absent_today,
            "late_arrivals": late_arrivals,
            "early_departures": early_departures,
            "average_work_hours": round(average_work_hours, 2),
            "date": today.isoformat(),
        }
    except Exception as exc:
        logger.error("Error calculating attendance summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute attendance summary",
        )


def get_today_attendance_status(db: Session, department: Optional[str] = None) -> List[Dict[str, Any]]:
    records = get_today_attendance_records(db)
    if department:
        dept_key = _normalize_department_value(department)
        if dept_key:
            records = [record for record in records if _normalize_department_value(record.get("department")) == dept_key]
    return records


class ReverseGeocodePayload(BaseModel):
    lat: float
    lon: float


# @router.post("/reverse-geocode")
# def reverse_geocode(
#     payload: ReverseGeocodePayload,
#     current_user: User = Depends(get_current_user),
# ):
#     """Return human-readable location details for the given coordinates via server-side geocoding."""
#     try:
#         details = location_service.get_location_details(payload.lat, payload.lon)
#         return details
#     except Exception as exc:  # pragma: no cover - defensive catch
#         logger.error("Reverse geocode failed: %s", exc, exc_info=True)
#         raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to fetch location details")

def get_today_attendance_records(db: Session, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Return today's attendance records with user details, selfie, and location.
    Only shows users who have checked in today.
    """
    try:
        # Clean up broken selfie references periodically
        _cleanup_broken_selfie_urls(db)
        
        if target_date:
            today_start = datetime.combine(target_date, datetime.min.time())
        else:
            today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get only users who have checked in today
        raw_records = (
            db.query(
                User.user_id,
                User.employee_id,
                User.name,
                User.email,
                User.department,
                Attendance.attendance_id,
                Attendance.check_in,
                Attendance.check_out,
                Attendance.gps_location,
                Attendance.selfie,
                Attendance.total_hours,
                Attendance.work_summary,
                Attendance.work_report,
            )
            .join(Attendance, User.user_id == Attendance.user_id)
            .filter(
                Attendance.check_in >= today_start,
                Attendance.check_in < today_end,
                User.is_active == True
            )
            .order_by(Attendance.check_in.desc())
            .all()
        )

        # Prepare the final result with only users who have checked in today
        results: List[Dict[str, Any]] = []
        timing_cache = _build_office_timing_cache(db)

        for row in raw_records:
            (
                user_id,
                employee_id,
                name,
                email,
                department,
                attendance_id,
                check_in,
                check_out,
                gps_location,
                selfie,
                total_hours,
                work_summary,
                work_report,
            ) = row

            # calculate hours if needed
            calculated_hours = 0.0
            if check_in and check_out:
                duration = check_out - check_in
                calculated_hours = round(duration.total_seconds() / 3600, 2)

            attendance_obj = Attendance(
                attendance_id=attendance_id,
                user_id=user_id,
                check_in=check_in,
                check_out=check_out,
                total_hours=total_hours if total_hours is not None else calculated_hours,
                gps_location=gps_location,
                selfie=selfie,
            )
            attendance_obj.work_summary = work_summary
            attendance_obj.work_report = work_report

            payload = _prepare_attendance_payload(attendance_obj)
            payload.update(
                {
                    "employee_id": employee_id,
                    "name": name or "Unknown",
                    "email": email or "",
                    "department": department or "N/A",
                }
            )

            timing = _resolve_office_timing(db, department, timing_cache)
            evaluation = _evaluate_attendance_status(check_in, check_out, timing)
            payload.update(
                {
                    "status": evaluation["status"],
                    "checkInStatus": evaluation["check_in_status"],
                    "checkOutStatus": evaluation["check_out_status"],
                    "scheduledStart": evaluation["scheduled_start"],
                    "scheduledEnd": evaluation["scheduled_end"],
                }
            )
            results.append(payload)

        return results
        
    except Exception as e:
        logger.error(f"Error in get_today_attendance_records: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving attendance records: {str(e)}"
        )
def save_selfie(user_id: int, selfie: UploadFile, prefix: str = 'checkin') -> Optional[str]:
    """Helper function to save selfie file"""
    if not selfie:
        return None
        
    UPLOAD_DIR = "static/selfies"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_extension = selfie.filename.split('.')[-1] if '.' in selfie.filename else 'jpg'
    file_name = f"{user_id}_{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(selfie.file, buffer)
    return file_path


def save_work_report_file(user_id: int, document: UploadFile) -> Optional[str]:
    """Save uploaded work report/document and return relative path."""
    if not document:
        return None

    UPLOAD_DIR = "static/work_reports"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = document.filename.split('.')[-1] if document.filename and '.' in document.filename else 'bin'
    file_name = f"{user_id}_work_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(document.file, buffer)
    return file_path


def save_base64_work_report(user_id: int, data: str) -> Optional[str]:
    """Persist a base64-encoded work report/document."""
    if not data:
        return None

    if data.startswith("data:"):
        header, b64data = data.split(",", 1)
        mime_part = header.split(";")[0].split(":")[-1]
        ext = mime_part.split("/")[-1] if "/" in mime_part else "bin"
    else:
        b64data = data
        ext = "bin"

    try:
        raw = base64.b64decode(b64data)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid work report payload"
        ) from exc

    upload_dir = "static/work_reports"
    os.makedirs(upload_dir, exist_ok=True)
    file_name = f"{user_id}_work_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    file_path = os.path.join(upload_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(raw)
    return file_path

def validate_and_process_location(location_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate location and return processed location data"""
    if not location_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location data is required for check-in/out"
        )
    
    try:
        # If gps_location is a string, try to parse it as JSON
        if isinstance(location_data, str):
            location_data = json.loads(location_data)
            
        # Validate required fields
        if not all(k in location_data for k in ['latitude', 'longitude']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude and longitude are required in location data"
            )
            
        try:
            latitude = float(location_data['latitude'])
            longitude = float(location_data['longitude'])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid latitude or longitude provided"
            )

        raw_accuracy = location_data.get('accuracy')
        accuracy_value: Optional[float] = None
        if raw_accuracy is not None:
            try:
                accuracy_value = float(raw_accuracy)
            except (TypeError, ValueError):
                accuracy_value = None

        normalized_payload = {
            'latitude': latitude,
            'longitude': longitude,
            'accuracy': accuracy_value
        }

        is_valid, message = location_service.validate_location(normalized_payload)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
            
        # Get detailed location info
        location_details = location_service.get_location_details(latitude, longitude)

        if accuracy_value is not None:
            location_details['accuracy'] = accuracy_value

        provided_address = location_data.get('address')
        if provided_address:
            location_details['address'] = provided_address

        provided_place_name = location_data.get('placeName') or location_data.get('place_name')
        if provided_place_name:
            location_details['place_name'] = provided_place_name

        provided_timestamp = location_data.get('timestamp')
        if provided_timestamp:
            location_details['timestamp'] = provided_timestamp
        
        return location_details
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid location data format. Must be valid JSON."
        )
    except Exception as e:
        logger.error(f"Location processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing location: {str(e)}"
        )

# Employee Check-In
# @router.post("/check-in", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
# async def employee_check_in_route(
#     request: Request,
#     user_id: int = Form(...),
#     gps_location: Optional[str] = Form(None),
#     selfie: Optional[UploadFile] = File(None),
#     location_data: Optional[str] = Form(None),
#     work_location: Optional[str] = Form('office'),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     try:
#         # Parse location data
#         try:
#             loc_data = json.loads(location_data) if location_data else None
#             processed_location = validate_and_process_location(loc_data or gps_location)
#         except json.JSONDecodeError:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Invalid location data format. Must be valid JSON."
#             )

#         # Validate user exists and is active
#         user = db.query(User).filter(User.user_id == user_id, User.is_active == True).first()
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found or inactive"
#             )

#         # Save selfie if provided
#         selfie_path = save_selfie(user_id, selfie, 'checkin') if selfie else None

#         # Check for existing check-in today without check-out
#         today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
#         existing_attendance = (
#             db.query(Attendance)
#             .filter(
#                 Attendance.user_id == user_id,
#                 Attendance.check_in >= today_start,
#                 Attendance.check_out.is_(None)
#             )
#             .first()
#         )

#         if existing_attendance:
#             return _prepare_attendance_payload(existing_attendance)

#         # Validate and set work location (default to 'office')
#         if work_location not in ['office', 'work_from_home']:
#             work_location = 'office'

#         # Create new check-in with location data
#         attendance = Attendance(
#             user_id=user_id,
#             check_in=now_ist(),
#             gps_location=_compose_location_entry(None, "Check-in", processed_location),
#             selfie=_dump_selfie_data(None, check_in=selfie_path) if selfie_path else None,
#             total_hours=0.0,
#             work_location=work_location
#         )
        
#         db.add(attendance)
#         db.commit()
#         db.refresh(attendance)
        
#         # Set user as online after check-in (respects previous offline status from same day)
#         from app.db.models.online_status import OnlineStatus
        
#         # Check if user was offline yesterday - if so, reset to online for new day
#         yesterday_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
#         today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        
#         # Get user's last status from yesterday
#         last_status_yesterday = db.query(OnlineStatus).filter(
#             OnlineStatus.user_id == user_id,
#             OnlineStatus.timestamp >= yesterday_start,
#             OnlineStatus.timestamp < today_start
#         ).order_by(OnlineStatus.timestamp.desc()).first()
        
#         # Check if user already has a status today
#         existing_status_today = db.query(OnlineStatus).filter(
#             OnlineStatus.user_id == user_id,
#             OnlineStatus.timestamp >= today_start
#         ).first()
        
#         # Only create new online status if:
#         # 1. No status exists today, OR
#         # 2. User was offline yesterday (daily reset)
#         should_set_online = (
#             not existing_status_today or 
#             (last_status_yesterday and not last_status_yesterday.is_online)
#         )
        
#         if should_set_online:
#             online_status = OnlineStatus(
#                 attendance_id=attendance.attendance_id,
#                 user_id=user_id,
#                 is_online=True,
#                 reason="Online status after check-in" + (" (daily reset)" if last_status_yesterday and not last_status_yesterday.is_online else ""),
#                 timestamp=now_ist()
#             )
#             db.add(online_status)
#             db.commit()
        
#         print(f"Successfully created check-in for user {user_id}, attendance ID: {attendance.attendance_id}")
        
#         return _prepare_attendance_payload(attendance)
        
#     except Exception as e:
#         db.rollback()
#         print(f"Error in check-in for user {user_id}: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"An error occurred while processing check-in: {str(e)}"
#         )

# Employee Check-In via JSON (base64 selfie)
@router.post("/check-in/json", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def employee_check_in_json(
    request: Request,
    payload: AttendanceJSONPayload, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if payload.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to check in for another user."
            )

        user = db.query(User).filter(User.user_id == payload.user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

        selfie_path = None
        if payload.selfie:
            data = payload.selfie
            if data.startswith('data:image'):
                header, b64data = data.split(',', 1)
            else:
                b64data = data
            raw = base64.b64decode(b64data)
            UPLOAD_DIR = "static/selfies"
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            file_name = f"{payload.user_id}_checkin_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            file_path = os.path.join(UPLOAD_DIR, file_name)
            with open(file_path, 'wb') as f:
                f.write(raw)
            selfie_path = file_path

        location_payload = _ensure_location_dict(payload.gps_location)
        processed_location = validate_and_process_location(location_payload)

        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        existing_attendance = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == payload.user_id,
                Attendance.check_in >= today_start,
                Attendance.check_out.is_(None)
            )
            .first()
        )
        if existing_attendance:
            return _prepare_attendance_payload(existing_attendance)

        # Get work location from payload or default to 'office'
        work_location = payload.work_location if payload.work_location else 'office'

        # Create new check-in with location data
        attendance = Attendance(
            user_id=payload.user_id,
            check_in=now_ist(),
            gps_location=_compose_location_entry(None, "Check-in", processed_location),
            selfie=_dump_selfie_data(None, check_in=selfie_path) if selfie_path else None,
            total_hours=0.0,
            work_location=work_location
        )
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        
        # Set user as online after check-in (respects previous offline status from same day)
        from app.db.models.online_status import OnlineStatus
        
        # Check if user was offline yesterday - if so, reset to online for new day
        yesterday_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get user's last status from yesterday
        last_status_yesterday = db.query(OnlineStatus).filter(
            OnlineStatus.user_id == payload.user_id,
            OnlineStatus.timestamp >= yesterday_start,
            OnlineStatus.timestamp < today_start
        ).order_by(OnlineStatus.timestamp.desc()).first()
        
        # Check if user already has a status today
        existing_status_today = db.query(OnlineStatus).filter(
            OnlineStatus.user_id == payload.user_id,
            OnlineStatus.timestamp >= today_start
        ).first()
        
        # Only create new online status if:
        # 1. No status exists today, OR
        # 2. User was offline yesterday (daily reset)
        should_set_online = (
            not existing_status_today or 
            (last_status_yesterday and not last_status_yesterday.is_online)
        )
        
        if should_set_online:
            online_status = OnlineStatus(
                attendance_id=attendance.attendance_id,
                user_id=payload.user_id,
                is_online=True,
                reason="Online status after check-in" + (" (daily reset)" if last_status_yesterday and not last_status_yesterday.is_online else ""),
                timestamp=now_ist()
            )
            db.add(online_status)
            db.commit()
        
        return _prepare_attendance_payload(attendance)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error in JSON check-in: {str(e)}")


# Employee Check-Out
# @router.post("/check-out", response_model=AttendanceOut)
# async def employee_check_out_route(
#     request: Request,
#     user_id: int = Form(...),
#     gps_location: Optional[str] = Form(None),
#     selfie: Optional[UploadFile] = File(None),
#     location_data: Optional[str] = Form(None),
#     work_summary: Optional[str] = Form(None, description="Summary of today's work"),
#     work_report: Optional[UploadFile] = File(None),
#     task_deadline_reason: Optional[str] = Form(None, description="Reason for incomplete tasks on deadline"),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     try:
#         # Validate user exists and is active
#         user = db.query(User).filter(User.user_id == user_id, User.is_active == True).first()
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found or inactive"
#             )

#         # Parse and validate location data
#         location_source = location_data or gps_location
#         processed_location: Dict[str, Any]
#         try:
#             normalized_location = _ensure_location_dict(location_source)
#             processed_location = validate_and_process_location(normalized_location)
#         except HTTPException:
#             raise
#         except Exception:
#             processed_location = {
#                 "address": "Location not provided",
#                 "latitude": None,
#                 "longitude": None,
#             }

#         # Check for overdue tasks before allowing checkout
#         from app.db.models.task import Task
#         from app.enums import TaskStatus
#         from datetime import date
        
#         today = date.today()
#         overdue_tasks = db.query(Task).filter(
#             Task.assigned_to == user_id,
#             Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
#             Task.due_date == today
#         ).all()
        
#         # If there are tasks due today, require a reason
#         if overdue_tasks:
#             reason_text = (task_deadline_reason or "").strip()
#             if not reason_text:
#                 task_titles = [task.title for task in overdue_tasks]
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail=f"You have tasks due today that are not completed: {', '.join(task_titles)}. Please provide a reason for not completing them before checkout."
#                 )
            
#             # Validate reason length and content
#             if len(reason_text) < 15:
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail="Task deadline reason must be at least 15 characters long."
#                 )
            
#             # Check if reason contains only numbers
#             if reason_text.isdigit():
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail="Task deadline reason cannot contain only numbers. Please provide a meaningful explanation."
#                 )

#         summary_text = (work_summary or "").strip()
#         if not summary_text:
#             # Provide a default work summary if none is provided (for automatic logout scenarios)
#             summary_text = "Automatic check-out (no summary provided)"
#             logger.info(f"User {user_id} checked out without work summary - using default")

#         # Save selfie if provided
#         selfie_path = save_selfie(user_id, selfie, 'checkout') if selfie else None
#         work_report_path = save_work_report_file(user_id, work_report) if work_report else None

#         # Find today's check-in
#         today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
#         attendance = (
#             db.query(Attendance)
#             .filter(
#                 Attendance.user_id == user_id,
#                 Attendance.check_in >= today_start,
#                 Attendance.check_out.is_(None)  # Only update if not already checked out
#             )
#             .order_by(Attendance.check_in.desc())
#             .first()
#         )

#         if not attendance:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No active check-in found for today"
#             )

#         # Update check-out with location data
#         attendance.check_out = now_ist()
#         if selfie_path:
#             attendance.selfie = _dump_selfie_data(attendance.selfie, check_out=selfie_path)
#         attendance.gps_location = _compose_location_entry(
#             attendance.gps_location,
#             "Check-out",
#             processed_location,
#         )
#         attendance.work_summary = summary_text
#         if work_report_path:
#             attendance.work_report = work_report_path
#         if overdue_tasks and task_deadline_reason:
#             attendance.task_deadline_reason = task_deadline_reason.strip()

#         # Calculate total hours worked
#         time_worked = attendance.check_out - attendance.check_in
#         attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)  # Convert to hours with 2 decimal places
        
#         # Automatically set user as offline after check-out
#         from app.db.models.online_status import OnlineStatus
#         offline_status = OnlineStatus(
#             attendance_id=attendance.attendance_id,
#             user_id=user_id,
#             is_online=False,
#             reason="Automatic offline status after check-out",
#             timestamp=now_ist()
#         )
#         db.add(offline_status)
        
#         db.commit()
#         db.refresh(attendance)
        
#         print(f"Successfully processed check-out for user {user_id}, attendance ID: {attendance.attendance_id}")
        
#         return _prepare_attendance_payload(attendance)
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         print(f"Error in check-out for user {user_id}: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"An error occurred while processing check-out: {str(e)}"
#         )


# Employee Check-Out via JSON (base64 selfie)
@router.post("/check-out/json", response_model=AttendanceOut)
async def employee_check_out_json(
    request: Request,
    payload: AttendanceJSONPayload, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if payload.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to check out for another user."
            )

        user = db.query(User).filter(User.user_id == payload.user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

        selfie_path = None
        if payload.selfie:
            try:
                data = payload.selfie
                if data.startswith('data:image'):
                    _, b64data = data.split(',', 1)
                else:
                    b64data = data
                raw = base64.b64decode(b64data)
            except Exception as decode_error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid selfie payload: {decode_error}"
                )

            UPLOAD_DIR = "static/selfies"
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            file_name = f"{payload.user_id}_checkout_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            file_path = os.path.join(UPLOAD_DIR, file_name)
            with open(file_path, 'wb') as f:
                f.write(raw)
            selfie_path = file_path

        # Check for overdue tasks before allowing checkout
        from app.db.models.task import Task
        from app.enums import TaskStatus
        from datetime import date
        
        today = date.today()
        overdue_tasks = db.query(Task).filter(
            Task.assigned_to == payload.user_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.due_date == today
        ).all()
        
        # If there are tasks due today, require a reason
        if overdue_tasks:
            reason_text = (payload.task_deadline_reason or "").strip()
            if not reason_text:
                task_titles = [task.title for task in overdue_tasks]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"You have tasks due today that are not completed: {', '.join(task_titles)}. Please provide a reason for not completing them before checkout."
                )
            
            # Validate reason length and content
            if len(reason_text) < 15:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task deadline reason must be at least 15 characters long."
                )
            
            # Check if reason contains only numbers
            if reason_text.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task deadline reason cannot contain only numbers. Please provide a meaningful explanation."
                )

        summary_text = (payload.work_summary or "").strip()
        if not summary_text:
            # Provide a default work summary if none is provided (for automatic logout scenarios)
            summary_text = "Automatic check-out (no summary provided)"
            logger.info(f"User {payload.user_id} checked out without work summary - using default")

        work_report_path = None
        if payload.work_report:
            work_report_path = save_base64_work_report(payload.user_id, payload.work_report)

        location_source = payload.gps_location or (payload.location_data or {}).get('check_out') or (payload.location_data or {}).get('check_in')
        processed_location: Dict[str, Any]
        try:
            location_payload = _ensure_location_dict(location_source)
            processed_location = validate_and_process_location(location_payload)
        except HTTPException:
            raise
        except Exception:
            processed_location = {
                "address": "Location not provided",
                "latitude": None,
                "longitude": None,
            }

        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        attendance = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == payload.user_id,
                Attendance.check_in >= today_start,
                Attendance.check_out.is_(None)
            )
            .order_by(Attendance.check_in.desc())
            .first()
        )
        if not attendance:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active check-in found for today")

        # Update check-out with location data
        attendance.check_out = now_ist()
        if selfie_path:
            attendance.selfie = _dump_selfie_data(attendance.selfie, check_out=selfie_path)
        attendance.gps_location = _compose_location_entry(
            attendance.gps_location,
            "Check-out",
            processed_location,
        )
        attendance.work_summary = summary_text
        if work_report_path:
            attendance.work_report = work_report_path
        if overdue_tasks and payload.task_deadline_reason:
            attendance.task_deadline_reason = payload.task_deadline_reason.strip()
        # Compute online-only working hours and store
        try:
            from app.crud.attendance_crud import compute_online_work_hours
            hours = compute_online_work_hours(db, attendance)
            attendance.total_hours = round(hours, 2)
        except Exception:
            # Fallback to wall-clock duration if online-hours calc fails for any reason
            time_worked = attendance.check_out - attendance.check_in
            attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)
        
        # Automatically set user as offline after check-out
        from app.db.models.online_status import OnlineStatus
        offline_status = OnlineStatus(
            attendance_id=attendance.attendance_id,
            user_id=payload.user_id,
            is_online=False,
            reason="Automatic offline status after check-out",
            timestamp=now_ist()
        )
        db.add(offline_status)
        
        db.commit()
        db.refresh(attendance)
        return _prepare_attendance_payload(attendance)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error in JSON check-out: {str(e)}")

# Employee Self-Attendance (Last 6 Months)
@router.get("/my-attendance/{user_id}")
def get_self_attendance(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Strictly "my attendance": users can only view their own records
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own attendance records",
        )

    six_months_ago = now_ist() - timedelta(days=180)
    records = (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= six_months_ago)
        .order_by(Attendance.check_in.desc())
        .all()
    )

    # Enrich with basic user details (employee_id, name, department) like /attendance/today
    user_row = (
        db.query(User.employee_id, User.name, User.department)
        .filter(User.user_id == user_id, User.is_active.is_(True))
        .first()
    )

    response: list[dict] = []
    for record in records:
        payload = _prepare_attendance_payload(record)
        if user_row:
            payload.update(
                {
                    "employee_id": user_row.employee_id,
                    "name": user_row.name or "Unknown",
                    "department": user_row.department or "N/A",
                }
            )
        response.append(payload)

    return response

# Today's Attendance Summary
@router.get("/summary")
def attendance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get attendance summary with statistics including late/early counts"""
    return get_attendance_summary(db, current_user)

# Today's Attendance Records (for Manager view)
@router.get("/today")
def get_today_attendance(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD) for which to fetch records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get attendance records for the specified date (defaults to today).

    Visibility rules:
    - ADMIN: See all users' attendance except Admins and self.
    - HR: See all users' attendance except Admins, other HRs, and self.
    - MANAGER: See users in their department(s) (supports comma-separated departments),
      excluding Admins, HRs, other Managers, and self.
    - TEAM_LEAD and EMPLOYEE: Cannot view this data (403).
    """
    target_date: Optional[date] = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )
    records = get_today_attendance_records(db, target_date)

    user_role = current_user.role

    # Admin: all users except admins and self
    if user_role == RoleEnum.ADMIN:
        allowed_ids = {
            u.user_id
            for u in db.query(User.user_id)
            .filter(User.is_active.is_(True))
            .filter(User.role != RoleEnum.ADMIN)
            .filter(User.user_id != current_user.user_id)
            .all()
        }
        return [r for r in records if r.get("user_id") in allowed_ids]

    # HR: all users except admins, HRs, and self
    if user_role == RoleEnum.HR:
        allowed_ids = {
            u.user_id
            for u in db.query(User.user_id)
            .filter(User.is_active.is_(True))
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]))
            .filter(User.user_id != current_user.user_id)
            .all()
        }
        return [r for r in records if r.get("user_id") in allowed_ids]

    # Manager: employees in own department(s), excluding admins/HRs/managers/self
    if user_role == RoleEnum.MANAGER:
        manager_depts = set(department_tokens_lower(current_user.department))
        if not manager_depts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manager must have a department assigned")

        candidates = (
            db.query(User.user_id, User.department)
            .filter(User.is_active.is_(True))
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]))
            .filter(User.user_id != current_user.user_id)
            .all()
        )

        allowed_ids = set()
        for uid, dept in candidates:
            user_depts = set(department_tokens_lower(dept))
            if manager_depts & user_depts:
                allowed_ids.add(uid)

        return [r for r in records if r.get("user_id") in allowed_ids]

    # TeamLead / Employee (and any other roles): forbidden
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view attendance records")
@router.get("/download/csv")
def download_attendance_csv(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    date_range: Optional[str] = Query(None, description="Optional date range: 'last_6_months' or 'last_1_year'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR))
):
    """Download attendance data as a CSV file with optional filters. Only accessible by Admin and HR."""
    from app.crud.attendance_crud import export_attendance_csv
    
    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    # Apply date range shortcut if explicit start date is not provided
    if not start_dt and date_range:
        now = now_ist()
        if date_range == "last_6_months":
            # 6 months ~ 180 days
            start_dt = now - timedelta(days=180)
        elif date_range == "last_1_year":
             # 1 year ~ 365 days
            start_dt = now - timedelta(days=365)
    
    output = export_attendance_csv(
        db,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        employee_id=employee_id,
        department=department.strip() if department else None,
    )
    
    # Generate filename with date range
    filename = "attendance_report.csv"
    if start_dt and end_dt:
        filename = f"attendance_report_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.csv"
    elif start_dt:
        filename = f"attendance_report_from_{start_dt.strftime('%Y%m%d')}.csv"
    elif end_dt:
        filename = f"attendance_report_until_{end_dt.strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ✅ Download Attendance as PDF
@router.get("/download/pdf")
def download_attendance_pdf(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    period_type: Optional[str] = Query(None, description="Period type: 'monthly', 'quarterly', or 'custom' (default: custom if start_date/end_date provided)"),
    month: Optional[int] = Query(None, ge=0, le=11, description="Month (0-11) for monthly period"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Quarter (1-4) for quarterly period"),
    year: Optional[int] = Query(None, description="Year for monthly or quarterly period"),
    department: Optional[str] = Query(None, description="Filter by department"),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
    db: Session = Depends(get_db)
):
    """Download attendance data as a PDF file with optional filters. Only accessible by Admin and HR."""
    from app.crud.attendance_crud import export_attendance_pdf
    
    # Determine date range: support monthly/quarterly/custom without changing existing logic.
    start_dt = None
    end_dt = None

    # Normalize period_type if provided
    if period_type:
        period_type = period_type.lower()
    elif month is not None or quarter is not None:
        # Infer period type from provided params
        if month is not None:
            period_type = 'monthly'
        elif quarter is not None:
            period_type = 'quarterly'
        else:
            period_type = None
    elif start_date or end_date:
        period_type = 'custom'

    try:
        if period_type == 'monthly':
            if month is None or year is None:
                raise HTTPException(status_code=400, detail="For monthly period, both 'month' (0-11) and 'year' are required")
            actual_month = month + 1
            start_dt = datetime(year, actual_month, 1)
            if actual_month == 12:
                end_dt = datetime(year + 1, 1, 1)
            else:
                end_dt = datetime(year, actual_month + 1, 1)
        elif period_type == 'quarterly':
            if quarter is None or year is None:
                raise HTTPException(status_code=400, detail="For quarterly period, both 'quarter' (1-4) and 'year' are required")
            if quarter == 1:
                start_dt = datetime(year, 1, 1)
                end_dt = datetime(year, 4, 1)
            elif quarter == 2:
                start_dt = datetime(year, 4, 1)
                end_dt = datetime(year, 7, 1)
            elif quarter == 3:
                start_dt = datetime(year, 7, 1)
                end_dt = datetime(year, 10, 1)
            elif quarter == 4:
                start_dt = datetime(year, 10, 1)
                end_dt = datetime(year + 1, 1, 1)
        elif period_type == 'custom':
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
        else:
            # No period_type provided; fall back to existing behaviour (parse start_date/end_date if present)
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date parameters: {str(e)}")
    
    buffer = export_attendance_pdf(
        db,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        employee_id=employee_id,
        department=department.strip() if department else None,
        generated_by=current_user.name,
    )
    
    # Generate filename with date range
    filename = "attendance_report.pdf"
    if start_dt and end_dt:
        filename = f"attendance_report_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.pdf"
    elif start_dt:
        filename = f"attendance_report_from_{start_dt.strftime('%Y%m%d')}.pdf"
    elif end_dt:
        filename = f"attendance_report_until_{end_dt.strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Get Today's Attendance Status (for Admin/HR/Manager)
@router.get("/today-status")
def get_today_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's attendance status for employees who have checked in today.
    Visibility rules:
    - ADMIN: See all employees (as-is).
    - HR: See all employees except Admins, other HRs, and self.
    - MANAGER: See employees in their department(s) (supports comma-separated values),
      excluding Admins, HRs, other Managers, and self.
    - Others: Not allowed.
    """
    user_role = current_user.role
    user_department = current_user.department
    
    if user_role == RoleEnum.ADMIN:
        # Admin can see all employees
        return get_today_attendance_status(db)

    records = get_today_attendance_status(db)

    if user_role == RoleEnum.HR:
        # HR can see all employees, excluding Admins, HRs, and themselves.
        allowed_ids = {
            u.user_id
            for u in db.query(User.user_id)
            .filter(User.is_active.is_(True))
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]))
            .filter(User.user_id != current_user.user_id)
            .all()
        }
        return [r for r in records if r.get("user_id") in allowed_ids]

    if user_role == RoleEnum.MANAGER:
        # Manager can see only employees in their own department(s),
        # excluding Admins, HRs, other Managers, and themselves.
        manager_depts = set(department_tokens_lower(user_department))
        if not manager_depts:
            raise HTTPException(status_code=400, detail="Manager must have a department assigned")

        candidates = (
            db.query(User.user_id, User.department)
            .filter(User.is_active.is_(True))
            .filter(User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]))
            .filter(User.user_id != current_user.user_id)
            .all()
        )
        allowed_ids = set()
        for uid, dept in candidates:
            user_depts = set(department_tokens_lower(dept))
            if manager_depts & user_depts:
                allowed_ids.add(uid)

        return [r for r in records if r.get("user_id") in allowed_ids]

    raise HTTPException(status_code=403, detail="Not authorized to view attendance")

# Get All Attendance History (for Admin/HR/Manager)
@router.get("/all")
def get_all_attendance_history(
    department: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all attendance history
    - ADMIN: See all users except Admins.
    - HR: See all users except Admins, HRs, and self.
    - MANAGER: See users in their department(s) (supports comma-separated),
      excluding Admins, HRs, other Managers, and self.
    - Others: Not allowed
    """
    user_role = current_user.role
    user_department = current_user.department
    
    records_query = (
        db.query(
            Attendance,
            User.name,
            User.department,
            User.employee_id,
            User.email,
        )
        .join(User, Attendance.user_id == User.user_id)
    )

    if user_role == RoleEnum.ADMIN:
        # Admin can see all non-admin users (optionally filter by department)
        records_query = records_query.filter(User.role != RoleEnum.ADMIN)
        if department:
            records_query = records_query.filter(User.department == department)
    elif user_role == RoleEnum.HR:
        # HR can see all non-admin/non-HR users except self; optional department filter applies
        records_query = records_query.filter(
            User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR]),
            User.user_id != current_user.user_id,
        )
        if department:
            records_query = records_query.filter(User.department == department)
    elif user_role == RoleEnum.MANAGER:
        # Manager can only see their department(s) — support comma-separated manager.department,
        # excluding Admins, HRs, other Managers, and self.
        if not user_department:
            raise HTTPException(status_code=400, detail="Manager must have a department assigned")
        manager_depts = department_tokens_lower(user_department)
        # Exclude disallowed roles and self first
        records_query = records_query.filter(
            User.role.notin_([RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]),
            User.user_id != current_user.user_id,
        )
        if manager_depts:
            patterns = [department_token_regex_pattern(d) for d in manager_depts]
            filters = [User.department.op("RLIKE")(pat) for pat in patterns]
            records_query = records_query.filter(or_(*filters))
        else:
            records_query = records_query.filter(User.department == user_department)
    else:
        raise HTTPException(status_code=403, detail="Not authorized to view attendance")

    try:
        records = records_query.order_by(Attendance.check_in.desc()).all()
    except Exception as e:
        logger.error(f"Error querying attendance records: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching attendance records: {str(e)}")

    # Format the response - include email and other user details
    result = []
    timing_cache = _build_office_timing_cache(db)
    for att, name, dept, emp_id, email in records:
        payload = _prepare_attendance_payload(att)
        payload.update(
            {
                "name": name,
                # "userName": name,
                "department": dept,
                "employee_id": emp_id,
                "email": email,
                # "userEmail": email,
            }
        )
        check_in_value = payload.get("check_in")
        if isinstance(check_in_value, datetime):
            payload["check_in"] = check_in_value.isoformat()
        check_out_value = payload.get("check_out")
        if isinstance(check_out_value, datetime):
            payload["check_out"] = check_out_value.isoformat()

        timing = _resolve_office_timing(db, dept, timing_cache)
        evaluation = _evaluate_attendance_status(att.check_in, att.check_out, timing)
        payload.update(
            {
                "status": evaluation["status"],
                "checkInStatus": evaluation["check_in_status"],
                "checkOutStatus": evaluation["check_out_status"],
                "scheduledStart": evaluation["scheduled_start"],
                "scheduledEnd": evaluation["scheduled_end"],
            }
        )
        result.append(payload)

    return result

@router.get("/office-hours", response_model=List[OfficeTimingOut])
def list_office_timings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only Admins can view office hours
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view office timings",
        )

    records = (
        db.query(OfficeTiming)
        .filter(OfficeTiming.is_active.is_(True))
        .order_by(OfficeTiming.department.is_(None).desc(), OfficeTiming.department.asc())
        .all()
    )
    return [_serialize_office_timing(record) for record in records]


@router.get("/office-hours/effective", response_model=OfficeTimingOut)
def get_effective_office_timing(
    department: Optional[str] = Query(default=None, description="Department to resolve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    timing = _resolve_office_timing(db, department)
    if not timing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office timing not configured")
    return _serialize_office_timing(timing)


@router.put("/office-hours", response_model=OfficeTimingOut, status_code=status.HTTP_201_CREATED)
def upsert_office_timing(
    payload: OfficeTimingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can modify office timings")

    normalized_department = _normalize_department_value(payload.department)

    try:
        start_time_obj = datetime.strptime(payload.start_time, "%H:%M").time()
        end_time_obj = datetime.strptime(payload.end_time, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time format. Use HH:MM") from exc

    if datetime.combine(now_ist().date(), end_time_obj) <= datetime.combine(now_ist().date(), start_time_obj):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time")

    query = db.query(OfficeTiming).filter(OfficeTiming.is_active.is_(True))
    if normalized_department is None:
        existing = query.filter(OfficeTiming.department.is_(None)).first()
    else:
        existing = query.filter(func.lower(OfficeTiming.department) == normalized_department.lower()).first()

    if existing:
        existing.start_time = start_time_obj
        existing.end_time = end_time_obj
        existing.check_in_grace_minutes = payload.check_in_grace_minutes
        existing.check_out_grace_minutes = payload.check_out_grace_minutes
        existing.department = normalized_department
        existing.is_active = True
        timing = existing
    else:
        timing = OfficeTiming(
            department=normalized_department,
            start_time=start_time_obj,
            end_time=end_time_obj,
            check_in_grace_minutes=payload.check_in_grace_minutes,
            check_out_grace_minutes=payload.check_out_grace_minutes,
            is_active=True,
        )
        db.add(timing)

    db.commit()
    db.refresh(timing)
    return _serialize_office_timing(timing)


@router.delete("/office-hours/{timing_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_office_timing(
    timing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can delete office timings")

    timing = db.query(OfficeTiming).filter(OfficeTiming.id == timing_id).first()
    if not timing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office timing not found")

    timing.is_active = False
    db.commit()


# Online/Offline Status Management
class OnlineStatusPayload(BaseModel):
    attendance_id: int
    is_online: bool
    reason: Optional[str] = None


@router.post("/online-status", status_code=status.HTTP_200_OK)
def update_online_status(
    payload: OnlineStatusPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user's online/offline status for attendance tracking.
    When offline, work hours calculation is paused.
    """
    from app.db.models.online_status import OnlineStatus
    
    # Verify attendance record exists and belongs to user
    attendance = db.query(Attendance).filter(
        Attendance.attendance_id == payload.attendance_id,
        Attendance.user_id == current_user.user_id
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Check if user has already checked out
    if attendance.check_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change status after checkout"
        )
    
    # Validate reason for going offline
    if not payload.is_online:
        if not payload.reason or len(payload.reason.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reason required (minimum 10 characters) for going offline"
            )
    
    # Create status log entry
    status_log = OnlineStatus(
        attendance_id=payload.attendance_id,
        user_id=current_user.user_id,
        is_online=payload.is_online,
        reason=payload.reason.strip() if payload.reason else None,
        timestamp=now_ist()
    )
    db.add(status_log)
    db.commit()
    db.refresh(status_log)
    
    return {
        "message": f"Status updated to {'online' if payload.is_online else 'offline'}",
        "status_id": status_log.id,
        "timestamp": status_log.timestamp.isoformat(),
        "is_online": status_log.is_online
    }


@router.get("/online-status/{attendance_id}")
def get_online_status_history(
    attendance_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get online/offline status history for an attendance record.
    Returns list of status changes with timestamps.
    """
    from app.db.models.online_status import OnlineStatus
    
    # Verify attendance belongs to user or user has permission
    attendance = db.query(Attendance).filter(
        Attendance.attendance_id == attendance_id
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Check permissions
    if attendance.user_id != current_user.user_id:
        if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get status history
    status_logs = db.query(OnlineStatus).filter(
        OnlineStatus.attendance_id == attendance_id
    ).order_by(OnlineStatus.timestamp.asc()).all()
    
    return {
        "attendance_id": attendance_id,
        "status_history": [
            {
                "id": log.id,
                "is_online": log.is_online,
                "reason": log.reason,
                "timestamp": log.timestamp.isoformat()
            }
            for log in status_logs
        ]
    }


@router.get("/current-online-status")
def get_all_current_online_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current online/offline status for all users who are checked in today.
    Returns a map of user_id to online status.
    Only accessible by admin, hr, and manager roles.
    """
    from app.db.models.online_status import OnlineStatus
    
    # Check permissions
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get today's date in UTC
    today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get all attendance records for today that haven't checked out
    today_attendances = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end,
        Attendance.check_out.is_(None)  # Only checked-in users
    ).all()
    
    status_map = {}
    
    for attendance in today_attendances:
        # Get the latest status log for this user today
        latest_status = db.query(OnlineStatus).filter(
            OnlineStatus.user_id == attendance.user_id,
            OnlineStatus.timestamp >= today_start,
            OnlineStatus.timestamp < today_end
        ).order_by(OnlineStatus.timestamp.desc()).first()
        
        # Default to online if no status logs today (just checked in)
        is_online = True if not latest_status else latest_status.is_online
        
        status_map[attendance.user_id] = {
            "is_online": is_online,
            "attendance_id": attendance.attendance_id,
            "check_in": attendance.check_in.isoformat(),
            "last_status_change": latest_status.timestamp.isoformat() if latest_status else attendance.check_in.isoformat()
        }
    
    return status_map


@router.get("/user-online-status/{user_id}")
def get_user_current_online_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current online/offline status for a specific user.
    """
    from app.db.models.online_status import OnlineStatus
    
    # Check permissions - user can check their own status, or admin/hr/manager can check anyone
    if current_user.user_id != user_id:
        if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get today's attendance for this user
    today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    attendance = db.query(Attendance).filter(
        Attendance.user_id == user_id,
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end
    ).first()
    
    if not attendance:
        return {
            "is_checked_in": False,
            "is_online": False,
            "message": "User has not checked in today"
        }
    
    # If checked out, they're offline
    if attendance.check_out:
        return {
            "is_checked_in": True,
            "is_online": False,
            "checked_out": True,
            "check_out_time": attendance.check_out.isoformat()
        }
    
    # Get latest status for today
    latest_status = db.query(OnlineStatus).filter(
        OnlineStatus.user_id == user_id,
        OnlineStatus.timestamp >= today_start,
        OnlineStatus.timestamp < today_end
    ).order_by(OnlineStatus.timestamp.desc()).first()
    
    is_online = True if not latest_status else latest_status.is_online
    
    return {
        "is_checked_in": True,
        "is_online": is_online,
        "attendance_id": attendance.attendance_id,
        "check_in": attendance.check_in.isoformat(),
        "last_status_change": latest_status.timestamp.isoformat() if latest_status else attendance.check_in.isoformat()
    }


@router.get("/working-hours/summary")
def working_hours_summary(
    period: Literal["week", "current_month", "last_month", "last_3_months", "custom"] = Query(
        "week",
        description="Date range filter: week, current_month, last_month, last_3_months, custom",
    ),
    user_id: Optional[int] = Query(None, description="Target user_id (defaults to current user)"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD). Required when period=custom"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD). Required when period=custom"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aggregate working hours for a user across a date range.
    Working hours only include time when user was online (based on OnlineStatus logs).
    """
    from app.db.models.online_status import OnlineStatus

    target_user_id = user_id if user_id is not None else current_user.user_id

    # Permission / role hierarchy:
    # - Everyone can view their own summary
    # - ADMIN: can view all except Admins (and self already handled)
    # - HR: can view all except Admins + HRs
    # - MANAGER: can view non-privileged users (not Admin/HR/Manager) in their department(s) (supports comma-separated)
    if target_user_id != current_user.user_id:
        target_user = db.query(User).filter(User.user_id == target_user_id).first()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if current_user.role == RoleEnum.ADMIN:
            if target_user.role == RoleEnum.ADMIN:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        elif current_user.role == RoleEnum.HR:
            if target_user.role in [RoleEnum.ADMIN, RoleEnum.HR]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        elif current_user.role == RoleEnum.MANAGER:
            if target_user.role in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            manager_tokens = set(department_tokens_lower(getattr(current_user, "department", None)))
            target_tokens = set(department_tokens_lower(getattr(target_user, "department", None)))
            if not manager_tokens or not target_tokens or not manager_tokens.intersection(target_tokens):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        else:
            # TeamLead/Employee/etc cannot view other users
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    def shift_month(year: int, month: int, delta_months: int) -> tuple[int, int]:
        m = month + delta_months
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        return y, m

    now = now_ist()

    # Build [start_dt, end_dt) bounds in naive IST
    if period == "week":
        today = now.date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        start_dt = datetime.combine(start_of_week, time.min)
        end_dt = now
    elif period == "current_month":
        start_dt = datetime(now.year, now.month, 1)
        end_dt = now
    elif period == "last_month":
        this_month_start = datetime(now.year, now.month, 1)
        ly, lm = shift_month(now.year, now.month, -1)
        start_dt = datetime(ly, lm, 1)
        end_dt = this_month_start
    elif period == "last_3_months":
        sy, sm = shift_month(now.year, now.month, -2)
        start_dt = datetime(sy, sm, 1)
        end_dt = now
    elif period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="For custom period, start_date and end_date are required (YYYY-MM-DD)")
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # inclusive end_date
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        if end_dt <= start_dt:
            raise HTTPException(status_code=400, detail="end_date must be the same as or after start_date")
    else:
        raise HTTPException(status_code=400, detail="Invalid period")

    def add_overlap_seconds(
        seg_start: datetime,
        seg_end: datetime,
        clamp_start: datetime,
        clamp_end: datetime,
    ) -> float:
        s = max(seg_start, clamp_start)
        e = min(seg_end, clamp_end)
        if e <= s:
            return 0.0
        return (e - s).total_seconds()

    def compute_online_offline_seconds(
        check_in_time: datetime,
        effective_start: datetime,
        effective_end: datetime,
        logs: list[OnlineStatus],
    ) -> tuple[float, float, bool]:
        """
        Compute (online_seconds, offline_seconds, status_at_end) for one attendance,
        clamped to [effective_start, effective_end).
        Assumes user is online at check-in by default.
        """
        online_seconds = 0.0
        offline_seconds = 0.0

        prev_time = check_in_time
        prev_status = True

        for log in logs:
            t = log.timestamp
            if t < check_in_time:
                continue

            # Handle out-of-order or duplicate timestamps gracefully
            if t <= prev_time:
                prev_status = log.is_online
                continue

            if t > effective_end:
                break

            seg_seconds = add_overlap_seconds(prev_time, t, effective_start, effective_end)
            if seg_seconds:
                if prev_status:
                    online_seconds += seg_seconds
                else:
                    offline_seconds += seg_seconds

            prev_time = t
            prev_status = log.is_online

        # Final segment until effective_end
        if effective_end > prev_time:
            seg_seconds = add_overlap_seconds(prev_time, effective_end, effective_start, effective_end)
            if seg_seconds:
                if prev_status:
                    online_seconds += seg_seconds
                else:
                    offline_seconds += seg_seconds

        return online_seconds, offline_seconds, prev_status

    # Fetch attendance sessions within the range.
    # Note: We intentionally scope by check_in date to avoid counting stale/open
    # attendance records that started before the requested period.
    attendances = (
        db.query(Attendance)
        .filter(Attendance.user_id == target_user_id)
        .filter(Attendance.check_in >= start_dt)
        .filter(Attendance.check_in < end_dt)
        .order_by(Attendance.check_in.asc())
        .all()
    )

    attendance_ids = [a.attendance_id for a in attendances]

    logs_by_attendance: Dict[int, List[OnlineStatus]] = {}
    if attendance_ids:
        status_logs = (
            db.query(OnlineStatus)
            .filter(OnlineStatus.attendance_id.in_(attendance_ids))
            .filter(OnlineStatus.timestamp < end_dt)
            .order_by(OnlineStatus.attendance_id.asc(), OnlineStatus.timestamp.asc())
            .all()
        )
        for log in status_logs:
            logs_by_attendance.setdefault(log.attendance_id, []).append(log)

    total_online_seconds = 0.0
    total_offline_seconds = 0.0
    days: Dict[str, Dict[str, Union[str, float, int]]] = {}
    attendance_breakdown: List[Dict[str, Any]] = []

    for att in attendances:
        att_end = att.check_out if att.check_out else now
        effective_end = min(att_end, end_dt)
        effective_start = max(att.check_in, start_dt)

        if effective_end <= effective_start:
            continue

        logs = logs_by_attendance.get(att.attendance_id, [])
        online_s, offline_s, status_at_end = compute_online_offline_seconds(
            check_in_time=att.check_in,
            effective_start=effective_start,
            effective_end=effective_end,
            logs=logs,
        )

        total_online_seconds += online_s
        total_offline_seconds += offline_s

        day_key = att.check_in.date().isoformat()
        day_entry = days.get(day_key)
        if not day_entry:
            day_entry = {
                "date": day_key,
                "working_hours": 0.0,
                "working_seconds": 0,
                "offline_hours": 0.0,
                "offline_seconds": 0,
            }
            days[day_key] = day_entry

        day_entry["working_seconds"] = int(day_entry["working_seconds"]) + int(online_s)
        day_entry["offline_seconds"] = int(day_entry["offline_seconds"]) + int(offline_s)
        day_entry["working_hours"] = round(float(day_entry["working_seconds"]) / 3600, 2)
        day_entry["offline_hours"] = round(float(day_entry["offline_seconds"]) / 3600, 2)

        attendance_breakdown.append(
            {
                "attendance_id": att.attendance_id,
                "date": day_key,
                "check_in": att.check_in.isoformat(),
                "check_out": att.check_out.isoformat() if att.check_out else None,
                "working_hours": round(online_s / 3600, 2),
                "working_seconds": int(online_s),
                "offline_hours": round(offline_s / 3600, 2),
                "offline_seconds": int(offline_s),
                "is_currently_online": status_at_end if att.check_out is None else False,
            }
        )

    days_list = sorted(days.values(), key=lambda x: x["date"])

    return {
        "user_id": target_user_id,
        "period": period,
        "range_start": start_dt.isoformat(),
        "range_end": end_dt.isoformat(),
        "total_working_hours": round(total_online_seconds / 3600, 2),
        "total_working_seconds": int(total_online_seconds),
        "total_offline_hours": round(total_offline_seconds / 3600, 2),
        "total_offline_seconds": int(total_offline_seconds),
        "days": days_list,
        "attendances": attendance_breakdown,
    }

@router.get("/working-hours/{attendance_id}")
def calculate_working_hours(
    attendance_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Calculate actual working hours based on online/offline status.
    Only counts time when user was online.
    """
    try:
        from app.db.models.online_status import OnlineStatus
        
        # Verify attendance
        attendance = db.query(Attendance).filter(
            Attendance.attendance_id == attendance_id
        ).first()
        
        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found"
            )
        
        # Check permissions
        if attendance.user_id != current_user.user_id:
            if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        # Get status history
        status_logs = db.query(OnlineStatus).filter(
            OnlineStatus.attendance_id == attendance_id
        ).order_by(OnlineStatus.timestamp.asc()).all()
        
        # Calculate working hours with proper pause/resume logic
        total_online_seconds = 0
        total_offline_seconds = 0
        last_online_time = None
        current_status = True  # Assume online after check-in (default)
        
        # Start from check-in time (naive IST)
        check_in_time = attendance.check_in
        last_online_time = check_in_time
        last_status_change_time = check_in_time
        
        # If no status logs exist, user has been online since check-in
        if not status_logs:
            end_time = attendance.check_out if attendance.check_out else now_ist()
            total_online_seconds = (end_time - check_in_time).total_seconds()
            total_offline_seconds = 0
        else:
            # Process status logs chronologically
            for log in status_logs:
                log_timestamp = log.timestamp
                
                if log.is_online:
                    # Going online (resume)
                    if not current_status:
                        # Was offline, now online - add offline duration
                        if last_status_change_time:
                            offline_duration = (log_timestamp - last_status_change_time).total_seconds()
                            total_offline_seconds += offline_duration
                    
                    last_online_time = log_timestamp
                    last_status_change_time = log_timestamp
                    current_status = True
                else:
                    # Going offline (pause)
                    if current_status and last_online_time:
                        # Was online, now offline - add online duration
                        online_duration = (log_timestamp - last_online_time).total_seconds()
                        total_online_seconds += online_duration
                    
                    last_online_time = None
                    last_status_change_time = log_timestamp
                    current_status = False
            
            # Handle final period until now or checkout
            end_time = attendance.check_out if attendance.check_out else now_ist()
            
            if current_status and last_online_time:
                # Currently online - add remaining online time
                final_online_duration = (end_time - last_online_time).total_seconds()
                total_online_seconds += final_online_duration
            elif not current_status and last_status_change_time:
                # Currently offline - add remaining offline time
                final_offline_duration = (end_time - last_status_change_time).total_seconds()
                total_offline_seconds += final_offline_duration
        
        # Convert to hours
        working_hours = total_online_seconds / 3600
        offline_hours = total_offline_seconds / 3600
        
        return {
            "attendance_id": attendance_id,
            "working_hours": round(working_hours, 2),
            "total_seconds": int(total_online_seconds),
            "total_offline_seconds": int(total_offline_seconds),
            "offline_hours": round(offline_hours, 2),
            "is_currently_online": current_status,
            "check_in": attendance.check_in.isoformat(),
            "check_out": attendance.check_out.isoformat() if attendance.check_out else None
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404, 403)
        raise
    except Exception as e:
        # Log the error and return a generic 500 error
        logger.error(f"Error calculating working hours for attendance {attendance_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate working hours"
        )

@router.get("/report/monthly-grid")
def attendance_monthly_grid_report(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.crud.attendance_crud import build_monthly_attendance_grid
    return build_monthly_attendance_grid(db, month, year, department)

@router.get("/report/monthly-grid/download/pdf")
def download_monthly_grid_pdf(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    department: Optional[str] = Query(None, description="Filter by department"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (Present/Absent/Leave/WFH)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    from app.crud.attendance_grid_export import export_monthly_grid_pdf

    buffer = export_monthly_grid_pdf(
        db, 
        month, 
        year, 
        department=department,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status
    )

    filename = f"attendance_grid_{month:02d}_{year}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/report/monthly-detailed-grid/download/pdf")
def download_monthly_detailed_grid_pdf(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    department: Optional[str] = Query(None, description="Filter by department"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (Present/Absent/Leave/WFH)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    from app.crud.attendance_grid_export import export_monthly_detailed_pdf

    buffer = export_monthly_detailed_pdf(
        db,
        month,
        year,
        department=department,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status
    )

    filename = f"attendance_detailed_grid_{month:02d}_{year}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/report/monthly-grid/download/csv")
def download_monthly_grid_csv(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    department: Optional[str] = Query(None, description="Filter by department"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (Present/Absent/Leave/WFH)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.HR)),
):
    from app.crud.attendance_grid_export import export_monthly_grid_csv

    output = export_monthly_grid_csv(
        db, 
        month, 
        year, 
        department=department,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        status=status
    )

    filename = f"attendance_grid_{month:02d}_{year}.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
