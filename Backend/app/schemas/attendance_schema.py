from pydantic import BaseModel, Field, field_validator, constr
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

class AttendanceOut(AttendanceBase):
    attendance_id: int = Field(..., gt=0, description="Unique attendance ID")
    user_id: int = Field(..., gt=0, description="User ID")
    check_in: datetime = Field(..., description="Check-in timestamp")
    check_out: Optional[datetime] = Field(None, description="Check-out timestamp")
    total_hours: float = Field(default=0.0, ge=0, le=24, description="Total work hours (0-24)")
    work_summary: Optional[constr(min_length=10, max_length=1000)] = Field(None, description="Work summary (10-1000 characters)")
    work_report: Optional[str] = Field(None, description="Work report file path or URL")
    work_location: Optional[Literal['office', 'work_from_home']] = Field('office', description="Work location type")

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

    model_config = {"from_attributes": True}
