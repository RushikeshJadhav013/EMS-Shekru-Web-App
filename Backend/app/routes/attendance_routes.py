from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, or_
from datetime import datetime, timedelta
from app.db.database import get_db
from app.db.models.attendance import Attendance
from app.db.models.user import User
from app.schemas.attendance_schema import AttendanceOut, LocationData
from fastapi.responses import StreamingResponse, JSONResponse
from app.dependencies import get_current_user
from app.enums import RoleEnum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, ValidationError
import base64
import os
import shutil
from io import BytesIO
import logging
import json
from ..utils.geolocation import location_service


router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceJSONPayload(BaseModel):
    user_id: int
    gps_location: Optional[Dict[str, Any]] = None
    selfie: Optional[str] = None  # base64 data URL or raw base64
    location_data: Optional[Dict[str, Any]] = None

# ---------------------------------
# Helper functions for Attendance
# ---------------------------------
logger = logging.getLogger(__name__)

def get_attendance_summary(db: Session) -> Dict[str, Any]:
    """
    Compute today's attendance summary: total employees, present, absent, late arrivals,
    early departures, and average work hours for today.
    """
    try:
        today = datetime.utcnow().date()
        
        # Total active employees
        total_employees = db.query(User).filter(User.is_active == True).count()
        if total_employees == 0:
            return {
                "total_employees": 0,
                "present_today": 0,
                "absent_today": 0,
                "late_arrivals": 0,
                "early_departures": 0,
                "average_work_hours": 0.0,
                "date": today.isoformat()
            }

        # Get all attendance records for today with user details
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        records = db.query(
            User.user_id,
            User.name,
            Attendance.check_in,
            Attendance.check_out
        ).join(
            Attendance, User.user_id == Attendance.user_id
        ).filter(
            Attendance.check_in.between(today_start, today_end),
            User.is_active == True
        ).all()

        # Process records
        present_user_ids = set()
        late_arrivals = 0
        early_departures = 0
        work_durations = []
        
        # Define working hours (10:00 - 18:00)
        work_start = datetime.strptime("10:00:00", "%H:%M:%S").time()
        work_end = datetime.strptime("18:00:00", "%H:%M:%S").time()
        
        for user_id, name, check_in, check_out in records:
            present_user_ids.add(user_id)
            
            # Check for late arrival
            if check_in and check_in.time() > work_start:
                late_arrivals += 1
                
            # Check for early departure
            if check_out and check_out.time() < work_end:
                early_departures += 1
                
            # Calculate work duration if both check-in and check-out exist
            if check_in and check_out:
                duration = (check_out - check_in).total_seconds() / 3600.0
                work_durations.append(duration)
            elif check_in:  # If only checked in, calculate duration until now
                duration = (datetime.utcnow() - check_in).total_seconds() / 3600.0
                work_durations.append(duration)
        
        present_employees = len(present_user_ids)
        absent_employees = max(0, total_employees - present_employees)
        avg_work_hours = round(sum(work_durations) / len(work_durations), 2) if work_durations else 0.0

        return {
            "total_employees": total_employees,
            "present_today": present_employees,
            "absent_today": absent_employees,
            "late_arrivals": late_arrivals,
            "early_departures": early_departures,
            "average_work_hours": avg_work_hours,
            "date": today.isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error in get_attendance_summary: {str(e)}", exc_info=True)
        # Return default values in case of error
        return {
            "total_employees": 0,
            "present_today": 0,
            "absent_today": 0,
            "late_arrivals": 0,
            "early_departures": 0,
            "average_work_hours": 0.0,
            "date": datetime.utcnow().date().isoformat(),
            "error": str(e)
        }

def get_today_attendance_records(db: Session) -> List[Dict[str, Any]]:
    """
    Return today's attendance records with user details, selfie, and location.
    Only shows users who have checked in today.
    """
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get only users who have checked in today
        attendance_records = (
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
        
        for (
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
            total_hours
        ) in attendance_records:
            status_text = "Checked In"
            if check_out:
                status_text = "Checked Out"
                
            # Format check-in and check-out times as ISO strings
            check_in_iso = check_in.isoformat() if check_in else None
            check_out_iso = check_out.isoformat() if check_out else None
            
            # Get location from GPS data if available
            location = "Location not available"
            if gps_location:
                try:
                    # If GPS is stored as a string, try to parse it
                    if isinstance(gps_location, str):
                        location = gps_location
                    # If it's a dictionary, extract relevant parts
                    elif isinstance(gps_location, dict):
                        location = gps_location.get("address", "Location available")
                except Exception as e:
                    logger.warning(f"Error parsing GPS data: {str(e)}")
                    location = "Location available"
            
            # Get selfie URL if available
            selfie_url = None
            if selfie:
                if selfie.startswith('http'):
                    selfie_url = selfie
                else:
                    # Assuming selfie is stored as a path relative to your static files
                    selfie_url = f"/static/selfies/{selfie}" if selfie else None
            
            # Calculate total hours if not provided
            calculated_hours = 0.0
            if check_in and check_out:
                duration = check_out - check_in
                calculated_hours = round(duration.total_seconds() / 3600, 2)
            
            results.append({
                "attendance_id": attendance_id,
                "user_id": user_id,
                "employee_id": employee_id,
                "name": name or "Unknown",
                "email": email or "",
                "department": department or "N/A",
                "check_in": check_in_iso,
                "check_out": check_out_iso,
                "status": status_text,
                "location": location,
                "gps_data": gps_location if gps_location else None,
                "selfie": selfie_url,
                "total_hours": float(total_hours) if total_hours is not None else calculated_hours
            })
            
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
            
        # Check if location is within allowed area
        is_valid, message = location_service.validate_location(location_data)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
            
        # Get detailed location info
        location_details = location_service.get_location_details(
            location_data['latitude'],
            location_data['longitude']
        )
        
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
            return {
                "attendance_id": existing_attendance.attendance_id,
                "user_id": existing_attendance.user_id,
                "check_in": existing_attendance.check_in,
                "check_out": existing_attendance.check_out,
                "gps_location": existing_attendance.gps_location,
                "selfie": existing_attendance.selfie,
                "total_hours": existing_attendance.total_hours
            }

        # Create new check-in with location data
        attendance = Attendance(
            user_id=user_id,
            check_in=datetime.utcnow(),
            gps_location={
                'latitude': processed_location['latitude'],
                'longitude': processed_location['longitude']
            },
            location_data=processed_location,
            selfie=selfie_path,
            total_hours=0.0
        )
        
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        
        print(f"Successfully created check-in for user {user_id}, attendance ID: {attendance.attendance_id}")
        
        return {
            "attendance_id": attendance.attendance_id,
            "user_id": attendance.user_id,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "gps_location": attendance.gps_location,
            "selfie": attendance.selfie,
            "total_hours": attendance.total_hours
        }
        
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
            return {
                "attendance_id": existing_attendance.attendance_id,
                "user_id": existing_attendance.user_id,
                "check_in": existing_attendance.check_in,
                "check_out": existing_attendance.check_out,
                "gps_location": existing_attendance.gps_location,
                "selfie": existing_attendance.selfie,
                "total_hours": existing_attendance.total_hours
            }

        # Create new check-in with location data
        attendance = Attendance(
            user_id=payload.user_id,
            check_in=datetime.utcnow(),
            gps_location={
                'latitude': payload.gps_location['latitude'],
                'longitude': payload.gps_location['longitude']
            },
            location_data=payload.gps_location,
            selfie=selfie_path,
            total_hours=0.0
        )
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        return {
            "attendance_id": attendance.attendance_id,
            "user_id": attendance.user_id,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "gps_location": attendance.gps_location,
            "selfie": attendance.selfie,
            "total_hours": attendance.total_hours
        }
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
        try:
            loc_data = json.loads(location_data) if location_data else None
            processed_location = validate_and_process_location(loc_data or gps_location)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid location data format. Must be valid JSON."
            )

        # Save selfie if provided
        selfie_path = save_selfie(user_id, selfie, 'checkout') if selfie else None

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
        attendance.selfie = selfie_path or attendance.selfie
        attendance.gps_location = {
            'latitude': processed_location['latitude'],
            'longitude': processed_location['longitude']
        }
        
        # Update or set location data
        if not attendance.location_data:
            attendance.location_data = {}
            
        if 'check_out' not in attendance.location_data:
            attendance.location_data['check_out'] = {}
            
        attendance.location_data.update({
            'check_out': {
                **processed_location,
                'timestamp': attendance.check_out.isoformat()
            }
        })

        # Calculate total hours worked
        time_worked = attendance.check_out - attendance.check_in
        attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)  # Convert to hours with 2 decimal places
        
        db.commit()
        db.refresh(attendance)
        
        print(f"Successfully processed check-out for user {user_id}, attendance ID: {attendance.attendance_id}")
        
        return {
            "attendance_id": attendance.attendance_id,
            "user_id": attendance.user_id,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "gps_location": attendance.gps_location,
            "selfie": attendance.selfie,
            "total_hours": attendance.total_hours
        }
        
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
            data = payload.selfie
            if data.startswith('data:image'):
                header, b64data = data.split(',', 1)
            else:
                b64data = data
            raw = base64.b64decode(b64data)
            UPLOAD_DIR = "static/selfies"
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            file_name = f"{payload.user_id}_checkout_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            file_path = os.path.join(UPLOAD_DIR, file_name)
            with open(file_path, 'wb') as f:
                f.write(raw)
            selfie_path = file_path

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
        attendance.selfie = selfie_path or attendance.selfie
        attendance.gps_location = {
            'latitude': payload.gps_location['latitude'],
            'longitude': payload.gps_location['longitude']
        }
        
        # Update or set location data
        if not attendance.location_data:
            attendance.location_data = {}
            
        if 'check_out' not in attendance.location_data:
            attendance.location_data['check_out'] = {}
            
        attendance.location_data.update({
            'check_out': {
                **payload.gps_location,
                'timestamp': attendance.check_out.isoformat()
            }
        })

        time_worked = attendance.check_out - attendance.check_in
        attendance.total_hours = round(time_worked.total_seconds() / 3600, 2)
        db.commit()
        db.refresh(attendance)
        return {
            "attendance_id": attendance.attendance_id,
            "user_id": attendance.user_id,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "gps_location": attendance.gps_location,
            "selfie": attendance.selfie,
            "total_hours": attendance.total_hours
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error in JSON check-out: {str(e)}")

# Employee Self-Attendance (Last 6 Months)
@router.get("/my-attendance/{user_id}", response_model=list[AttendanceOut])
def get_self_attendance(user_id: int, db: Session = Depends(get_db)):
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    return (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id, Attendance.check_in >= six_months_ago)
        .order_by(Attendance.check_in.desc())
        .all()
    )

