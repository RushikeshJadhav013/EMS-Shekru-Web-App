import math
from typing import Dict, Any, Optional, Tuple
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging

logger = logging.getLogger(__name__)

# PVG College coordinates (example - replace with actual coordinates)
PVG_COLLEGE_COORDS = (18.4649, 73.8678)  # Example coordinates for PVG College, Pune
ALLOWED_RADIUS_METERS = 100  # 100 meters radius from the allowed location

class LocationService:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="attendance_system")

    def get_address_from_coords(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Get address details from coordinates using geocoding"""
        try:
            location = self.geolocator.reverse(f"{lat}, {lon}", exactly_one=True)
            if location:
                return {
                    'address': location.address,
                    'raw': location.raw
                }
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding error: {str(e)}")
        return None

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        return geodesic((lat1, lon1), (lat2, lon2)).meters

    def is_within_allowed_location(self, lat: float, lon: float) -> bool:
        """Check if the given coordinates are within the allowed radius"""
        distance = self.calculate_distance(
            lat, lon,
            PVG_COLLEGE_COORDS[0], PVG_COLLEGE_COORDS[1]
        )
        return distance <= ALLOWED_RADIUS_METERS

    def validate_location(self, location_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if the location is within the allowed area
        Returns: (is_valid: bool, message: str)
        """
        try:
            lat = location_data.get('latitude')
            lon = location_data.get('longitude')
            
            if not all([lat, lon]):
                return False, "Location data is incomplete"
                
            if not self.is_within_allowed_location(lat, lon):
                return False, "You must be within the PVG College premises to check in"
                
            return True, "Location verified"
            
        except Exception as e:
            logger.error(f"Location validation error: {str(e)}")
            return False, f"Error validating location: {str(e)}"

    def get_location_details(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get detailed location information"""
        address_info = self.get_address_from_coords(lat, lon)
        
        return {
            'latitude': lat,
            'longitude': lon,
            'address': address_info.get('address') if address_info else "Address not available",
            'place_name': address_info.get('raw', {}).get('display_name', '').split(',')[0] if address_info else "Location",
            'accuracy': None,  # Can be set from GPS data if available
            'timestamp': None,  # Will be set when saving
            'is_valid': self.is_within_allowed_location(lat, lon)
        }

# Singleton instance
location_service = LocationService()
