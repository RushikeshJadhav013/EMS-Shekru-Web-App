from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
import json

class LocationData(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    place_name: Optional[str] = None
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None

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
    gps_location: Optional[Dict[str, Any]] = None
    selfie: Optional[str] = None
    location_data: Optional[Dict[str, Any]] = None

class AttendanceOut(AttendanceBase):
    attendance_id: int
    user_id: int
    check_in: datetime
    check_out: Optional[datetime] = None
    total_hours: float

    class Config:
        from_attributes = True
