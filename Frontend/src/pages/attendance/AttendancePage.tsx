import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import AttendanceCamera from '@/components/attendance/AttendanceCamera';
import { Clock, MapPin, Calendar, LogIn, LogOut, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { AttendanceRecord } from '@/types';
import { format } from 'date-fns';
import { getCurrentLocation as fetchPreciseLocation, getCurrentLocationFast, getCurrentLocationWithContinuousImprovement } from '@/utils/geolocation';

type GeoLocation = {
  latitude: number;
  longitude: number;
  accuracy?: number | null;
  address?: string;
  updatedAt?: number;
};

const AttendancePage: React.FC = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [showCamera, setShowCamera] = useState(false);
  const [isCheckingIn, setIsCheckingIn] = useState(true);
  const [showCheckoutDialog, setShowCheckoutDialog] = useState(false);
  const [todaysWork, setTodaysWork] = useState('');
  const [workPdf, setWorkPdf] = useState<File | null>(null);
  const [currentAttendance, setCurrentAttendance] = useState<AttendanceRecord | null>(null);
  const [attendanceHistory, setAttendanceHistory] = useState<AttendanceRecord[]>([]);
  const [location, setLocation] = useState<GeoLocation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshingLocation, setIsRefreshingLocation] = useState(false);
  const [isGettingFastLocation, setIsGettingFastLocation] = useState(true);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [locationWatcher, setLocationWatcher] = useState<{ stop: () => void } | null>(null);
  const [isImprovingAccuracy, setIsImprovingAccuracy] = useState(false);

  // Helper to fetch today's attendance for current user
  const fetchTodayAttendance = async () => {
    if (!user?.id) return;
    try {
      const res = await fetch(`http://127.0.0.1:8000/attendance/my-attendance/${user.id}`);
      if (!res.ok) throw new Error('Failed to fetch attendance');
      const data = await res.json();
      
      // Parse backend response and find today's record
      const today = format(new Date(), 'yyyy-MM-dd');
      const todayRecord = data.find((rec: any) => {
        const recordDate = format(new Date(rec.check_in), 'yyyy-MM-dd');
        return recordDate === today;
      });
      
      if (todayRecord) {
        // Convert backend format to frontend format
        // Use ISO datetime strings for proper timezone handling
        const checkInDate = new Date(todayRecord.check_in);
        const checkOutDate = todayRecord.check_out ? new Date(todayRecord.check_out) : null;
        
        const attendance: AttendanceRecord = {
          id: todayRecord.attendance_id.toString(),
          userId: todayRecord.user_id.toString(),
          date: format(checkInDate, 'yyyy-MM-dd'),
          checkInTime: todayRecord.check_in, // Use ISO datetime string
          checkOutTime: todayRecord.check_out || undefined, // Use ISO datetime string
          checkInLocation: { latitude: 0, longitude: 0, address: todayRecord.gps_location || 'N/A' },
          checkInSelfie: todayRecord.selfie || '',
          status: 'present',
          workHours: todayRecord.total_hours
        };
        setCurrentAttendance(attendance);
        
        // Store all history
        const history = data.map((rec: any) => ({
          id: rec.attendance_id.toString(),
          userId: rec.user_id.toString(),
          date: format(new Date(rec.check_in), 'yyyy-MM-dd'),
          checkInTime: rec.check_in, // Use ISO datetime string
          checkOutTime: rec.check_out || undefined, // Use ISO datetime string
          checkInLocation: { latitude: 0, longitude: 0, address: rec.gps_location || 'N/A' },
          checkInSelfie: rec.selfie || '',
          status: 'present',
          workHours: rec.total_hours
        }));
        setAttendanceHistory(history);
      } else {
        setCurrentAttendance(null);
      }
    } catch (err) {
      console.error('Failed to fetch attendance:', err);
      setCurrentAttendance(null);
    }
  };

  const refreshLocation = useCallback(async (): Promise<GeoLocation> => {
    try {
      const preciseLocation = await fetchPreciseLocation();
      const refreshed: GeoLocation = {
        latitude: preciseLocation.latitude,
        longitude: preciseLocation.longitude,
        accuracy: preciseLocation.accuracy ?? null,
        address:
          preciseLocation.address ||
          `${preciseLocation.latitude.toFixed(6)}, ${preciseLocation.longitude.toFixed(6)}`,
        updatedAt: Date.now(),
      };
      setLocation(refreshed);
      return refreshed;
    } catch (error: any) {
      const errorMessage =
        error?.message || t.attendance.locationRequired || 'Unable to fetch your location';
      toast({
        title: 'Location Error',
        description: errorMessage,
        variant: 'destructive',
      });
      throw new Error(errorMessage);
    }
  }, [toast, t.attendance.locationRequired]);

  const stopContinuousLocationImprovement = useCallback(() => {
    if (locationWatcher) {
      locationWatcher.stop();
      setLocationWatcher(null);
      setIsImprovingAccuracy(false);
    }
  }, [locationWatcher]);

  const startContinuousLocationImprovement = useCallback(() => {
    // Stop any existing watcher
    if (locationWatcher) {
      locationWatcher.stop();
    }

    setIsImprovingAccuracy(true);
    
    try {
      const watcher = getCurrentLocationWithContinuousImprovement(
        (improvedLocation) => {
          const refreshed: GeoLocation = {
            latitude: improvedLocation.latitude,
            longitude: improvedLocation.longitude,
            accuracy: improvedLocation.accuracy ?? null,
            address: improvedLocation.address || `${improvedLocation.latitude.toFixed(6)}, ${improvedLocation.longitude.toFixed(6)}`,
            updatedAt: Date.now(),
          };
          setLocation(refreshed);
          
          // Stop improving if we get very accurate location (< 10 meters)
          if (improvedLocation.accuracy && improvedLocation.accuracy < 10) {
            setIsImprovingAccuracy(false);
          }
        },
        10 // Target 10 meters accuracy
      );
      
      setLocationWatcher(watcher);
      
      // Auto-stop after 30 seconds
      setTimeout(() => {
        watcher.stop();
        setIsImprovingAccuracy(false);
      }, 30000);
    } catch (error) {
      console.error('Failed to start continuous location improvement:', error);
      setIsImprovingAccuracy(false);
    }
  }, [locationWatcher]);

  const refreshLocationFast = useCallback(async (): Promise<GeoLocation> => {
    try {
      setIsGettingFastLocation(true);
      setLocationError(null);
      const fastLocation = await getCurrentLocationFast();
      const refreshed: GeoLocation = {
        latitude: fastLocation.latitude,
        longitude: fastLocation.longitude,
        accuracy: fastLocation.accuracy ?? null,
        address: fastLocation.address || `${fastLocation.latitude.toFixed(6)}, ${fastLocation.longitude.toFixed(6)}`,
        updatedAt: Date.now(),
      };
      setLocation(refreshed);
      setIsGettingFastLocation(false);
      return refreshed;
    } catch (error: any) {
      const errorMessage =
        error?.message || t.attendance.locationRequired || 'Unable to fetch your location';
      setLocationError(errorMessage);
      setIsGettingFastLocation(false);
      toast({
        title: 'Location Error',
        description: errorMessage,
        variant: 'destructive',
      });
      throw new Error(errorMessage);
    }
  }, [toast, t.attendance.locationRequired]);

  useEffect(() => {
    fetchTodayAttendance();
    
    // Get location immediately when page loads
    const initLocation = async () => {
      try {
        await refreshLocationFast();
        // After initial fast location, start continuous improvement
        startContinuousLocationImprovement();
      } catch (error) {
        console.error('Initial location fetch failed:', error);
        setLocationError(error instanceof Error ? error.message : 'Failed to get location');
      }
    };
    
    initLocation();
    
    // Auto-refresh at midnight to reset for new day
    const checkMidnight = setInterval(() => {
      const now = new Date();
      if (now.getHours() === 0 && now.getMinutes() === 0) {
        setCurrentAttendance(null);
        fetchTodayAttendance();
      }
    }, 60000); // Check every minute
    
    return () => {
      clearInterval(checkMidnight);
      stopContinuousLocationImprovement();
    };
  }, [user?.id, refreshLocationFast]);

  const handleCheckIn = async () => {
    try {
      await refreshLocation();
    } catch (error: any) {
      toast({
          title: 'Location Required',
        description: error?.message || 'Please enable location services and try again.',
          variant: 'destructive',
        });
        return;
    }

    setIsLoading(true);
    
    try {
      // First, take a selfie if camera is available
      setShowCamera(true);
      setIsCheckingIn(true);
    } catch (error) {
      console.error('Error initializing camera:', error);
      toast({
        title: 'Error',
        description: 'Failed to initialize camera. Please try again.',
        variant: 'destructive',
      });
      setIsLoading(false);
    }
  };

  const handleCheckOut = async () => {
    try {
      await refreshLocation();
    } catch (error: any) {
      toast({
        title: 'Location Required',
        description: error?.message || t.attendance.locationRequired,
        variant: 'destructive',
      });
      return;
    }
    setShowCheckoutDialog(true);
  };

  const confirmCheckOut = () => {
    if (!todaysWork.trim()) {
      toast({
        title: 'Work Summary Required',
        description: 'Please provide today\'s work summary before checking out.',
        variant: 'destructive',
      });
      return;
    }
    setIsCheckingIn(false);
    setShowCamera(true);
    setShowCheckoutDialog(false);
  };

  const handleCameraCapture = async (imageData: string) => {
    setIsLoading(true);
    try {
      const activeLocation = await refreshLocation().catch(() => location);
      if (!activeLocation || !user?.id) throw new Error('Location or user missing');
      
      const formData = new FormData();
      formData.append('user_id', String(user.id));

      const locationPayload = {
        latitude: activeLocation.latitude,
        longitude: activeLocation.longitude,
        accuracy: activeLocation.accuracy ?? null,
        address: activeLocation.address ?? '',
        timestamp: new Date().toISOString(),
      };
      const locationJson = JSON.stringify(locationPayload);
      formData.append('gps_location', locationJson);
      formData.append('location_data', locationJson);

      if (!isCheckingIn) {
        if (!todaysWork.trim()) {
          throw new Error('Work summary is required to check out.');
        }
        formData.append('work_summary', todaysWork.trim());
        if (workPdf) {
          formData.append('work_report', workPdf, workPdf.name);
        }
      }

      
      // Convert base64 image to blob and append
      const selfieBlob = await fetch(imageData).then(r => r.blob());
      formData.append('selfie', selfieBlob, 'selfie.jpg');
      
      let apiUrl = '';
      if (isCheckingIn) apiUrl = 'http://127.0.0.1:8000/attendance/check-in';
      else apiUrl = 'http://127.0.0.1:8000/attendance/check-out';
      
      const response = await fetch(apiUrl, { method: 'POST', body: formData });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Attendance API error');
      }
      
      // Fetch updated attendance
      await fetchTodayAttendance();
      
      toast({ 
        title: 'Success', 
        description: isCheckingIn ? 'Successfully checked in!' : 'Successfully checked out!',
        variant: 'default'
      });
      if (!isCheckingIn) {
        setTodaysWork('');
        setWorkPdf(null);
      }
    } catch (error) {
      console.error('Attendance error:', error);
      toast({ 
        title: 'Error', 
        description: error instanceof Error ? error.message : 'Failed to record attendance', 
        variant: 'destructive' 
      });
    } finally {
      setShowCamera(false);
      setIsLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setWorkPdf(file);
    }
  };

  const getStatusBadge = (status: string, checkInTime?: string, checkOutTime?: string) => {
    if (status === 'late' || checkInTime && checkInTime > '09:30:00') {
      return <Badge variant="destructive">Late</Badge>;
    }
    if (checkOutTime && checkOutTime < '18:00:00') {
      return <Badge variant="outline" className="border-orange-500 text-orange-500">Early</Badge>;
    }
    if (status === 'present') {
      return <Badge variant="default" className="bg-green-500">On Time</Badge>;
    }
    return null;
  };

  const formatIST = (dateString: string, timeString?: string) => {
    if (!timeString) return '-';
    
    // If timeString is an ISO datetime string (contains 'T'), use it directly
    let date: Date;
    if (timeString.includes('T')) {
      // It's an ISO datetime string - check if it has timezone info
      if (timeString.includes('Z') || timeString.includes('+') || timeString.includes('-', 10)) {
        // Has explicit timezone info
        date = new Date(timeString);
      } else {
        // No timezone info - assume UTC (backend stores UTC)
        date = new Date(timeString + 'Z');
      }
    } else {
      // It's just a time string (HH:MM:SS), assume UTC and combine with date
      date = new Date(`${dateString}T${timeString}Z`);
    }
    
    // Convert to IST and format
    return date.toLocaleString('en-IN', { 
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  if (showCamera) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">
            {isCheckingIn ? t.attendance.checkIn : t.attendance.checkOut}
          </h2>
        </div>
        <AttendanceCamera
          onCapture={handleCameraCapture}
          onCancel={() => setShowCamera(false)}
        />
        {isLoading && (
          <div className="text-center">
            <p className="text-muted-foreground animate-pulse">Recognizing face...</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Modern Header */}
      <div className="bg-gradient-to-r from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800 rounded-2xl p-6 shadow-sm border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg">
              <Clock className="h-7 w-7 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold">{t.navigation.attendance}</h2>
              <p className="text-sm text-muted-foreground mt-1">Mark your daily attendance</p>
            </div>
          </div>
          <Badge variant="outline" className="text-base px-4 py-2 bg-white dark:bg-gray-950">
            <Calendar className="h-4 w-4 mr-2" />
            {format(new Date(), 'dd MMM yyyy')}
          </Badge>
        </div>
      </div>

      {/* Location Status Card - Prominent Display */}
      <Card className="border-0 shadow-lg bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950">
        <CardHeader className="border-b bg-white/50 dark:bg-gray-900/50">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl font-semibold flex items-center gap-2">
                <MapPin className="h-5 w-5 text-blue-600" />
                Current Location
              </CardTitle>
              <CardDescription>Your real-time GPS location</CardDescription>
            </div>
            <div className="flex gap-2">
              {!isImprovingAccuracy && location && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    startContinuousLocationImprovement();
                    toast({
                      title: 'Improving Accuracy',
                      description: 'Getting more precise location...',
                    });
                  }}
                  disabled={isRefreshingLocation || isGettingFastLocation}
                >
                  Improve Accuracy
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  setIsRefreshingLocation(true);
                  stopContinuousLocationImprovement();
                  try {
                    await refreshLocationFast();
                    startContinuousLocationImprovement();
                    toast({
                      title: 'Location Updated',
                      description: 'Your location has been refreshed successfully',
                    });
                  } catch (error: any) {
                    // Error already handled in refreshLocationFast
                  } finally {
                    setIsRefreshingLocation(false);
                  }
                }}
                disabled={isRefreshingLocation || isGettingFastLocation}
              >
                {isRefreshingLocation ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Refreshing...
                  </>
                ) : (
                  'Refresh'
           
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          {isGettingFastLocation ? (
            <div className="flex flex-col items-center justify-center py-8 space-y-3">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm font-medium">Detecting your location...</p>
              <p className="text-xs text-muted-foreground">This should take just a moment</p>
            </div>
          ) : locationError ? (
            <div className="flex flex-col items-center justify-center py-8 space-y-3">
              <AlertCircle className="h-8 w-8 text-red-500" />
              <p className="text-sm font-medium text-red-600">{locationError}</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => refreshLocationFast()}
              >
                Try Again
              </Button>
            </div>
          ) : location ? (
            <div className="space-y-4">
              <div className="bg-white dark:bg-gray-900 rounded-lg p-4 space-y-3">
                <div className="flex items-start gap-3">
                  <MapPin className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 space-y-1">
                    <p className="font-medium text-sm">Address</p>
                    <p className="text-sm text-muted-foreground">{location.address}</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Latitude</p>
                    <p className="font-mono text-sm font-semibold">{location.latitude.toFixed(6)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Longitude</p>
                    <p className="font-mono text-sm font-semibold">{location.longitude.toFixed(6)}</p>
                  </div>
                </div>
                
                <div className="flex items-center justify-between pt-2 border-t text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1">
                      <span className="font-medium">Accuracy:</span>
                      <span className={`font-semibold ${
                        location.accuracy && location.accuracy < 10 ? 'text-green-600' :
                        location.accuracy && location.accuracy < 50 ? 'text-yellow-600' :
                        'text-orange-600'
                      }`}>
                        {location.accuracy ? `±${Math.round(location.accuracy)}m` : 'Unknown'}
                      </span>
                    </span>
                    {isImprovingAccuracy && (
                      <Badge variant="outline" className="text-xs py-0 px-2 border-blue-500 text-blue-600">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Improving...
                      </Badge>
                    )}
                  </div>
                  {location.updatedAt && (
                    <span>
                      {new Date(location.updatedAt).toLocaleTimeString('en-IN', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 space-y-3">
              <AlertCircle className="h-8 w-8 text-orange-500" />
              <p className="text-sm font-medium">Location not available</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => refreshLocationFast()}
              >
                Get Location
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Current Status Card */}
      <Card className="border-0 shadow-lg">
        <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
          <CardTitle className="text-xl font-semibold">{t.attendance.todayStatus}</CardTitle>
          <CardDescription>Your attendance status for today</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {currentAttendance ? (
                <>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <LogIn className="h-4 w-4 text-green-500" />
                      <span className="text-sm font-medium">Check-in Time</span>
                      {getStatusBadge(currentAttendance.status, currentAttendance.checkInTime)}
                    </div>
                    <p className="text-lg font-semibold">
                      {formatIST(currentAttendance.date, currentAttendance.checkInTime)}
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <LogOut className="h-4 w-4 text-red-500" />
                      <span className="text-sm font-medium">Check-out Time</span>
                      {currentAttendance.checkOutTime && 
                        getStatusBadge(currentAttendance.status, undefined, currentAttendance.checkOutTime)}
                    </div>
                    <p className="text-lg font-semibold">
                      {currentAttendance.checkOutTime 
                        ? formatIST(currentAttendance.date, currentAttendance.checkOutTime)
                        : '-'}
                    </p>
                  </div>
                  
                  {currentAttendance.workHours && (
                    <div className="col-span-2">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="h-4 w-4 text-blue-500" />
                        <span className="text-sm font-medium">Total Work Hours</span>
                      </div>
                      <p className="text-lg font-semibold">{currentAttendance.workHours} hours</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="col-span-2 text-center py-8 text-muted-foreground">
                  <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Not checked in yet</p>
                </div>
              )}
            </div>
            
            <div className="flex gap-3 pt-4">
              {!currentAttendance ? (
                <Button onClick={handleCheckIn} size="lg" className="flex-1 gap-2 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-md">
                  <LogIn className="h-5 w-5" />
                  {t.attendance.checkIn}
                </Button>
              ) : !currentAttendance.checkOutTime ? (
                <Button onClick={handleCheckOut} size="lg" className="flex-1 gap-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 shadow-md">
                  <LogOut className="h-5 w-5" />
                  {t.attendance.checkOut}
                </Button>
              ) : (
                <div className="flex-1 text-center">
                  <Badge className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0">
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Attendance Completed for Today
                  </Badge>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Attendance History */}
      <Card className="border-0 shadow-lg">
        <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
          <CardTitle className="text-xl font-semibold">{t.attendance.history}</CardTitle>
          <CardDescription>Your recent attendance records</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {attendanceHistory.length > 0 ? (
              attendanceHistory.slice(-10).reverse().map((record) => (
                <div key={record.id} className="flex items-center justify-between p-4 rounded-lg border hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-md">
                      <Calendar className="h-6 w-6 text-white" />
                    </div>
                    <div>
                      <p className="font-medium">{format(new Date(record.date), 'dd MMM yyyy')}</p>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>In: {formatIST(record.date, record.checkInTime)}</span>
                        <span>Out: {formatIST(record.date, record.checkOutTime)}</span>
                        {record.workHours && <span>{record.workHours}h</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(record.status, record.checkInTime, record.checkOutTime)}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-center py-8 text-muted-foreground">No attendance history</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Checkout Confirmation Dialog */}
      <Dialog open={showCheckoutDialog} onOpenChange={setShowCheckoutDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold">Confirm Check-out</DialogTitle>
            <DialogDescription>
              Please provide today's work summary before checking out. You can optionally upload a work report PDF.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="work-summary">Today's Work Summary <span className="text-red-500">*</span></Label>
              <Input
                id="work-summary"
                placeholder="Brief description of today's work..."
                value={todaysWork}
                onChange={(e) => setTodaysWork(e.target.value)}
                className="mt-2"
                required
              />
            </div>
            <div>
              <Label htmlFor="work-pdf">Upload Work Report PDF (Optional)</Label>
              <div className="mt-2 flex items-center gap-2">
                <Input
                  id="work-pdf"
                  type="file"
                  accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
                  onChange={handleFileUpload}
                />
                {workPdf && (
                  <Badge variant="outline">
                    <FileText className="h-3 w-3 mr-1" />
                    {workPdf.name}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCheckoutDialog(false)}>
              Cancel
            </Button>
            <Button onClick={confirmCheckOut} className="bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700">
              Proceed to Check-out
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AttendancePage;