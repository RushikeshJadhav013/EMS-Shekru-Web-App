import math
from typing import Dict, Any, Optional, Tuple
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging
import time

logger = logging.getLogger(__name__)

# PVG College coordinates focus area (center point) and radius
PVG_COLLEGE_COORDS = (18.46719, 73.86622)
ALLOWED_RADIUS_METERS = 350  # Allow ~350m radius to cover main blocks and parking

# Bounding polygon around campus (lat, lon pairs) for accuracy fallback
PVG_BOUNDARY = [
    (18.47022, 73.86231),
    (18.47102, 73.86582),
    (18.46966, 73.86874),
    (18.46688, 73.87119),
    (18.46401, 73.87157),
    (18.46218, 73.86849),
    (18.46261, 73.86423),
]

class LocationService:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="attendance_system")
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds = 300  # cache results for 5 minutes

    def _cache_key(self, lat: float, lon: float) -> str:
        # Round coordinates to reduce cache fragmentation
        return f"{round(lat, 5)}:{round(lon, 5)}"

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

    def _point_in_boundary(self, lat: float, lon: float) -> bool:
        """Simple ray casting to determine if a point lies within PVG boundary polygon."""
        x, y = lon, lat
        inside = False
        n = len(PVG_BOUNDARY)
        for i in range(n):
            lat_i, lon_i = PVG_BOUNDARY[i]
            lat_j, lon_j = PVG_BOUNDARY[(i + 1) % n]
            xi, yi = lon_i, lat_i
            xj, yj = lon_j, lat_j
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
        return inside

    def is_within_allowed_location(self, lat: float, lon: float) -> bool:
        """Check if the given coordinates are within the allowed radius"""
        distance = self.calculate_distance(
            lat, lon,
            PVG_COLLEGE_COORDS[0], PVG_COLLEGE_COORDS[1]
        )
        if distance <= ALLOWED_RADIUS_METERS:
            return True

        return self._point_in_boundary(lat, lon)

    def validate_location(self, location_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if the location is within the allowed area
        Returns: (is_valid: bool, message: str)
        """
        try:
            lat = location_data.get('latitude')
            lon = location_data.get('longitude')
            accuracy = location_data.get('accuracy')

            if not all([lat, lon]):
                return False, "Location data is incomplete"

            # Allow looser validation if reported accuracy is poor (>150m) by accepting boundary check
            if not self.is_within_allowed_location(lat, lon):
                if accuracy and accuracy > 150:
                    return True, "Location accepted with high GPS drift"
                return False, "You must be within the PVG College premises to check in"

            return True, "Location verified"
            
        except Exception as e:
            logger.error(f"Location validation error: {str(e)}")
            return False, f"Error validating location: {str(e)}"

    def get_location_details(self, lat: float, lon: float) -> Dict[str, Any]:
        """Get detailed location information"""
        cache_key = self._cache_key(lat, lon)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._cache_ttl_seconds:
            return cached[1]

        address_info = self.get_address_from_coords(lat, lon)
        
        details = {
            'latitude': lat,
            'longitude': lon,
            'address': address_info.get('address') if address_info else "Address not available",
            'place_name': address_info.get('raw', {}).get('display_name', '').split(',')[0] if address_info else "Location",
            'accuracy': None,  # Can be set from GPS data if available
            'timestamp': None,  # Will be set when saving
            'is_valid': self.is_within_allowed_location(lat, lon)
        }

        self._cache[cache_key] = (now, details)
        return details

# Singleton instance
location_service = LocationService()
