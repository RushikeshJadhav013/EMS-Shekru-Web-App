import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

type Holiday = {
  date: Date;
  name: string;
};
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Calendar } from '@/components/ui/calendar';
import { DatePicker } from '@/components/ui/date-picker';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { addDays, isSameDay } from 'date-fns';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/hooks/use-toast';
import { format } from 'date-fns';
import { useAuth } from '@/contexts/AuthContext';
import { apiService } from '@/lib/api';
import { 
  CalendarDays, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Calendar as CalendarIcon,
  User,
  FileText,
  Timer,
  Pencil,
  Trash2
} from 'lucide-react';

interface LeaveRequest {
  id: string;
  employeeId: string;
  employeeName: string;
  department: string;
  type: 'annual' | 'sick' | 'casual' | 'maternity' | 'paternity' | 'unpaid';
  startDate: Date;
  endDate: Date;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  approvedBy?: string;
  comments?: string;
  requestDate: Date;
}

export default function LeaveManagement() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());
  
  // Initialize leave requests from localStorage or use default mock data
  const initializeLeaveRequests = (): LeaveRequest[] => {
    const stored = localStorage.getItem('leaveRequests');
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as LeaveRequest[];
        // Convert date strings back to Date objects
        return parsed.map((req) => ({
          ...req,
          startDate: new Date(req.startDate),
          endDate: new Date(req.endDate),
          requestDate: new Date(req.requestDate)
        }));
      } catch (error) {
        console.error('Error parsing leave requests:', error);
      }
    }
    // Default mock data
    return [
      {
        id: '1',
        employeeId: 'EMP001',
        employeeName: 'John Doe',
        department: 'Engineering',
        type: 'annual',
        startDate: new Date(2024, 0, 15),
        endDate: new Date(2024, 0, 17),
        reason: 'Family vacation',
        status: 'pending',
        requestDate: new Date(2024, 0, 10)
      },
      {
        id: '2',
        employeeId: 'EMP002',
        employeeName: 'Jane Smith',
        department: 'Marketing',
        type: 'sick',
        startDate: new Date(2024, 0, 20),
        endDate: new Date(2024, 0, 21),
        reason: 'Medical appointment',
        status: 'approved',
        approvedBy: 'Manager',
        requestDate: new Date(2024, 0, 18)
      }
    ];
  };
  
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>(initializeLeaveRequests());
  const loadStoredHolidays = () => {
    const stored = localStorage.getItem('companyHolidays');
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as { date: string; name: string }[];
        return parsed.map((h) => ({ date: new Date(h.date), name: h.name }));
      } catch (error) {
        console.error('Failed to parse stored holidays:', error);
      }
    }
    return [
      { date: new Date(2025, 0, 1), name: 'New Year' },
      { date: new Date(2025, 1, 26), name: 'Republic Day' },
    ];
  };
  const [approvalRequests, setApprovalRequests] = useState<LeaveRequest[]>([]);
  const [approvalHistory, setApprovalHistory] = useState<LeaveRequest[]>([]);

  const [formData, setFormData] = useState({
    type: 'annual',
    startDate: new Date(),
    endDate: new Date(),
    reason: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [approvingLeaveId, setApprovingLeaveId] = useState<string | null>(null);
  const [leaveHistoryPeriod, setLeaveHistoryPeriod] = useState<string>('current_month');
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingLeave, setEditingLeave] = useState<LeaveRequest | null>(null);
  const [editFormData, setEditFormData] = useState({
    startDate: new Date(),
    endDate: new Date(),
    reason: ''
  });
  const [isUpdatingLeave, setIsUpdatingLeave] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [leaveToDelete, setLeaveToDelete] = useState<LeaveRequest | null>(null);
  const [isDeletingLeave, setIsDeletingLeave] = useState(false);

  // Company holidays state
  const [holidays, setHolidays] = useState<Holiday[]>(loadStoredHolidays());

  const [holidayForm, setHolidayForm] = useState<{ date: Date; name: string }>({ date: new Date(), name: '' });

  const handleAddHoliday = () => {
    if (!holidayForm.name) return;
    setHolidays([...holidays, { date: holidayForm.date, name: holidayForm.name }]);
    setHolidayForm({ date: new Date(), name: '' });
    toast({ title: 'Holiday added', description: 'Company holiday added to calendar.' });
  };

  const handleRemoveHoliday = (date: Date) => {
    setHolidays(holidays.filter(h => !isSameDay(h.date, date)));
    toast({ title: 'Holiday removed', description: 'Company holiday removed from calendar.' });
  };

  const handleSaveWeekOff = () => {
    const department = weekOffForm.department.trim();
    if (!department) {
      toast({
        title: 'Department required',
        description: 'Please enter or pick a department before saving the week-off.',
        variant: 'destructive',
      });
      return;
    }
    if (weekOffForm.days.length === 0) {
      toast({
        title: 'Pick at least one day',
        description: 'Select one or more days to mark as weekly off.',
        variant: 'destructive',
      });
      return;
    }
    const uniqueDays = Array.from(new Set(weekOffForm.days));
    setWeekOffConfig((prev) => ({
      ...prev,
      [department]: uniqueDays,
    }));
    toast({
      title: 'Week-off saved',
      description: `${department} will now have days off on ${uniqueDays
        .map((day) => weekDayLabels[day] || day)
        .join(', ')}.`,
    });
  };

  const handleRemoveWeekOff = (department: string) => {
    setWeekOffConfig((prev) => {
      const updated = { ...prev };
      delete updated[department];
      return updated;
    });
    toast({
      title: 'Week-off removed',
      description: `${department} no longer has a dedicated weekly off set.`,
    });
  };

  const loadStoredWeekOffs = () => {
    const stored = localStorage.getItem('departmentWeekOffs');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed && typeof parsed === 'object') {
          return parsed as Record<string, string[]>;
        }
      } catch (error) {
        console.error('Failed to parse week-off rules:', error);
      }
    }
    return {};
  };

  const [weekOffConfig, setWeekOffConfig] = useState<Record<string, string[]>>(loadStoredWeekOffs);
  const [companyDepartments, setCompanyDepartments] = useState<string[]>([]);
  const [weekOffForm, setWeekOffForm] = useState<{ department: string; days: string[] }>({
    department: '',
    days: ['saturday'],
  });

  useEffect(() => {
    localStorage.setItem('departmentWeekOffs', JSON.stringify(weekOffConfig));
  }, [weekOffConfig]);

  const [leaveBalance, setLeaveBalance] = useState({
    annual: { allocated: 15, used: 0, remaining: 15 },
    sick: { allocated: 10, used: 0, remaining: 10 },
    casual: { allocated: 5, used: 0, remaining: 5 },
  });

  const weekDayOptions = [
    { value: 'sunday', label: 'Sunday', emoji: '☀️' },
    { value: 'monday', label: 'Monday', emoji: '🌤️' },
    { value: 'tuesday', label: 'Tuesday', emoji: '🌥️' },
    { value: 'wednesday', label: 'Wednesday', emoji: '⛅' },
    { value: 'thursday', label: 'Thursday', emoji: '🌦️' },
    { value: 'friday', label: 'Friday', emoji: '🌈' },
    { value: 'saturday', label: 'Saturday', emoji: '💫' },
  ];

  const weekDayLabels = weekDayOptions.reduce<Record<string, string>>((acc, day) => {
    acc[day.value] = `${day.label}`;
    return acc;
  }, {});

  const weekDayIndexMap: Record<string, number> = {
    sunday: 0,
    monday: 1,
    tuesday: 2,
    wednesday: 3,
    thursday: 4,
    friday: 5,
    saturday: 6,
  };

  const departmentOptions = useMemo(() => {
    const deptSet = new Set<string>();
    companyDepartments.forEach((dept) => dept && deptSet.add(dept));
    leaveRequests.forEach((req) => req.department && deptSet.add(req.department));
    approvalRequests.forEach((req) => req.department && deptSet.add(req.department));
    if (user?.department) {
      deptSet.add(user.department);
    }
    Object.keys(weekOffConfig).forEach((dept) => dept && deptSet.add(dept));
    return Array.from(deptSet).filter(Boolean).sort((a, b) => a.localeCompare(b));
  }, [companyDepartments, leaveRequests, approvalRequests, user?.department, weekOffConfig]);

  useEffect(() => {
    if (!weekOffForm.department && departmentOptions.length > 0) {
      setWeekOffForm((prev) => ({ ...prev, department: departmentOptions[0] }));
    }
  }, [departmentOptions, weekOffForm.department]);

  useEffect(() => {
    if (!weekOffForm.department) {
      return;
    }
    const existing = weekOffConfig[weekOffForm.department];
    if (existing) {
      const sameLength = existing.length === weekOffForm.days.length;
      const sameValues = sameLength && existing.every((day) => weekOffForm.days.includes(day));
      if (!sameValues) {
        setWeekOffForm((prev) => ({
          ...prev,
          days: existing,
        }));
      }
    } else if (weekOffForm.days.length === 0) {
      setWeekOffForm((prev) => ({ ...prev, days: ['saturday'] }));
    }
  }, [weekOffForm.department, weekOffForm.days.length, weekOffConfig]);

  const userWeekOffDays = useMemo(() => {
    if (!user?.department) return [];
    return weekOffConfig[user.department] || [];
  }, [user?.department, weekOffConfig]);

  const canApproveLeaves = ['admin', 'hr', 'manager'].includes(user?.role || '');
  const canViewTeamLeaves = ['team_lead'].includes(user?.role || '');
  // Admins should not have an option to apply for leave from the admin dashboard
  const canApply = user?.role !== 'admin';

  // determine default tab based on available tabs for the current user
  const getDefaultTab = () => {
    return canApply
      ? 'request'
      : (canApproveLeaves || canViewTeamLeaves) ? 'approvals' : 'calendar';
  };

  const [activeTab, setActiveTab] = useState(getDefaultTab());

  // Save leave requests to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('leaveRequests', JSON.stringify(leaveRequests));
  }, [leaveRequests]);

  useEffect(() => {
    localStorage.setItem(
      'companyHolidays',
      JSON.stringify(
        holidays.map((h) => ({
          ...h,
          date: h.date.toISOString(),
        })),
      ),
    );
  }, [holidays]);

  useEffect(() => {
    const loadDepartments = async () => {
      try {
        const response = await apiService.getDepartments();
        if (Array.isArray(response)) {
          const names = response
            .map((dept: any) => dept.name || dept.department || '')
            .filter(Boolean);
          setCompanyDepartments(names);
        }
      } catch (error) {
        console.error('Failed to fetch departments for week-off planner:', error);
      }
    };

    loadDepartments();
  }, []);

  const loadLeaveRequests = useCallback(async (period: string = leaveHistoryPeriod) => {
    if (!user) return;
    try {
      const requests = await apiService.getLeaveRequests(period);
      
      // Convert API response to our local format
      const formattedRequests: LeaveRequest[] = requests.map((req) => {
        const leaveType = (req.leave_type || 'annual').toLowerCase() as LeaveRequest['type'];
        const status = (String(req.status || 'pending').toLowerCase() as LeaveRequest['status']);
        return {
          id: String(req.leave_id),
          employeeId: String(req.user_id),
          employeeName: user?.name || String(req.user_id),
          department: user?.department || '',
          type: leaveType,
          startDate: new Date(req.start_date),
          endDate: new Date(req.end_date),
          reason: req.reason,
          status,
          requestDate: new Date(req.start_date)
        };
      });
      
      setLeaveRequests(formattedRequests);
    } catch (error) {
      console.error('Error fetching leave requests:', error);
      // If API fails, use localStorage data
    }
  }, [leaveHistoryPeriod, user]);

  const loadLeaveBalance = useCallback(async () => {
    if (!user) return;
    try {
      const response = await apiService.getLeaveBalance();
      const defaults = {
        annual: { allocated: 15, used: 0, remaining: 15 },
        sick: { allocated: 10, used: 0, remaining: 10 },
        casual: { allocated: 5, used: 0, remaining: 5 },
      };

      response.balances.forEach((item) => {
        const key = item.leave_type.toLowerCase();
        if (key in defaults) {
          defaults[key as keyof typeof defaults] = {
            allocated: item.allocated,
            used: item.used,
            remaining: item.remaining,
          };
        }
      });

      setLeaveBalance(defaults);
    } catch (error) {
      console.error('Error fetching leave balance:', error);
    }
  }, [user]);

  // Load leave requests from API on component mount and when period changes
  useEffect(() => {
    const fetchLeaveRequests = async () => {
      await loadLeaveRequests(leaveHistoryPeriod);
    };

    const fetchApprovals = async () => {
      try {
        if (!(canApproveLeaves || canViewTeamLeaves)) return;
        const approvals = await apiService.getLeaveApprovals();
        const formatted: LeaveRequest[] = approvals.map((req) => ({
          id: String(req.leave_id),
          employeeId: String(req.user_id),
          employeeName: req.name || req.employee_id,
          department: req.department || '',
          type: (req.leave_type || 'annual').toLowerCase() as LeaveRequest['type'],
          startDate: new Date(req.start_date),
          endDate: new Date(req.end_date),
          reason: req.reason,
          status: (String(req.status || 'pending').toLowerCase() as LeaveRequest['status']),
          requestDate: new Date(req.start_date)
        }));
        setApprovalRequests(formatted);
      } catch (error) {
        console.error('Error fetching approvals:', error);
      }
    };

    const fetchApprovalHistory = async () => {
      try {
        if (!canApproveLeaves) return;
        const history = await apiService.getLeaveApprovalsHistory();
        const formatted: LeaveRequest[] = history.map((req) => ({
          id: String(req.leave_id),
          employeeId: String(req.user_id),
          employeeName: req.name || req.employee_id,
          department: req.department || '',
          type: (req.leave_type || 'annual').toLowerCase() as LeaveRequest['type'],
          startDate: new Date(req.start_date),
          endDate: new Date(req.end_date),
          reason: req.reason,
          status: (String(req.status || 'approved').toLowerCase() as LeaveRequest['status']),
          requestDate: new Date(req.start_date)
        }));
        setApprovalHistory(formatted);
      } catch (error) {
        console.error('Error fetching approvals history:', error);
      }
    };

    if (user) {
      fetchLeaveRequests();
      fetchApprovals();
      fetchApprovalHistory();
      loadLeaveBalance();
    }
  }, [user, leaveHistoryPeriod, loadLeaveRequests, loadLeaveBalance]);

  // Handle URL parameters for tab navigation and leave highlighting
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    const leaveId = searchParams.get('leaveId');
    
    if (tabParam) {
      setActiveTab(tabParam);
    }
    
    // If leaveId is provided, highlight the specific request
    if (leaveId) {
      setTimeout(() => {
        const element = document.getElementById(`leave-request-${leaveId}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          element.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
          setTimeout(() => {
            element.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
          }, 3000);
        }
      }, 300);
    }
  }, [searchParams]);
  // compute visible tabs count and columns class for the TabsList
  const tabsCount = (canApply ? 1 : 0) + ((canApproveLeaves || canViewTeamLeaves) ? 1 : 0) + 1; // calendar always present
  const colsClass = tabsCount === 3 ? 'grid-cols-3' : (tabsCount === 2 ? 'grid-cols-2' : 'grid-cols-1');

  const handleSubmitRequest = async () => {
    if (!user?.id || !formData.reason.trim()) {
      toast({
        title: 'Error',
        description: 'Please fill in all required fields',
        variant: 'destructive'
      });
      return;
    }

    setIsSubmitting(true);

    try {
      // Prepare data for API
      const leaveRequestData = {
        employee_id: String(user.id),
        start_date: format(formData.startDate, 'yyyy-MM-dd'),
        end_date: format(formData.endDate, 'yyyy-MM-dd'),
        reason: formData.reason,
        leave_type: formData.type
      };

      // Submit to API
      const response = await apiService.submitLeaveRequest(leaveRequestData);

      // Create local leave request object for immediate UI update
      const newRequest: LeaveRequest = {
        id: String(response.leave_id),
        employeeId: user.id,
        employeeName: user.name || '',
        department: user.department || '',
        type: formData.type as LeaveRequest['type'],
        startDate: formData.startDate,
        endDate: formData.endDate,
        reason: formData.reason,
        status: 'pending',
        requestDate: new Date()
      };

      // Refresh leave history from API to get the latest data
      try {
        await loadLeaveRequests(leaveHistoryPeriod);
        await loadLeaveBalance();
      } catch (refreshError) {
        console.error('Error refreshing leave requests:', refreshError);
        // Fallback: add to local state if refresh fails
        setLeaveRequests([...leaveRequests, newRequest]);
      }
      
      toast({
        title: 'Success',
        description: 'Leave request submitted successfully'
      });
      
      // Reset form
      setFormData({
        type: 'annual',
        startDate: new Date(),
        endDate: new Date(),
        reason: ''
      });
    } catch (error) {
      console.error('Error submitting leave request:', error);
      toast({
        title: 'Error',
        description: 'Failed to submit leave request. Please try again.',
        variant: 'destructive'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApproveReject = async (id: string, status: 'approved' | 'rejected') => {
    const request = approvalRequests.find(req => req.id === id) || leaveRequests.find(req => req.id === id);
    
    if (!request) {
      toast({
        title: 'Error',
        description: 'Leave request not found',
        variant: 'destructive'
      });
      return;
    }

    // Prevent multiple clicks
    if (approvingLeaveId) {
      return;
    }

    setApprovingLeaveId(id);

    try {
      // Call API to approve/reject
      const approved = status === 'approved';
      await apiService.approveLeaveRequest(id, approved);
      
      // Update approvals list (primary)
      setApprovalRequests(approvalRequests.map(req => 
        req.id === id 
          ? { ...req, status, approvedBy: user?.name }
          : req
      ));

      // Refresh leave history to get updated status
      try {
        await loadLeaveRequests(leaveHistoryPeriod);
        await loadLeaveBalance();
      } catch (refreshError) {
        console.error('Error refreshing leave requests:', refreshError);
        // Fallback: update local state if refresh fails
        setLeaveRequests(leaveRequests.map(req => 
          req.id === id 
            ? { ...req, status, approvedBy: user?.name }
            : req
        ));
      }
      
      toast({
        title: 'Success',
        description: `Leave request ${status} successfully`
      });
    } catch (error) {
      console.error('Error approving/rejecting leave request:', error);
      toast({
        title: 'Error',
        description: `Failed to ${status} leave request. Please try again.`,
        variant: 'destructive'
      });
    } finally {
      setApprovingLeaveId(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved': return 'default';
      case 'rejected': return 'destructive';
      case 'pending': return 'secondary';
      default: return 'outline';
    }
  };

  const getStatusBadgeStyle = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-gradient-to-r from-amber-400 to-yellow-500 hover:from-amber-500 hover:to-yellow-600 text-white border-2 border-amber-300 dark:border-amber-600 shadow-lg shadow-amber-200/50 dark:shadow-amber-900/50';
      case 'approved':
        return 'bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700 text-white border-2 border-emerald-300 dark:border-emerald-600 shadow-lg shadow-emerald-200/50 dark:shadow-emerald-900/50';
      case 'rejected':
        return 'bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white border-2 border-rose-300 dark:border-rose-600 shadow-lg shadow-rose-200/50 dark:shadow-rose-900/50';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  const getLeaveTypeColor = (type: string) => {
    switch (type) {
      case 'annual': return 'bg-blue-100 text-blue-800';
      case 'sick': return 'bg-red-100 text-red-800';
      case 'casual': return 'bg-green-100 text-green-800';
      case 'maternity': return 'bg-purple-100 text-purple-800';
      case 'paternity': return 'bg-indigo-100 text-indigo-800';
      case 'unpaid': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const handleEditLeave = (leave: LeaveRequest) => {
    setEditingLeave(leave);
    setEditFormData({
      startDate: leave.startDate,
      endDate: leave.endDate,
      reason: leave.reason
    });
    setIsEditDialogOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!editingLeave) return;
    if (!editFormData.reason.trim()) {
      toast({
        title: 'Error',
        description: 'Reason is required',
        variant: 'destructive'
      });
      return;
    }

    setIsUpdatingLeave(true);
    try {
      await apiService.updateLeaveRequest(editingLeave.id, {
        start_date: format(editFormData.startDate, 'yyyy-MM-dd'),
        end_date: format(editFormData.endDate, 'yyyy-MM-dd'),
        reason: editFormData.reason,
        leave_type: editingLeave.type
      });
      await loadLeaveRequests(leaveHistoryPeriod);
      await loadLeaveBalance();
      toast({
        title: 'Leave Updated',
        description: 'Your leave request has been updated successfully.'
      });
      setIsEditDialogOpen(false);
      setEditingLeave(null);
    } catch (error) {
      console.error('Error updating leave request:', error);
      toast({
        title: 'Error',
        description: 'Failed to update leave request. Please try again.',
        variant: 'destructive'
      });
    } finally {
      setIsUpdatingLeave(false);
    }
  };

  const handleDeleteLeave = (leave: LeaveRequest) => {
    setLeaveToDelete(leave);
    setIsDeleteDialogOpen(true);
  };

  const confirmDeleteLeave = async () => {
    if (!leaveToDelete) return;
    setIsDeletingLeave(true);
    try {
      await apiService.deleteLeaveRequest(leaveToDelete.id);
      await loadLeaveRequests(leaveHistoryPeriod);
      await loadLeaveBalance();
      toast({
        title: 'Leave Deleted',
        description: 'Your leave request has been deleted.'
      });
      setIsDeleteDialogOpen(false);
      setLeaveToDelete(null);
    } catch (error) {
      console.error('Error deleting leave request:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete leave request. Please try again.',
        variant: 'destructive'
      });
    } finally {
      setIsDeletingLeave(false);
    }
  };

  // Filter requests based on role
  const getFilteredRequests = () => {
    // Admin can see all leave requests
    if (user?.role === 'admin') {
      return leaveRequests;
    } 
    // HR can see all leave requests (except admin requests if any)
    else if (user?.role === 'hr') {
      return leaveRequests.filter(req => req.employeeId !== user?.id);
    } 
    // Manager can see requests from their department or team
    else if (user?.role === 'manager') {
      return leaveRequests.filter(req => 
        req.employeeId !== user?.id && req.department === user?.department
      );
    } 
    // Team lead can see requests from their team
    else if (user?.role === 'team_lead') {
      return leaveRequests.filter(req => 
        req.employeeId !== user?.id && req.department === user?.department
      );
    }
    // Employees see only their own requests
    return leaveRequests.filter(req => req.employeeId === user?.id);
  };


  return (
    <div className="container mx-auto p-4 sm:p-6 space-y-6">
      {/* Modern Header */}
      <div className="bg-gradient-to-r from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800 rounded-2xl p-6 shadow-sm border">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <CalendarDays className="h-7 w-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Leave Management</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage leave requests and view calendar</p>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className={`grid w-full ${colsClass} h-12 bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 border`}>
          {canApply && <TabsTrigger value="request">Apply Leave</TabsTrigger>}
          {(canApproveLeaves || canViewTeamLeaves) && (
            <TabsTrigger value="approvals">
              {canApproveLeaves ? 'Approvals' : 'Team Leaves'}
            </TabsTrigger>
          )}
          <TabsTrigger value="calendar">Leave Calendar</TabsTrigger>
        </TabsList>

        {canApply && (
          <TabsContent value="request" className="space-y-4">
          {/* Leave Balance Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="border-0 bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-blue-50">Annual Leave</p>
                    <p className="text-3xl font-bold mt-1">
                      {leaveBalance.annual.remaining}/{leaveBalance.annual.allocated}
                    </p>
                    <p className="text-xs text-blue-100 mt-1">{leaveBalance.annual.used} used</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <CalendarDays className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-0 bg-gradient-to-br from-red-500 to-rose-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-red-50">Sick Leave</p>
                    <p className="text-3xl font-bold mt-1">
                      {leaveBalance.sick.remaining}/{leaveBalance.sick.allocated}
                    </p>
                    <p className="text-xs text-red-100 mt-1">{leaveBalance.sick.used} used</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <AlertCircle className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-0 bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-green-50">Casual Leave</p>
                    <p className="text-3xl font-bold mt-1">
                      {leaveBalance.casual.remaining}/{leaveBalance.casual.allocated}
                    </p>
                    <p className="text-xs text-green-100 mt-1">{leaveBalance.casual.used} used</p>
                  </div>
                  <div className="h-12 w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <Clock className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Leave Request Form */}
          <Card className="border-0 shadow-lg">
            <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
              <CardTitle className="text-xl font-semibold">Request Leave</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Leave Type</Label>
                  <Select
                    value={formData.type}
                    onValueChange={(value) => setFormData({...formData, type: value})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="annual">Annual Leave</SelectItem>
                      <SelectItem value="sick">Sick Leave</SelectItem>
                      <SelectItem value="casual">Casual Leave</SelectItem>
                      <SelectItem value="maternity">Maternity Leave</SelectItem>
                      <SelectItem value="paternity">Paternity Leave</SelectItem>
                      <SelectItem value="unpaid">Unpaid Leave</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Duration</Label>
                  <div className="flex gap-2">
                    <DatePicker
                      date={formData.startDate}
                      onDateChange={(date) => date && setFormData({...formData, startDate: date})}
                      placeholder="Start date"
                    />
                    <DatePicker
                      date={formData.endDate}
                      onDateChange={(date) => date && setFormData({...formData, endDate: date})}
                      placeholder="End date"
                    />
                  </div>
                </div>
              </div>
              <div>
                <Label>Reason</Label>
                <Textarea
                  value={formData.reason}
                  onChange={(e) => setFormData({...formData, reason: e.target.value})}
                  placeholder="Please provide a reason for your leave request..."
                  rows={3}
                />
              </div>
              <Button 
                onClick={handleSubmitRequest}
                disabled={isSubmitting}
                className="gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 shadow-md"
              >
                <CalendarIcon className="h-4 w-4" />
                {isSubmitting ? 'Submitting...' : 'Submit Request'}
              </Button>
            </CardContent>
          </Card>

          {/* My Leave History - Premium UI */}
          <Card className="border-0 shadow-xl bg-gradient-to-br from-white to-slate-50 dark:from-slate-900 dark:to-slate-800 overflow-hidden">
            <CardHeader className="border-b bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 dark:from-indigo-950 dark:via-purple-950 dark:to-pink-950">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
                    <CalendarDays className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400 bg-clip-text text-transparent">
                      My Leave History
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      Track all your leave requests and their status
                    </p>
                  </div>
                </div>
                <Select
                  value={leaveHistoryPeriod}
                  onValueChange={(value) => setLeaveHistoryPeriod(value)}
                >
                  <SelectTrigger className="w-[200px] bg-white dark:bg-slate-800 border-2 shadow-md hover:shadow-lg transition-all">
                    <SelectValue placeholder="Select period" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="current_month">Current Month</SelectItem>
                    <SelectItem value="last_3_months">Last 3 Months</SelectItem>
                    <SelectItem value="last_6_months">Last 6 Months</SelectItem>
                    <SelectItem value="last_1_year">Last 1 Year</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              {leaveRequests.filter(req => String(req.employeeId) === String(user?.id)).length === 0 ? (
                <div className="text-center py-16">
                  <div className="h-24 w-24 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900 dark:to-purple-900 flex items-center justify-center mx-auto mb-4">
                    <AlertCircle className="h-12 w-12 text-indigo-500 dark:text-indigo-400 opacity-50" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">No Leave History</h3>
                  <p className="text-sm text-muted-foreground">No leave requests found for the selected period.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {leaveRequests.filter(req => String(req.employeeId) === String(user?.id)).map((request) => {
                    const daysCount = Math.ceil((request.endDate.getTime() - request.startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1;
                    const statusConfig = {
                      pending: { 
                        bg: 'bg-amber-50 dark:bg-amber-950', 
                        border: 'border-amber-200 dark:border-amber-800',
                        icon: Clock,
                        iconColor: 'text-amber-600 dark:text-amber-400'
                      },
                      approved: { 
                        bg: 'bg-emerald-50 dark:bg-emerald-950', 
                        border: 'border-emerald-200 dark:border-emerald-800',
                        icon: CheckCircle,
                        iconColor: 'text-emerald-600 dark:text-emerald-400'
                      },
                      rejected: { 
                        bg: 'bg-red-50 dark:bg-red-950', 
                        border: 'border-red-200 dark:border-red-800',
                        icon: XCircle,
                        iconColor: 'text-red-600 dark:text-red-400'
                      }
                    };
                    const config = statusConfig[request.status] || statusConfig.pending;
                    const StatusIcon = config.icon;
                    
                    return (
                      <div 
                        key={request.id} 
                        className={`group relative overflow-hidden rounded-xl border-2 ${config.border} ${config.bg} p-5 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 space-y-3">
                            <div className="flex items-center gap-3 flex-wrap">
                              <div className={`h-10 w-10 rounded-lg ${config.bg} flex items-center justify-center shadow-md`}>
                                <StatusIcon className={`h-5 w-5 ${config.iconColor}`} />
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-3 flex-wrap">
                                  <div className="flex items-center gap-2">
                                    <CalendarIcon className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                                      {format(request.startDate, 'MMM dd, yyyy')}
                                    </span>
                                    <span className="text-gray-400">→</span>
                                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                                      {format(request.endDate, 'MMM dd, yyyy')}
                                    </span>
                                  </div>
                                  <Badge className={`${getLeaveTypeColor(request.type)} font-medium`}>
                                    {request.type}
                                  </Badge>
                                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                                    <Timer className="h-3.5 w-3.5" />
                                    <span>{daysCount} {daysCount === 1 ? 'day' : 'days'}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                            
                            <div className="pl-13">
                              <div className="flex items-start gap-2">
                                <FileText className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                                  {request.reason}
                                </p>
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex flex-col items-end gap-2">
                            {request.status === 'pending' && (
                              <div className="flex items-center gap-2">
                                <Button
                                  size="sm"
                                  className="group gap-2 rounded-xl bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-4 py-2 font-semibold text-white shadow-lg shadow-indigo-200/50 transition-all hover:from-sky-500 hover:via-indigo-500 hover:to-indigo-600 hover:shadow-indigo-300/70 dark:shadow-indigo-900/50"
                                  onClick={() => handleEditLeave(request)}
                                >
                                  <Pencil className="h-4 w-4 transition-transform group-hover:scale-110" />
                                  <span className="hidden sm:inline">Edit</span>
                                </Button>
                                <Button
                                  size="sm"
                                  className="group gap-2 rounded-xl bg-gradient-to-r from-rose-500 via-red-500 to-orange-500 px-4 py-2 font-semibold text-white shadow-lg shadow-rose-200/50 transition-all hover:from-rose-600 hover:via-red-500 hover:to-red-600 hover:shadow-rose-300/70 dark:shadow-rose-900/50"
                                  onClick={() => handleDeleteLeave(request)}
                                >
                                  <Trash2 className="h-4 w-4 transition-transform group-hover:scale-110" />
                                  <span className="hidden sm:inline">Delete</span>
                                </Button>
                              </div>
                            )}
                            <Badge 
                              className={`px-5 py-2 text-sm font-bold capitalize transition-all duration-300 ${getStatusBadgeStyle(request.status)}`}
                            >
                              {request.status}
                            </Badge>
                            {request.approvedBy && (
                              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                <User className="h-3 w-3" />
                                <span>by {request.approvedBy}</span>
                              </div>
                            )}
                          </div>
                        </div>
                        
                        {/* Decorative gradient overlay */}
                        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-indigo-200/20 to-purple-200/20 dark:from-indigo-800/20 dark:to-purple-800/20 rounded-full blur-2xl -z-0" />
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        )}

        <TabsContent value="calendar">
          <Card className="border-0 shadow-lg">
            <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
              <CardTitle className="text-xl font-semibold">Leave Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Admin holiday management UI */}
              {user?.role === 'admin' && (
                <div className="mb-6 space-y-6">
                  <div className="p-4 border rounded-lg bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <CalendarIcon className="h-5 w-5 text-amber-600" />
                      Set Company Holidays
                    </h3>
                    <div className="flex gap-2 items-center mb-2">
                      <DatePicker
                        date={holidayForm.date}
                        onDateChange={(date) => date && setHolidayForm({ ...holidayForm, date })}
                        placeholder="Select holiday date"
                        className="flex-1"
                      />
                      <Input
                        type="text"
                        placeholder="Holiday name"
                        value={holidayForm.name}
                        onChange={e => setHolidayForm({ ...holidayForm, name: e.target.value })}
                      />
                      <Button onClick={handleAddHoliday} className="gap-2 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-700 hover:to-yellow-700">
                        <CalendarIcon className="h-4 w-4" />
                        Add Holiday
                      </Button>
                    </div>
                    <div>
                      <h4 className="font-medium mb-1">Current Holidays:</h4>
                      <ul>
                        {holidays.map(h => (
                          <li key={h.date.toISOString()} className="flex items-center gap-2 mb-1">
                            <span>{h.name} ({h.date.toDateString()})</span>
                            <Button size="sm" variant="destructive" onClick={() => handleRemoveHoliday(h.date)}>Remove</Button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="p-4 border rounded-lg bg-gradient-to-r from-sky-50 to-indigo-50 dark:from-slate-900 dark:to-indigo-950">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold mb-1 flex items-center gap-2">
                          <Clock className="h-5 w-5 text-sky-600" />
                          Department Week-off Planner
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Define weekly off days for each department to keep schedules aligned.
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      <div className="space-y-2">
                        <Label>Department</Label>
                        {departmentOptions.length > 0 ? (
                          <Select
                            value={weekOffForm.department}
                            onValueChange={(value) =>
                              setWeekOffForm((prev) => ({ ...prev, department: value }))
                            }
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select department" />
                            </SelectTrigger>
                            <SelectContent>
                              {departmentOptions.map((dept) => (
                                <SelectItem key={dept} value={dept}>
                                  {dept}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input
                            placeholder="e.g., Engineering"
                            value={weekOffForm.department}
                            onChange={(e) =>
                              setWeekOffForm((prev) => ({ ...prev, department: e.target.value }))
                            }
                          />
                        )}
                      </div>
                      <div className="space-y-2 md:col-span-2">
                        <Label>Weekly Off Days</Label>
                        <div className="flex flex-wrap gap-2">
                          {weekDayOptions.map((day) => {
                            const isSelected = weekOffForm.days.includes(day.value);
                            return (
                              <button
                                key={day.value}
                                type="button"
                                onClick={() =>
                                  setWeekOffForm((prev) => {
                                    const exists = prev.days.includes(day.value);
                                    const nextDays = exists
                                      ? prev.days.filter((d) => d !== day.value)
                                      : prev.days.length >= 2
                                        ? prev.days
                                        : [...prev.days, day.value];
                                    if (!exists && prev.days.length >= 2) {
                                      toast({
                                        title: 'Limit reached',
                                        description: 'You can only select up to two weekly off days.',
                                      });
                                    }
                                    return { ...prev, days: nextDays };
                                  })
                                }
                                className={`rounded-full px-3 py-1 text-sm border transition ${
                                  isSelected
                                    ? 'border-sky-500 bg-white text-sky-600 shadow-sm'
                                    : 'border-slate-300 text-slate-600 hover:bg-white'
                                }`}
                              >
                                {day.emoji} {day.label}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Tip: Select up to two days if the department enjoys a long weekend.
                        </p>
                      </div>
                      <div className="space-y-2 flex flex-col justify-end md:col-span-3">
                        <Button
                          className="rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-700 hover:to-indigo-700 self-start"
                          onClick={handleSaveWeekOff}
                        >
                          Save Week-off
                        </Button>
                      </div>
                    </div>
                    <div className="mt-4">
                      <h4 className="font-medium mb-2">Active Week-off Rules</h4>
                      {Object.keys(weekOffConfig).length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No department-specific week-offs defined yet.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {Object.entries(weekOffConfig).map(([dept, days]) => (
                            <div
                              key={dept}
                              className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-950/60 px-3 py-2 text-sm"
                            >
                              <div>
                                <p className="font-semibold text-slate-800 dark:text-slate-100">
                                  {dept}
                                </p>
                                <p className="text-muted-foreground text-xs">
                                  Weekly off: {days.map((day) => weekDayLabels[day] || day).join(', ')}
                                </p>
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-rose-500 hover:text-rose-600"
                                onClick={() => handleRemoveWeekOff(dept)}
                              >
                                Remove
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
              {/* Calendar with holidays highlighted */}
              <div className="flex justify-center">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={setSelectedDate}
                  className="rounded-xl border-2 shadow-lg p-4 bg-white dark:bg-gray-950"
                  modifiers={{
                    holiday: holidays.map(h => h.date),
                    weekOff: (date) =>
                      userWeekOffDays.some(
                        (day) => weekDayIndexMap[day] === date.getDay(),
                      ),
                  }}
                  modifiersClassNames={{
                    holiday:
                      'bg-gradient-to-br from-amber-400 to-yellow-500 text-white font-bold hover:from-amber-500 hover:to-yellow-600 transition-all duration-300 shadow-md',
                    weekOff:
                      'border border-sky-400 text-sky-600 font-semibold bg-sky-50 hover:bg-sky-100',
                  }}
                  footer={
                  <div className="mt-4 p-4 bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 rounded-lg">
                    <h4 className="font-semibold mb-2 flex items-center gap-2">
                      <CalendarIcon className="h-4 w-4 text-amber-600" />
                      Company Holidays:
                    </h4>
                    <ul className="space-y-1">
                      {holidays.map(h => (
                        <li key={h.date.toISOString()} className="text-sm flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-gradient-to-r from-amber-400 to-yellow-500"></span>
                          <span className="font-medium">{h.name}</span>
                          <span className="text-muted-foreground">({h.date.toDateString()})</span>
                        </li>
                      ))}
                    </ul>
                    {Object.keys(weekOffConfig).length > 0 && (
                      <div className="mt-4">
                        <h4 className="font-semibold mb-2 flex items-center gap-2">
                          <Clock className="h-4 w-4 text-sky-600" />
                          Department Week-offs:
                        </h4>
                        <ul className="space-y-1">
                          {Object.entries(weekOffConfig).map(([dept, days]) => (
                            <li key={`weekoff-${dept}`} className="text-sm flex items-center gap-2">
                              <span className="h-2 w-2 rounded-full bg-sky-400" />
                              <span className="font-medium">{dept}</span>
                              <span className="text-muted-foreground">
                                {days.map((day) => weekDayLabels[day] || day).join(', ')}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                }
                />
              </div>
              {userWeekOffDays.length > 0 && (
                <p className="mt-4 text-sm text-muted-foreground text-center">
                  Your department ({user?.department || 'N/A'}) enjoys weekly off on{' '}
                  <span className="font-medium text-sky-600">
                    {userWeekOffDays.map((day) => weekDayLabels[day] || day).join(', ')}
                  </span>
                  .
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {(canApproveLeaves || canViewTeamLeaves) && (
          <TabsContent value="approvals">
            <Card className="border-0 shadow-lg">
              <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
                <CardTitle className="text-xl font-semibold">
                  {canApproveLeaves ? 'Leave Approval Requests' : 'Team Leave Requests'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {(approvalRequests.length === 0) ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <AlertCircle className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>No leave requests to display</p>
                    </div>
                  ) : (
                    approvalRequests.map((request) => (
                    <div 
                      key={request.id} 
                      id={`leave-request-${request.id}`}
                      className="border rounded-lg p-4 transition-all duration-300 hover:bg-slate-50 dark:hover:bg-slate-900 hover:shadow-md">
                      <div className="flex items-center justify-between">
                        <div className="space-y-2 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <User className="h-4 w-4" />
                            <span className="font-medium">{request.employeeName}</span>
                            <Badge className={getLeaveTypeColor(request.type)}>
                              {request.type}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              ID: {request.employeeId}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
                            <div className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              <span>{request.department}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <CalendarDays className="h-3 w-3" />
                              <span>
                                {format(request.startDate, 'MMM dd')} - {format(request.endDate, 'MMM dd, yyyy')}
                              </span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              <span>
                                {Math.ceil((request.endDate.getTime() - request.startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1} days
                              </span>
                            </div>
                          </div>
                          <div className="text-sm">
                            <span className="font-medium">Reason:</span> {request.reason}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {request.status === 'pending' && canApproveLeaves ? (
                            <>
                              <Button
                                size="sm"
                                className="gap-1 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                                onClick={() => handleApproveReject(request.id, 'approved')}
                                disabled={approvingLeaveId === request.id}
                              >
                                <CheckCircle className="h-4 w-4" />
                                {approvingLeaveId === request.id ? 'Processing...' : 'Approve'}
                              </Button>
                              <Button
                                size="sm"
                                className="gap-1 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700"
                                onClick={() => handleApproveReject(request.id, 'rejected')}
                                disabled={approvingLeaveId === request.id}
                              >
                                <XCircle className="h-4 w-4" />
                                {approvingLeaveId === request.id ? 'Processing...' : 'Reject'}
                              </Button>
                            </>
                          ) : (
                            <Badge className={`px-4 py-1.5 text-sm font-bold capitalize transition-all duration-300 ${getStatusBadgeStyle(request.status)}`}>
                              {request.status.charAt(0).toUpperCase() + request.status.slice(1)}
                            </Badge>
                          )}
                          {request.status !== 'pending' && request.approvedBy && (
                            <span className="text-xs text-muted-foreground">
                              by {request.approvedBy}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )))}
                  <div className="pt-6 border-t mt-6">
                    <h3 className="font-semibold mb-3">Recent Decisions</h3>
                    {approvalHistory.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No recent approvals or rejections.</p>
                    ) : (
                      <div className="space-y-3">
                        {approvalHistory.map((request) => (
                          <div key={`hist-${request.id}`} className="border rounded-lg p-3 flex items-center justify-between">
                            <div className="text-sm">
                              <div className="font-medium">{request.employeeName}</div>
                              <div className="text-muted-foreground">
                                {format(request.startDate, 'MMM dd')} - {format(request.endDate, 'MMM dd, yyyy')} • {request.department}
                              </div>
                            </div>
                            <Badge className={`px-4 py-1.5 text-sm font-bold capitalize transition-all duration-300 ${getStatusBadgeStyle(request.status)}`}>
                              {request.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Edit Leave Dialog */}
      <Dialog
        open={isEditDialogOpen}
        onOpenChange={(open) => {
          setIsEditDialogOpen(open);
          if (!open) {
            setEditingLeave(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Leave Request</DialogTitle>
            <DialogDescription>
              Update your leave dates or reason. Only pending requests can be modified.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Start Date</Label>
                <DatePicker
                  date={editFormData.startDate}
                  onDateChange={(date) => date && setEditFormData(prev => ({ ...prev, startDate: date }))}
                />
              </div>
              <div>
                <Label>End Date</Label>
                <DatePicker
                  date={editFormData.endDate}
                  onDateChange={(date) => date && setEditFormData(prev => ({ ...prev, endDate: date }))}
                />
              </div>
            </div>
            <div>
              <Label>Reason</Label>
              <Textarea
                value={editFormData.reason}
                onChange={(e) => setEditFormData(prev => ({ ...prev, reason: e.target.value }))}
                rows={4}
                placeholder="Update the reason for your leave request..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)} disabled={isUpdatingLeave}>
              Cancel
            </Button>
            <Button onClick={handleEditSubmit} disabled={isUpdatingLeave}>
              {isUpdatingLeave ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Leave Confirmation */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteDialogOpen(open);
          if (!open) {
            setLeaveToDelete(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Leave Request</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete your leave request.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingLeave}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700"
              onClick={confirmDeleteLeave}
              disabled={isDeletingLeave}
            >
              {isDeletingLeave ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}