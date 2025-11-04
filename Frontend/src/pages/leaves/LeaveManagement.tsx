import React, { useState, useEffect } from 'react';
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
import { addDays, isSameDay } from 'date-fns';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/hooks/use-toast';
import { format } from 'date-fns';
import { useAuth } from '@/contexts/AuthContext';
import { useNotifications } from '@/contexts/NotificationContext';
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
  Timer
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
  const { addNotification } = useNotifications();
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

  const [formData, setFormData] = useState({
    type: 'annual',
    startDate: new Date(),
    endDate: new Date(),
    reason: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [approvingLeaveId, setApprovingLeaveId] = useState<string | null>(null);

  // Company holidays state
  const [holidays, setHolidays] = useState<Holiday[]>([
    { date: new Date(2025, 0, 1), name: 'New Year' },
    { date: new Date(2025, 1, 26), name: 'Republic Day' },
    // Add more default holidays here
  ]);

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

  const leaveBalance = {
    annual: 15,
    sick: 10,
    casual: 5,
    used: {
      annual: 3,
      sick: 2,
      casual: 1
    }
  };

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

  // Load leave requests from API on component mount
  useEffect(() => {
    const fetchLeaveRequests = async () => {
      try {
        const requests = await apiService.getLeaveRequests();
        
        // Convert API response to our local format
        const formattedRequests: LeaveRequest[] = requests.map((req) => ({
          id: req.id,
          employeeId: req.employee_id,
          employeeName: req.employee_id, // You might want to fetch employee name separately
          department: '', // Not in API response, might need to fetch
          type: req.leave_type as LeaveRequest['type'],
          startDate: new Date(req.start_date),
          endDate: new Date(req.end_date),
          reason: req.reason,
          status: req.status as LeaveRequest['status'],
          requestDate: new Date(req.created_at)
        }));
        
        setLeaveRequests(formattedRequests);
      } catch (error) {
        console.error('Error fetching leave requests:', error);
        // If API fails, use localStorage data
      }
    };

    if (user) {
      fetchLeaveRequests();
    }
  }, [user]);

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
        employee_id: user.id,
        leave_type: formData.type,
        start_date: format(formData.startDate, 'yyyy-MM-dd'),
        end_date: format(formData.endDate, 'yyyy-MM-dd'),
        reason: formData.reason
      };

      // Submit to API
      const response = await apiService.submitLeaveRequest(leaveRequestData);

      // Create local leave request object for immediate UI update
      const newRequest: LeaveRequest = {
        id: response.id,
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

      // Update local state
      setLeaveRequests([...leaveRequests, newRequest]);
      
      // Send notification to approver based on hierarchy
      const getSuperiorRole = () => {
        switch (user?.role) {
          case 'employee': return 'team_lead';
          case 'team_lead': return 'manager';
          case 'manager': return 'hr';
          case 'hr': return 'admin';
          default: return null;
        }
      };
      
      const superiorRole = getSuperiorRole();
      if (superiorRole) {
        addNotification({
          title: 'New Leave Request',
          message: `${user?.name} has requested ${formData.type} leave from ${format(formData.startDate, 'MMM dd')} to ${format(formData.endDate, 'MMM dd')}`,
          type: 'leave',
          metadata: {
            leaveId: newRequest.id,
            requesterId: user?.id,
            requesterName: user?.name,
          }
        });
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
    const request = leaveRequests.find(req => req.id === id);
    
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
      
      // Update local state
      setLeaveRequests(leaveRequests.map(req => 
        req.id === id 
          ? { ...req, status, approvedBy: user?.name }
          : req
      ));
      
      // Notify the requester
      addNotification({
        title: `Leave Request ${status === 'approved' ? 'Approved' : 'Rejected'}`,
        message: `Your ${request.type} leave request from ${format(request.startDate, 'MMM dd')} to ${format(request.endDate, 'MMM dd')} has been ${status} by ${user?.name}`,
        type: 'leave',
        metadata: {
          leaveId: id,
          requesterId: request.employeeId,
          requesterName: request.employeeName,
        }
      });
      
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
                      {leaveBalance.annual - leaveBalance.used.annual}/{leaveBalance.annual}
                    </p>
                    <p className="text-xs text-blue-100 mt-1">{leaveBalance.used.annual} used</p>
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
                      {leaveBalance.sick - leaveBalance.used.sick}/{leaveBalance.sick}
                    </p>
                    <p className="text-xs text-red-100 mt-1">{leaveBalance.used.sick} used</p>
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
                      {leaveBalance.casual - leaveBalance.used.casual}/{leaveBalance.casual}
                    </p>
                    <p className="text-xs text-green-100 mt-1">{leaveBalance.used.casual} used</p>
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

          {/* My Leave Requests */}
          <Card className="border-0 shadow-lg">
            <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
              <CardTitle className="text-xl font-semibold">My Leave History</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {leaveRequests.filter(req => req.employeeId === user?.id).map((request) => (
                  <div key={request.id} className="border rounded-lg p-4 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <CalendarIcon className="h-4 w-4" />
                          <span className="font-medium">
                            {format(request.startDate, 'MMM dd')} - {format(request.endDate, 'MMM dd, yyyy')}
                          </span>
                          <Badge className={getLeaveTypeColor(request.type)}>
                            {request.type}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{request.reason}</p>
                      </div>
                      <Badge variant={getStatusColor(request.status)}>
                        {request.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
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
                <div className="mb-6 p-4 border rounded-lg bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950">
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
              )}
              {/* Calendar with holidays highlighted */}
              <div className="flex justify-center">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={setSelectedDate}
                  className="rounded-xl border-2 shadow-lg p-4 bg-white dark:bg-gray-950"
                modifiers={{
                  holiday: holidays.map(h => h.date)
                }}
                modifiersClassNames={{
                  holiday: 'bg-gradient-to-br from-amber-400 to-yellow-500 text-white font-bold hover:from-amber-500 hover:to-yellow-600 transition-all duration-300 shadow-md'
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
                  </div>
                }
                />
              </div>
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
                <div className="space-y-4">
                  {getFilteredRequests().length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <AlertCircle className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>No leave requests to display</p>
                    </div>
                  ) : (
                    getFilteredRequests().map((request) => (
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
                            <Badge variant={getStatusColor(request.status)}>
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
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}