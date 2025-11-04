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

  const departments = ['Engineering', 'Marketing', 'Sales', 'HR', 'Finance', 'Operations'];
  
  const employeePerformance: EmployeePerformance[] = [
    {
      id: '1',
      employeeId: 'EMP001',
      name: 'John Doe',
      department: 'Engineering',
      role: 'Software Engineer',
      attendanceScore: 95,
      taskCompletionRate: 88,
      productivity: 92,
      qualityScore: 90,
      overallRating: 91,
      month: 'December',
      year: 2024
    },
    {
      id: '2',
      employeeId: 'EMP002',
      name: 'Jane Smith',
      department: 'Marketing',
      role: 'Marketing Lead',
      attendanceScore: 98,
      taskCompletionRate: 94,
      productivity: 96,
      qualityScore: 93,
      overallRating: 95,
      month: 'December',
      year: 2024
    },
    {
      id: '3',
      employeeId: 'EMP003',
      name: 'Mike Johnson',
      department: 'Sales',
      role: 'Sales Executive',
      attendanceScore: 87,
      taskCompletionRate: 82,
      productivity: 85,
      qualityScore: 88,
      overallRating: 85,
      month: 'December',
      year: 2024
    },
    {
      id: '4',
      employeeId: 'EMP004',
      name: 'Sarah Williams',
      department: 'HR',
      role: 'HR Manager',
      attendanceScore: 96,
      taskCompletionRate: 91,
      productivity: 94,
      qualityScore: 92,
      overallRating: 93,
      month: 'December',
      year: 2024
    }
  ];

  const departmentMetrics: DepartmentMetrics[] = [
    {
      department: 'Engineering',
      totalEmployees: 45,
      avgProductivity: 89,
      avgAttendance: 92,
      tasksCompleted: 342,
      tasksPending: 58,
      performanceScore: 88
    },
    {
      department: 'Marketing',
      totalEmployees: 20,
      avgProductivity: 94,
      avgAttendance: 95,
      tasksCompleted: 156,
      tasksPending: 24,
      performanceScore: 92
    },
    {
      department: 'Sales',
      totalEmployees: 35,
      avgProductivity: 86,
      avgAttendance: 88,
      tasksCompleted: 278,
      tasksPending: 42,
      performanceScore: 85
    },
    {
      department: 'HR',
      totalEmployees: 12,
      avgProductivity: 91,
      avgAttendance: 94,
      tasksCompleted: 98,
      tasksPending: 12,
      performanceScore: 90
    }
  ];

  const filteredPerformance = employeePerformance.filter(emp => 
    selectedDepartment === 'all' || emp.department === selectedDepartment
  );

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
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl flex items-center gap-2">
              <FileText className="h-6 w-6" />
              Performance Reports
            </CardTitle>
            <div className="flex gap-2">
              <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                <SelectTrigger className="w-[150px]">
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
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="Year" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2024">2024</SelectItem>
                  <SelectItem value="2023">2023</SelectItem>
                  <SelectItem value="2022">2022</SelectItem>
                </SelectContent>
              </Select>
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger className="w-[180px]">
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
        </CardHeader>
      </Card>

      <Tabs value={selectedReportType} onValueChange={setSelectedReportType} className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="performance">Employee Performance</TabsTrigger>
          <TabsTrigger value="department">Department Metrics</TabsTrigger>
          <TabsTrigger value="summary">Executive Summary</TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Individual Performance Metrics</CardTitle>
                <Button onClick={() => downloadReport('performance')}>
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {filteredPerformance.map((employee) => {
                  const productivity = calculateProductivity(employee.employeeId);
                  const qualityScore = calculateQualityScore(employee.employeeId);
                  const overallRating = calculateOverallRating(employee);
                  const badge = getPerformanceBadge(overallRating);
                  const rating = getEmployeeRating(employee.employeeId);
                  const hasRating = !!rating;
                  
                  return (
                    <Card key={employee.id}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h3 className="font-semibold text-lg">{employee.name}</h3>
                            <p className="text-sm text-muted-foreground">
                              {employee.employeeId} • {employee.department} • {employee.role}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={badge.variant}>{badge.text}</Badge>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => openRatingDialog(employee)}
                            >
                              <Edit className="h-4 w-4 mr-1" />
                              {hasRating ? 'Update Rating' : 'Add Rating'}
                            </Button>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          <div>
                            <p className="text-sm text-muted-foreground">Attendance</p>
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-muted-foreground" />
                              <span className={`font-semibold ${getPerformanceColor(employee.attendanceScore)}`}>
                                {employee.attendanceScore}%
                              </span>
                            </div>
                            <Progress value={employee.attendanceScore} className="mt-2" />
                            <p className="text-xs text-muted-foreground mt-1">Auto-calculated</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Task Completion</p>
                            <div className="flex items-center gap-2">
                              <Target className="h-4 w-4 text-muted-foreground" />
                              <span className={`font-semibold ${getPerformanceColor(employee.taskCompletionRate)}`}>
                                {employee.taskCompletionRate}%
                              </span>
                            </div>
                            <Progress value={employee.taskCompletionRate} className="mt-2" />
                            <p className="text-xs text-muted-foreground mt-1">Auto-calculated</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Productivity</p>
                            <div className="flex items-center gap-2">
                              <Activity className="h-4 w-4 text-muted-foreground" />
                              {hasRating ? (
                                <>
                                  <span className={`font-semibold ${getPerformanceColor(productivity)}`}>
                                    {Math.round(productivity)}%
                                  </span>
                                  <div className="flex">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                      <Star
                                        key={star}
                                        className={`h-3 w-3 ${
                                          star <= rating.productivityRating
                                            ? 'fill-yellow-400 text-yellow-400'
                                            : 'text-gray-300'
                                        }`}
                                      />
                                    ))}
                                  </div>
                                </>
                              ) : (
                                <span className="text-sm text-muted-foreground">Not rated</span>
                              )}
                            </div>
                            <Progress value={productivity} className="mt-2" />
                            <p className="text-xs text-muted-foreground mt-1">Manual rating</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Quality Score</p>
                            <div className="flex items-center gap-2">
                              <Award className="h-4 w-4 text-muted-foreground" />
                              {hasRating ? (
                                <>
                                  <span className={`font-semibold ${getPerformanceColor(qualityScore)}`}>
                                    {Math.round(qualityScore)}%
                                  </span>
                                  <div className="flex">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                      <Star
                                        key={star}
                                        className={`h-3 w-3 ${
                                          star <= rating.qualityRating
                                            ? 'fill-yellow-400 text-yellow-400'
                                            : 'text-gray-300'
                                        }`}
                                      />
                                    ))}
                                  </div>
                                </>
                              ) : (
                                <span className="text-sm text-muted-foreground">Not rated</span>
                              )}
                            </div>
                            <Progress value={qualityScore} className="mt-2" />
                            <p className="text-xs text-muted-foreground mt-1">Manual rating</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Overall Rating</p>
                            <div className="flex items-center gap-2">
                              <BarChart3 className="h-4 w-4 text-muted-foreground" />
                              {overallRating > 0 ? (
                                <span className={`font-semibold text-lg ${getPerformanceColor(overallRating)}`}>
                                  {overallRating}%
                                </span>
                              ) : (
                                <span className="text-sm text-muted-foreground">Pending</span>
                              )}
                            </div>
                            <Progress value={overallRating} className="mt-2" />
                            <p className="text-xs text-muted-foreground mt-1">Average of all metrics</p>
                          </div>
                        </div>
                        {hasRating && (
                          <div className="mt-4 pt-4 border-t">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <p className="text-sm font-medium mb-1">Productivity Comments:</p>
                                <p className="text-sm text-muted-foreground">{rating.productivityDescription}</p>
                              </div>
                              <div>
                                <p className="text-sm font-medium mb-1">Quality Comments:</p>
                                <p className="text-sm text-muted-foreground">{rating.qualityDescription}</p>
                              </div>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="department" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Department Performance Overview</CardTitle>
                <Button onClick={() => downloadReport('department')}>
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {departmentMetrics.map((dept) => {
                  const badge = getPerformanceBadge(dept.performanceScore);
                  return (
                    <Card key={dept.department}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-4">
                          <h3 className="font-semibold text-lg">{dept.department}</h3>
                          <Badge variant={badge.variant}>{badge.text}</Badge>
                        </div>
                        <div className="space-y-3">
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-muted-foreground">Total Employees</span>
                            <span className="font-semibold">{dept.totalEmployees}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-muted-foreground">Avg Productivity</span>
                            <span className={`font-semibold ${getPerformanceColor(dept.avgProductivity)}`}>
                              {dept.avgProductivity}%
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-muted-foreground">Avg Attendance</span>
                            <span className={`font-semibold ${getPerformanceColor(dept.avgAttendance)}`}>
                              {dept.avgAttendance}%
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-muted-foreground">Tasks Completed</span>
                            <span className="font-semibold text-green-600">{dept.tasksCompleted}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-sm text-muted-foreground">Tasks Pending</span>
                            <span className="font-semibold text-yellow-600">{dept.tasksPending}</span>
                          </div>
                          <div className="pt-2 border-t">
                            <div className="flex justify-between items-center">
                              <span className="text-sm font-medium">Performance Score</span>
                              <span className={`font-bold text-lg ${getPerformanceColor(dept.performanceScore)}`}>
                                {dept.performanceScore}%
                              </span>
                            </div>
                            <Progress value={dept.performanceScore} className="mt-2" />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="summary" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Top Performer</p>
                    <p className="text-xl font-bold">Jane Smith</p>
                    <p className="text-sm text-green-600">95% Overall</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-green-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Performance</p>
                    <p className="text-xl font-bold">88.5%</p>
                    <p className="text-sm text-muted-foreground">All Employees</p>
                  </div>
                  <Activity className="h-8 w-8 text-blue-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Tasks Completed</p>
                    <p className="text-xl font-bold">874</p>
                    <p className="text-sm text-green-600">+12% vs last month</p>
                  </div>
                  <Target className="h-8 w-8 text-purple-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Best Department</p>
                    <p className="text-xl font-bold">Marketing</p>
                    <p className="text-sm text-green-600">92% Score</p>
                  </div>
                  <Award className="h-8 w-8 text-yellow-500" />
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Executive Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="prose max-w-none">
                <h3 className="text-lg font-semibold mb-2">Key Findings</h3>
                <ul className="space-y-2 text-sm">
                  <li>Overall employee performance improved by 8% compared to last month</li>
                  <li>Marketing department shows the highest productivity at 94%</li>
                  <li>Task completion rate across all departments is at 87%</li>
                  <li>Attendance rates remain steady at 92% organization-wide</li>
                </ul>

                <h3 className="text-lg font-semibold mb-2 mt-4">Recommendations</h3>
                <ul className="space-y-2 text-sm">
                  <li>Implement performance improvement plans for underperforming employees</li>
                  <li>Recognize and reward top performers to maintain motivation</li>
                  <li>Provide additional training for departments with lower productivity scores</li>
                  <li>Review and optimize task allocation to improve completion rates</li>
                </ul>

                <h3 className="text-lg font-semibold mb-2 mt-4">Action Items</h3>
                <ul className="space-y-2 text-sm">
                  <li>Schedule one-on-one meetings with employees scoring below 75%</li>
                  <li>Plan quarterly awards ceremony for top performers</li>
                  <li>Conduct department-wise training needs assessment</li>
                  <li>Implement weekly task review meetings</li>
                </ul>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline">
                  <FileSpreadsheet className="h-4 w-4 mr-2" />
                  Generate Full Report
                </Button>
                <Button>
                  <Download className="h-4 w-4 mr-2" />
                  Download Summary
                </Button>
              </div>
            </CardContent>
          </Card>
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
  );
}