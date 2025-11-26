import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  FileText, 
  Download, 
  TrendingUp, 
  TrendingDown,
  Users,
  Clock,
  Target,
  Award,
  Calendar,
  BarChart3,
  PieChart,
  Activity,
  Filter,
  FileSpreadsheet,
  Star,
  Edit
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { toast } from '@/hooks/use-toast';
import RatingDialog, { EmployeeRating } from '@/components/rating/RatingDialog';

interface EmployeePerformance {
  id: string;
  employeeId: string;
  name: string;
  department: string;
  role: string;
  attendanceScore: number;
  taskCompletionRate: number;
  productivity: number;
  qualityScore: number;
  overallRating: number;
  month: string;
  year: number;
}

interface DepartmentMetrics {
  department: string;
  totalEmployees: number;
  avgProductivity: number;
  avgAttendance: number;
  tasksCompleted: number;
  tasksPending: number;
  performanceScore: number;
}

export default function Reports() {
  const { t } = useLanguage();
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth().toString());
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear().toString());
  const [selectedDepartment, setSelectedDepartment] = useState('all');
  const [selectedReportType, setSelectedReportType] = useState('performance');
  const [ratingDialogOpen, setRatingDialogOpen] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<EmployeePerformance | null>(null);
  const [employeeRatings, setEmployeeRatings] = useState<Record<string, EmployeeRating>>({});
  const [expandedDepartments, setExpandedDepartments] = useState<Set<string>>(new Set());
  
  // State for API data
  const [employeePerformance, setEmployeePerformance] = useState<EmployeePerformance[]>([]);
  const [departmentMetrics, setDepartmentMetrics] = useState<DepartmentMetrics[]>([]);
  const [executiveSummary, setExecutiveSummary] = useState<any>(null);
  const [departments, setDepartments] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load ratings from localStorage on mount
  useEffect(() => {
    const savedRatings = localStorage.getItem('employeeRatings');
    if (savedRatings) {
      setEmployeeRatings(JSON.parse(savedRatings));
    }
  }, []);

  // Save ratings to localStorage whenever they change
  useEffect(() => {
    if (Object.keys(employeeRatings).length > 0) {
      localStorage.setItem('employeeRatings', JSON.stringify(employeeRatings));
    }
  }, [employeeRatings]);

  // Load departments on mount
  useEffect(() => {
    loadDepartments();
  }, []);

  // Load report data when filters change
  useEffect(() => {
    loadReportData();
  }, [selectedMonth, selectedYear, selectedDepartment]);

  const loadDepartments = async () => {
    try {
      const response = await fetch('http://172.105.56.142/reports/departments', {
        headers: {
          'Authorization': localStorage.getItem('token') || '',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setDepartments(data.departments || []);
      }
    } catch (error) {
      console.error('Failed to load departments:', error);
    }
  };

  const loadReportData = async () => {
    setIsLoading(true);
    try {
      const headers = {
        'Authorization': localStorage.getItem('token') || '',
      };

      const month = parseInt(selectedMonth);
      const year = parseInt(selectedYear);
      const dept = selectedDepartment !== 'all' ? selectedDepartment : undefined;

      // Build query parameters
      const empParams = new URLSearchParams({
        month: month.toString(),
        year: year.toString(),
        ...(dept && { department: dept }),
      });

      const deptParams = new URLSearchParams({
        month: month.toString(),
        year: year.toString(),
      });

      const summaryParams = new URLSearchParams({
        month: month.toString(),
        year: year.toString(),
      });

      // Fetch all data in parallel
      const [empResponse, deptResponse, summaryResponse] = await Promise.all([
        fetch(`http://172.105.56.142/reports/employee-performance?${empParams}`, { headers }),
        fetch(`http://172.105.56.142/reports/department-metrics?${deptParams}`, { headers }),
        fetch(`http://172.105.56.142/reports/executive-summary?${summaryParams}`, { headers }),
      ]);

      // Handle employee performance response
      if (empResponse.ok) {
        const empData = await empResponse.json();
        setEmployeePerformance(empData.employees || []);
      } else {
        console.error('Employee performance error:', empResponse.status, await empResponse.text());
        setEmployeePerformance([]);
      }

      // Handle department metrics response
      if (deptResponse.ok) {
        const deptData = await deptResponse.json();
        setDepartmentMetrics(deptData.departments || []);
      } else {
        console.error('Department metrics error:', deptResponse.status, await deptResponse.text());
        setDepartmentMetrics([]);
      }

      // Handle executive summary response
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setExecutiveSummary(summaryData);
      } else {
        console.error('Executive summary error:', summaryResponse.status, await summaryResponse.text());
        setExecutiveSummary(null);
      }

      // Show error toast if any request failed
      if (!empResponse.ok || !deptResponse.ok || !summaryResponse.ok) {
        toast({
          title: 'Partial Data Load',
          description: 'Some report data could not be loaded. Check console for details.',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Failed to load report data:', error);
      setEmployeePerformance([]);
      setDepartmentMetrics([]);
      setExecutiveSummary(null);
      toast({
        title: 'Error',
        description: 'Failed to load report data. Please check if backend is running.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveRating = (rating: EmployeeRating) => {
    setEmployeeRatings(prev => ({
      ...prev,
      [rating.employeeId]: rating
    }));
  };

  const openRatingDialog = (employee: EmployeePerformance) => {
    setSelectedEmployee(employee);
    setRatingDialogOpen(true);
  };

  const getEmployeeRating = (employeeId: string) => {
    return employeeRatings[employeeId];
  };

  const calculateProductivity = (employeeId: string) => {
    const rating = getEmployeeRating(employeeId);
    if (!rating) return 0;
    return (rating.productivityRating / 5) * 100;
  };

  const calculateQualityScore = (employeeId: string) => {
    const rating = getEmployeeRating(employeeId);
    if (!rating) return 0;
    return (rating.qualityRating / 5) * 100;
  };

  const calculateOverallRating = (employee: EmployeePerformance) => {
    const productivity = calculateProductivity(employee.employeeId);
    const qualityScore = calculateQualityScore(employee.employeeId);
    
    // If no manual ratings exist, return 0
    if (productivity === 0 || qualityScore === 0) return 0;
    
    // Calculate average of all 4 metrics
    return Math.round(
      (employee.attendanceScore + employee.taskCompletionRate + productivity + qualityScore) / 4
    );
  };

  const filteredPerformance = employeePerformance;

  // Group employees by department
  const employeesByDepartment = React.useMemo(() => {
    const grouped: Record<string, EmployeePerformance[]> = {};
    filteredPerformance.forEach(emp => {
      const dept = emp.department || 'No Department';
      if (!grouped[dept]) {
        grouped[dept] = [];
      }
      grouped[dept].push(emp);
    });
    return grouped;
  }, [filteredPerformance]);

  const toggleDepartment = (department: string) => {
    setExpandedDepartments(prev => {
      const newSet = new Set(prev);
      if (newSet.has(department)) {
        newSet.delete(department);
      } else {
        newSet.add(department);
      }
      return newSet;
    });
  };

  const expandAllDepartments = () => {
    setExpandedDepartments(new Set(Object.keys(employeesByDepartment)));
  };

  const collapseAllDepartments = () => {
    setExpandedDepartments(new Set());
  };

  const getPerformanceColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 75) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getPerformanceBadge = (score: number) => {
    if (score >= 90) return { variant: 'default' as const, text: 'Excellent' };
    if (score >= 75) return { variant: 'secondary' as const, text: 'Good' };
    if (score >= 60) return { variant: 'outline' as const, text: 'Average' };
    return { variant: 'destructive' as const, text: 'Poor' };
  };

  const downloadReport = (type: string) => {
    const data = type === 'performance' ? filteredPerformance : departmentMetrics;
    const headers = type === 'performance' 
      ? ['Employee ID', 'Name', 'Department', 'Role', 'Attendance', 'Task Completion', 'Productivity', 'Quality', 'Overall Rating']
      : ['Department', 'Total Employees', 'Avg Productivity', 'Avg Attendance', 'Tasks Completed', 'Tasks Pending', 'Performance Score'];

    const csvData = type === 'performance'
      ? filteredPerformance.map(emp => [
          emp.employeeId,
          emp.name,
          emp.department,
          emp.role,
          emp.attendanceScore,
          emp.taskCompletionRate,
          emp.productivity,
          emp.qualityScore,
          emp.overallRating
        ])
      : departmentMetrics.map(dept => [
          dept.department,
          dept.totalEmployees,
          dept.avgProductivity,
          dept.avgAttendance,
          dept.tasksCompleted,
          dept.tasksPending,
          dept.performanceScore
        ]);

    const csvContent = [headers, ...csvData].map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}_report_${selectedMonth}_${selectedYear}.csv`;
    a.click();

    toast({
      title: 'Success',
      description: 'Report downloaded successfully'
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 space-y-4 sm:space-y-6">
        {/* Header Section */}
        <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg rounded-2xl shadow-xl border border-white/20 p-4 sm:p-6 lg:p-8">
          <div className="flex flex-col gap-4 lg:gap-0 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg">
                <FileText className="h-6 w-6 sm:h-7 sm:w-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Performance Reports
                </h1>
                <p className="text-sm text-muted-foreground mt-1">Track and analyze team performance</p>
              </div>
            </div>
            
            {/* Filters - Responsive Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3 lg:flex lg:gap-2">
              <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                <SelectTrigger className="w-full sm:w-auto lg:w-[140px] h-10 bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 shadow-sm">
                  <Calendar className="h-4 w-4 mr-2 text-muted-foreground" />
                  <SelectValue placeholder="Month" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">January</SelectItem>
                  <SelectItem value="1">February</SelectItem>
                  <SelectItem value="2">March</SelectItem>
                  <SelectItem value="3">April</SelectItem>
                  <SelectItem value="4">May</SelectItem>
                  <SelectItem value="5">June</SelectItem>
                  <SelectItem value="6">July</SelectItem>
                  <SelectItem value="7">August</SelectItem>
                  <SelectItem value="8">September</SelectItem>
                  <SelectItem value="9">October</SelectItem>
                  <SelectItem value="10">November</SelectItem>
                  <SelectItem value="11">December</SelectItem>
                </SelectContent>
              </Select>
              <Select value={selectedYear} onValueChange={setSelectedYear}>
                <SelectTrigger className="w-full sm:w-auto lg:w-[110px] h-10 bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 shadow-sm">
                  <SelectValue placeholder="Year" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2025">2025</SelectItem>
                  <SelectItem value="2024">2024</SelectItem>
                  <SelectItem value="2023">2023</SelectItem>
                  <SelectItem value="2022">2022</SelectItem>
                </SelectContent>
              </Select>
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger className="w-full sm:w-auto lg:w-[160px] h-10 bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 shadow-sm">
                  <Filter className="h-4 w-4 mr-2 text-muted-foreground" />
                  <SelectValue placeholder="Department" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map(dept => (
                    <SelectItem key={dept} value={dept}>{dept}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Tabs Navigation */}
        <Tabs value={selectedReportType} onValueChange={setSelectedReportType} className="space-y-4 sm:space-y-6">
          <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg rounded-2xl shadow-lg border border-white/20 p-2">
            <TabsList className="grid w-full grid-cols-1 sm:grid-cols-3 gap-2 bg-transparent">
              <TabsTrigger 
                value="performance" 
                className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all duration-200 rounded-xl py-3 text-sm sm:text-base"
              >
                <Users className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">Employee Performance</span>
                <span className="sm:hidden">Employees</span>
              </TabsTrigger>
              <TabsTrigger 
                value="department" 
                className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-pink-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all duration-200 rounded-xl py-3 text-sm sm:text-base"
              >
                <PieChart className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">Department Metrics</span>
                <span className="sm:hidden">Departments</span>
              </TabsTrigger>
              <TabsTrigger 
                value="summary" 
                className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-emerald-500 data-[state=active]:to-teal-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all duration-200 rounded-xl py-3 text-sm sm:text-base"
              >
                <BarChart3 className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">Executive Summary</span>
                <span className="sm:hidden">Summary</span>
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="performance" className="space-y-4">
            <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg rounded-2xl shadow-xl border border-white/20 overflow-hidden">
              <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-slate-800 dark:to-slate-700">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-slate-800 dark:text-white">Individual Performance Metrics</h2>
                    <p className="text-sm text-muted-foreground mt-1">Detailed employee performance analysis</p>
                  </div>
                  <Button 
                    onClick={() => downloadReport('performance')} 
                    className="w-full sm:w-auto bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 shadow-lg"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                </div>
              </div>
              <div className="p-4 sm:p-6">
                {isLoading ? (
                  <div className="text-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto"></div>
                    <p className="mt-4 text-muted-foreground">Loading employee performance data...</p>
                  </div>
                ) : filteredPerformance.length === 0 ? (
                  <div className="text-center py-12">
                    <div className="mx-auto w-16 h-16 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mb-4">
                      <Users className="h-8 w-8 text-slate-400" />
                    </div>
                    <p className="text-lg font-medium text-slate-700 dark:text-slate-300">No employee data available</p>
                    <p className="text-sm text-muted-foreground mt-2">Try selecting a different month, year, or department.</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Expand/Collapse All Buttons */}
                    <div className="flex justify-end gap-2">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={expandAllDepartments}
                        className="text-xs"
                      >
                        Expand All
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={collapseAllDepartments}
                        className="text-xs"
                      >
                        Collapse All
                      </Button>
                    </div>

                    {/* Department Groups */}
                    {Object.entries(employeesByDepartment).map(([department, employees]) => {
                      const isExpanded = expandedDepartments.has(department);
                      const deptAvgScore = Math.round(
                        employees.reduce((sum, emp) => sum + calculateOverallRating(emp), 0) / employees.length
                      );
                      
                      return (
                        <div key={department} className="border-2 border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                          {/* Department Header - Clickable */}
                          <button
                            onClick={() => toggleDepartment(department)}
                            className="w-full p-4 sm:p-6 bg-gradient-to-r from-slate-100 to-gray-100 dark:from-slate-800 dark:to-gray-800 hover:from-slate-200 hover:to-gray-200 dark:hover:from-slate-700 dark:hover:to-gray-700 transition-all duration-200"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-4">
                                <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl shadow-lg">
                                  <Users className="h-6 w-6 text-white" />
                                </div>
                                <div className="text-left">
                                  <h3 className="text-xl font-bold text-slate-800 dark:text-white">{department}</h3>
                                  <p className="text-sm text-muted-foreground mt-1">
                                    {employees.length} {employees.length === 1 ? 'Employee' : 'Employees'} • Avg Score: {deptAvgScore}%
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-3">
                                <Badge className={`px-4 py-2 text-sm font-bold ${getPerformanceBadge(deptAvgScore).variant === 'default' ? 'bg-green-500' : getPerformanceBadge(deptAvgScore).variant === 'secondary' ? 'bg-yellow-500' : 'bg-red-500'} text-white`}>
                                  {getPerformanceBadge(deptAvgScore).text}
                                </Badge>
                                <div className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
                                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                  </svg>
                                </div>
                              </div>
                            </div>
                          </button>

                          {/* Employee List - Collapsible */}
                          {isExpanded && (
                            <div className="p-4 sm:p-6 space-y-4 bg-white dark:bg-slate-900">
                              {employees.map((employee) => {
                    const productivity = calculateProductivity(employee.employeeId);
                    const qualityScore = calculateQualityScore(employee.employeeId);
                    const overallRating = calculateOverallRating(employee);
                    const badge = getPerformanceBadge(overallRating);
                    const rating = getEmployeeRating(employee.employeeId);
                    const hasRating = !!rating;
                    
                    return (
                      <div 
                        key={employee.id} 
                        className="bg-gradient-to-br from-white to-slate-50 dark:from-slate-800 dark:to-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 p-4 sm:p-6 hover:shadow-xl transition-all duration-300 hover:scale-[1.01]"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
                          <div className="flex items-center gap-3">
                            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                              {employee.name.charAt(0)}
                            </div>
                            <div>
                              <h3 className="font-bold text-lg text-slate-800 dark:text-white">{employee.name}</h3>
                              <p className="text-xs sm:text-sm text-muted-foreground">
                                {employee.employeeId} • {employee.department} • {employee.role}
                              </p>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge 
                              variant={badge.variant} 
                              className="text-xs sm:text-sm px-3 py-1 shadow-md"
                            >
                              {badge.text}
                            </Badge>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => openRatingDialog(employee)}
                              className="text-xs sm:text-sm shadow-sm hover:shadow-md transition-shadow"
                            >
                              <Edit className="h-3 w-3 sm:h-4 sm:w-4 mr-1" />
                              {hasRating ? 'Update' : 'Rate'}
                            </Button>
                          </div>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                            <div className="bg-white dark:bg-slate-800 rounded-lg p-3 sm:p-4 shadow-sm border border-slate-100 dark:border-slate-700">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                                  <Clock className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                </div>
                                <p className="text-xs sm:text-sm font-medium text-muted-foreground">Attendance</p>
                              </div>
                              <div className="flex items-baseline gap-2 mb-2">
                                <span className={`text-2xl sm:text-3xl font-bold ${getPerformanceColor(employee.attendanceScore)}`}>
                                  {employee.attendanceScore}
                                </span>
                                <span className="text-sm text-muted-foreground">%</span>
                              </div>
                              <Progress value={employee.attendanceScore} className="h-2 mb-2" />
                              <p className="text-xs text-muted-foreground">Auto-calculated</p>
                            </div>
                            <div className="bg-white dark:bg-slate-800 rounded-lg p-3 sm:p-4 shadow-sm border border-slate-100 dark:border-slate-700">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                                  <Target className="h-4 w-4 text-green-600 dark:text-green-400" />
                                </div>
                                <p className="text-xs sm:text-sm font-medium text-muted-foreground">Tasks</p>
                              </div>
                              <div className="flex items-baseline gap-2 mb-2">
                                <span className={`text-2xl sm:text-3xl font-bold ${getPerformanceColor(employee.taskCompletionRate)}`}>
                                  {employee.taskCompletionRate}
                                </span>
                                <span className="text-sm text-muted-foreground">%</span>
                              </div>
                              <Progress value={employee.taskCompletionRate} className="h-2 mb-2" />
                              <p className="text-xs text-muted-foreground">Auto-calculated</p>
                            </div>
                            <div className="bg-white dark:bg-slate-800 rounded-lg p-3 sm:p-4 shadow-sm border border-slate-100 dark:border-slate-700">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                                  <Activity className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                                </div>
                                <p className="text-xs sm:text-sm font-medium text-muted-foreground">Productivity</p>
                              </div>
                              {hasRating ? (
                                <>
                                  <div className="flex items-baseline gap-2 mb-2">
                                    <span className={`text-2xl sm:text-3xl font-bold ${getPerformanceColor(productivity)}`}>
                                      {Math.round(productivity)}
                                    </span>
                                    <span className="text-sm text-muted-foreground">%</span>
                                  </div>
                                  <div className="flex gap-1 mb-2">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                      <Star
                                        key={star}
                                        className={`h-3 w-3 sm:h-4 sm:w-4 ${
                                          star <= rating.productivityRating
                                            ? 'fill-yellow-400 text-yellow-400'
                                            : 'text-gray-300'
                                        }`}
                                      />
                                    ))}
                                  </div>
                                  <Progress value={productivity} className="h-2 mb-2" />
                                </>
                              ) : (
                                <div className="py-4">
                                  <span className="text-sm text-muted-foreground">Not rated yet</span>
                                </div>
                              )}
                              <p className="text-xs text-muted-foreground">Manual rating</p>
                            </div>
                            <div className="bg-white dark:bg-slate-800 rounded-lg p-3 sm:p-4 shadow-sm border border-slate-100 dark:border-slate-700">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
                                  <Award className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                                </div>
                                <p className="text-xs sm:text-sm font-medium text-muted-foreground">Quality</p>
                              </div>
                              {hasRating ? (
                                <>
                                  <div className="flex items-baseline gap-2 mb-2">
                                    <span className={`text-2xl sm:text-3xl font-bold ${getPerformanceColor(qualityScore)}`}>
                                      {Math.round(qualityScore)}
                                    </span>
                                    <span className="text-sm text-muted-foreground">%</span>
                                  </div>
                                  <div className="flex gap-1 mb-2">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                      <Star
                                        key={star}
                                        className={`h-3 w-3 sm:h-4 sm:w-4 ${
                                          star <= rating.qualityRating
                                            ? 'fill-yellow-400 text-yellow-400'
                                            : 'text-gray-300'
                                        }`}
                                      />
                                    ))}
                                  </div>
                                  <Progress value={qualityScore} className="h-2 mb-2" />
                                </>
                              ) : (
                                <div className="py-4">
                                  <span className="text-sm text-muted-foreground">Not rated yet</span>
                                </div>
                              )}
                              <p className="text-xs text-muted-foreground">Manual rating</p>
                            </div>
                            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 dark:from-indigo-900/30 dark:to-blue-900/30 rounded-lg p-3 sm:p-4 shadow-md border-2 border-indigo-200 dark:border-indigo-700">
                              <div className="flex items-center gap-2 mb-2">
                                <div className="p-2 bg-indigo-100 dark:bg-indigo-900/50 rounded-lg">
                                  <BarChart3 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                                </div>
                                <p className="text-xs sm:text-sm font-medium text-indigo-900 dark:text-indigo-200">Overall</p>
                              </div>
                              {overallRating > 0 ? (
                                <>
                                  <div className="flex items-baseline gap-2 mb-2">
                                    <span className={`text-3xl sm:text-4xl font-bold ${getPerformanceColor(overallRating)}`}>
                                      {overallRating}
                                    </span>
                                    <span className="text-sm text-muted-foreground">%</span>
                                  </div>
                                  <Progress value={overallRating} className="h-2 mb-2" />
                                </>
                              ) : (
                                <div className="py-4">
                                  <span className="text-sm text-muted-foreground">Pending ratings</span>
                                </div>
                              )}
                              <p className="text-xs text-muted-foreground">Average score</p>
                            </div>
                          </div>
                          {hasRating && (
                            <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
                              <h4 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">Performance Comments</h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 border border-purple-200 dark:border-purple-800">
                                  <p className="text-xs font-semibold text-purple-900 dark:text-purple-200 mb-1 flex items-center gap-1">
                                    <Activity className="h-3 w-3" />
                                    Productivity
                                  </p>
                                  <p className="text-sm text-slate-700 dark:text-slate-300">{rating.productivityDescription}</p>
                                </div>
                                <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 border border-amber-200 dark:border-amber-800">
                                  <p className="text-xs font-semibold text-amber-900 dark:text-amber-200 mb-1 flex items-center gap-1">
                                    <Award className="h-3 w-3" />
                                    Quality
                                  </p>
                                  <p className="text-sm text-slate-700 dark:text-slate-300">{rating.qualityDescription}</p>
                                </div>
                              </div>
                            </div>
                          )}
                                </div>
                              );
                            })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="department" className="space-y-4">
            <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg rounded-2xl shadow-xl border border-white/20 overflow-hidden">
              <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-slate-800 dark:to-slate-700">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-slate-800 dark:text-white">Department Performance Overview</h2>
                    <p className="text-sm text-muted-foreground mt-1">Compare department metrics and performance</p>
                  </div>
                  <Button 
                    onClick={() => downloadReport('department')} 
                    className="w-full sm:w-auto bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700 shadow-lg"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                </div>
              </div>
              <div className="p-4 sm:p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
                  {departmentMetrics.map((dept) => {
                    const badge = getPerformanceBadge(dept.performanceScore);
                    return (
                      <div 
                        key={dept.department}
                        className="bg-gradient-to-br from-white to-purple-50 dark:from-slate-800 dark:to-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 p-4 sm:p-6 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]"
                      >
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-3">
                            <div className="p-3 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl shadow-lg">
                              <Users className="h-5 w-5 text-white" />
                            </div>
                            <h3 className="font-bold text-lg text-slate-800 dark:text-white">{dept.department}</h3>
                          </div>
                          <Badge variant={badge.variant} className="shadow-md">
                            {badge.text}
                          </Badge>
                        </div>
                        
                        <div className="space-y-4">
                          <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                            <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                              <Users className="h-4 w-4" />
                              Employees
                            </span>
                            <span className="font-bold text-lg">{dept.totalEmployees}</span>
                          </div>
                          
                          <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                              <p className="text-xs text-muted-foreground mb-1">Productivity</p>
                              <p className={`text-xl font-bold ${getPerformanceColor(dept.avgProductivity)}`}>
                                {dept.avgProductivity}%
                              </p>
                            </div>
                            <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                              <p className="text-xs text-muted-foreground mb-1">Attendance</p>
                              <p className={`text-xl font-bold ${getPerformanceColor(dept.avgAttendance)}`}>
                                {dept.avgAttendance}%
                              </p>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                              <p className="text-xs text-muted-foreground mb-1">Completed</p>
                              <p className="text-xl font-bold text-green-600">{dept.tasksCompleted}</p>
                            </div>
                            <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                              <p className="text-xs text-muted-foreground mb-1">Pending</p>
                              <p className="text-xl font-bold text-yellow-600">{dept.tasksPending}</p>
                            </div>
                          </div>
                          
                          <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">Performance Score</span>
                              <span className={`font-bold text-2xl ${getPerformanceColor(dept.performanceScore)}`}>
                                {dept.performanceScore}%
                              </span>
                            </div>
                            <Progress value={dept.performanceScore} className="h-3" />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="summary" className="space-y-4 sm:space-y-6">
            {isLoading ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-500 border-t-transparent mx-auto"></div>
                <p className="mt-4 text-muted-foreground">Loading executive summary...</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-2xl shadow-lg border border-green-200 dark:border-green-800 p-6 hover:shadow-xl transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div className="p-3 bg-green-500 rounded-xl shadow-lg">
                      <TrendingUp className="h-6 w-6 text-white" />
                    </div>
                  </div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">Top Performer</p>
                  <p className="text-2xl font-bold text-slate-800 dark:text-white mb-1">{executiveSummary?.topPerformer?.name || 'N/A'}</p>
                  <p className="text-sm font-semibold text-green-600">{executiveSummary?.topPerformer?.score || 0}% Overall</p>
                </div>
                
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-2xl shadow-lg border border-blue-200 dark:border-blue-800 p-6 hover:shadow-xl transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div className="p-3 bg-blue-500 rounded-xl shadow-lg">
                      <Activity className="h-6 w-6 text-white" />
                    </div>
                  </div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">Avg Performance</p>
                  <p className="text-2xl font-bold text-slate-800 dark:text-white mb-1">{executiveSummary?.avgPerformance || 0}%</p>
                  <p className="text-sm text-muted-foreground">All Employees</p>
                </div>
                
                <div className="bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-2xl shadow-lg border border-purple-200 dark:border-purple-800 p-6 hover:shadow-xl transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div className="p-3 bg-purple-500 rounded-xl shadow-lg">
                      <Target className="h-6 w-6 text-white" />
                    </div>
                  </div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">Tasks Completed</p>
                  <p className="text-2xl font-bold text-slate-800 dark:text-white mb-1">{executiveSummary?.totalTasksCompleted || 0}</p>
                  <p className="text-sm text-muted-foreground">This month</p>
                </div>
                
                <div className="bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-900/20 dark:to-yellow-900/20 rounded-2xl shadow-lg border border-amber-200 dark:border-amber-800 p-6 hover:shadow-xl transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div className="p-3 bg-amber-500 rounded-xl shadow-lg">
                      <Award className="h-6 w-6 text-white" />
                    </div>
                  </div>
                  <p className="text-sm font-medium text-muted-foreground mb-1">Best Department</p>
                  <p className="text-2xl font-bold text-slate-800 dark:text-white mb-1">{executiveSummary?.bestDepartment?.name || 'N/A'}</p>
                  <p className="text-sm font-semibold text-amber-600">{executiveSummary?.bestDepartment?.score || 0}% Score</p>
                </div>
              </div>
            )}

            <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg rounded-2xl shadow-xl border border-white/20 overflow-hidden">
              <div className="p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-slate-800 dark:to-slate-700">
                <h2 className="text-xl sm:text-2xl font-bold text-slate-800 dark:text-white">Executive Summary</h2>
                <p className="text-sm text-muted-foreground mt-1">Insights and recommendations</p>
              </div>
              <div className="p-4 sm:p-6 space-y-6">
                {isLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-4 border-emerald-500 border-t-transparent mx-auto"></div>
                    <p className="mt-4 text-muted-foreground">Loading summary...</p>
                  </div>
                ) : executiveSummary ? (
                  <div className="space-y-6">
                    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-4 sm:p-6 border border-blue-200 dark:border-blue-800">
                      <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-blue-500 rounded-lg">
                          <BarChart3 className="h-5 w-5 text-white" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white">Key Findings</h3>
                      </div>
                      <ul className="space-y-2">
                        {executiveSummary.keyFindings?.map((finding: string, index: number) => (
                          <li key={index} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                            <span className="text-blue-500 mt-1">•</span>
                            <span>{finding}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-xl p-4 sm:p-6 border border-purple-200 dark:border-purple-800">
                      <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-purple-500 rounded-lg">
                          <Target className="h-5 w-5 text-white" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white">Recommendations</h3>
                      </div>
                      <ul className="space-y-2">
                        {executiveSummary.recommendations?.map((rec: string, index: number) => (
                          <li key={index} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                            <span className="text-purple-500 mt-1">•</span>
                            <span>{rec}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 rounded-xl p-4 sm:p-6 border border-emerald-200 dark:border-emerald-800">
                      <div className="flex items-center gap-2 mb-4">
                        <div className="p-2 bg-emerald-500 rounded-lg">
                          <FileText className="h-5 w-5 text-white" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white">Action Items</h3>
                      </div>
                      <ul className="space-y-2">
                        {executiveSummary.actionItems?.map((item: string, index: number) => (
                          <li key={index} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                            <span className="text-emerald-500 mt-1">•</span>
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <div className="mx-auto w-16 h-16 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mb-4">
                      <FileText className="h-8 w-8 text-slate-400" />
                    </div>
                    <p className="text-lg font-medium text-slate-700 dark:text-slate-300">No summary data available</p>
                  </div>
                )}

                <div className="flex flex-col sm:flex-row justify-end gap-2 sm:gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                  <Button variant="outline" className="w-full sm:w-auto shadow-sm">
                    <FileSpreadsheet className="h-4 w-4 mr-2" />
                    Generate Full Report
                  </Button>
                  <Button className="w-full sm:w-auto bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 shadow-lg">
                    <Download className="h-4 w-4 mr-2" />
                    Download Summary
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {selectedEmployee && (
          <RatingDialog
            open={ratingDialogOpen}
            onOpenChange={setRatingDialogOpen}
            employeeId={selectedEmployee.employeeId}
            employeeName={selectedEmployee.name}
            onSave={handleSaveRating}
            currentRatings={getEmployeeRating(selectedEmployee.employeeId)}
          />
        )}
      </div>
    </div>
  );
}