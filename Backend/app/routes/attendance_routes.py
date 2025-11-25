import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, or_
from datetime import datetime, timedelta, time, date
from zoneinfo import ZoneInfo
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from app.db.models.office_timing import OfficeTiming
from app.schemas.attendance_schema import AttendanceOut, LocationData
from fastapi.responses import StreamingResponse, JSONResponse
from app.dependencies import get_current_user
from app.enums import RoleEnum
from typing import Optional, List, Dict, Any, Union, Tuple
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


router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceJSONPayload(BaseModel):
    user_id: int
    gps_location: Optional[Dict[str, Any]] = None
    selfie: Optional[str] = None  # base64 data URL or raw base64
    location_data: Optional[Dict[str, Any]] = None
    work_summary: Optional[str] = None
    work_report: Optional[str] = None  # base64 data URL or raw base64

# ---------------------------------
# Helper functions for Attendance
# ---------------------------------
logger = logging.getLogger(__name__)

INDIA_TZ = ZoneInfo("Asia/Kolkata")
UTC_TZ = ZoneInfo("UTC")


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
    value = dt
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)
    return value.astimezone(INDIA_TZ)


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
        start_dt = datetime.combine(local_check_in.date(), timing.start_time, tzinfo=INDIA_TZ)
        if timing.check_in_grace_minutes:
            start_dt += timedelta(minutes=timing.check_in_grace_minutes)
        if local_check_in > start_dt:
            late = True
            check_in_status = "late"

    if local_check_out:
        check_out_status = "on_time"
        if timing:
            end_reference_date = local_check_out.date() if local_check_out else local_check_in.date()
            end_dt = datetime.combine(end_reference_date, timing.end_time, tzinfo=INDIA_TZ)
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
        "gps_location": location_label,
        "locationLabel": location_label,
        "checkInLocationLabel": location_sections.get("check_in"),
        "checkOutLocationLabel": location_sections.get("check_out"),
        "selfie": check_in_selfie_path,
        "checkInSelfie": check_in_selfie_path,
        "checkOutSelfie": check_out_selfie_path,
        "work_summary": getattr(attendance, "work_summary", None),
        "workSummary": getattr(attendance, "work_summary", None),
        "work_report": work_report_url,
        "workReport": work_report_url,
    }

def get_attendance_summary(db: Session) -> Dict[str, Any]:
    """Compute today's summary using configured office timings."""
    try:
        today = datetime.utcnow().date()
        
        total_employees = db.query(User).filter(User.is_active.is_(True)).count()
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
        
        records = (
            db.query(Attendance, User)
            .join(User, Attendance.user_id == User.user_id)
            .filter(
                Attendance.check_in >= today_start,
                Attendance.check_in <= today_end,
                User.is_active.is_(True),
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


@router.post("/reverse-geocode")
def reverse_geocode(payload: ReverseGeocodePayload):
    """Return human-readable location details for the given coordinates via server-side geocoding."""
    try:
        details = location_service.get_location_details(payload.lat, payload.lon)
        return details
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.error("Reverse geocode failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to fetch location details")

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
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
@router.post("/check-in", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def employee_check_in_route(
    request: Request,
    user_id: int = Form(...),
    gps_location: Optional[str] = Form(None),
    selfie: Optional[UploadFile] = File(None),
    location_data: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Parse location data
        try:
            loc_data = json.loads(location_data) if location_data else None
            processed_location = validate_and_process_location(loc_data or gps_location)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid location data format. Must be valid JSON."
            )

        # Validate user exists and is active
        user = db.query(User).filter(User.user_id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive"
            )

        # Save selfie if provided
        selfie_path = save_selfie(user_id, selfie, 'checkin') if selfie else None

        # Check for existing check-in today without check-out
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        existing_attendance = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == user_id,
                Attendance.check_in >= today_start,
                Attendance.check_out.is_(None)
            )
            .first()
        )

        if existing_attendance:
            return _prepare_attendance_payload(existing_attendance)

        # Create new check-in with location data
        attendance = Attendance(
            user_id=user_id,
            check_in=datetime.utcnow(),
            gps_location=_compose_location_entry(None, "Check-in", processed_location),
            selfie=_dump_selfie_data(None, check_in=selfie_path) if selfie_path else None,
            total_hours=0.0
        )
        
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        
        print(f"Successfully created check-in for user {user_id}, attendance ID: {attendance.attendance_id}")
        
        return _prepare_attendance_payload(attendance)
        
    except Exception as e:
        db.rollback()
        print(f"Error in check-in for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing check-in: {str(e)}"
        )

# Employee Check-In via JSON (base64 selfie)
@router.post("/check-in/json", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def employee_check_in_json(
    request: Request,
    payload: AttendanceJSONPayload, 
    db: Session = Depends(get_db)
):
    try:
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

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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

        # Create new check-in with location data
        attendance = Attendance(
            user_id=payload.user_id,
            check_in=datetime.utcnow(),
            gps_location=_compose_location_entry(None, "Check-in", processed_location),
            selfie=_dump_selfie_data(None, check_in=selfie_path) if selfie_path else None,
            total_hours=0.0
        )
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        return _prepare_attendance_payload(attendance)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error in JSON check-in: {str(e)}")


# Employee Check-Out
@router.post("/check-out", response_model=AttendanceOut)
async def employee_check_out_route(
    request: Request,
    user_id: int = Form(...),
    gps_location: Optional[str] = Form(None),
    selfie: Optional[UploadFile] = File(None),
    location_data: Optional[str] = Form(None),
    work_summary: str = Form(..., description="Required summary of today's work"),
    work_report: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    try:
        # Validate user exists and is active
        user = db.query(User).filter(User.user_id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive"
            )

        # Parse and validate location data
        location_source = location_data or gps_location
        processed_location: Dict[str, Any]
        try:
            normalized_location = _ensure_location_dict(location_source)
            processed_location = validate_and_process_location(normalized_location)
        except HTTPException:
            raise
        except Exception:
            processed_location = {
                "address": "Location not provided",
                "latitude": None,
                "longitude": None,
            }

        summary_text = (work_summary or "").strip()
        if not summary_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work summary is required for check-out"
            )

        # Save selfie if provided
        selfie_path = save_selfie(user_id, selfie, 'checkout') if selfie else None
        work_report_path = save_work_report_file(user_id, work_report) if work_report else None

        # Find today's check-in
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        attendance = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == user_id,
                Attendance.check_in >= today_start,
                Attendance.check_out.is_(None)  # Only update if not already checked out
            )
            .order_by(Attendance.check_in.desc())
            .first()
        )

        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active check-in found for today"
            )

        # Update check-out with location data
        attendance.check_out = datetime.utcnow()
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

        # Calculate total hours worked
        time_worked = attendance.check_out - attendance.check_in
        attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)  # Convert to hours with 2 decimal places
        
        db.commit()
        db.refresh(attendance)
        
        print(f"Successfully processed check-out for user {user_id}, attendance ID: {attendance.attendance_id}")
        
        return _prepare_attendance_payload(attendance)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in check-out for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing check-out: {str(e)}"
        )


