from pydantic import BaseModel, Field, field_validator, constr, computed_field
from typing import Optional, Dict, Any, Union, Literal
from datetime import datetime
import json

class LocationData(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")
    address: Optional[constr(max_length=500)] = Field(None, description="Human-readable address")
    place_name: Optional[constr(max_length=255)] = Field(None, description="Place name")
    accuracy: Optional[float] = Field(None, ge=0, le=10000, description="GPS accuracy in meters")
    timestamp: Optional[datetime] = Field(None, description="Location timestamp")

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within valid range"""
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within valid range"""
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return v

    @field_validator('accuracy')
    @classmethod
    def validate_accuracy(cls, v: Optional[float]) -> Optional[float]:
        """Validate GPS accuracy is reasonable"""
        if v is not None and v < 0:
            raise ValueError('GPS accuracy cannot be negative')
        if v is not None and v > 10000:
            raise ValueError('GPS accuracy seems unreasonably high (>10km)')
        return v

    def to_dict(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'place_name': self.place_name,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class AttendanceBase(BaseModel):
    gps_location: Optional[Union[Dict[str, Any], str]] = Field(None, description="GPS location data")
    selfie: Optional[str] = Field(None, description="Base64 encoded selfie image")
    location_data: Optional[Union[Dict[str, Any], str]] = Field(None, description="Detailed location data")
    work_location: Optional[Literal['office', 'work_from_home']] = Field('office', description="Work location type: 'office' or 'work_from_home'")

class AttendanceOut(AttendanceBase):
    attendance_id: int = Field(..., gt=0, description="Unique attendance ID")
    company_id: int = Field(..., gt=0, description="Company this attendance belongs to")
    user_id: int = Field(..., gt=0, description="User ID")
    check_in: datetime = Field(..., description="Check-in timestamp")
    check_out: Optional[datetime] = Field(None, description="Check-out timestamp")
    total_hours: float = Field(default=0.0, ge=0, le=24, description="Total work hours (0-24)")
    work_summary: Optional[str] = Field(None, description="Work summary")
    work_report: Optional[str] = Field(None, description="Work report file path or URL")
    work_location: Optional[Literal['office', 'work_from_home']] = Field('office', description="Work location type")
    task_deadline_reason: Optional[str] = Field(None, description="Reason for incomplete tasks on deadline")

    @computed_field
    @property
    def total_hours_formatted(self) -> str:
        """Format total_hours as HH:MM (e.g., 2.58 → '2:35')"""
        hours = int(self.total_hours)
        minutes = int(round((self.total_hours - hours) * 60))
        return f"{hours}:{minutes:02d}"

    @field_validator('check_out')
    @classmethod
    def validate_check_out(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate check-out is after check-in"""
        if v is not None and 'check_in' in info.data:
            check_in = info.data['check_in']
            if v <= check_in:
                raise ValueError('Check-out time must be after check-in time')
            # Validate reasonable work duration (max 24 hours)
            duration = (v - check_in).total_seconds() / 3600
            if duration > 24:
                raise ValueError('Work duration cannot exceed 24 hours')
        return v

    @field_validator('total_hours')
    @classmethod
    def validate_total_hours(cls, v: float) -> float:
        """Validate total hours is reasonable"""
        if v < 0:
            raise ValueError('Total hours cannot be negative')
        if v > 24:
            raise ValueError('Total hours cannot exceed 24 hours in a day')
        return round(v, 2)

    @field_validator('work_summary')
    @classmethod
    def validate_work_summary(cls, v: Optional[str]) -> Optional[str]:
        """Validate work summary - allow existing short summaries for backward compatibility"""
        if v is not None and v.strip():
            # For backward compatibility, allow existing short summaries
            # Only enforce minimum length for new entries (this is handled at input validation)
            if len(v.strip()) > 1000:
                raise ValueError('Work summary cannot exceed 1000 characters')
            return v.strip()
        return None

    @field_validator('task_deadline_reason')
    @classmethod
    def validate_task_deadline_reason(cls, v: Optional[str]) -> Optional[str]:
        """Validate task deadline reason - allow existing short reasons for backward compatibility"""
        if v is not None and v.strip():
            # For backward compatibility, allow existing short reasons
            # Only enforce minimum length for new entries (this is handled at input validation)
            if len(v.strip()) > 500:
                raise ValueError('Task deadline reason cannot exceed 500 characters')
            return v.strip()
        return None

    model_config = {"from_attributes": True}