import React, { useState, useEffect } from 'react';
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
import { Clock, MapPin, Calendar, LogIn, LogOut, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { AttendanceRecord } from '@/types';
import { format } from 'date-fns';

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
  const [location, setLocation] = useState<{ latitude: number; longitude: number; address?: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

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

  useEffect(() => {
    fetchTodayAttendance();
    getCurrentLocation();
    
    // Auto-refresh at midnight to reset for new day
    const checkMidnight = setInterval(() => {
      const now = new Date();
      if (now.getHours() === 0 && now.getMinutes() === 0) {
        setCurrentAttendance(null);
        fetchTodayAttendance();
      }
    }, 60000); // Check every minute
    
    return () => clearInterval(checkMidnight);
  }, [user?.id]);

  const getCurrentLocation = (): Promise<void> => {
    if (navigator.geolocation) {
      // Request high accuracy GPS location and refine until accuracy <= 10m or timeout
      return new Promise((resolve) => {
        const MIN_ACCURACY = 10; // meters
        const TIMEOUT_MS = 15000;
        let watchId: number | null = null;
        const clear = () => { if (watchId !== null) navigator.geolocation.clearWatch(watchId); };
        const onSuccess = async (position: GeolocationPosition) => {
          const loc = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            address: ''
          };
          try {
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${loc.latitude}&lon=${loc.longitude}&format=json&addressdetails=1&zoom=18`);
            const data = await response.json();
            if (data.address) {
              const addressParts: string[] = [];
              if (data.address.house_number) addressParts.push(data.address.house_number);
              if (data.address.road) addressParts.push(data.address.road);
              if (data.address.suburb) addressParts.push(data.address.suburb);
              if (data.address.village) addressParts.push(data.address.village);
              if (data.address.town) addressParts.push(data.address.town);
              if (data.address.city) addressParts.push(data.address.city);
              if (data.address.state_district) addressParts.push(data.address.state_district);
              if (data.address.state) addressParts.push(data.address.state);
              if (data.address.postcode) addressParts.push(data.address.postcode);
              loc.address = addressParts.join(', ') || data.display_name;
            } else {
              loc.address = data.display_name || `${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`;
            }
          } catch {
            loc.address = `${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`;
          }
          setLocation(loc);
          if (loc.accuracy <= MIN_ACCURACY) {
            clear();
            resolve();
          }
        };
        const onError = (error: GeolocationPositionError) => {
          clear();
          let errorMessage = t.attendance.locationRequired;
          switch(error.code) {
            case error.PERMISSION_DENIED:
              errorMessage = "Location permission denied. Please enable location access in your browser settings.";
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage = "Location information is unavailable. Please check your GPS settings.";
              break;
            case error.TIMEOUT:
              errorMessage = "Location request timed out. Please try again.";
              break;
          }
          toast({ title: 'Location Error', description: errorMessage, variant: 'destructive' });
          resolve();
        };
        watchId = navigator.geolocation.watchPosition(onSuccess, onError, {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: TIMEOUT_MS,
        });
        // Safety timeout
        setTimeout(() => { clear(); resolve(); }, TIMEOUT_MS);
      });
    } else {
      toast({
        title: 'Location Not Supported',
        description: 'Your browser does not support geolocation. Please use a modern browser.',
        variant: 'destructive',
      });
      return Promise.resolve();
    }
  };

  const handleCheckIn = async () => {
    if (!location) {
      await getCurrentLocation();
      if (!location) {
        toast({
          title: 'Location Required',
          description: 'Please enable location services and try again.',
          variant: 'destructive',
        });
        return;
      }
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

  const handleCheckOut = () => {
    if (!location) {
      toast({
        title: 'Error',
        description: t.attendance.locationRequired,
        variant: 'destructive',
      });
      return;
    }
    setShowCheckoutDialog(true);
  };

  const confirmCheckOut = () => {
    setIsCheckingIn(false);
    setShowCamera(true);
    setShowCheckoutDialog(false);
  };

  const handleCameraCapture = async (imageData: string) => {
    setIsLoading(true);
    try {
      if (!location || !user?.id) throw new Error('Location or user missing');
      
      const formData = new FormData();
      formData.append('user_id', String(user.id));
      
      // Format GPS location properly
      const gpsLocation = `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}${location.address ? ' - ' + location.address : ''}`;
      formData.append('gps_location', gpsLocation);
      
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
    if (file && file.type === 'application/pdf') {
      setWorkPdf(file);
    } else {
      toast({
        title: 'Error',
        description: 'Please upload a PDF file',
        variant: 'destructive',
      });
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

      {/* Current Status Card */}
      <Card className="border-0 shadow-lg">
        <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
          <CardTitle className="text-xl font-semibold">{t.attendance.todayStatus}</CardTitle>
          <CardDescription>Your attendance status for today</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {location && (
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <MapPin className="h-4 w-4 mt-0.5" />
                <span className="flex-1">{location.address}</span>
              </div>
            )}
            
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
              You can optionally add today's work report before checking out.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="work-summary">Today's Work Summary (Optional)</Label>
              <Input
                id="work-summary"
                placeholder="Brief description of today's work..."
                value={todaysWork}
                onChange={(e) => setTodaysWork(e.target.value)}
                className="mt-2"
              />
            </div>
            <div>
              <Label htmlFor="work-pdf">Upload Work Report PDF (Optional)</Label>
              <div className="mt-2 flex items-center gap-2">
                <Input
                  id="work-pdf"
                  type="file"
                  accept="application/pdf"
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