# Employee Check-Out via JSON (base64 selfie)
@router.post("/check-out/json", response_model=AttendanceOut)
async def employee_check_out_json(
    request: Request,
    payload: AttendanceJSONPayload, 
    db: Session = Depends(get_db)
):
    try:
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

        summary_text = (payload.work_summary or "").strip()
        if not summary_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work summary is required for check-out"
            )

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

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
        attendance.check_out = datetime.utcnow()
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

        time_worked = attendance.check_out - attendance.check_in
        attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)
        db.commit()
        db.refresh(attendance)
        return _prepare_attendance_payload(attendance)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error in JSON check-out: {str(e)}")

# Employee Self-Attendance (Last 6 Months)
@router.get("/my-attendance/{user_id}", response_model=list[AttendanceOut])
def get_self_attendance(user_id: int, db: Session = Depends(get_db)):
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    records = (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= six_months_ago)
        .order_by(Attendance.check_in.desc())
        .all()
    )

    return [_prepare_attendance_payload(record) for record in records]

# Today's Attendance Summary
@router.get("/summary")
def attendance_summary(db: Session = Depends(get_db)):
    """Get attendance summary with statistics including late/early counts"""
    return get_attendance_summary(db)

# Today's Attendance Records (for Manager view)
@router.get("/today")
def get_today_attendance(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD) for which to fetch records"),
    db: Session = Depends(get_db),
):
    """Get attendance records for the specified date (defaults to today)."""
    target_date: Optional[date] = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )
    return get_today_attendance_records(db, target_date)
@router.get("/download/csv")
def download_attendance_csv(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Filter by department"),
    db: Session = Depends(get_db)
):
    """Download attendance data as a CSV file with optional filters."""
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
    department: Optional[str] = Query(None, description="Filter by department"),
    db: Session = Depends(get_db)
):
    """Download attendance data as a PDF file with optional filters."""
    from app.crud.attendance_crud import export_attendance_pdf
    
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
    
    buffer = export_attendance_pdf(
        db,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        employee_id=employee_id,
        department=department.strip() if department else None,
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
    Get today's attendance status for all employees
    - ADMIN: See all employees
    - HR: See only their department employees
    - MANAGER: See only their department employees
    - Others: Not allowed
    """
    user_role = current_user.role
    user_department = current_user.department
    
    if user_role == RoleEnum.ADMIN:
        # Admin can see all employees
        return get_today_attendance_status(db)
    elif user_role == RoleEnum.HR:
        # HR can see only their department
        if not user_department:
            raise HTTPException(status_code=400, detail="HR must have a department assigned")
        return get_today_attendance_status(db, department=user_department)
    elif user_role == RoleEnum.MANAGER:
        # Manager can see only their department
        if not user_department:
            raise HTTPException(status_code=400, detail="Manager must have a department assigned")
        return get_today_attendance_status(db, department=user_department)
    else:
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
    - ADMIN: See all employees (or filter by department)
    - HR: See only their department employees (department filter is automatic)
    - MANAGER: See only their department employees (department filter is automatic)
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
        # Admin can see all or filter by department
        if department:
            records_query = records_query.filter(User.department == department)
    elif user_role == RoleEnum.HR:
        # HR can only see their department's attendance
        if not user_department:
            raise HTTPException(status_code=400, detail="HR must have a department assigned")
        records_query = records_query.filter(User.department == user_department)
        # Allow additional department filter if provided (for admin override scenarios)
        if department and department != user_department:
            raise HTTPException(status_code=403, detail="HR can only view their own department's attendance")
    elif user_role == RoleEnum.MANAGER:
        # Manager can only see their department
        if not user_department:
            raise HTTPException(status_code=400, detail="Manager must have a department assigned")
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
                "userName": name,
                "department": dept,
                "employee_id": emp_id,
                "email": email,
                "userEmail": email,
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
    if current_user.role not in {RoleEnum.ADMIN, RoleEnum.HR, RoleEnum.MANAGER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view office timings")

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

    if datetime.combine(datetime.utcnow().date(), end_time_obj) <= datetime.combine(datetime.utcnow().date(), start_time_obj):
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
    return None