type LocationData = {
  latitude: number;
  longitude: number;
  accuracy?: number;
  address?: string;
  placeName?: string;
  timestamp?: number;
};

const getErrorMessage = (error: GeolocationPositionError): string => {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return 'Location permission denied. Please enable location access in your browser.';
    case error.POSITION_UNAVAILABLE:
      return 'Location information is unavailable. Please check your GPS settings.';
    case error.TIMEOUT:
      return 'The request to get user location timed out. Try again from an open area.';
    default:
      return 'Unable to retrieve your location.';
  }
};

const waitForAccuratePosition = (): Promise<GeolocationPosition> => {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser'));
      return;
    }

    const MIN_ACCURACY_METERS = 25;
    const MAX_WAIT_MS = 20000;

    let bestPosition: GeolocationPosition | null = null;
    let watchId: number | null = null;
    const cleanup = () => {
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
      }
      clearTimeout(timeoutId);
    };

    const resolveWithPosition = (position: GeolocationPosition) => {
      cleanup();
      resolve(position);
    };

    const timeoutId = window.setTimeout(() => {
      if (bestPosition) {
        resolveWithPosition(bestPosition);
      } else {
        cleanup();
        reject(new Error('Unable to determine precise location. Please retry from an open sky area.'));
      }
    }, MAX_WAIT_MS);

    watchId = navigator.geolocation.watchPosition(
      (position) => {
        const accuracy = position.coords.accuracy ?? Number.MAX_SAFE_INTEGER;
        if (!bestPosition || accuracy < (bestPosition.coords.accuracy ?? Number.MAX_SAFE_INTEGER)) {
          bestPosition = position;
        }
        if (accuracy <= MIN_ACCURACY_METERS) {
          resolveWithPosition(position);
        }
      },
      (error) => {
        if (bestPosition) {
          resolveWithPosition(bestPosition);
          return;
        }
        cleanup();
        reject(new Error(getErrorMessage(error)));
      },
      {
        enableHighAccuracy: true,
        timeout: MAX_WAIT_MS,
        maximumAge: 0,
      }
    );
  });
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
    const position = await waitForAccuratePosition();
    const { latitude, longitude, accuracy } = position.coords;
    
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
