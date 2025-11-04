// PVG College coordinates (replace with actual coordinates)
const PVG_COLLEGE_COORDS = {
  latitude: 18.4649,
  longitude: 73.8678,
  address: "PVG College, Parvati, Pune, Maharashtra 411009",
  radius: 100 // meters
};

type Position = {
  coords: {
    latitude: number;
    longitude: number;
    accuracy: number;
  };
};

type LocationData = {
  latitude: number;
  longitude: number;
  accuracy?: number;
  address?: string;
  placeName?: string;
  timestamp?: number;
};

/**
 * Get current position using Geolocation API
 */
export const getCurrentPosition = (): Promise<Position> => {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser'));
      return;
    }

    const options = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    };

    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position as unknown as Position),
      (error) => {
        let errorMessage = 'Unable to retrieve your location';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = 'Please enable location services to check in/out';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = 'Location information is unavailable';
            break;
          case error.TIMEOUT:
            errorMessage = 'The request to get user location timed out';
            break;
        }
        reject(new Error(errorMessage));
      },
      options
    );
  });
};

/**
 * Calculate distance between two points in meters using Haversine formula
 */
const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const R = 6371e3; // Earth's radius in meters
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δφ = ((lat2 - lat1) * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c; // Distance in meters
};

/**
 * Check if current location is within allowed radius
 */
export const isWithinAllowedLocation = (
  currentLat: number,
  currentLon: number,
  allowedLat: number = PVG_COLLEGE_COORDS.latitude,
  allowedLon: number = PVG_COLLEGE_COORDS.longitude,
  allowedRadiusMeters: number = PVG_COLLEGE_COORDS.radius
): boolean => {
  const distance = calculateDistance(
    currentLat,
    currentLon,
    allowedLat,
    allowedLon
  );
  return distance <= allowedRadiusMeters;
};

/**
 * Get address from coordinates using reverse geocoding
 */
export const getAddressFromCoords = async (
  lat: number,
  lon: number
): Promise<{ address: string; placeName: string }> => {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`
    );
    
    if (!response.ok) {
      throw new Error('Failed to fetch address');
    }
    
    const data = await response.json();
    
    return {
      address: data.display_name || 'Address not available',
      placeName: data.address?.building || data.address?.road || 'Location'
    };
  } catch (error) {
    console.error('Error getting address:', error);
    return {
      address: 'Address not available',
      placeName: 'Location'
    };
  }
};

/**
 * Get current location with validation
 */
export const getCurrentLocation = async (): Promise<LocationData> => {
  try {
    const position = await getCurrentPosition();
    const { latitude, longitude, accuracy } = position.coords;
    
    // Check if within allowed location
    const isAllowed = isWithinAllowedLocation(latitude, longitude);
    if (!isAllowed) {
      throw new Error('You must be within the PVG College premises to check in/out');
    }
    
    // Get address details
    const { address, placeName } = await getAddressFromCoords(latitude, longitude);
    
    return {
      latitude,
      longitude,
      accuracy,
      address,
      placeName,
      timestamp: Date.now()
    };
  } catch (error) {
    console.error('Error getting location:', error);
    throw error;
  }
};
