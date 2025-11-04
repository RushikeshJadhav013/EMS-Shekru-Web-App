import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useNotifications } from '@/contexts/NotificationContext';
import { Task, UserRole } from '@/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { 
  Plus, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  Pause, 
  PlayCircle,
  Calendar,
  User,
  Filter,
  Search,
  MessageSquare,
  Paperclip,
  ChevronRight,
  ListTodo,
  Grid3x3,
  FileText,
  XCircle
} from 'lucide-react';
import { format } from 'date-fns';

// Mock data for demo
const mockEmployees = {
  admin: [],
  hr: ['employee@company.com', 'teamlead@company.com', 'manager@company.com'],
  manager: ['employee@company.com', 'teamlead@company.com'],
  team_lead: ['employee@company.com'],
  employee: []
};

const TaskManagement: React.FC = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const { toast } = useToast();
  const { addNotification } = useNotifications();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    assignedTo: [] as string[],
    priority: 'medium' as Task['priority'],
    deadline: '',
    department: '',
    employeeId: ''
  });

  // Load mock tasks
  useEffect(() => {
    const storedTasks = localStorage.getItem('tasks');
    if (storedTasks) {
      setTasks(JSON.parse(storedTasks));
    } else {
      // Generate mock tasks
      const mockTasks: Task[] = [
        {
          id: '1',
          title: 'Complete Project Documentation',
          description: 'Prepare comprehensive documentation for the new employee management system',
          assignedTo: ['employee@company.com'],
          assignedBy: user?.id || '1',
          priority: 'high',
          status: 'in-progress',
          deadline: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
          startDate: new Date().toISOString(),
          tags: ['documentation', 'urgent'],
          progress: 60,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        },
        {
          id: '2',
          title: 'Team Meeting Preparation',
          description: 'Prepare agenda and materials for quarterly team meeting',
          assignedTo: ['teamlead@company.com'],
          assignedBy: user?.id || '1',
          priority: 'medium',
          status: 'todo',
          deadline: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
          startDate: new Date().toISOString(),
          tags: ['meeting', 'planning'],
          progress: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
      ];
      setTasks(mockTasks);
      localStorage.setItem('tasks', JSON.stringify(mockTasks));
    }
  }, [user]);

  // Check if user can assign tasks to others
  const canAssignTasks = () => {
    if (!user) return false;
    return user.role !== 'employee';
  };

  // Get assignable users based on role
  const getAssignableUsers = () => {
    if (!user) return [];
    
    switch (user.role) {
      case 'admin':
        return [...mockEmployees.hr, ...mockEmployees.manager, ...mockEmployees.team_lead, ...mockEmployees.employee];
      case 'hr':
        return [...mockEmployees.manager, ...mockEmployees.team_lead, ...mockEmployees.employee];
      case 'manager':
        return [...mockEmployees.team_lead, ...mockEmployees.employee];
      case 'team_lead':
        return mockEmployees.employee;
      default:
        return [];
    }
  };

  // Filter tasks based on search and status
  const filteredTasks = tasks.filter(task => {
    const matchesSearch = task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          task.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = filterStatus === 'all' || task.status === filterStatus;
    
    // Role-based task visibility
    const isVisible = user && (
      task.assignedBy === user.id ||
      task.assignedTo.includes(user.email || '') ||
      user.role === 'admin' ||
      (user.role === 'hr' && task.assignedBy !== '1') ||
      (user.role === 'manager' && !['1', '2'].includes(task.assignedBy))
    );
    
    return matchesSearch && matchesStatus && isVisible;
  });

  // Create new task
  const handleCreateTask = () => {
    if (!user) return;
    
    const task: Task = {
      id: Date.now().toString(),
      title: newTask.title,
      description: newTask.description,
      assignedTo: newTask.assignedTo.length > 0 ? newTask.assignedTo : [user.email],
      assignedBy: user.id,
      priority: newTask.priority,
      status: 'todo',
      deadline: newTask.deadline,
      startDate: new Date().toISOString(),
      tags: [],
      progress: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    const updatedTasks = [...tasks, task];
    setTasks(updatedTasks);
    localStorage.setItem('tasks', JSON.stringify(updatedTasks));
    
    // Send notification to assignee if task is assigned to someone else
    if (task.assignedTo.length > 0 && task.assignedTo[0] !== user.email && task.assignedTo[0] !== 'self') {
      addNotification({
        title: 'New Task Assigned',
        message: `${user.name} assigned you a new task: "${task.title}"`,
        type: 'task',
        metadata: {
          taskId: task.id,
          requesterId: user.id,
          requesterName: user.name,
        }
      });
    }
    
    toast({
      title: 'Task Created',
      description: `Task "${task.title}" has been created successfully.`,
    });

    setIsCreateDialogOpen(false);
    setNewTask({
      title: '',
      description: '',
      assignedTo: [],
      priority: 'medium',
      deadline: '',
      department: '',
      employeeId: ''
    });
  };

  // Update task status
  const updateTaskStatus = (taskId: string, newStatus: Task['status']) => {
    const updatedTasks = tasks.map(task => 
      task.id === taskId 
        ? { 
            ...task, 
            status: newStatus,
            completedDate: newStatus === 'completed' ? new Date().toISOString() : undefined,
            updatedAt: new Date().toISOString()
          } 
        : task
    );
    setTasks(updatedTasks);
    localStorage.setItem('tasks', JSON.stringify(updatedTasks));
    
    toast({
      title: 'Status Updated',
      description: `Task status changed to ${newStatus}.`,
    });
  };

  // Get status color
  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'todo': return 'bg-slate-500';
      case 'in-progress': return 'bg-blue-500';
      case 'review': return 'bg-yellow-500';
      case 'completed': return 'bg-green-500';
      case 'cancelled': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  // Get priority color
  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'low': return 'bg-green-100 text-green-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'urgent': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6 animate-fade-in p-4 sm:p-6">
      {/* Modern Header */}
      <div className="bg-gradient-to-r from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800 rounded-2xl p-6 shadow-sm border">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
              <ListTodo className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{t.navigation.tasks}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Manage and track all tasks across your organization
              </p>
            </div>
          </div>
        
          {canAssignTasks() && (
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 shadow-md">
                  <Plus className="h-4 w-4" />
                  Create Task
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto border-2 shadow-2xl">
                <DialogHeader className="pb-4 border-b bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950 dark:to-purple-950 -m-6 mb-0 p-6 rounded-t-lg">
                  <div className="flex items-center gap-3">
                    <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
                      <Plus className="h-6 w-6 text-white" />
                    </div>
                    <div>
                      <DialogTitle className="text-2xl font-bold">Create New Task</DialogTitle>
                      <DialogDescription className="mt-1">
                        Assign a new task to team members
                      </DialogDescription>
                    </div>
                  </div>
                </DialogHeader>
              
              <div className="space-y-5 mt-6">
                <div className="space-y-2">
                  <Label htmlFor="title" className="text-sm font-semibold flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-gradient-to-r from-violet-500 to-purple-600"></div>
                    Task Title <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="title"
                    value={newTask.title}
                    onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                    placeholder="Enter task title"
                    className="h-11 border-2 focus:ring-2 focus:ring-violet-500 transition-all"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="description" className="text-sm font-semibold flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-gradient-to-r from-violet-500 to-purple-600"></div>
                    Description <span className="text-red-500">*</span>
                  </Label>
                  <Textarea
                    id="description"
                    value={newTask.description}
                    onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                    placeholder="Enter task description"
                    rows={4}
                    className="resize-none border-2 focus:ring-2 focus:ring-violet-500 transition-all"
                  />
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="priority" className="text-sm font-semibold flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-violet-600" />
                      Priority
                    </Label>
                    <Select
                      value={newTask.priority}
                      onValueChange={(value: Task['priority']) => 
                        setNewTask({ ...newTask, priority: value })
                      }
                    >
                      <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="border-2 shadow-xl">
                        <SelectItem value="low" className="cursor-pointer">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-green-500"></div>
                            Low
                          </div>
                        </SelectItem>
                        <SelectItem value="medium" className="cursor-pointer">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-yellow-500"></div>
                            Medium
                          </div>
                        </SelectItem>
                        <SelectItem value="high" className="cursor-pointer">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-orange-500"></div>
                            High
                          </div>
                        </SelectItem>
                        <SelectItem value="urgent" className="cursor-pointer">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-red-500"></div>
                            Urgent
                          </div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="deadline" className="text-sm font-semibold flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-violet-600" />
                      Deadline
                    </Label>
                    <Input
                      id="deadline"
                      type="date"
                      value={newTask.deadline}
                      onChange={(e) => setNewTask({ ...newTask, deadline: e.target.value })}
                      className="h-11 border-2 focus:ring-2 focus:ring-violet-500 transition-all"
                    />
                  </div>
                </div>
                
                {getAssignableUsers().length > 0 && (
                  <div className="space-y-2">
                    <Label htmlFor="assignTo" className="text-sm font-semibold flex items-center gap-2">
                      <User className="h-4 w-4 text-violet-600" />
                      Assign To
                    </Label>
                    <Select
                      value={newTask.assignedTo[0] || ''}
                      onValueChange={(value) => 
                        setNewTask({ ...newTask, assignedTo: [value] })
                      }
                    >
                      <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                        <SelectValue placeholder="Select employee" />
                      </SelectTrigger>
                      <SelectContent className="border-2 shadow-xl">
                        <SelectItem value="self" className="cursor-pointer">Self</SelectItem>
                        {getAssignableUsers().map(email => (
                          <SelectItem key={email} value={email} className="cursor-pointer">
                            {email}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="department" className="text-sm font-semibold flex items-center gap-2">
                      <Filter className="h-4 w-4 text-violet-600" />
                      Department
                    </Label>
                    <Input
                      id="department"
                      value={newTask.department}
                      onChange={(e) => setNewTask({ ...newTask, department: e.target.value })}
                      placeholder="Enter department"
                      className="h-11 border-2 focus:ring-2 focus:ring-violet-500 transition-all"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="employeeId" className="text-sm font-semibold flex items-center gap-2">
                      <User className="h-4 w-4 text-violet-600" />
                      Employee ID
                    </Label>
                    <Input
                      id="employeeId"
                      value={newTask.employeeId}
                      onChange={(e) => setNewTask({ ...newTask, employeeId: e.target.value })}
                      placeholder="Enter employee ID"
                      className="h-11 border-2 focus:ring-2 focus:ring-violet-500 transition-all"
                    />
                  </div>
                </div>
                
                <div className="flex justify-end gap-3 pt-6 border-t mt-6">
                  <Button 
                    variant="outline" 
                    onClick={() => setIsCreateDialogOpen(false)}
                    className="h-11 px-6 border-2 hover:bg-slate-50 dark:hover:bg-slate-900"
                  >
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleCreateTask}
                    disabled={!newTask.title || !newTask.description}
                    className="h-11 px-6 gap-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="h-5 w-5" />
                    Create Task
                  </Button>
                </div>
              </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        <Card className="border-0 bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-blue-50">Total Tasks</CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <ListTodo className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{tasks.length}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-cyan-50">In Progress</CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Clock className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {tasks.filter(t => t.status === 'in-progress').length}
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-0 bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-green-50">Completed</CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {tasks.filter(t => t.status === 'completed').length}
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-0 bg-gradient-to-br from-red-500 to-rose-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-red-50">Overdue</CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {tasks.filter(t => 
                t.status !== 'completed' && 
                new Date(t.deadline) < new Date()
              ).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card className="border-0 shadow-lg">
        <CardHeader className="border-b bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <Filter className="h-5 w-5 text-white" />
              </div>
              <CardTitle className="text-xl font-semibold">Task Management</CardTitle>
            </div>
            
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9 w-full sm:w-[200px] h-10 bg-white dark:bg-gray-950 border-gray-200 dark:border-gray-800 focus:ring-2 focus:ring-violet-500"
                  placeholder="Search tasks..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-full sm:w-[150px] h-10 bg-white dark:bg-gray-950">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="todo">To Do</SelectItem>
                  <SelectItem value="in-progress">In Progress</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
                </SelectContent>
              </Select>
              
              <div className="flex gap-1">
                <Button
                  variant={viewMode === 'list' ? 'default' : 'outline'}
                  size="icon"
                  onClick={() => setViewMode('list')}
                  className={viewMode === 'list' ? 'bg-gradient-to-r from-violet-600 to-purple-600' : ''}
                >
                  <ListTodo className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="icon"
                  onClick={() => setViewMode('grid')}
                  className={viewMode === 'grid' ? 'bg-gradient-to-r from-violet-600 to-purple-600' : ''}
                >
                  <Grid3x3 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="pt-6">
          {viewMode === 'list' ? (
            <div className="rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
              <Table>
                <TableHeader className="bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Task</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Deadline</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTasks.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No tasks found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredTasks.map((task) => (
                      <TableRow key={task.id} className="hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                        <TableCell>
                          <div>
                            <p className="font-medium">{task.title}</p>
                            <p className="text-sm text-muted-foreground line-clamp-1">
                              {task.description}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">
                              {task.assignedTo[0] || 'Self'}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={getPriorityColor(task.priority)}>
                            {task.priority}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">
                              {format(new Date(task.deadline), 'MMM dd, yyyy')}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={task.status}
                            onValueChange={(value: Task['status']) => 
                              updateTaskStatus(task.id, value)
                            }
                          >
                            <SelectTrigger className="w-[170px] h-10 bg-white dark:bg-gray-950 border-2 hover:border-violet-300 dark:hover:border-violet-700 transition-all duration-300 hover:shadow-md">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="border-2 shadow-2xl min-w-[200px]">
                              <SelectItem value="todo" className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors py-2.5">
                                <div className="flex items-center gap-3">
                                  <div className="h-3 w-3 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 shadow-md animate-pulse flex-shrink-0" />
                                  <span className="font-medium text-sm">To Do</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="in-progress" className="cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-950 transition-colors py-2.5">
                                <div className="flex items-center gap-3">
                                  <div className="h-3 w-3 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 shadow-md animate-pulse flex-shrink-0" />
                                  <span className="font-medium text-sm">In Progress</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="review" className="cursor-pointer hover:bg-yellow-50 dark:hover:bg-yellow-950 transition-colors py-2.5">
                                <div className="flex items-center gap-3">
                                  <div className="h-3 w-3 rounded-full bg-gradient-to-br from-yellow-400 to-amber-600 shadow-md animate-pulse flex-shrink-0" />
                                  <span className="font-medium text-sm">Review</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="completed" className="cursor-pointer hover:bg-green-50 dark:hover:bg-green-950 transition-colors py-2.5">
                                <div className="flex items-center gap-3">
                                  <div className="h-3 w-3 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 shadow-md flex-shrink-0" />
                                  <span className="font-medium text-sm flex-1">Completed</span>
                                  <CheckCircle2 className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                                </div>
                              </SelectItem>
                              <SelectItem value="cancelled" className="cursor-pointer hover:bg-red-50 dark:hover:bg-red-950 transition-colors py-2.5">
                                <div className="flex items-center gap-3">
                                  <div className="h-3 w-3 rounded-full bg-gradient-to-br from-red-400 to-rose-600 shadow-md flex-shrink-0" />
                                  <span className="font-medium text-sm flex-1">Cancelled</span>
                                  <XCircle className="h-3.5 w-3.5 text-red-600 flex-shrink-0" />
                                </div>
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedTask(task)}
                            className="hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-violet-950"
                          >
                            View
                            <ChevronRight className="h-4 w-4 ml-1" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              {filteredTasks.map((task) => (
                <Card key={task.id} className="border-0 shadow-md hover:shadow-xl transition-all duration-300 cursor-pointer transform hover:scale-105 bg-gradient-to-br from-white to-slate-50 dark:from-gray-900 dark:to-slate-900"
                      onClick={() => setSelectedTask(task)}>
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="text-lg">{task.title}</CardTitle>
                        <CardDescription className="line-clamp-2">
                          {task.description}
                        </CardDescription>
                      </div>
                      <Badge className={getPriorityColor(task.priority)}>
                        {task.priority}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span>{task.assignedTo[0] || 'Self'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span>{format(new Date(task.deadline), 'MMM dd, yyyy')}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`h-2 w-2 rounded-full ${getStatusColor(task.status)}`} />
                          <span className="text-sm capitalize">{task.status.replace('-', ' ')}</span>
                        </div>
                        {task.progress !== undefined && (
                          <span className="text-sm text-muted-foreground">{task.progress}%</span>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Task Detail Dialog */}
      {selectedTask && (
        <Dialog open={!!selectedTask} onOpenChange={() => setSelectedTask(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader className="pb-4 border-b">
              <div className="flex items-start gap-3">
                <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg flex-shrink-0">
                  <ListTodo className="h-6 w-6 text-white" />
                </div>
                <div className="flex-1">
                  <DialogTitle className="text-2xl font-bold">{selectedTask.title}</DialogTitle>
                  <DialogDescription className="mt-1">
                    Task ID: {selectedTask.id}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>
            
            <Tabs defaultValue="details" className="mt-6">
              <TabsList className="grid w-full grid-cols-3 h-12 bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 border">
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="activity">Activity</TabsTrigger>
                <TabsTrigger value="comments">Comments</TabsTrigger>
              </TabsList>
              
              <TabsContent value="details" className="space-y-6 mt-6">
                <div className="p-4 rounded-lg bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 border">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                      <FileText className="h-4 w-4 text-white" />
                    </div>
                    Description
                  </h4>
                  <p className="text-muted-foreground leading-relaxed">{selectedTask.description}</p>
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                    <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                      <User className="h-4 w-4 text-violet-600" />
                      Assigned To
                    </h4>
                    <p className="text-muted-foreground font-medium">{selectedTask.assignedTo[0] || 'Self'}</p>
                  </div>
                  <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                    <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                      <AlertCircle className="h-4 w-4 text-violet-600" />
                      Priority
                    </h4>
                    <Badge className={getPriorityColor(selectedTask.priority)}>
                      {selectedTask.priority}
                    </Badge>
                  </div>
                  <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                    <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                      <Calendar className="h-4 w-4 text-violet-600" />
                      Deadline
                    </h4>
                    <p className="text-muted-foreground font-medium">
                      {format(new Date(selectedTask.deadline), 'MMM dd, yyyy')}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                    <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                      <Clock className="h-4 w-4 text-violet-600" />
                      Status
                    </h4>
                    <div className="flex items-center gap-2">
                      <div className={`h-3 w-3 rounded-full ${getStatusColor(selectedTask.status)} shadow-md`} />
                      <span className="capitalize font-medium">{selectedTask.status.replace('-', ' ')}</span>
                    </div>
                  </div>
                </div>
                
                {selectedTask.tags && selectedTask.tags.length > 0 && (
                  <div className="p-4 rounded-lg bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950 dark:to-purple-950 border">
                    <h4 className="font-semibold mb-3 flex items-center gap-2">
                      <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                        <Paperclip className="h-4 w-4 text-white" />
                      </div>
                      Tags
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedTask.tags.map(tag => (
                        <Badge key={tag} className="bg-white dark:bg-gray-900 border-violet-200 dark:border-violet-800 hover:bg-violet-50 dark:hover:bg-violet-950 transition-colors">{tag}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </TabsContent>
              
              <TabsContent value="activity" className="mt-6">
                <div className="space-y-4">
                  <div className="flex items-start gap-4 p-4 rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 hover:shadow-md transition-all">
                    <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg flex-shrink-0">
                      <PlayCircle className="h-6 w-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-lg">Task Created</p>
                      <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        {format(new Date(selectedTask.createdAt), 'MMM dd, yyyy HH:mm')}
                      </p>
                    </div>
                  </div>
                  {selectedTask.completedDate && (
                    <div className="flex items-start gap-4 p-4 rounded-lg border bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 hover:shadow-md transition-all">
                      <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg flex-shrink-0">
                        <CheckCircle2 className="h-6 w-6 text-white" />
                      </div>
                      <div className="flex-1">
                        <p className="font-semibold text-lg">Task Completed</p>
                        <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                          <Clock className="h-3 w-3" />
                          {format(new Date(selectedTask.completedDate), 'MMM dd, yyyy HH:mm')}
                        </p>
                      </div>
                    </div>
                  )}
                  {!selectedTask.completedDate && (
                    <div className="text-center py-8">
                      <div className="h-16 w-16 rounded-full bg-gradient-to-br from-slate-100 to-gray-200 dark:from-slate-800 dark:to-gray-900 flex items-center justify-center mx-auto mb-3">
                        <Clock className="h-8 w-8 text-muted-foreground" />
                      </div>
                      <p className="text-sm text-muted-foreground">Task is in progress</p>
                    </div>
                  )}
                </div>
              </TabsContent>
              
              <TabsContent value="comments" className="mt-6">
                <div className="space-y-6">
                  <div className="p-4 rounded-lg border bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900">
                    <div className="flex flex-col sm:flex-row gap-3">
                      <Textarea 
                        placeholder="Add a comment..." 
                        rows={3} 
                        className="flex-1 resize-none bg-white dark:bg-gray-950 border-gray-200 dark:border-gray-800 focus:ring-2 focus:ring-violet-500 transition-all"
                      />
                      <Button className="gap-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 shadow-md h-fit">
                        <MessageSquare className="h-4 w-4" />
                        Post
                      </Button>
                    </div>
                  </div>
                  <div className="text-center py-12">
                    <div className="h-20 w-20 rounded-full bg-gradient-to-br from-violet-100 to-purple-100 dark:from-violet-900 dark:to-purple-900 flex items-center justify-center mx-auto mb-4">
                      <MessageSquare className="h-10 w-10 text-violet-600 dark:text-violet-400" />
                    </div>
                    <p className="text-sm text-muted-foreground font-medium">No comments yet</p>
                    <p className="text-xs text-muted-foreground mt-1">Be the first to comment on this task</p>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default TaskManagement;