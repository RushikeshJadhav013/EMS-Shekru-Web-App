from typing import Dict, Any, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class LocationService:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="attendance_system")
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds = 60  # cache results briefly to keep locations fresh

    def _cache_key(self, lat: float, lon: float) -> str:
        # Round coordinates to reduce cache fragmentation
        return f"{round(lat, 5)}:{round(lon, 5)}"

    def _extract_place_name(self, address_info: Optional[Dict[str, Any]]) -> str:
        if not address_info:
            return "Current location"

        raw = address_info.get("raw", {})
        structured_address = raw.get("address", {})

        preferred_keys = [
            "amenity",
            "building",
            "shop",
            "road",
            "neighbourhood",
            "suburb",
            "city",
            "town",
            "village",
            "state",
        ]
        for key in preferred_keys:
            value = structured_address.get(key)
            if value:
                return value

        display_name = raw.get("display_name") or address_info.get("address")
        if display_name:
            return display_name.split(",")[0].strip()

        return "Current location"

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

    def validate_location(self, location_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that the location payload contains usable coordinates.
        Returns: (is_valid: bool, message: str)
        """
        try:
            lat = location_data.get('latitude')
            lon = location_data.get('longitude')
            accuracy = location_data.get('accuracy')

            if lat is None or lon is None:
                return False, "Location data is incomplete"

            # Ensure values can be converted to floats
            try:
                float(lat)
                float(lon)
            except (TypeError, ValueError):
                return False, "Invalid latitude or longitude values"

            if accuracy is not None:
                try:
                    float(accuracy)
                except (TypeError, ValueError):
                    return False, "Invalid accuracy value"

            return True, "Location captured successfully"
            
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
            'address': address_info.get('address') if address_info else f"{lat}, {lon}",
            'place_name': self._extract_place_name(address_info),
            'accuracy': None,  # Can be set from GPS data if available
            'timestamp': datetime.utcnow().isoformat(),
            'is_valid': True
        }

        self._cache[cache_key] = (now, details)
        return details

# Singleton instance
location_service = LocationService()
