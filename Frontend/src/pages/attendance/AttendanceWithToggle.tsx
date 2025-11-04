import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { toast } from '@/hooks/use-toast';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import AttendanceCamera from '@/components/attendance/AttendanceCamera';
import { Clock, MapPin, Calendar, LogIn, LogOut, FileText, CheckCircle, AlertCircle, Users, Filter } from 'lucide-react';
import { AttendanceRecord, UserRole } from '@/types';
import { format } from 'date-fns';

const AttendanceWithToggle: React.FC = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [viewMode, setViewMode] = useState<'self' | 'employee'>('self');
  const [showCamera, setShowCamera] = useState(false);
  const [isCheckingIn, setIsCheckingIn] = useState(true);
  const [showCheckoutDialog, setShowCheckoutDialog] = useState(false);
  const [todaysWork, setTodaysWork] = useState('');
  const [workPdf, setWorkPdf] = useState<File | null>(null);
  const [currentAttendance, setCurrentAttendance] = useState<AttendanceRecord | null>(null);
  const [attendanceHistory, setAttendanceHistory] = useState<AttendanceRecord[]>([]);
  const [employeeAttendanceData, setEmployeeAttendanceData] = useState<AttendanceRecord[]>([]);
  const [location, setLocation] = useState<{ latitude: number; longitude: number; address?: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [filterRole, setFilterRole] = useState<'all' | UserRole>('all');

  // Determine if user can view employee attendance
  const canViewEmployeeAttendance = user?.role && ['admin', 'hr', 'manager'].includes(user.role);

  // Access rules for attendance viewing
  const getViewableRoles = (): UserRole[] => {
    if (user?.role === 'admin') return ['admin', 'hr', 'manager', 'team_lead', 'employee'];
    if (user?.role === 'hr') return ['hr', 'manager', 'team_lead', 'employee'];
    if (user?.role === 'manager') return ['team_lead', 'employee'];
    return [];
  };

  useEffect(() => {
    loadFromBackend();
    getCurrentLocation();
    if (viewMode === 'employee' && canViewEmployeeAttendance) {
      loadEmployeeAttendance();
    }
  }, [viewMode]);

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      const MIN_ACCURACY = 10;
      const TIMEOUT_MS = 15000;
      let watchId: number | null = null;
      const clear = () => { if (watchId !== null) navigator.geolocation.clearWatch(watchId); };
      watchId = navigator.geolocation.watchPosition(async (position) => {
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
        }
      }, (error) => {
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
      }, { enableHighAccuracy: true, maximumAge: 0, timeout: TIMEOUT_MS });
      setTimeout(() => clear(), TIMEOUT_MS);
    } else {
      toast({
        title: 'Location Not Supported',
        description: 'Your browser does not support geolocation. Please use a modern browser.',
        variant: 'destructive',
      });
    }
  };

  const loadFromBackend = async () => {
    try {
      if (!user?.id) return;
      const res = await fetch(`http://127.0.0.1:8000/attendance/my-attendance/${user.id}`);
      if (!res.ok) return;
      const data = await res.json();
      setAttendanceHistory(
        data.map((rec: any) => ({
          id: String(rec.attendance_id),
          userId: String(rec.user_id),
          date: format(new Date(rec.check_in), 'yyyy-MM-dd'),
          checkInTime: rec.check_in, // Use ISO datetime string
          checkOutTime: rec.check_out || undefined, // Use ISO datetime string
          checkInLocation: { latitude: 0, longitude: 0, address: rec.gps_location || 'N/A' },
          checkInSelfie: rec.selfie || '',
          status: 'present',
          workHours: rec.total_hours,
        }))
      );
      const today = format(new Date(), 'yyyy-MM-dd');
      const todayRecord = data.find((rec: any) => format(new Date(rec.check_in), 'yyyy-MM-dd') === today);
      if (todayRecord) {
        setCurrentAttendance({
          id: String(todayRecord.attendance_id),
          userId: String(todayRecord.user_id),
          date: format(new Date(todayRecord.check_in), 'yyyy-MM-dd'),
          checkInTime: todayRecord.check_in, // Use ISO datetime string
          checkOutTime: todayRecord.check_out || undefined, // Use ISO datetime string
          checkInLocation: { latitude: 0, longitude: 0, address: todayRecord.gps_location || 'N/A' },
          checkInSelfie: todayRecord.selfie || '',
          status: 'present',
          workHours: todayRecord.total_hours,
        });
      } else {
        setCurrentAttendance(null);
      }
    } catch (e) {
      // ignore
    }
  };

  const loadEmployeeAttendance = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://127.0.0.1:8000/attendance/all', {
        headers: { 'Authorization': token ? `Bearer ${token}` : '' }
      });
      if (!res.ok) return;
      const data = await res.json();
      const records: AttendanceRecord[] = data
        .filter((rec: any) => new Date(rec.check_in))
        .map((rec: any) => ({
          id: String(rec.attendance_id),
          userId: String(rec.employee_id || rec.user_id),
          date: rec.check_in ? (rec.check_in.includes('T') ? rec.check_in.slice(0,10) : format(new Date(rec.check_in), 'yyyy-MM-dd')) : selectedDate,
          checkInTime: rec.check_in || undefined, // Use ISO datetime string if available
          checkOutTime: rec.check_out || undefined, // Use ISO datetime string if available
          checkInLocation: { latitude: 0, longitude: 0, address: rec.gps_location || 'N/A' },
          checkInSelfie: rec.selfie || '',
          status: 'present',
          workHours: rec.total_hours,
        }))
        .filter((r: AttendanceRecord) => r.date === selectedDate)
        .filter((r: AttendanceRecord) => filterRole === 'all' ? true : true);
      setEmployeeAttendanceData(records);
    } catch (e) {
      // ignore
    }
  };

  const handleCheckIn = () => {
    if (!location) {
      toast({
        title: 'Error',
        description: t.attendance.locationRequired,
        variant: 'destructive',
      });
      return;
    }
    setIsCheckingIn(true);
    setShowCamera(true);
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
      if (!location) {
        await getCurrentLocation();
      }
      if (!location || !user?.id) throw new Error('Location or user missing');
      const gpsLocation = `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}${location.address ? ' - ' + location.address : ''}`;
      if (location.accuracy && location.accuracy > 10) {
        toast({ title: 'Low GPS Accuracy', description: `Proceeding with ±${Math.round(location.accuracy)}m.`, variant: 'default' });
      }
      const payload = {
        user_id: user.id,
        gps_location: gpsLocation,
        selfie: imageData,
      };
      const endpoint = isCheckingIn ? 'http://127.0.0.1:8000/attendance/check-in-json' : 'http://127.0.0.1:8000/attendance/check-out-json';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Attendance API error');
      }
      await loadFromBackend();
      toast({ title: 'Success', description: isCheckingIn ? t.attendance.checkedIn : t.attendance.checkedOut });
    } catch (e: any) {
      toast({ title: 'Error', description: e?.message || 'Failed to record attendance', variant: 'destructive' });
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
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{t.navigation.attendance}</h2>
        <div className="flex items-center gap-4">
          {canViewEmployeeAttendance && (
            <div className="flex items-center space-x-2">
              <Switch
                id="view-mode"
                checked={viewMode === 'employee'}
                onCheckedChange={(checked) => setViewMode(checked ? 'employee' : 'self')}
              />
              <Label htmlFor="view-mode" className="cursor-pointer">
                {viewMode === 'self' ? 'Self Attendance' : 'Employee Attendance'}
              </Label>
            </div>
          )}
          <Badge variant="outline" className="text-lg px-3 py-1">
            <Calendar className="h-4 w-4 mr-2" />
            {format(new Date(), 'dd MMM yyyy')}
          </Badge>
        </div>
      </div>

      {viewMode === 'self' ? (
        <>
          {/* Self Attendance View */}
          <Card>
            <CardHeader>
              <CardTitle>{t.attendance.todayStatus}</CardTitle>
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
                    <Button onClick={handleCheckIn} size="lg" className="flex-1">
                      <LogIn className="h-5 w-5 mr-2" />
                      {t.attendance.checkIn}
                    </Button>
                  ) : !currentAttendance.checkOutTime ? (
                    <Button onClick={handleCheckOut} size="lg" variant="destructive" className="flex-1">
                      <LogOut className="h-5 w-5 mr-2" />
                      {t.attendance.checkOut}
                    </Button>
                  ) : (
                    <div className="flex-1 text-center">
                      <Badge variant="outline" className="px-4 py-2">
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
          <Card>
            <CardHeader>
              <CardTitle>{t.attendance.history}</CardTitle>
              <CardDescription>Your recent attendance records</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {attendanceHistory.length > 0 ? (
                  attendanceHistory.slice(-10).reverse().map((record) => (
                    <div key={record.id} className="flex items-center justify-between p-3 rounded-lg border">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                          <Calendar className="h-5 w-5 text-primary" />
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
        </>
      ) : (
        <>
          {/* Employee Attendance View */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Employee Attendance
              </CardTitle>
              <CardDescription>View and manage team attendance records</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="flex-1">
                    <Label htmlFor="date-filter">Date</Label>
                    <Input
                      id="date-filter"
                      type="date"
                      value={selectedDate}
                      onChange={(e) => {
                        setSelectedDate(e.target.value);
                        loadEmployeeAttendance();
                      }}
                      className="mt-1"
                    />
                  </div>
                  <div className="flex-1">
                    <Label htmlFor="role-filter">Role Filter</Label>
                    <Select value={filterRole} onValueChange={(value: any) => setFilterRole(value)}>
                      <SelectTrigger id="role-filter" className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Roles</SelectItem>
                        {getViewableRoles().map(role => (
                          <SelectItem key={role} value={role}>{role}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee ID</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Check-in</TableHead>
                        <TableHead>Check-out</TableHead>
                        <TableHead>Work Hours</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Location</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {employeeAttendanceData.length > 0 ? (
                        employeeAttendanceData.map((record) => (
                          <TableRow key={record.id}>
                            <TableCell className="font-medium">{record.userId}</TableCell>
                            <TableCell>{format(new Date(record.date), 'dd MMM yyyy')}</TableCell>
                            <TableCell>{formatIST(record.date, record.checkInTime)}</TableCell>
                            <TableCell>{formatIST(record.date, record.checkOutTime)}</TableCell>
                            <TableCell>{record.workHours || '-'} h</TableCell>
                            <TableCell>
                              {getStatusBadge(record.status, record.checkInTime, record.checkOutTime)}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {record.checkInLocation.address || 'N/A'}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            No attendance records found
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Checkout Confirmation Dialog */}
      <Dialog open={showCheckoutDialog} onOpenChange={setShowCheckoutDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Check-out</DialogTitle>
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
            <Button onClick={confirmCheckOut}>
              Proceed to Check-out
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AttendanceWithToggle;