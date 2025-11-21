import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar, Clock, MapPin, Search, Filter, Download, AlertCircle, CheckCircle, Users, X, User, Settings } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { AttendanceRecord } from '@/types';
import { format, subMonths, subDays } from 'date-fns';
import { DatePicker } from '@/components/ui/date-picker';

interface EmployeeAttendance extends AttendanceRecord {
  userName: string;
  userEmail: string;
  department: string;
  employeeId?: string;
  checkInStatus?: string;
  checkOutStatus?: string;
  scheduledStart?: string | null;
  scheduledEnd?: string | null;
  workSummary?: string | null;
  workReport?: string | null;
}

interface OfficeTiming {
  id: number;
  department?: string | null;
  start_time: string;
  end_time: string;
  check_in_grace_minutes: number;
  check_out_grace_minutes: number;
}

type TimingFormState = {
  startTime: string;
  endTime: string;
  checkInGrace: number | '';
  checkOutGrace: number | '';
};

type DepartmentTimingFormState = TimingFormState & {
  department: string;
};

const resolveGraceValue = (value: number | '') => (value === '' ? 0 : value);

const AttendanceManager: React.FC = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const isAdmin = user?.role === 'admin';
  const [attendanceRecords, setAttendanceRecords] = useState<EmployeeAttendance[]>([]);
  const [filteredRecords, setFilteredRecords] = useState<EmployeeAttendance[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<EmployeeAttendance | null>(null);
  const [showSelfieModal, setShowSelfieModal] = useState(false);
const [summaryModal, setSummaryModal] = useState<{ open: boolean; summary: string | null }>({ open: false, summary: null });
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterDate, setFilterDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [isExporting, setIsExporting] = useState(false);
  const [summary, setSummary] = useState<{ total_employees: number; present_today: number; late_arrivals: number; early_departures: number; absent_today: number }>({ total_employees: 0, present_today: 0, late_arrivals: 0, early_departures: 0, absent_today: 0 });
  
  // Export modal states
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportType, setExportType] = useState<'csv' | 'pdf' | null>(null);
  const [quickFilter, setQuickFilter] = useState<string>('custom');
  const [startDate, setStartDate] = useState<Date | undefined>(undefined);
  const [endDate, setEndDate] = useState<Date | undefined>(new Date());
  const [employeeFilter, setEmployeeFilter] = useState<'all' | 'specific'>('all');
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [employees, setEmployees] = useState<Array<{ user_id: number; employee_id: string; name: string; department?: string | null }>>([]);
  const [filteredEmployees, setFilteredEmployees] = useState<Array<{ user_id: number; employee_id: string; name: string; department?: string | null }>>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<{ user_id: number; employee_id: string; name: string; department?: string | null } | null>(null);
  const [selectedDepartmentFilter, setSelectedDepartmentFilter] = useState<string>('');
  const [departments, setDepartments] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'attendance' | 'office-hours'>('attendance');
  const [officeTimings, setOfficeTimings] = useState<OfficeTiming[]>([]);
  const [officeFormLoading, setOfficeFormLoading] = useState(false);
  const [globalTimingForm, setGlobalTimingForm] = useState<TimingFormState>({
    startTime: '09:30',
    endTime: '18:00',
    checkInGrace: 15,
    checkOutGrace: 0,
  });
  const [departmentTimingForm, setDepartmentTimingForm] = useState<DepartmentTimingFormState>({
    department: '',
    startTime: '09:30',
    endTime: '18:00',
    checkInGrace: 15,
    checkOutGrace: 0,
  });
 
  const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: token } : {};
  };

  const resolveMediaUrl = (url?: string | null) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const normalized = url.startsWith('/') ? url : `/${url}`;
    return `http://127.0.0.1:8000${normalized}`;
  };

  useEffect(() => {
    loadAllAttendance();
    fetchSummary();
    loadEmployees();
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadOfficeTimings();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (employeeFilter !== 'specific') {
      setFilteredEmployees([]);
      return;
    }

    let subset = employees;
    const normalizedDept = selectedDepartmentFilter.trim().toLowerCase();
    if (normalizedDept) {
      subset = subset.filter(
        (emp) => (emp.department || '').trim().toLowerCase() === normalizedDept,
      );
    }

    const searchValue = employeeSearch.trim().toLowerCase();
    if (searchValue) {
      subset = subset.filter(
        (emp) =>
          emp.name.toLowerCase().includes(searchValue) ||
          emp.employee_id?.toLowerCase().includes(searchValue),
      );
    }

    setFilteredEmployees(subset);
  }, [employeeFilter, selectedDepartmentFilter, employeeSearch, employees]);

  useEffect(() => {
    if (employeeFilter === 'specific') {
      if (!selectedDepartmentFilter && departments.length === 1) {
        setSelectedDepartmentFilter(departments[0]);
      }
    } else {
      setSelectedDepartmentFilter('');
      setSelectedEmployee(null);
    }
  }, [employeeFilter, departments, selectedDepartmentFilter]);

  const loadEmployees = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/employees');
      if (!res.ok) throw new Error(`Failed to load employees: ${res.status}`);
      const data = await res.json();
      const departmentSet = new Set<string>();
      const mapped = data.map((emp: any) => {
        const department = emp.department || emp.department_name || '';
        if (department) {
          departmentSet.add(department);
        }
        return {
        user_id: emp.user_id || emp.userId,
        employee_id: emp.employee_id || emp.employeeId || '',
          name: emp.name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim(),
          department,
        };
      });
      setEmployees(mapped);
      setDepartments(Array.from(departmentSet).sort((a, b) => a.localeCompare(b)));
    } catch (err) {
      console.error('loadEmployees error', err);
    }
  };

  const loadOfficeTimings = async () => {
    if (!isAdmin) return;
    setOfficeFormLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/attendance/office-hours', {
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
      });
      if (!res.ok) throw new Error(`Failed to load office timings: ${res.status}`);
      const data: OfficeTiming[] = await res.json();
      setOfficeTimings(data);

      const globalTiming = data.find((entry) => !entry.department || entry.department === '');
      if (globalTiming) {
        setGlobalTimingForm({
          startTime: (globalTiming.start_time || '').slice(0, 5) || '09:30',
          endTime: (globalTiming.end_time || '').slice(0, 5) || '18:00',
          checkInGrace: globalTiming.check_in_grace_minutes ?? 0,
          checkOutGrace: globalTiming.check_out_grace_minutes ?? 0,
        });
      }

      const timingDepartments = data
        .map((entry) => entry.department)
        .filter((dept): dept is string => Boolean(dept && dept.trim()));
      if (timingDepartments.length) {
        setDepartments((prev) => {
          const merged = new Set(prev);
          timingDepartments.forEach((dept) => merged.add(dept));
          return Array.from(merged).sort((a, b) => a.localeCompare(b));
        });
      }
    } catch (error) {
      console.error('loadOfficeTimings error', error);
      toast({
        title: 'Office timing fetch failed',
        description: 'Unable to load configured office timings.',
        variant: 'destructive',
      });
    } finally {
      setOfficeFormLoading(false);
    }
  };

  const handleGlobalTimingSave = async () => {
    try {
      setOfficeFormLoading(true);
      const payload = {
        department: null,
        start_time: globalTimingForm.startTime,
        end_time: globalTimingForm.endTime,
        check_in_grace_minutes: resolveGraceValue(globalTimingForm.checkInGrace),
        check_out_grace_minutes: resolveGraceValue(globalTimingForm.checkOutGrace),
      };
      const res = await fetch('http://127.0.0.1:8000/attendance/office-hours', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to save office timing: ${res.status}`);
      await loadOfficeTimings();
      toast({ title: 'Office time saved', description: 'Global office timing updated successfully.' });
    } catch (error) {
      console.error('handleGlobalTimingSave error', error);
      toast({
        title: 'Save failed',
        description: 'Unable to save global office time. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setOfficeFormLoading(false);
    }
  };

  const handleDepartmentTimingSave = async () => {
    if (!departmentTimingForm.department.trim()) {
      toast({
        title: 'Department required',
        description: 'Please specify a department before saving.',
        variant: 'destructive',
      });
      return;
    }

    try {
      setOfficeFormLoading(true);
      const payload = {
        department: departmentTimingForm.department.trim(),
        start_time: departmentTimingForm.startTime,
        end_time: departmentTimingForm.endTime,
        check_in_grace_minutes: resolveGraceValue(departmentTimingForm.checkInGrace),
        check_out_grace_minutes: resolveGraceValue(departmentTimingForm.checkOutGrace),
      };
      const res = await fetch('http://127.0.0.1:8000/attendance/office-hours', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to save department office timing: ${res.status}`);
      await loadOfficeTimings();
      toast({
        title: 'Department timing saved',
        description: `Office timing updated for ${departmentTimingForm.department}.`,
      });
    } catch (error) {
      console.error('handleDepartmentTimingSave error', error);
      toast({
        title: 'Save failed',
        description: 'Unable to save department office time. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setOfficeFormLoading(false);
    }
  };

  const handleDepartmentTimingEdit = (timing: OfficeTiming) => {
    setDepartmentTimingForm({
      department: timing.department || '',
      startTime: (timing.start_time || '').slice(0, 5) || '09:30',
      endTime: (timing.end_time || '').slice(0, 5) || '18:00',
      checkInGrace: timing.check_in_grace_minutes ?? 0,
      checkOutGrace: timing.check_out_grace_minutes ?? 0,
    });
  };

  const handleDepartmentTimingDelete = async (timing: OfficeTiming) => {
    if (!window.confirm(`Remove office timing for ${timing.department || 'all departments'}?`)) {
      return;
    }

    try {
      setOfficeFormLoading(true);
      const res = await fetch(`http://127.0.0.1:8000/attendance/office-hours/${timing.id}`, {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders(),
        },
      });
      if (!res.ok) throw new Error(`Failed to delete office timing: ${res.status}`);
      await loadOfficeTimings();
      if (
        timing.department &&
        departmentTimingForm.department.trim().toLowerCase() === timing.department.trim().toLowerCase()
      ) {
        setDepartmentTimingForm({
          department: '',
          startTime: globalTimingForm.startTime,
          endTime: globalTimingForm.endTime,
          checkInGrace: globalTimingForm.checkInGrace,
          checkOutGrace: globalTimingForm.checkOutGrace,
        });
      }
      toast({ title: 'Office timing removed', description: 'The office timing has been deactivated.' });
    } catch (error) {
      console.error('handleDepartmentTimingDelete error', error);
      toast({
        title: 'Delete failed',
        description: 'Unable to remove the office timing. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setOfficeFormLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/attendance/summary');
      if (!res.ok) throw new Error(`Failed to load summary: ${res.status}`);
      const data = await res.json();
      setSummary(data);
    } catch (err) {
      console.error('fetchSummary error', err);
    }
  };

  useEffect(() => {
    filterRecords();
  }, [searchTerm, filterStatus, filterDate, attendanceRecords]);

  const loadAllAttendance = (targetDate?: string) => {
    // Fetch today's attendance from backend
    // For Admin/HR/Manager: Load today's attendance records
    (async () => {
      try {
        const query = targetDate ? `?date=${encodeURIComponent(targetDate)}` : '';
        const res = await fetch(`http://127.0.0.1:8000/attendance/today${query}`);
        
        if (!res.ok) {
          const errorText = await res.text();
          console.error(`Failed to load attendance: ${res.status}`, errorText);
          throw new Error(`Failed to load attendance: ${res.status} - ${errorText}`);
        }
        
        const data = await res.json();
        console.log('Attendance data received:', data);
        
        // Transform backend data to EmployeeAttendance format
        const transformedData: EmployeeAttendance[] = data.map((rec: any) => {
          const checkIn = rec.check_in || rec.checkInTime;
          const checkOut = rec.check_out || rec.checkOutTime;
          const checkInDate = checkIn ? new Date(checkIn) : null;

          const status = (rec.status || 'present').toLowerCase();
          const checkInStatus = rec.checkInStatus || rec.check_in_status || null;
          const checkOutStatus = rec.checkOutStatus || rec.check_out_status || null;
          const scheduledStart = rec.scheduledStart || rec.scheduled_start || null;
          const scheduledEnd = rec.scheduledEnd || rec.scheduled_end || null;
          
          return {
            id: String(rec.attendance_id || rec.id || ''),
            userId: String(rec.user_id || rec.userId || ''),
            userName: rec.userName || rec.name || 'Unknown',
            userEmail: rec.userEmail || rec.email || '',
            employeeId: rec.employee_id || rec.employeeId || String(rec.user_id || rec.userId || ''),
            department: rec.department || 'N/A',
            date: checkInDate ? format(checkInDate, 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
            checkInTime: checkIn || undefined,
            checkOutTime: checkOut || undefined,
            checkInLocation: { 
              latitude: 0, 
              longitude: 0, 
              address: rec.checkInLocationLabel || rec.locationLabel || rec.gps_location || rec.checkInLocation?.address || 'N/A' 
            },
            checkInSelfie: resolveMediaUrl(rec.checkInSelfie || rec.selfie || rec.selfie_url),
            checkOutSelfie: resolveMediaUrl(rec.checkOutSelfie || rec.check_out_selfie || rec.checkout_selfie_url),
            status: (status as any) || 'present',
            workHours: rec.total_hours || rec.workHours || 0,
            checkInStatus: checkInStatus || undefined,
            checkOutStatus: checkOutStatus || undefined,
            scheduledStart: scheduledStart || undefined,
            scheduledEnd: scheduledEnd || undefined,
            workSummary: rec.workSummary || rec.work_summary || null,
            workReport: resolveMediaUrl(rec.workReport || rec.work_report),
          };
        });
        
        console.log('Transformed attendance records:', transformedData);
        setAttendanceRecords(transformedData);
      } catch (err) {
        console.error('loadAllAttendance error', err);
        toast({
          title: 'Error',
          description: 'Failed to load attendance records. Please try again.',
          variant: 'destructive',
        });
      }
    })();
  };

  const filterRecords = () => {
    let filtered = [...attendanceRecords];
    
    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(record => 
        record.userName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        record.userEmail.toLowerCase().includes(searchTerm.toLowerCase()) ||
        record.department.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (record.employeeId && record.employeeId.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (record.userId && record.userId.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }
    
    // Filter by status
    if (filterStatus !== 'all') {
      filtered = filtered.filter(record => {
        const statusValue = record.status?.toLowerCase() || '';
        const checkInStatusValue = record.checkInStatus?.toLowerCase() || '';
        const checkOutStatusValue = record.checkOutStatus?.toLowerCase() || '';
        if (filterStatus === 'late') {
          return statusValue === 'late' || checkInStatusValue === 'late';
        }
        if (filterStatus === 'early') {
          return checkOutStatusValue === 'early';
        }
        if (filterStatus === 'present') {
          return statusValue === 'present' && checkOutStatusValue !== 'early';
        }
        return true;
      });
    }
    
    // Filter by date
    if (filterDate) {
      filtered = filtered.filter(record => record.date === filterDate);
    }
    
    setFilteredRecords(filtered);
  };

  const getStatusBadge = (record: EmployeeAttendance) => {
    const badges: React.ReactNode[] = [];
    
    if (!record.checkOutTime) {
      badges.push(
        <Badge key="active" variant="default" className="bg-blue-500 text-xs">
          Awaiting Check-out
        </Badge>,
      );
    }
    
    if (record.checkInStatus === 'late' || record.status === 'late') {
      badges.push(
        <Badge key="late" variant="destructive" className="text-xs">
          Late Check-in
        </Badge>,
      );
    }

    if (record.checkOutStatus === 'early') {
      badges.push(
        <Badge key="early" variant="outline" className="border-orange-500 text-orange-500 text-xs">
          Early Check-out
        </Badge>,
      );
    }

    if (badges.length === 0) {
      badges.push(
        <Badge key="ontime" variant="default" className="bg-green-500 text-xs">
          On Schedule
        </Badge>,
      );
    }
    
    return badges;
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

  const handleQuickFilter = (filter: string) => {
    setQuickFilter(filter);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    
    switch (filter) {
      case 'last_month':
        setStartDate(subMonths(today, 1));
        setEndDate(today);
        break;
      case 'last_3_months':
        setStartDate(subMonths(today, 3));
        setEndDate(today);
        break;
      case 'last_6_months':
        setStartDate(subMonths(today, 6));
        setEndDate(today);
        break;
      case 'custom':
        // Don't modify dates when custom is selected, let user choose
        break;
    }
  };

  const openExportModal = (type: 'csv' | 'pdf') => {
    setExportType(type);
    setExportModalOpen(true);
    // Set default dates
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    setEndDate(today);
    setStartDate(undefined);
    setQuickFilter('custom');
    setEmployeeFilter('all');
    setEmployeeSearch('');
    setSelectedEmployee(null);
    setSelectedDepartmentFilter('');
    setFilteredEmployees([]);
  };

  const performExport = async () => {
    if (!startDate && !endDate) {
      toast({
        title: 'Date Range Required',
        description: 'Please select at least a start date or end date for the export.',
        variant: 'destructive',
      });
      return;
    }

    if (employeeFilter === 'specific' && !selectedEmployee) {
      toast({
        title: 'Employee Selection Required',
        description: 'Please select an employee to export their data.',
        variant: 'destructive',
      });
      return;
    }

    setIsExporting(true);
    setExportModalOpen(false);

    try {
      const params = new URLSearchParams();
      
      if (employeeFilter === 'specific' && selectedEmployee) {
        params.append('employee_id', selectedEmployee.employee_id || selectedEmployee.user_id.toString());
        if (selectedDepartmentFilter) {
          params.append('department', selectedDepartmentFilter);
        }
      }
      
      if (startDate) {
        params.append('start_date', format(startDate, 'yyyy-MM-dd'));
      }
      
      if (endDate) {
        params.append('end_date', format(endDate, 'yyyy-MM-dd'));
      }

      const apiUrl = `http://127.0.0.1:8000/attendance/download/${exportType}?${params.toString()}`;
      const res = await fetch(apiUrl, { method: 'GET' });

      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      const dateStr = startDate && endDate 
        ? `${format(startDate, 'yyyyMMdd')}_${format(endDate, 'yyyyMMdd')}`
        : startDate 
        ? `from_${format(startDate, 'yyyyMMdd')}`
        : endDate 
        ? `until_${format(endDate, 'yyyyMMdd')}`
        : 'all';
      
      const empStr = employeeFilter === 'specific' && selectedEmployee
        ? `_${selectedEmployee.employee_id || selectedEmployee.user_id}`
        : '';
      
      a.download = `attendance_report${empStr}_${dateStr}.${exportType}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast({
        title: 'Export Successful',
        description: `Attendance data exported as ${exportType?.toUpperCase()} successfully.`,
        variant: 'default',
      });
    } catch (err) {
      console.error(`Export ${exportType} failed`, err);
      let message = String(err);
      if (err && typeof err === 'object' && 'message' in err) {
        message = (err as any).message || message;
      }
      toast({
        title: 'Export Failed',
        description: `Failed to export ${exportType?.toUpperCase()}: ${message}`,
        variant: 'destructive',
      });
    } finally {
      setIsExporting(false);
      setExportType(null);
    }
  };

  const exportToCSV = () => {
    openExportModal('csv');
  };
  
  const exportToPDF = () => {
    openExportModal('pdf');
  };


  const todayStats = {
    total: summary.total_employees,
    present: summary.present_today,
    late: summary.late_arrivals,
    early: summary.early_departures,
  };

  const formatTimeDisplay = (timeValue?: string | null) => {
    if (!timeValue) return '--:--';
    const normalized = timeValue.includes(':') ? timeValue.slice(0, 5) : timeValue;
    const [hour, minute] = normalized.split(':');
    if (hour === undefined || minute === undefined) return normalized;
    try {
      const date = new Date();
      date.setHours(Number(hour), Number(minute));
      return date.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return normalized;
    }
  };

  const globalTimingEntry = officeTimings.find(
    (entry) => !entry.department || entry.department === '',
  );
  const configuredDepartmentCount = officeTimings.filter(
    (entry) => entry.department && entry.department.trim(),
  ).length;
  const officeQuickStats = [
    {
      label: 'Default Start',
      value: formatTimeDisplay(globalTimingEntry?.start_time || globalTimingForm.startTime),
      accent: 'from-blue-500 to-indigo-500',
    },
    {
      label: 'Default End',
      value: formatTimeDisplay(globalTimingEntry?.end_time || globalTimingForm.endTime),
      accent: 'from-emerald-500 to-teal-500',
    },
    {
      label: 'Check-in Grace',
      value: `${globalTimingEntry?.check_in_grace_minutes ?? resolveGraceValue(globalTimingForm.checkInGrace)} mins`,
      accent: 'from-orange-500 to-amber-500',
    },
    {
      label: 'Overrides',
      value: configuredDepartmentCount,
      accent: 'from-purple-500 to-pink-500',
    },
  ];

  const handleDepartmentSelect = (value: string) => {
    if (value === '__clear__') {
      setDepartmentTimingForm({
        department: '',
        startTime: globalTimingForm.startTime,
        endTime: globalTimingForm.endTime,
        checkInGrace: globalTimingForm.checkInGrace,
        checkOutGrace: globalTimingForm.checkOutGrace,
      });
      return;
    }

    const target = officeTimings.find(
      (entry) =>
        entry.department &&
        entry.department.trim().toLowerCase() === value.trim().toLowerCase(),
    );

    if (target) {
      handleDepartmentTimingEdit(target);
    } else {
      setDepartmentTimingForm((prev) => ({
        ...prev,
        department: value,
      }));
    }
  };

  const attendanceContent = (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800 rounded-2xl p-6 shadow-sm border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
              <Clock className="h-7 w-7 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold">Employee Attendance</h2>
              <p className="text-sm text-muted-foreground mt-1">Monitor team attendance and export reports</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button 
              onClick={exportToCSV} 
              variant="outline" 
              className="gap-2 hover:bg-white dark:hover:bg-gray-800"
              disabled={isExporting}
            >
              <Download className="h-4 w-4" />
              {isExporting ? 'Exporting...' : 'Export CSV'}
            </Button>
            <Button 
              onClick={exportToPDF} 
              variant="outline" 
              className="gap-2 hover:bg-white dark:hover:bg-gray-800"
              disabled={isExporting}
            >
              <Download className="h-4 w-4" />
              {isExporting ? 'Exporting...' : 'Export PDF'}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-0 bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-blue-50">Total Employees</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{todayStats.total}</div>
          </CardContent>
        </Card>
        <Card className="border-0 bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-green-50">Present Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{todayStats.present}</div>
          </CardContent>
        </Card>
        <Card className="border-0 bg-gradient-to-br from-orange-500 to-amber-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-orange-50">Late Arrivals</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{todayStats.late}</div>
          </CardContent>
        </Card>
        <Card className="border-0 bg-gradient-to-br from-yellow-500 to-amber-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-yellow-50">Early Departures</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{todayStats.early}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-0 shadow-lg">
        <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
          <CardTitle className="text-xl font-semibold">Attendance Records</CardTitle>
          <CardDescription>View and manage employee attendance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-3 mb-6">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name, email, employee ID, or department..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 h-11 bg-white dark:bg-gray-950 border-gray-200 dark:border-gray-800 focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[200px] h-11 bg-white dark:bg-gray-950">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="present">On Schedule</SelectItem>
                <SelectItem value="late">Late Arrivals</SelectItem>
                <SelectItem value="early">Early Departures</SelectItem>
              </SelectContent>
            </Select>
            <DatePicker
              date={selectedDate}
              onDateChange={(date) => {
                if (date) {
                  setSelectedDate(date);
                  const formatted = format(date, 'yyyy-MM-dd');
                  setFilterDate(formatted);
                  loadAllAttendance(formatted);
                }
              }}
              placeholder="Select date"
              className="w-[200px]"
            />
          </div>

          <div className="rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
                  <tr className="hover:bg-transparent">
                    <th className="text-left p-3 font-medium">Employee</th>
                    <th className="text-left p-3 font-medium">Employee ID</th>
                    <th className="text-left p-3 font-medium">Department</th>
                    <th className="text-left p-3 font-medium">Check In</th>
                    <th className="text-left p-3 font-medium">Check Out</th>
                    <th className="text-left p-3 font-medium">Hours</th>
                    <th className="text-left p-3 font-medium">Location</th>
                    <th className="text-left p-3 font-medium">Selfie</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Work Summary</th>
                    <th className="text-left p-3 font-medium">Work Report</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.length > 0 ? (
                    filteredRecords.map((record) => (
                      <tr key={record.id} className="border-t hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                        <td className="p-3">
                          <div>
                            <p className="font-medium">{record.userName}</p>
                            <p className="text-sm text-muted-foreground">{record.userEmail}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <div>
                            <p className="font-medium text-sm">{record.employeeId || record.userId || 'N/A'}</p>
                            <p className="text-xs text-muted-foreground">ID: {record.userId}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <Badge variant="outline">{record.department}</Badge>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-green-500" />
                            <span>{formatIST(record.date, record.checkInTime)}</span>
                          </div>
                          {record.scheduledStart && (
                            <div className="text-xs text-muted-foreground">
                              Scheduled: {record.scheduledStart}
                            </div>
                          )}
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-red-500" />
                            <span>{formatIST(record.date, record.checkOutTime)}</span>
                          </div>
                          {record.scheduledEnd && (
                            <div className="text-xs text-muted-foreground">
                              Scheduled: {record.scheduledEnd}
                            </div>
                          )}
                        </td>
                        <td className="p-3">
                          {record.workHours ? (
                            <Badge variant="secondary">{record.workHours}h</Badge>
                          ) : '-'}
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <MapPin className="h-3 w-3" />
                            <span>{record.checkInLocation?.address ?? '-'}</span>
                          </div>
                        </td>
                        <td className="p-3">
                          <div 
                            className="h-10 w-10 rounded-full overflow-hidden border-2 border-gray-200 dark:border-gray-700 cursor-pointer hover:opacity-80 transition-opacity"
                            onClick={() => {
                              setSelectedRecord(record);
                              setShowSelfieModal(true);
                            }}
                          >
                            {record.checkInSelfie ? (
                              <img 
                                src={record.checkInSelfie} 
                                alt={`${record.userName}'s selfie`} 
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  const target = e.currentTarget as HTMLImageElement;
                                  target.style.display = 'none';
                                  // Create fallback div
                                  const fallback = document.createElement('div');
                                  fallback.className = 'w-full h-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center';
                                  fallback.innerHTML = '<svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>';
                                  target.parentNode?.appendChild(fallback);
                                }}
                              />
                            ) : null}
                            {!record.checkInSelfie && (
                              <div className="w-full h-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                <User className="h-5 w-5 text-gray-400" />
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="p-3">
                          <div className="flex flex-wrap gap-1">
                            {getStatusBadge(record)}
                          </div>
                        </td>
                        <td className="p-3 text-sm text-muted-foreground max-w-[200px]">
                          {record.workSummary ? (
                            <button
                              type="button"
                              className="text-left truncate max-w-[180px] hover:text-blue-600"
                              onClick={() => setSummaryModal({ open: true, summary: record.workSummary || '' })}
                            >
                              {record.workSummary.length > 40
                                ? `${record.workSummary.slice(0, 40)}…`
                                : record.workSummary}
                            </button>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="p-3">
                          {record.workReport ? (
                            <a
                              href={record.workReport}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-blue-600 hover:underline"
                            >
                              View Report
                            </a>
                          ) : (
                            <span className="text-muted-foreground text-sm">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={9} className="p-8 text-center text-muted-foreground">
                        <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>No attendance records found for the selected date</p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showSelfieModal} onOpenChange={setShowSelfieModal}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              {selectedRecord?.userName}'s Attendance
            </DialogTitle>
          </DialogHeader>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 py-4">
            {/* Check-in Selfie */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-green-500"></div>
                <h3 className="font-medium">Check-in Selfie</h3>
              </div>
              <div className="relative aspect-[3/4] bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
                {selectedRecord?.checkInSelfie ? (
                  <img 
                    src={selectedRecord.checkInSelfie} 
                    alt="Check-in selfie" 
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      const target = e.currentTarget as HTMLImageElement;
                      target.style.display = 'none';
                      // Create fallback div
                      const fallback = document.createElement('div');
                      fallback.className = 'w-full h-full flex flex-col items-center justify-center text-gray-400';
                      fallback.innerHTML = '<svg class="h-12 w-12 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg><p>No selfie available</p>';
                      target.parentNode?.appendChild(fallback);
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                    <User className="h-12 w-12 mb-2" />
                    <p>No selfie available</p>
                  </div>
                )}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4 text-white">
                  <p className="font-medium">Check-in: {selectedRecord?.checkInTime ? format(new Date(selectedRecord.checkInTime), 'hh:mm a') : 'N/A'}</p>
                  <p className="text-sm opacity-80">{selectedRecord?.checkInLocation?.address || 'Location not available'}</p>
                </div>
              </div>
            </div>

            {/* Check-out Selfie */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500"></div>
                <h3 className="font-medium">Check-out Selfie</h3>
              </div>
              <div className="relative aspect-[3/4] bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
                {selectedRecord?.checkOutSelfie ? (
                  <img 
                    src={selectedRecord.checkOutSelfie} 
                    alt="Check-out selfie" 
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      const target = e.currentTarget as HTMLImageElement;
                      target.style.display = 'none';
                      // Create fallback div
                      const fallback = document.createElement('div');
                      fallback.className = 'w-full h-full flex flex-col items-center justify-center text-gray-400';
                      fallback.innerHTML = '<svg class="h-12 w-12 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg><p>No check-out selfie</p><p class="text-sm">Not checked out yet</p>';
                      target.parentNode?.appendChild(fallback);
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                    <User className="h-12 w-12 mb-2" />
                    <p>No check-out selfie</p>
                    <p className="text-sm">Not checked out yet</p>
                  </div>
                )}
                {selectedRecord?.checkOutTime && (
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4 text-white">
                    <p className="font-medium">Check-out: {format(new Date(selectedRecord.checkOutTime), 'hh:mm a')}</p>
                    <p className="text-sm opacity-80">{selectedRecord.checkOutLocation?.address || 'Location not available'}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setShowSelfieModal(false)}
              className="gap-2"
            >
              <X className="h-4 w-4" />
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={summaryModal.open}
        onOpenChange={(open) => setSummaryModal({ open, summary: open ? summaryModal.summary : null })}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Work Summary</DialogTitle>
            <DialogDescription>Detail submitted during check-out.</DialogDescription>
          </DialogHeader>
          <div className="py-4 text-sm text-muted-foreground whitespace-pre-wrap">
            {summaryModal.summary || 'No summary provided.'}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSummaryModal({ open: false, summary: null })}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Export Modal */}
      <Dialog open={exportModalOpen} onOpenChange={setExportModalOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Export Attendance Report ({exportType?.toUpperCase()})</DialogTitle>
            <DialogDescription>
              Configure your export preferences. Select date range and employee filter options.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-6 py-4 flex-1 overflow-y-auto pr-1">
            {/* Quick Filter Dropdown */}
            <div className="space-y-2">
              <Label htmlFor="quick-filter">Quick Filter</Label>
              <Select value={quickFilter} onValueChange={handleQuickFilter}>
                <SelectTrigger id="quick-filter">
                  <SelectValue placeholder="Select time period" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="last_month">Last Month</SelectItem>
                  <SelectItem value="last_3_months">Last 3 Months</SelectItem>
                  <SelectItem value="last_6_months">Last 6 Months</SelectItem>
                  <SelectItem value="custom">Custom Date Range</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Date Range Selection */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start-date">Start Date</Label>
                <DatePicker
                  date={startDate}
                  onDateChange={setStartDate}
                  placeholder="Select start date"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end-date">End Date</Label>
                <DatePicker
                  date={endDate}
                  onDateChange={setEndDate}
                  placeholder="Select end date"
                />
              </div>
            </div>

            {/* Employee Filter */}
            <div className="space-y-2">
              <Label>Employee Filter</Label>
              <div className="flex gap-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="all-employees"
                    name="employee-filter"
                    checked={employeeFilter === 'all'}
                    onChange={() => {
                      setEmployeeFilter('all');
                      setSelectedEmployee(null);
                      setEmployeeSearch('');
                    setSelectedDepartmentFilter('');
                    setFilteredEmployees([]);
                    }}
                    className="h-4 w-4 text-blue-600"
                  />
                  <Label htmlFor="all-employees" className="cursor-pointer">All Employees</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="specific-employee"
                    name="employee-filter"
                    checked={employeeFilter === 'specific'}
                    onChange={() => {
                      setEmployeeFilter('specific');
                      setSelectedEmployee(null);
                      setSelectedDepartmentFilter('');
                      setEmployeeSearch('');
                      setFilteredEmployees([]);
                    }}
                    className="h-4 w-4 text-blue-600"
                  />
                  <Label htmlFor="specific-employee" className="cursor-pointer">Specific Employee</Label>
                </div>
              </div>
            </div>

            {/* Employee Selection */}
            {employeeFilter === 'specific' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="department-select">Department</Label>
                  <Select
                    value={selectedDepartmentFilter}
                    onValueChange={(value) => {
                      setSelectedDepartmentFilter(value);
                      setSelectedEmployee(null);
                      setEmployeeSearch('');
                    }}
                  >
                    <SelectTrigger id="department-select">
                      <SelectValue placeholder="Select department" />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.length ? (
                        departments.map((dept) => (
                          <SelectItem key={dept} value={dept}>
                            {dept}
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="__empty" disabled>
                          No departments available
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                </div>

                {selectedDepartmentFilter ? (
                  <div className="space-y-2">
                    <Label htmlFor="employee-search">Select Employee</Label>
                    <div className="relative">
                      <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="employee-search"
                        placeholder="Search by name or employee ID..."
                        value={employeeSearch}
                        onChange={(e) => setEmployeeSearch(e.target.value)}
                        className="pl-10"
                      />
                    </div>
                    <div className="border rounded-md max-h-40 overflow-y-auto mt-2">
                      {filteredEmployees.length ? (
                        filteredEmployees.map((emp) => {
                          const isSelected = selectedEmployee?.user_id === emp.user_id;
                          return (
                            <button
                              type="button"
                              key={emp.user_id}
                              onClick={() => setSelectedEmployee(emp)}
                              className={`w-full text-left p-3 border-b last:border-b-0 transition-colors ${
                                isSelected
                                  ? 'bg-blue-50 dark:bg-blue-900'
                                  : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                              }`}
                            >
                              <div className="font-medium">{emp.name}</div>
                              <div className="text-sm text-muted-foreground">
                                {emp.employee_id ? `ID: ${emp.employee_id}` : 'User ID: ' + emp.user_id}
                              </div>
                            </button>
                          );
                        })
                      ) : (
                        <div className="p-3 text-sm text-muted-foreground">
                          No employees found for this department.
                        </div>
                      )}
                    </div>
                    {selectedEmployee && (
                      <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900 rounded-md flex items-center justify-between">
                        <div>
                          <div className="font-medium">{selectedEmployee.name}</div>
                          {selectedEmployee.employee_id && (
                            <div className="text-sm text-muted-foreground">ID: {selectedEmployee.employee_id}</div>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedEmployee(null);
                            setEmployeeSearch('');
                          }}
                        >
                          Clear
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Select a department to view its employees.
                  </p>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setExportModalOpen(false);
                setExportType(null);
              }}
              disabled={isExporting}
            >
              Cancel
            </Button>
            <Button
              onClick={performExport}
              disabled={isExporting || (!startDate && !endDate) || (employeeFilter === 'specific' && !selectedEmployee)}
            >
              {isExporting ? 'Exporting...' : `Export ${exportType?.toUpperCase()}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );

  const officeHoursContent = (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white rounded-3xl p-6 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-2xl bg-white/15 flex items-center justify-center shadow-lg">
              <Clock className="h-8 w-8" />
            </div>
            <div>
              <p className="text-sm uppercase tracking-widest text-white/70">Scheduling Hub</p>
              <h2 className="text-3xl font-bold">Office Hours Control Center</h2>
              <p className="text-white/80 mt-1">
                Define global timings, override specific departments, and keep every team aligned.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Badge variant="secondary" className="bg-white/20 text-white border-white/30">
              {configuredDepartmentCount} Department Override{configuredDepartmentCount === 1 ? '' : 's'}
            </Badge>
            <Badge variant="secondary" className="bg-white/20 text-white border-white/30">
              {officeTimings.length} Total Rule{officeTimings.length === 1 ? '' : 's'}
            </Badge>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-6">
          {officeQuickStats.map((stat) => (
            <div
              key={stat.label}
              className={`rounded-2xl bg-gradient-to-br ${stat.accent} p-4 shadow-lg`}
            >
              <p className="text-sm text-white/70">{stat.label}</p>
              <p className="text-2xl font-semibold mt-1">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="shadow-xl border border-blue-100 dark:border-slate-800">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl font-semibold">Global Office Hours</CardTitle>
            <CardDescription>
              Default schedule applied to every department unless specifically overridden.
            </CardDescription>
        </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
                <Label htmlFor="global-start" className="text-sm font-medium text-blue-600">
                  Start Time
                </Label>
              <Input
                id="global-start"
                type="time"
                value={globalTimingForm.startTime}
                  onChange={(e) =>
                    setGlobalTimingForm((prev) => ({ ...prev, startTime: e.target.value }))
                  }
                  className="h-12 border-2 border-blue-100 focus:border-blue-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="global-end" className="text-sm font-medium text-blue-600">
                  End Time
                </Label>
              <Input
                id="global-end"
                type="time"
                value={globalTimingForm.endTime}
                  onChange={(e) =>
                    setGlobalTimingForm((prev) => ({ ...prev, endTime: e.target.value }))
                  }
                  className="h-12 border-2 border-blue-100 focus:border-blue-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="global-grace-in" className="text-sm font-medium text-blue-600">
                  Check-in Grace (minutes)
                </Label>
              <Input
                id="global-grace-in"
                type="number"
                min={0}
                max={180}
                value={globalTimingForm.checkInGrace}
                onChange={(e) =>
                  setGlobalTimingForm((prev) => ({
                    ...prev,
                    checkInGrace: e.target.value === '' ? '' : Number(e.target.value),
                  }))
                }
                className="h-12 border-2 border-blue-100 focus:border-blue-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="global-grace-out" className="text-sm font-medium text-blue-600">
                  Check-out Grace (minutes)
                </Label>
              <Input
                id="global-grace-out"
                type="number"
                min={0}
                max={180}
                value={globalTimingForm.checkOutGrace}
                onChange={(e) =>
                  setGlobalTimingForm((prev) => ({
                    ...prev,
                    checkOutGrace: e.target.value === '' ? '' : Number(e.target.value),
                  }))
                }
                className="h-12 border-2 border-blue-100 focus:border-blue-400"
              />
            </div>
          </div>
            <div className="flex flex-wrap justify-end gap-3">
              <Button
                variant="outline"
                className="border-2 border-blue-200 text-blue-600 hover:bg-blue-50 dark:text-blue-300"
                onClick={() => loadOfficeTimings()}
                disabled={officeFormLoading}
              >
                Refresh
              </Button>
              <Button
                onClick={handleGlobalTimingSave}
                disabled={officeFormLoading}
                className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-md"
              >
              {officeFormLoading ? 'Saving...' : 'Save Global Settings'}
            </Button>
          </div>
        </CardContent>
      </Card>

        <Card className="shadow-xl border border-purple-100 dark:border-slate-800">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl font-semibold">Department Overrides</CardTitle>
            <CardDescription>
              Override the global schedule for particular departments or create new ones.
            </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium text-purple-600">Department</Label>
              {departments.length > 0 && (
                <Select
                  value={
                    departmentTimingForm.department &&
                    departments.some(
                      (dept) =>
                        dept.trim().toLowerCase() ===
                        departmentTimingForm.department?.trim().toLowerCase(),
                    )
                      ? departmentTimingForm.department
                      : '__custom__'
                  }
                  onValueChange={(value) => {
                    if (value === '__custom__') return;
                    handleDepartmentSelect(value);
                  }}
                >
                  <SelectTrigger className="h-12 border-2 border-purple-100 focus:border-purple-400">
                    <SelectValue placeholder="Select department to edit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__custom__">Custom / New Department</SelectItem>
                    {departments.map((dept) => (
                      <SelectItem key={dept} value={dept}>
                        {dept}
                      </SelectItem>
                    ))}
                    <SelectItem value="__clear__" className="text-red-500">
                      Clear Selection
                    </SelectItem>
                  </SelectContent>
                </Select>
              )}
            <Input
              id="department-name"
              placeholder="e.g., Engineering"
              value={departmentTimingForm.department}
                onChange={(e) =>
                  setDepartmentTimingForm((prev) => ({ ...prev, department: e.target.value }))
                }
                className="h-12 border-2 border-purple-100 focus:border-purple-400"
            />
            {departments.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {departments.map((dept) => {
                    const isSelected =
                      dept.trim().toLowerCase() ===
                      departmentTimingForm.department?.trim().toLowerCase();
                    return (
                      <button
                    key={dept}
                    type="button"
                        onClick={() => handleDepartmentSelect(dept)}
                        className={`px-3 py-1.5 rounded-full text-sm transition-all ${
                          isSelected
                            ? 'bg-purple-600 text-white shadow-lg'
                            : 'bg-purple-50 text-purple-700 hover:bg-purple-100'
                        }`}
                  >
                    {dept}
                      </button>
                    );
                  })}
              </div>
            )}
          </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
                <Label htmlFor="dept-start" className="text-sm font-medium text-purple-600">
                  Start Time
                </Label>
              <Input
                id="dept-start"
                type="time"
                value={departmentTimingForm.startTime}
                  onChange={(e) =>
                    setDepartmentTimingForm((prev) => ({ ...prev, startTime: e.target.value }))
                  }
                  className="h-12 border-2 border-purple-100 focus:border-purple-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="dept-end" className="text-sm font-medium text-purple-600">
                  End Time
                </Label>
              <Input
                id="dept-end"
                type="time"
                value={departmentTimingForm.endTime}
                  onChange={(e) =>
                    setDepartmentTimingForm((prev) => ({ ...prev, endTime: e.target.value }))
                  }
                  className="h-12 border-2 border-purple-100 focus:border-purple-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="dept-grace-in" className="text-sm font-medium text-purple-600">
                  Check-in Grace (minutes)
                </Label>
              <Input
                id="dept-grace-in"
                type="number"
                min={0}
                max={180}
                value={departmentTimingForm.checkInGrace}
                onChange={(e) =>
                  setDepartmentTimingForm((prev) => ({
                    ...prev,
                    checkInGrace: e.target.value === '' ? '' : Number(e.target.value),
                  }))
                }
                className="h-12 border-2 border-purple-100 focus:border-purple-400"
              />
            </div>
            <div className="space-y-2">
                <Label htmlFor="dept-grace-out" className="text-sm font-medium text-purple-600">
                  Check-out Grace (minutes)
                </Label>
              <Input
                id="dept-grace-out"
                type="number"
                min={0}
                max={180}
                value={departmentTimingForm.checkOutGrace}
                onChange={(e) =>
                  setDepartmentTimingForm((prev) => ({
                    ...prev,
                    checkOutGrace: e.target.value === '' ? '' : Number(e.target.value),
                  }))
                }
                className="h-12 border-2 border-purple-100 focus:border-purple-400"
              />
            </div>
          </div>

            <div className="flex flex-wrap justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setDepartmentTimingForm({
                  department: '',
                  startTime: globalTimingForm.startTime,
                  endTime: globalTimingForm.endTime,
                  checkInGrace: globalTimingForm.checkInGrace,
                  checkOutGrace: globalTimingForm.checkOutGrace,
                })
              }
                className="border-2 border-purple-200 text-purple-600 hover:bg-purple-50 dark:text-purple-300"
            >
              Reset
            </Button>
              <Button
                onClick={handleDepartmentTimingSave}
                disabled={officeFormLoading || !departmentTimingForm.department.trim()}
                className="gap-2 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 shadow-md"
              >
              {officeFormLoading ? 'Saving...' : 'Save Department Timing'}
            </Button>
          </div>
        </CardContent>
      </Card>
      </div>

      <Card className="shadow-xl border border-slate-100 dark:border-slate-800">
        <CardHeader className="space-y-1 pb-4">
          <CardTitle className="text-xl font-semibold">Configured Schedules</CardTitle>
          <CardDescription>
            Overview of current global and department-specific office timings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {officeTimings.length > 0 ? (
            <div className="grid gap-4">
                  {officeTimings.map((timing) => {
                    const isGlobalTiming = !timing.department;
                    return (
                  <div
                    key={timing.id}
                    className="group border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-gradient-to-r from-white to-slate-50 dark:from-slate-900 dark:to-slate-950 shadow-sm hover:shadow-lg transition-shadow"
                  >
                    <div>
                      <p className="text-sm uppercase tracking-wider text-slate-500">
                        {isGlobalTiming ? 'Global Schedule' : 'Department'}
                      </p>
                      <h3 className="text-xl font-semibold">
                          {isGlobalTiming ? 'All Departments' : timing.department}
                      </h3>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <Badge variant="secondary" className="bg-blue-50 text-blue-700">
                          Start: {formatTimeDisplay(timing.start_time)}
                        </Badge>
                        <Badge variant="secondary" className="bg-green-50 text-green-700">
                          End: {formatTimeDisplay(timing.end_time)}
                        </Badge>
                        <Badge variant="secondary" className="bg-amber-50 text-amber-700">
                          Grace In: {timing.check_in_grace_minutes}m
                        </Badge>
                        <Badge variant="secondary" className="bg-rose-50 text-rose-700">
                          Grace Out: {timing.check_out_grace_minutes}m
                        </Badge>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                        className="border-2 border-blue-200 text-blue-600 hover:bg-blue-50 dark:text-blue-300"
                            onClick={() => handleDepartmentTimingEdit(timing)}
                          >
                            Edit
                          </Button>
                          {!isGlobalTiming && (
                            <Button
                              size="sm"
                              variant="ghost"
                          className="text-destructive hover:bg-red-50"
                              onClick={() => handleDepartmentTimingDelete(timing)}
                              disabled={officeFormLoading}
                            >
                              Remove
                            </Button>
                          )}
                    </div>
                  </div>
                    );
                  })}
            </div>
          ) : (
            <div className="p-10 text-center">
              <Clock className="h-12 w-12 mx-auto text-slate-300 mb-3" />
              <p className="text-lg font-medium">No office timings configured yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Start by adding a global schedule, then override specific departments as needed.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="space-y-6">
      {isAdmin ? (
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as 'attendance' | 'office-hours')}
          className="space-y-6"
        >
          <TabsList className="flex w-full md:w-auto">
            <TabsTrigger value="attendance" className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Attendance
            </TabsTrigger>
            <TabsTrigger value="office-hours" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Office Hours
            </TabsTrigger>
          </TabsList>
          <TabsContent value="attendance" className="space-y-6">
            {attendanceContent}
          </TabsContent>
          <TabsContent value="office-hours" className="space-y-6">
            {officeHoursContent}
          </TabsContent>
        </Tabs>
      ) : (
        attendanceContent
      )}
    </div>
  );
};

export default AttendanceManager;