# Today's Attendance Summary
@router.get("/summary")
def attendance_summary(db: Session = Depends(get_db)):
    """Get attendance summary with statistics including late/early counts"""
    return get_attendance_summary(db)

# Today's Attendance Records (for Manager view)
@router.get("/today")
def get_today_attendance(db: Session = Depends(get_db)):
    """Get today's attendance records with employee details"""
    return get_today_attendance_records(db)
@router.get("/download/csv")
def download_attendance_csv(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
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
    
    output = export_attendance_csv(db, user_id=user_id, start_date=start_dt, end_date=end_dt, employee_id=employee_id)
    
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
    
    buffer = export_attendance_pdf(db, user_id=user_id, start_date=start_dt, end_date=end_dt, employee_id=employee_id)
    
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's attendance status for all employees
    - ADMIN: See all employees
    - HR: See all employees
    - MANAGER: See only their department employees
    - Others: Not allowed
    """
    user_role = current_user.get("role")
    user_department = current_user.get("department")
    
    if user_role == RoleEnum.ADMIN.value or user_role == RoleEnum.HR.value:
        # Admin and HR can see all employees
        return get_today_attendance_status(db)
    elif user_role == RoleEnum.MANAGER.value:
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all attendance history
    - ADMIN: See all employees
    - HR: See all employees  
    - MANAGER: See only their department employees (department filter is automatic)
    - Others: Not allowed
    """
    user_role = current_user.get("role")
    user_department = current_user.get("department")
    
    if user_role == RoleEnum.ADMIN.value or user_role == RoleEnum.HR.value:
        # Admin and HR can see all or filter by department
        records = get_all_attendance(db, department=department)
    elif user_role == RoleEnum.MANAGER.value:
        # Manager can only see their department
        if not user_department:
            raise HTTPException(status_code=400, detail="Manager must have a department assigned")
        records = get_all_attendance(db, department=user_department)
    else:
        raise HTTPException(status_code=403, detail="Not authorized to view attendance")
    
    # Format the response - include email and other user details
    result = []
    for att, name, dept, emp_id in records:
        # Get user details including email
        user = db.query(User).filter(User.user_id == att.user_id).first()
        result.append({
            "attendance_id": att.attendance_id,
            "user_id": att.user_id,
            "employee_id": emp_id,
            "name": name,
            "userName": name,  # Add for frontend compatibility
            "email": user.email if user else None,
            "userEmail": user.email if user else None,  # Add for frontend compatibility
            "department": dept,
            "check_in": att.check_in.isoformat() if att.check_in else None,  # Return ISO format
            "check_out": att.check_out.isoformat() if att.check_out else None,  # Return ISO format
            "total_hours": att.total_hours,
            "gps_location": att.gps_location,
            "selfie": att.selfie
        })
    
    return result