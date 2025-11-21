import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useNotifications } from '@/contexts/NotificationContext';
import { Task as BaseTask, UserRole } from '@/types';
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
  XCircle,
  UserCheck,
  Pencil,
  Trash2,
  Share2,
  Loader2,
  RefreshCcw,
  Download,
  FileSpreadsheet,
  FileDown
} from 'lucide-react';
import { format } from 'date-fns';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const ROLE_ORDER: UserRole[] = ['admin', 'hr', 'manager', 'team_lead', 'employee'];

type BackendTask = {
  task_id: number;
  title: string;
  description?: string | null;
  status?: string | null;
  due_date?: string | null;
  priority?: string | null;
  assigned_to: number | string;
  assigned_by: number | string;
  created_at?: string | null;
  updated_at?: string | null;
  last_passed_by?: number | null;
  last_passed_to?: number | null;
  last_pass_note?: string | null;
  last_passed_at?: string | null;
};

type TaskWithPassMeta = BaseTask & {
  lastPassedBy?: string;
  lastPassedTo?: string;
  lastPassNote?: string;
  lastPassedAt?: string;
};

type BackendEmployee = {
  user_id: number | string;
  employee_id?: string | null;
  name: string;
  email: string;
  role: string;
  department?: string;
};

type EmployeeSummary = {
  userId: string;
  employeeId: string;
  name: string;
  email: string;
  role: UserRole;
  department?: string;
};

type TaskHistoryEntry = {
  id: number;
  task_id: number;
  user_id: number;
  action: string;
  details?: Record<string, unknown> | null;
  created_at: string;
};

const normalizeRole = (role: string | null | undefined): UserRole => {
  const normalized = role?.trim().toLowerCase();
  switch (normalized) {
    case 'admin':
      return 'admin';
    case 'hr':
      return 'hr';
    case 'manager':
      return 'manager';
    case 'teamlead':
    case 'team_lead':
    case 'teamlead ': // handle accidental spacing
      return 'team_lead';
    case 'employee':
    default:
      return 'employee';
  }
};

const backendToFrontendPriority: Record<string, BaseTask['priority']> = {
  low: 'low',
  Low: 'low',
  medium: 'medium',
  Medium: 'medium',
  high: 'high',
  High: 'high',
  urgent: 'urgent',
  Urgent: 'urgent',
};

const frontendToBackendPriority: Record<BaseTask['priority'], string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  urgent: 'Urgent',
};

const backendToFrontendStatus: Record<string, BaseTask['status']> = {
  pending: 'todo',
  Pending: 'todo',
  'in progress': 'in-progress',
  'In Progress': 'in-progress',
  completed: 'completed',
  Completed: 'completed',
};

const frontendToBackendStatus: Record<BaseTask['status'], string> = {
  'todo': 'Pending',
  'in-progress': 'In Progress',
  'review': 'In Progress',
  'completed': 'Completed',
  'cancelled': 'Completed',
};

const mapBackendTaskToFrontend = (task: BackendTask): TaskWithPassMeta => {
  const nowIso = new Date().toISOString();
  const createdAt = task.created_at ?? nowIso;
  const updatedAt = task.updated_at ?? createdAt;
  const deadlineIso = task.due_date ? new Date(task.due_date).toISOString() : '';
  const priority = backendToFrontendPriority[task.priority ?? 'Medium'] ?? 'medium';
  const status = backendToFrontendStatus[task.status ?? 'Pending'] ?? 'todo';
  const assignedTo = task.assigned_to !== undefined && task.assigned_to !== null
    ? [String(task.assigned_to)]
    : [];
  const assignedBy = task.assigned_by !== undefined && task.assigned_by !== null
    ? String(task.assigned_by)
    : '';
  const lastPassedBy = task.last_passed_by !== undefined && task.last_passed_by !== null ? String(task.last_passed_by) : undefined;
  const lastPassedTo = task.last_passed_to !== undefined && task.last_passed_to !== null ? String(task.last_passed_to) : undefined;
  const lastPassedAt = task.last_passed_at ? new Date(task.last_passed_at).toISOString() : undefined;

  return {
    id: String(task.task_id),
    title: task.title,
    description: task.description ?? '',
    assignedTo,
    assignedBy,
    priority,
    status,
    deadline: deadlineIso,
    startDate: createdAt,
    completedDate: status === 'completed' ? updatedAt : undefined,
    tags: [],
    progress: 0,
    createdAt,
    updatedAt,
    lastPassedBy,
    lastPassedTo,
    lastPassNote: task.last_pass_note ?? undefined,
    lastPassedAt,
  };
};

const formatDisplayDate = (date?: string | null) => {
  if (!date) return 'No deadline';
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return 'No deadline';
  return format(parsed, 'MMM dd, yyyy');
};

const formatDateForInput = (date?: string | null) => {
  if (!date) return '';
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return '';
  const year = parsed.getFullYear();
  const month = `${parsed.getMonth() + 1}`.padStart(2, '0');
  const day = `${parsed.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const formatRoleLabel = (role?: UserRole) => {
  switch (role) {
    case 'admin':
      return 'Admin';
    case 'hr':
      return 'HR';
    case 'manager':
      return 'Manager';
    case 'team_lead':
      return 'Team Lead';
    case 'employee':
      return 'Employee';
    default:
      return undefined;
  }
};

const TaskManagement: React.FC = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const { toast } = useToast();
  const { addNotification } = useNotifications();
  const [tasks, setTasks] = useState<TaskWithPassMeta[]>([]);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskWithPassMeta | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [taskOwnershipFilter, setTaskOwnershipFilter] = useState<'all' | 'received' | 'created'>('received');
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    assignedTo: [] as string[],
    priority: 'medium' as BaseTask['priority'],
    deadline: '',
    department: '',
    employeeId: '',
  });
  const [departments, setDepartments] = useState<string[]>([]);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskWithPassMeta | null>(null);
  const [editTaskForm, setEditTaskForm] = useState({
    title: '',
    description: '',
    assignedTo: '',
    deadline: '',
  });
  const [isUpdatingTask, setIsUpdatingTask] = useState(false);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [isPassDialogOpen, setIsPassDialogOpen] = useState(false);
  const [passTaskTarget, setPassTaskTarget] = useState<TaskWithPassMeta | null>(null);
  const [passAssignee, setPassAssignee] = useState('');
  const [passNote, setPassNote] = useState('');
  const [isPassingTask, setIsPassingTask] = useState(false);
  const [taskHistory, setTaskHistory] = useState<Record<string, TaskHistoryEntry[]>>({});
  const [isFetchingHistory, setIsFetchingHistory] = useState<string | null>(null);

  // Export states
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv'>('pdf');
  const [exportDateRange, setExportDateRange] = useState<'1month' | '3months' | '6months' | 'custom' | 'all'>('all');
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [exportUserFilter, setExportUserFilter] = useState<string>('all');
  const [isExporting, setIsExporting] = useState(false);

  const isCreateDisabled = !newTask.title.trim() || !newTask.description.trim() || !newTask.assignedTo.length || isSubmitting;

  const userId = useMemo(() => {
    if (user?.id === undefined || user?.id === null) return null;
    return String(user.id);
  }, [user?.id]);

  const [authToken, setAuthToken] = useState<string>(() => {
    const storedToken = localStorage.getItem('token') || '';
    if (!storedToken) return '';
    return storedToken.startsWith('Bearer ') ? storedToken : `Bearer ${storedToken}`;
  });

  useEffect(() => {
    if (user?.role === 'admin') {
      setTaskOwnershipFilter('created');
    } else {
      setTaskOwnershipFilter((prev) =>
        prev === 'received' || prev === 'created' ? prev : 'received'
      );
    }
  }, [user?.role]);

  useEffect(() => {
    const storedToken = localStorage.getItem('token') || '';
    if (!storedToken) {
      setAuthToken('');
      return;
    }
    setAuthToken(storedToken.startsWith('Bearer ') ? storedToken : `Bearer ${storedToken}`);
  }, [user?.id]);

  const authorizedHeaders = useMemo(() => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (authToken) {
      headers.Authorization = authToken;
    }

    return headers;
  }, [authToken]);

  const fetchAndStoreHistory = useCallback(async (taskId: string) => {
    if (!authToken) return;
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/history`, {
        headers: authorizedHeaders,
      });
      if (!response.ok) {
        throw new Error(`Failed to load history (${response.status})`);
      }
      const data: TaskHistoryEntry[] = await response.json();
      setTaskHistory((prev) => ({ ...prev, [taskId]: data }));
    } catch (error) {
      console.error('Failed to fetch task history', error);
    }
  }, [authToken, authorizedHeaders]);

  useEffect(() => {
    if (!selectedTask) return;
    const alreadyLoaded = taskHistory[selectedTask.id];
    if (!alreadyLoaded && authToken) {
      setIsFetchingHistory(selectedTask.id);
      fetchAndStoreHistory(selectedTask.id).finally(() => setIsFetchingHistory(null));
    }
  }, [authToken, fetchAndStoreHistory, selectedTask, taskHistory]);

  const fetchEmployees = useCallback(async () => {
    if (!authToken) {
      toast({
        title: 'Authentication required',
        description: 'Please log in again to load employees.',
        variant: 'destructive',
      });
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/employees`, {
        headers: authorizedHeaders,
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch employees: ${response.status}`);
      }
      const data: BackendEmployee[] = await response.json();
      const formatted = data.map((emp) => ({
        userId: String(emp.user_id),
        employeeId: emp.employee_id ? String(emp.employee_id) : '',
        name: emp.name,
        email: emp.email,
        department: emp.department ?? undefined,
        role: normalizeRole(emp.role),
      }));
      setEmployees(formatted);

      const uniqueDepartments = new Set<string>();
      formatted.forEach((emp) => {
        if (emp.department) uniqueDepartments.add(emp.department);
      });
      if (user?.department) uniqueDepartments.add(user.department);
      setDepartments(Array.from(uniqueDepartments));
    } catch (error) {
      console.error('Failed to fetch employees', error);
      toast({
        title: 'Employee fetch failed',
        description: 'Unable to load employees from server.',
        variant: 'destructive',
      });
    }
  }, [authToken, authorizedHeaders, toast, user?.department]);

  const fetchTasks = useCallback(async () => {
    if (!userId) return;
    if (!authToken) {
      setTasks([]);
      toast({
        title: 'Authentication required',
        description: 'Please log in again to load your tasks.',
        variant: 'destructive',
      });
      return;
    }
    setIsLoadingTasks(true);
    try {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        headers: authorizedHeaders,
      });
      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('token');
          setAuthToken('');
          toast({
            title: 'Session expired',
            description: 'Please log in again to continue.',
            variant: 'destructive',
          });
          return;
        }
        throw new Error(`Failed to fetch tasks: ${response.status}`);
      }
      const data: BackendTask[] = await response.json();
      const converted = data.map(mapBackendTaskToFrontend);
      setTasks(converted);
      setTaskHistory({});
      await Promise.all(converted.map((task) => fetchAndStoreHistory(task.id)));
    } catch (error) {
      console.error('Failed to fetch tasks', error);
      toast({
        title: 'Task fetch failed',
        description: 'Unable to load tasks from server.',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingTasks(false);
    }
  }, [authToken, authorizedHeaders, fetchAndStoreHistory, toast, userId]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Check if user can assign tasks to others
  const canAssignTasks = () => Boolean(userId);

  const extendedEmployees = useMemo(() => {
    if (!userId || !user) return employees;
    const exists = employees.some((emp) => emp.userId === userId);
    if (exists) return employees;
    return [
      ...employees,
      {
        userId,
        employeeId: '',
        name: user.name,
        email: user.email,
        department: user.department || undefined,
        role: user.role,
      },
    ];
  }, [employees, user, userId]);

  const assignableEmployees = useMemo(() => {
    if (!user || !userId) return [];

    return extendedEmployees.filter((emp) => {
      if (emp.userId === userId) return true;

      const sameDepartment = !user.department || !emp.department || emp.department === user.department;

      switch (user.role) {
        case 'admin':
          return ['hr', 'manager'].includes(emp.role);
        case 'hr':
          return sameDepartment && ['manager', 'team_lead', 'employee'].includes(emp.role);
        case 'manager':
          return sameDepartment && ['team_lead', 'employee'].includes(emp.role);
        case 'team_lead':
          return sameDepartment && emp.role === 'employee';
        case 'employee':
          return false;
        default:
          return false;
      }
    });
  }, [extendedEmployees, user, userId]);

  const passEligibleEmployees = useMemo(() => {
    if (!user || !userId) return [] as EmployeeSummary[];
    const currentIndex = ROLE_ORDER.indexOf(user.role);
    return extendedEmployees.filter((emp) => {
      if (emp.userId === userId) return false;
      const targetIndex = ROLE_ORDER.indexOf(emp.role);
      if (targetIndex === -1) return false;
      if (targetIndex <= currentIndex) return false;
      if (user.role !== 'admin' && user.department && emp.department && emp.department !== user.department) {
        return false;
      }
      return true;
    });
  }, [extendedEmployees, user, userId]);

  const assignableDepartments = useMemo(() => {
    if (!user || !userId) return departments;
    if (user.role === 'admin') return departments;
    if (!user.department) return departments;
    return departments.filter((dept) => dept === user.department);
  }, [departments, user, userId]);

  const employeesById = useMemo(() => {
    const map = new Map<string, EmployeeSummary>();
    employees.forEach((emp) => {
      map.set(emp.userId, emp);
    });
    if (user && userId && !map.has(userId)) {
      map.set(userId, {
        userId,
        employeeId: '',
        name: user.name,
        email: user.email,
        department: user.department || undefined,
        role: user.role,
      });
    }
    return map;
  }, [employees, user, userId]);

  const getAssigneeLabel = useCallback((assigneeId: string) => {
    if (!assigneeId) return 'Self';
    if (userId && assigneeId === userId) {
      return user?.name || 'Self';
    }
    const assignee = employeesById.get(assigneeId);
    if (assignee) {
      const identifier = assignee.employeeId || assignee.email;
      return `${assignee.name}${identifier ? ` (${identifier})` : ''}`;
    }
    return assigneeId;
  }, [employeesById, user, userId]);

  const getAssignedByInfo = useCallback((assignedById: string) => {
    if (!assignedById) {
      return { name: 'Unknown', roleLabel: undefined };
    }

    if (userId && assignedById === userId) {
      return {
        name: user?.name || 'Self',
        roleLabel: formatRoleLabel(user?.role),
      };
    }

    const assigner = employeesById.get(assignedById);
    if (assigner) {
      return {
        name: assigner.name,
        roleLabel: formatRoleLabel(assigner.role),
      };
    }

    return {
      name: `User #${assignedById}`,
      roleLabel: undefined,
    };
  }, [employeesById, user?.name, user?.role, userId]);

  useEffect(() => {
    if (!user || !userId || !isCreateDialogOpen) return;
    if (!newTask.assignedTo.length) {
      setNewTask((prev) => ({
        ...prev,
        assignedTo: [userId],
        department: user.department || prev.department,
      }));
    }
  }, [isCreateDialogOpen, newTask.assignedTo.length, user, userId]);

  useEffect(() => {
    if (!user || !userId) return;
    const currentAssigneeId = newTask.assignedTo[0];
    const assignee = currentAssigneeId ? employeesById.get(currentAssigneeId) : null;
    const nextDepartment = assignee?.department || user.department || '';
    const nextEmployeeId = assignee?.employeeId || '';

    if (newTask.department !== nextDepartment || newTask.employeeId !== nextEmployeeId) {
      setNewTask((prev) => ({
        ...prev,
        department: nextDepartment,
        employeeId: nextEmployeeId,
      }));
    }
  }, [employeesById, newTask.assignedTo, newTask.department, newTask.employeeId, user, userId]);

  // Filter tasks based on search and status
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      const matchesSearch = task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            task.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = filterStatus === 'all' || task.status === filterStatus;

      const isVisible = userId && user ? (
        task.assignedBy === userId ||
        task.assignedTo.includes(userId) ||
        user.role === 'admin'
      ) : false;

      return matchesSearch && matchesStatus && Boolean(isVisible);
    });
  }, [filterStatus, searchQuery, tasks, user, userId]);

  const filteredReceivedTasks = useMemo(() => {
    if (!userId) return [] as TaskWithPassMeta[];
    return filteredTasks.filter((task) => task.assignedTo.includes(userId));
  }, [filteredTasks, userId]);

  const filteredCreatedTasks = useMemo(() => {
    if (!userId) return [] as TaskWithPassMeta[];
    return filteredTasks.filter((task) => task.assignedBy === userId);
  }, [filteredTasks, userId]);

  const visibleTasks = useMemo(() => {
    if (taskOwnershipFilter === 'all') {
      return filteredTasks;
    }

    if (taskOwnershipFilter === 'created') {
      return filteredCreatedTasks;
    }

    return filteredReceivedTasks;
  }, [filteredCreatedTasks, filteredReceivedTasks, filteredTasks, taskOwnershipFilter]);

  const selectedTaskAssignerInfo = useMemo(() => {
    if (!selectedTask) return null;
    return getAssignedByInfo(selectedTask.assignedBy);
  }, [getAssignedByInfo, selectedTask]);

  const selectedTaskHistory = useMemo(() => {
    if (!selectedTask) return [];
    return taskHistory[selectedTask.id] ?? [];
  }, [selectedTask, taskHistory]);

  // Create new task
  const canAssignToSelection = useMemo(() => {
    if (!user || !userId) return [];
    return assignableEmployees;
  }, [assignableEmployees, user, userId]);

  const departmentOptions = useMemo(() => {
    const sanitized = assignableDepartments.filter((dept) => dept && dept.trim().length > 0);
    if (sanitized.length) return sanitized;
    if (user?.department) return [user.department];
    return [];
  }, [assignableDepartments, user?.department]);

  const handleCreateTask = async () => {
    if (!user || !userId) return;

    const assignedEmployee = newTask.assignedTo[0] || userId;
    const selectedEmployee = assignableEmployees.find((emp) => emp.userId === assignedEmployee || emp.email === assignedEmployee);
    const assignedToIdRaw = selectedEmployee?.userId ?? userId;
    const assignedByIdRaw = userId;

    const assignedToBackend = Number(assignedToIdRaw);
    const assignedByBackend = Number(assignedByIdRaw);

    if (!Number.isFinite(assignedToBackend) || !Number.isFinite(assignedByBackend)) {
      toast({
        title: 'Invalid assignee',
        description: 'Unable to determine assignee identifiers. Please ensure the selected user exists and try again.',
        variant: 'destructive',
      });
      return;
    }

    const payload = {
      title: newTask.title,
      description: newTask.description,
      priority: frontendToBackendPriority[newTask.priority],
      due_date: newTask.deadline || null,
      assigned_to: assignedToBackend,
      assigned_by: assignedByBackend,
    };

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: authorizedHeaders,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = Array.isArray(errorData?.detail)
          ? errorData.detail.map((item) => (typeof item === 'string' ? item : item.msg || JSON.stringify(item))).join(', ')
          : typeof errorData?.detail === 'string'
            ? errorData.detail
            : JSON.stringify(errorData || {});
        throw new Error(detail || `Failed to create task (${response.status})`);
      }

      const createdTask: BackendTask = await response.json();
      const convertedTask = mapBackendTaskToFrontend(createdTask);

      setTasks((prev) => [...prev, convertedTask]);

      if (convertedTask.assignedTo[0] && userId && convertedTask.assignedTo[0] !== userId) {
        addNotification({
          title: 'New Task Assigned',
          message: `${user.name} assigned you a new task: "${convertedTask.title}"`,
          type: 'task',
          metadata: {
            taskId: convertedTask.id,
            requesterId: user.id,
            requesterName: user.name,
          }
        });
      }

      toast({
        title: 'Task Created',
        description: `Task "${convertedTask.title}" has been created successfully.`,
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
    } catch (err: unknown) {
      console.error('Failed to create task', err);
      const message = err instanceof Error ? err.message : 'Unable to create task. Please try again.';
      toast({
        title: 'Task creation failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const openPassDialog = useCallback((task: TaskWithPassMeta) => {
    setPassTaskTarget(task);
    const eligible = passEligibleEmployees;
    const fallbackAssignee = eligible.find((emp) => emp.userId === task.assignedTo[0]);
    if (fallbackAssignee) {
      setPassAssignee(fallbackAssignee.userId);
    } else if (eligible.length > 0) {
      setPassAssignee(eligible[0].userId);
    } else {
      setPassAssignee('');
    }
    setPassNote('');
    setIsPassDialogOpen(true);
  }, [passEligibleEmployees]);

  const closePassDialog = useCallback(() => {
    setIsPassDialogOpen(false);
    setPassTaskTarget(null);
    setPassAssignee('');
    setPassNote('');
    setIsPassingTask(false);
  }, []);

  const handlePassTask = useCallback(async () => {
    if (!passTaskTarget || !authToken) {
      toast({
        title: 'Unable to pass task',
        description: 'Authentication missing or task not selected.',
        variant: 'destructive',
      });
      return;
    }

    if (!passAssignee) {
      toast({
        title: 'Select assignee',
        description: 'Please choose a team member to pass the task to.',
        variant: 'destructive',
      });
      return;
    }

    setIsPassingTask(true);
    try {
      const payload = {
        new_assignee_id: Number(passAssignee),
        note: passNote.trim() || undefined,
      };

      const response = await fetch(`${API_BASE_URL}/tasks/${passTaskTarget.id}/pass`, {
        method: 'POST',
        headers: authorizedHeaders,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail ?? `Failed to pass task (${response.status})`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }

      const updatedTask: BackendTask = await response.json();
      const converted = mapBackendTaskToFrontend(updatedTask);
      setTasks((prev) => prev.map((task) => (task.id === converted.id ? converted : task)));
      setSelectedTask((prev) => (prev && prev.id === converted.id ? converted : prev));

      await fetchAndStoreHistory(converted.id);

      toast({
        title: 'Task passed successfully',
        description: `Task is now assigned to ${getAssigneeLabel(converted.assignedTo[0] || '')}.`,
      });

      closePassDialog();
    } catch (error) {
      console.error('Failed to pass task', error);
      const message = error instanceof Error ? error.message : 'Unable to pass the task. Please try again.';
      toast({
        title: 'Task pass failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsPassingTask(false);
    }
  }, [authToken, authorizedHeaders, closePassDialog, fetchAndStoreHistory, getAssigneeLabel, passAssignee, passNote, passTaskTarget, toast]);

  const resetEditState = useCallback(() => {
    setIsEditDialogOpen(false);
    setEditingTask(null);
    setEditTaskForm({
      title: '',
      description: '',
      assignedTo: '',
      deadline: '',
    });
    setIsUpdatingTask(false);
  }, []);

  const handleEditClick = useCallback((task: TaskWithPassMeta) => {
    setEditingTask(task);
    setEditTaskForm({
      title: task.title,
      description: task.description,
      assignedTo: task.assignedTo[0] || '',
      deadline: formatDateForInput(task.deadline),
    });
    setIsEditDialogOpen(true);
  }, []);

  const handleUpdateTask = useCallback(async () => {
    if (!editingTask) return;
    if (!authToken) {
      toast({
        title: 'Authentication required',
        description: 'Please log in again to update tasks.',
        variant: 'destructive',
      });
      return;
    }

    const trimmedTitle = editTaskForm.title.trim();
    const trimmedDescription = editTaskForm.description.trim();
    if (!trimmedTitle) {
      toast({
        title: 'Title required',
        description: 'Task title cannot be empty.',
        variant: 'destructive',
      });
      return;
    }
    if (!trimmedDescription) {
      toast({
        title: 'Description required',
        description: 'Task description cannot be empty.',
        variant: 'destructive',
      });
      return;
    }

    const currentAssignee = editingTask.assignedTo[0] || '';
    const nextAssignee = editTaskForm.assignedTo || currentAssignee;
    if (!nextAssignee) {
      toast({
        title: 'Assignee required',
        description: 'Please choose who the task should be assigned to.',
        variant: 'destructive',
      });
      return;
    }

    const assignedToNumber = Number(nextAssignee);
    if (!Number.isFinite(assignedToNumber)) {
      toast({
        title: 'Invalid assignee',
        description: 'Unable to determine the selected assignee.',
        variant: 'destructive',
      });
      return;
    }

    const payload: Record<string, unknown> = {};
    if (trimmedTitle !== editingTask.title) {
      payload.title = trimmedTitle;
    }
    if (trimmedDescription !== editingTask.description) {
      payload.description = trimmedDescription;
    }
    if (nextAssignee !== currentAssignee) {
      payload.assigned_to = assignedToNumber;
    }

    const originalDeadline = editingTask.deadline ? formatDateForInput(editingTask.deadline) : '';
    if (editTaskForm.deadline !== originalDeadline) {
      payload.due_date = editTaskForm.deadline || null;
    }

    if (Object.keys(payload).length === 0) {
      toast({
        title: 'No changes detected',
        description: 'Update at least one field before saving.',
        variant: 'default',
      });
      return;
    }

    setIsUpdatingTask(true);
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${editingTask.id}`, {
        method: 'PUT',
        headers: authorizedHeaders,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail ?? `Failed to update task (${response.status})`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }

      const updatedTask: BackendTask = await response.json();
      const converted = mapBackendTaskToFrontend(updatedTask);
      setTasks((prev) => prev.map((task) => (task.id === converted.id ? converted : task)));
      setSelectedTask((prev) => (prev && prev.id === converted.id ? converted : prev));

      await fetchAndStoreHistory(converted.id);

      toast({
        title: 'Task updated',
        description: `Task "${converted.title}" has been updated successfully.`,
      });

      resetEditState();
    } catch (error) {
      console.error('Failed to update task', error);
      const message = error instanceof Error ? error.message : 'Unable to update the task. Please try again.';
      toast({
        title: 'Task update failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setIsUpdatingTask(false);
    }
  }, [authToken, authorizedHeaders, editTaskForm.deadline, editTaskForm.description, editTaskForm.assignedTo, editTaskForm.title, editingTask, fetchAndStoreHistory, resetEditState, toast]);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    if (!authToken) {
      toast({
        title: 'Authentication required',
        description: 'Please log in again to delete tasks.',
        variant: 'destructive',
      });
      return;
    }

    const confirmDelete = window.confirm('Are you sure you want to delete this task?');
    if (!confirmDelete) return;

    setDeletingTaskId(taskId);
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: authorizedHeaders,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail ?? `Failed to delete task (${response.status})`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }

      setTasks((prev) => prev.filter((task) => task.id !== taskId));
      setSelectedTask((prev) => (prev && prev.id === taskId ? null : prev));
      setTaskHistory((prev) => {
        if (!(taskId in prev)) return prev;
        const next = { ...prev };
        delete next[taskId];
        return next;
      });

      toast({
        title: 'Task deleted',
        description: 'The task has been removed successfully.',
      });
    } catch (error) {
      console.error('Failed to delete task', error);
      const message = error instanceof Error ? error.message : 'Unable to delete the task. Please try again.';
      toast({
        title: 'Task deletion failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setDeletingTaskId(null);
    }
  }, [authToken, authorizedHeaders, toast]);

  // Update task status
  const updateTaskStatus = async (taskId: string, newStatus: BaseTask['status']) => {
    setUpdatingTaskId(taskId);
    try {
      const backendStatus = frontendToBackendStatus[newStatus];
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/status?status=${encodeURIComponent(backendStatus)}`, {
        method: 'PUT',
        headers: authorizedHeaders,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update status (${response.status})`);
      }

      const updatedTask: BackendTask = await response.json();
      const convertedTask = mapBackendTaskToFrontend(updatedTask);

      setTasks((prev) => prev.map((task) => (task.id === taskId ? convertedTask : task)));

      await fetchAndStoreHistory(convertedTask.id);

      toast({
        title: 'Task status updated',
        description: `Task marked as ${newStatus.replace('-', ' ')}`,
      });
    } catch (err: unknown) {
      console.error('Failed to update task status', err);
      const message = err instanceof Error ? err.message : 'Unable to update task status. Please try again.';
      toast({
        title: 'Status update failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setUpdatingTaskId(null);
    }
  };

  // Get status color
  const getStatusColor = (status: BaseTask['status']) => {
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
  const getPriorityColor = (priority: BaseTask['priority']) => {
    switch (priority) {
      case 'low': return 'bg-green-100 text-green-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'urgent': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Export functions
  const getFilteredTasksForExport = useCallback(() => {
    let filteredTasks = [...tasks];
    
    // Apply date range filter
    if (exportDateRange !== 'all') {
      const now = new Date();
      let startDate: Date;
      
      switch (exportDateRange) {
        case '1month':
          startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
          break;
        case '3months':
          startDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
          break;
        case '6months':
          startDate = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
          break;
        case 'custom':
          if (exportStartDate) {
            startDate = new Date(exportStartDate);
          } else {
            startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
          }
          break;
        default:
          startDate = new Date(now.getFullYear(), 0, 1);
      }
      
      const endDate = exportEndDate ? new Date(exportEndDate) : new Date();
      filteredTasks = filteredTasks.filter(task => {
        const taskDate = new Date(task.createdAt);
        return taskDate >= startDate && taskDate <= endDate;
      });
    }
    
    // Apply user filter
    if (exportUserFilter !== 'all') {
      filteredTasks = filteredTasks.filter(task => 
        task.assignedTo.includes(exportUserFilter) || 
        task.assignedBy === exportUserFilter
      );
    }
    
    // Apply department filter for non-admin users
    if (user?.role !== 'admin' && user?.department) {
      filteredTasks = filteredTasks.filter(task => {
        const assignee = employeesById.get(task.assignedTo[0] || '');
        const assigner = employeesById.get(task.assignedBy);
        return (assignee?.department === user.department) || (assigner?.department === user.department);
      });
    }
    
    return filteredTasks;
  }, [tasks, exportDateRange, exportStartDate, exportEndDate, exportUserFilter, user, employeesById]);

  const exportToCSV = useCallback(() => {
    const filteredTasks = getFilteredTasksForExport();
    
    const headers = [
      'Task ID',
      'Title',
      'Description',
      'Status',
      'Priority',
      'Assigned By',
      'Assigned To',
      'Created Date',
      'Due Date',
      'Completed Date',
      'Department',
      'Last Passed By',
      'Last Passed To',
      'Last Pass Note'
    ];
    
    const csvData = filteredTasks.map(task => {
      const assignee = employeesById.get(task.assignedTo[0] || '');
      const assigner = employeesById.get(task.assignedBy);
      const lastPassedBy = task.lastPassedBy ? employeesById.get(task.lastPassedBy) : null;
      const lastPassedTo = task.lastPassedTo ? employeesById.get(task.lastPassedTo) : null;
      
      return [
        task.id,
        `"${task.title.replace(/"/g, '""')}"`,
        `"${task.description.replace(/"/g, '""')}"`,
        task.status.replace('-', ' ').toUpperCase(),
        task.priority.toUpperCase(),
        assigner?.name || 'Unknown',
        assignee?.name || 'Unknown',
        task.createdAt ? format(new Date(task.createdAt), 'MMM dd, yyyy HH:mm') : '',
        task.deadline ? format(new Date(task.deadline), 'MMM dd, yyyy') : '',
        task.completedDate ? format(new Date(task.completedDate), 'MMM dd, yyyy HH:mm') : '',
        assignee?.department || assigner?.department || 'Unknown',
        lastPassedBy?.name || '',
        lastPassedTo?.name || '',
        `"${(task.lastPassNote || '').replace(/"/g, '""')}"`
      ];
    });
    
    const csvContent = [headers, ...csvData].map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    const dateRange = exportDateRange === 'custom' 
      ? `${exportStartDate || 'start'}_${exportEndDate || 'end'}`
      : exportDateRange;
    const userFilter = exportUserFilter !== 'all' ? `_user_${exportUserFilter}` : '';
    
    link.setAttribute('href', url);
    link.setAttribute('download', `task_report_${dateRange}${userFilter}_${format(new Date(), 'yyyy-MM-dd')}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [getFilteredTasksForExport, employeesById, exportDateRange, exportStartDate, exportEndDate, exportUserFilter]);

  const exportToPDF = useCallback(async () => {
    const filteredTasks = getFilteredTasksForExport();
    
    // Simple PDF export using window.print() styled for printing
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      toast({
        title: 'Export Failed',
        description: 'Please allow popups for this site to export PDF.',
        variant: 'destructive',
      });
      return;
    }
    
    const dateRange = exportDateRange === 'custom' 
      ? `${exportStartDate || 'start'} - ${exportEndDate || 'end'}`
      : exportDateRange === 'all' ? 'All Time' : exportDateRange;
    const userFilter = exportUserFilter !== 'all' 
      ? employeesById.get(exportUserFilter)?.name || 'Unknown User'
      : 'All Users';
    
    const tableRows = filteredTasks.map(task => {
      const assignee = employeesById.get(task.assignedTo[0] || '');
      const assigner = employeesById.get(task.assignedBy);
      const lastPassedBy = task.lastPassedBy ? employeesById.get(task.lastPassedBy) : null;
      const lastPassedTo = task.lastPassedTo ? employeesById.get(task.lastPassedTo) : null;
      
      return `
        <tr>
          <td>${task.id}</td>
          <td>${task.title}</td>
          <td>${task.description.substring(0, 100)}${task.description.length > 100 ? '...' : ''}</td>
          <td><span class="status-${task.status}">${task.status.replace('-', ' ').toUpperCase()}</span></td>
          <td><span class="priority-${task.priority}">${task.priority.toUpperCase()}</span></td>
          <td>${assigner?.name || 'Unknown'}</td>
          <td>${assignee?.name || 'Unknown'}</td>
          <td>${task.createdAt ? format(new Date(task.createdAt), 'MMM dd, yyyy HH:mm') : ''}</td>
          <td>${task.deadline ? format(new Date(task.deadline), 'MMM dd, yyyy') : ''}</td>
          <td>${task.completedDate ? format(new Date(task.completedDate), 'MMM dd, yyyy HH:mm') : ''}</td>
          <td>${assignee?.department || assigner?.department || 'Unknown'}</td>
          <td>${lastPassedBy?.name || ''}</td>
          <td>${lastPassedTo?.name || ''}</td>
          <td>${task.lastPassNote || ''}</td>
        </tr>
      `;
    }).join('');
    
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Task Report</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #4F46E5; }
            .header-info { margin-bottom: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4F46E5; color: white; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .status-todo { background: #94a3b8; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .status-in-progress { background: #3b82f6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .status-completed { background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .priority-low { background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .priority-medium { background: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .priority-high { background: #ef4444; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            .priority-urgent { background: #dc2626; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
            @media print { body { margin: 10px; } }
          </style>
        </head>
        <body>
          <h1>Task Management Report</h1>
          <div class="header-info">
            <p><strong>Date Range:</strong> ${dateRange}</p>
            <p><strong>User Filter:</strong> ${userFilter}</p>
            <p><strong>Total Tasks:</strong> ${filteredTasks.length}</p>
            <p><strong>Generated on:</strong> ${format(new Date(), 'MMM dd, yyyy HH:mm')}</p>
          </div>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Description</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Assigned By</th>
                <th>Assigned To</th>
                <th>Created</th>
                <th>Due Date</th>
                <th>Completed</th>
                <th>Department</th>
                <th>Last Passed By</th>
                <th>Last Passed To</th>
                <th>Pass Note</th>
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </body>
      </html>
    `);
    
    printWindow.document.close();
    printWindow.focus();
    
    // Wait for the content to load before printing
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 500);
  }, [getFilteredTasksForExport, employeesById, exportDateRange, exportStartDate, exportEndDate, exportUserFilter]);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    
    try {
      if (exportFormat === 'csv') {
        exportToCSV();
      } else {
        await exportToPDF();
      }
      
      toast({
        title: 'Export Successful',
        description: `Task report exported as ${exportFormat.toUpperCase()}`,
      });
      
      setIsExportDialogOpen(false);
    } catch (error) {
      console.error('Export failed:', error);
      toast({
        title: 'Export Failed',
        description: 'Failed to export task report. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsExporting(false);
    }
  }, [exportFormat, exportToCSV, exportToPDF, toast]);

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
                      onValueChange={(value: BaseTask['priority']) => 
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
                
                <div className="space-y-2">
                  <Label htmlFor="assignTo" className="text-sm font-semibold flex items-center gap-2">
                    <User className="h-4 w-4 text-violet-600" />
                    Assign To
                  </Label>
                  <Select
                    value={newTask.assignedTo[0] || ''}
                    onValueChange={(value) =>
                      setNewTask({ ...newTask, assignedTo: value ? [value] : [] })
                    }
                  >
                    <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                      <SelectValue placeholder="Select assignee" />
                    </SelectTrigger>
                    <SelectContent className="border-2 shadow-xl">
                      {userId && user && (
                        <SelectItem value={userId} className="cursor-pointer">
                          {user.name} (Self)
                        </SelectItem>
                      )}
                      {canAssignToSelection
                        .filter((emp) => emp.userId !== userId)
                        .map((emp) => (
                          <SelectItem key={emp.userId} value={emp.userId} className="cursor-pointer">
                            {emp.name}
                            {emp.department ? ` • ${emp.department}` : ''}
                            {emp.employeeId ? ` (${emp.employeeId})` : ''}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="department" className="text-sm font-semibold flex items-center gap-2">
                      <Filter className="h-4 w-4 text-violet-600" />
                      Department
                    </Label>
                    <Select
                      value={newTask.department}
                      onValueChange={(value) => setNewTask({ ...newTask, department: value })}
                      disabled={!departmentOptions.length}
                    >
                      <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                        <SelectValue placeholder={departmentOptions.length ? 'Select department' : 'No department available'} />
                      </SelectTrigger>
                      <SelectContent className="border-2 shadow-xl">
                        {departmentOptions.map((dept) => (
                          <SelectItem key={dept} value={dept} className="cursor-pointer">
                            {dept}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="employeeId" className="text-sm font-semibold flex items-center gap-2">
                      <User className="h-4 w-4 text-violet-600" />
                      Employee ID
                    </Label>
                    <Input
                      id="employeeId"
                      value={newTask.employeeId}
                      readOnly
                      placeholder="Auto populated"
                      className="h-11 border-2 focus:ring-2 focus:ring-violet-500 transition-all bg-muted"
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
                    disabled={isCreateDisabled}
                    className="h-11 px-6 gap-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="h-5 w-5" />
                    {isSubmitting ? 'Creating...' : 'Create Task'}
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

              <div className="flex items-center gap-1 rounded-lg bg-muted/50 p-1">
                {user?.role !== 'admin' && (
                  <Button
                    size="sm"
                    variant={taskOwnershipFilter === 'received' ? 'default' : 'outline'}
                    onClick={() => setTaskOwnershipFilter('received')}
                    className={taskOwnershipFilter === 'received' ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-md' : ''}
                  >
                    Received
                  </Button>
                )}
                <Button
                  size="sm"
                  variant={taskOwnershipFilter === 'created' ? 'default' : 'outline'}
                  onClick={() => setTaskOwnershipFilter('created')}
                  className={taskOwnershipFilter === 'created' ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-md' : ''}
                >
                  Created
                </Button>
              </div>

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
              
              {/* Export Buttons */}
              {canAssignTasks() && (
                <div className="flex items-center gap-2 border-l border-gray-200 dark:border-gray-800 pl-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsExportDialogOpen(true)}
                    className="gap-2 h-10 bg-white dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:bg-violet-50 dark:hover:bg-violet-950"
                  >
                    <Download className="h-4 w-4" />
                    Export
                  </Button>
                </div>
              )}
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
                    <TableHead>Assigned By</TableHead>
                    <TableHead>Assigned To</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Deadline</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Pass</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingTasks ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                        Loading tasks...
                      </TableCell>
                    </TableRow>
                  ) : visibleTasks.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                        {user?.role !== 'admin' && taskOwnershipFilter === 'created'
                          ? 'No created tasks found'
                          : user?.role !== 'admin' && taskOwnershipFilter === 'received'
                            ? 'No received tasks found'
                            : 'No tasks found'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    visibleTasks.map((task) => {
                      const assignedByInfo = getAssignedByInfo(task.assignedBy);
                      const canManageTask = Boolean((user?.role === 'admin') || (userId && task.assignedBy === userId));
                      const isReceivedTask = Boolean(userId && task.assignedTo.includes(userId));
                      const canPassTask = isReceivedTask && task.assignedTo[0] === userId && passEligibleEmployees.length > 0;
                      const lastPassByLabel = task.lastPassedBy ? getAssigneeLabel(task.lastPassedBy) : null;
                      const lastPassToLabel = task.lastPassedTo ? getAssigneeLabel(task.lastPassedTo) : null;
                      const lastPassTimestamp = task.lastPassedAt ? format(new Date(task.lastPassedAt), 'MMM dd, yyyy HH:mm') : null;
                      return (
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
                              <UserCheck className="h-4 w-4 text-muted-foreground" />
                              <div className="flex flex-col">
                                <span className="text-sm font-medium">{assignedByInfo.name}</span>
                                {assignedByInfo.roleLabel && (
                                  <span className="text-xs text-muted-foreground">{assignedByInfo.roleLabel}</span>
                                )}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <User className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm">
                                {getAssigneeLabel(task.assignedTo[0] || '')}
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
                                {formatDisplayDate(task.deadline)}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={task.status}
                              onValueChange={(value: BaseTask['status']) => 
                                updateTaskStatus(task.id, value)
                              }
                              disabled={updatingTaskId === task.id}
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
                            {task.lastPassedBy && task.lastPassedTo ? (
                              <div className="flex flex-col gap-1 text-sm">
                                <div className="flex items-center gap-2">
                                  <Share2 className="h-3.5 w-3.5 text-violet-600" />
                                  <span>
                                    <span className="font-medium text-foreground">{lastPassByLabel}</span>
                                    <span className="text-muted-foreground"> → </span>
                                    <span className="font-medium text-foreground">{lastPassToLabel}</span>
                                  </span>
                                </div>
                                {task.lastPassNote && (
                                  <span className="text-xs italic text-muted-foreground">“{task.lastPassNote}”</span>
                                )}
                                {lastPassTimestamp && (
                                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {lastPassTimestamp}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedTask(task)}
                                className="hover:bg-violet-50 hover:text-violet-600 dark:hover:bg-violet-950"
                              >
                                View
                                <ChevronRight className="h-4 w-4 ml-1" />
                              </Button>
                              {canPassTask && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => openPassDialog(task)}
                                  className="flex items-center gap-1"
                                >
                                  <Share2 className="h-4 w-4" />
                                  Pass
                                </Button>
                              )}
                              {canManageTask && (
                                <>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleEditClick(task)}
                                    className="flex items-center gap-1"
                                  >
                                    <Pencil className="h-4 w-4" />
                                    Edit
                                  </Button>
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => handleDeleteTask(task.id)}
                                    disabled={deletingTaskId === task.id}
                                    className="flex items-center gap-1"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                    {deletingTaskId === task.id ? 'Deleting...' : 'Delete'}
                                  </Button>
                                </>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              {visibleTasks.map((task) => {
                const assignedByInfo = getAssignedByInfo(task.assignedBy);
                const canManageTask = Boolean((user?.role === 'admin') || (userId && task.assignedBy === userId));
                const isReceivedTask = Boolean(userId && task.assignedTo.includes(userId));
                const canPassTask = isReceivedTask && task.assignedTo[0] === userId && passEligibleEmployees.length > 0;
                const lastPassByLabel = task.lastPassedBy ? getAssigneeLabel(task.lastPassedBy) : null;
                const lastPassToLabel = task.lastPassedTo ? getAssigneeLabel(task.lastPassedTo) : null;
                return (
                  <Card
                    key={task.id}
                    className="border-0 shadow-md hover:shadow-xl transition-all duration-300 cursor-pointer transform hover:scale-105 bg-gradient-to-br from-white to-slate-50 dark:from-gray-900 dark:to-slate-900"
                    onClick={() => setSelectedTask(task)}
                  >
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
                    <CardContent className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <UserCheck className="h-4 w-4 text-muted-foreground" />
                        <div className="flex flex-col">
                          <span>{assignedByInfo.name}</span>
                          {assignedByInfo.roleLabel && (
                            <span className="text-xs text-muted-foreground">{assignedByInfo.roleLabel}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span>{getAssigneeLabel(task.assignedTo[0] || '')}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span>{formatDisplayDate(task.deadline)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`h-2 w-2 rounded-full ${getStatusColor(task.status)}`} />
                          <span className="text-sm capitalize">{task.status.replace('-', ' ')}</span>
                        </div>
                        {typeof task.progress === 'number' && (
                          <span className="text-sm text-muted-foreground">{task.progress}%</span>
                        )}
                      </div>
                      <div className="mt-4">
                        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Pass History
                        </div>
                        {task.lastPassedBy && task.lastPassedTo ? (
                          <div className="mt-2 p-3 rounded-lg border bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950/40 dark:to-purple-950/40 flex flex-col gap-2">
                            <div className="flex items-center gap-2 text-sm">
                              <Share2 className="h-4 w-4 text-violet-600" />
                              <span>
                                <span className="font-semibold text-foreground">{lastPassByLabel}</span>
                                <span className="text-muted-foreground"> → </span>
                                <span className="font-semibold text-foreground">{lastPassToLabel}</span>
                              </span>
                            </div>
                            {task.lastPassNote && (
                              <div className="text-xs italic text-muted-foreground">“{task.lastPassNote}”</div>
                            )}
                            {task.lastPassedAt && (
                              <div className="text-xs text-muted-foreground flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {format(new Date(task.lastPassedAt), 'MMM dd, yyyy HH:mm')}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="mt-2 text-xs text-muted-foreground">
                            No pass actions recorded yet.
                          </div>
                        )}
                      </div>
                      {canManageTask && (
                        <div className="flex items-center gap-2 pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleEditClick(task);
                            }}
                            className="flex items-center gap-1"
                          >
                            <Pencil className="h-4 w-4" />
                            Edit
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteTask(task.id);
                            }}
                            disabled={deletingTaskId === task.id}
                            className="flex items-center gap-1"
                          >
                            <Trash2 className="h-4 w-4" />
                            {deletingTaskId === task.id ? 'Deleting...' : 'Delete'}
                          </Button>
                        </div>
                      )}
                      {canPassTask && (
                        <div className="flex items-center gap-2 pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              openPassDialog(task);
                            }}
                            className="flex items-center gap-1"
                          >
                            <Share2 className="h-4 w-4" />
                            Pass Task
                          </Button>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pass Task Dialog */}
      <Dialog open={isPassDialogOpen} onOpenChange={(open) => {
        if (!open) {
          closePassDialog();
        } else {
          setIsPassDialogOpen(true);
        }
      }}>
        <DialogContent className="max-w-xl border-2 shadow-2xl">
          <DialogHeader className="pb-4 border-b bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950 dark:to-purple-950 -m-6 mb-0 p-6 rounded-t-lg">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
                <Share2 className="h-6 w-6 text-white" />
              </div>
              <div>
                <DialogTitle className="text-2xl font-bold">Pass Task</DialogTitle>
                <DialogDescription className="mt-1">
                  Reassign this task to a lower hierarchy member
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-5 mt-6">
            <div className="space-y-2">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <User className="h-4 w-4 text-violet-600" />
                Select Assignee
              </Label>
              <Select
                value={passAssignee}
                onValueChange={setPassAssignee}
              >
                <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                  <SelectValue placeholder="Choose team member" />
                </SelectTrigger>
                <SelectContent className="border-2 shadow-xl max-h-72 overflow-auto">
                  {passEligibleEmployees.length === 0 && (
                    <div className="py-3 px-4 text-sm text-muted-foreground">
                      No eligible team members found.
                    </div>
                  )}
                  {passEligibleEmployees.map((emp) => (
                      <SelectItem key={emp.userId} value={emp.userId} className="cursor-pointer">
                        {emp.name}
                        {emp.department ? ` • ${emp.department}` : ''}
                        {emp.employeeId ? ` (${emp.employeeId})` : ''}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <FileText className="h-4 w-4 text-violet-600" />
                Reason / Notes
              </Label>
              <Textarea
                value={passNote}
                onChange={(e) => setPassNote(e.target.value)}
                placeholder="Add context about why you're passing the task or partial progress made"
                rows={4}
                className="resize-none border-2 focus:ring-2 focus:ring-violet-500 transition-all"
              />
            </div>

            <div className="flex justify-end gap-3 pt-6 border-t mt-6">
              <Button
                variant="outline"
                onClick={closePassDialog}
                className="h-11 px-6 border-2 hover:bg-slate-50 dark:hover:bg-slate-900"
              >
                Cancel
              </Button>
              <Button
                onClick={handlePassTask}
                disabled={isPassingTask || !passAssignee}
                className="h-11 px-6 gap-2 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isPassingTask ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Passing...
                  </>
                ) : (
                  'Pass Task'
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditDialogOpen} onOpenChange={(open) => {
        if (!open) {
          resetEditState();
        } else {
          setIsEditDialogOpen(true);
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto border-2 shadow-2xl">
          <DialogHeader className="pb-4 border-b bg-gradient-to-r from-blue-50 to-slate-50 dark:from-blue-950 dark:to-slate-950 -m-6 mb-0 p-6 rounded-t-lg">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
                <Pencil className="h-6 w-6 text-white" />
              </div>
              <div>
                <DialogTitle className="text-2xl font-bold">Edit Task</DialogTitle>
                <DialogDescription className="mt-1">
                  Update task details and assignment
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-5 mt-6">
            <div className="space-y-2">
              <Label htmlFor="edit-title" className="text-sm font-semibold flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600"></div>
                Task Title <span className="text-red-500">*</span>
              </Label>
              <Input
                id="edit-title"
                value={editTaskForm.title}
                onChange={(e) => setEditTaskForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="Enter task title"
                className="h-11 border-2 focus:ring-2 focus:ring-blue-500 transition-all"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-description" className="text-sm font-semibold flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600"></div>
                Description <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="edit-description"
                value={editTaskForm.description}
                onChange={(e) => setEditTaskForm((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="Enter task description"
                rows={4}
                className="resize-none border-2 focus:ring-2 focus:ring-blue-500 transition-all"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-assignTo" className="text-sm font-semibold flex items-center gap-2">
                  <User className="h-4 w-4 text-blue-600" />
                  Assign To
                </Label>
                <Select
                  value={editTaskForm.assignedTo || ''}
                  onValueChange={(value) => setEditTaskForm((prev) => ({ ...prev, assignedTo: value }))}
                >
                  <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                    <SelectValue placeholder="Select assignee" />
                  </SelectTrigger>
                  <SelectContent className="border-2 shadow-xl">
                    {userId && user && (
                      <SelectItem value={userId} className="cursor-pointer">
                        {user.name} (Self)
                      </SelectItem>
                    )}
                    {assignableEmployees
                      .filter((emp) => emp.userId !== userId)
                      .map((emp) => (
                        <SelectItem key={emp.userId} value={emp.userId} className="cursor-pointer">
                          {emp.name}
                          {emp.department ? ` • ${emp.department}` : ''}
                          {emp.employeeId ? ` (${emp.employeeId})` : ''}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-deadline" className="text-sm font-semibold flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-blue-600" />
                  Deadline
                </Label>
                <Input
                  id="edit-deadline"
                  type="date"
                  value={editTaskForm.deadline}
                  onChange={(e) => setEditTaskForm((prev) => ({ ...prev, deadline: e.target.value }))}
                  className="h-11 border-2 focus:ring-2 focus:ring-blue-500 transition-all"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-6 border-t mt-6">
              <Button
                variant="outline"
                onClick={resetEditState}
                className="h-11 px-6 border-2 hover:bg-slate-50 dark:hover:bg-slate-900"
              >
                Cancel
              </Button>
              <Button
                onClick={handleUpdateTask}
                disabled={isUpdatingTask}
                className="h-11 px-6 gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUpdatingTask ? 'Updating...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Task Detail Dialog */}
      {selectedTask && (
        <Dialog open={Boolean(selectedTask)} onOpenChange={() => setSelectedTask(null)}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold">{selectedTask.title}</DialogTitle>
              <DialogDescription>
                Detailed view of task assignments and progress
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="details" className="mt-4">
              <TabsList className="grid grid-cols-3 gap-2 bg-muted/50">
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="activity">Activity</TabsTrigger>
                <TabsTrigger value="comments">Comments</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="mt-4">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 rounded-lg bg-gradient-to-r from-slate-50 to-gray-50 dark:from-slate-900 dark:to-gray-900 border">
                      <h4 className="font-semibold mb-3 flex items-center gap-2">
                        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                          <FileText className="h-4 w-4 text-white" />
                        </div>
                        Description
                      </h4>
                      <p className="text-muted-foreground leading-relaxed">{selectedTask.description}</p>
                    </div>

                    <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                      <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                        <UserCheck className="h-4 w-4 text-violet-600" />
                        Assigned By
                      </h4>
                      <p className="text-muted-foreground font-medium">
                        {selectedTaskAssignerInfo?.name || 'Unknown'}
                        {selectedTaskAssignerInfo?.roleLabel && (
                          <span className="block text-xs text-muted-foreground">{selectedTaskAssignerInfo.roleLabel}</span>
                        )}
                      </p>
                    </div>

                    <div className="p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-shadow">
                      <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                        <User className="h-4 w-4 text-violet-600" />
                        Assigned To
                      </h4>
                      <p className="text-muted-foreground font-medium">{getAssigneeLabel(selectedTask.assignedTo[0] || '')}</p>
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
                        {formatDisplayDate(selectedTask.deadline)}
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
                </div>
              </TabsContent>

              <TabsContent value="activity" className="mt-6">
                <div className="space-y-4">
                  {isFetchingHistory && selectedTask && isFetchingHistory === selectedTask.id ? (
                    <div className="flex justify-center py-8 text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                  ) : selectedTaskHistory.length === 0 ? (
                    <div className="text-center py-8">
                      <div className="h-16 w-16 rounded-full bg-gradient-to-br from-slate-100 to-gray-200 dark:from-slate-800 dark:to-gray-900 flex items-center justify-center mx-auto mb-3">
                        <Clock className="h-8 w-8 text-muted-foreground" />
                      </div>
                      <p className="text-sm text-muted-foreground">No history entries yet</p>
                    </div>
                  ) : (
                    selectedTaskHistory.map((entry) => {
                      const actor = employeesById.get(String(entry.user_id));
                      const actorName = actor?.name ?? (entry.user_id ? `User #${entry.user_id}` : 'Unknown');
                      const entryTime = format(new Date(entry.created_at), 'MMM dd, yyyy HH:mm');
                      const details = entry.details || {};

                      const renderDetails = () => {
                        if (!details) return null;
                        if (entry.action === 'passed') {
                          const from = details.from ? getAssigneeLabel(String(details.from)) : 'Unknown';
                          const to = details.to ? getAssigneeLabel(String(details.to)) : 'Unknown';
                          const toName = typeof details.to_name === 'string' ? details.to_name : null;
                          const note = typeof details.note === 'string' && details.note.trim().length > 0 ? details.note : null;
                          return (
                            <div className="text-sm text-muted-foreground space-y-1">
                              <div>From: <span className="font-medium text-foreground">{from}</span></div>
                              <div>To: <span className="font-medium text-foreground">{toName || to}</span></div>
                              {note && <div className="italic">"{note}"</div>}
                            </div>
                          );
                        }

                        if (entry.action === 'status_changed') {
                          const from = typeof details.from === 'string' ? details.from : 'Unknown';
                          const to = typeof details.to === 'string' ? details.to : 'Unknown';
                          return (
                            <div className="text-sm text-muted-foreground space-y-1">
                              <div>Status changed from <span className="font-medium text-foreground">{from}</span> to <span className="font-medium text-foreground">{to}</span></div>
                            </div>
                          );
                        }

                        if (entry.action === 'updated') {
                          const changes = details.changes as Record<string, { from: unknown; to: unknown }> | undefined;
                          if (!changes) return null;
                          return (
                            <div className="text-sm text-muted-foreground space-y-1">
                              {Object.entries(changes).map(([field, change]) => (
                                <div key={field}>
                                  <span className="font-medium text-foreground capitalize">{field.replace('_', ' ')}:</span> {String(change.from)} → {String(change.to)}
                                </div>
                              ))}
                            </div>
                          );
                        }

                        if (entry.action === 'created') {
                          return (
                            <div className="text-sm text-muted-foreground">
                              Task assigned to <span className="font-medium text-foreground">{getAssigneeLabel(String(details.assigned_to ?? ''))}</span>
                            </div>
                          );
                        }

                        return null;
                      };

                      const actionLabelMap: Record<string, string> = {
                        created: 'Task Created',
                        passed: 'Task Passed',
                        status_changed: 'Status Changed',
                        updated: 'Task Updated',
                      };

                      const actionLabel = actionLabelMap[entry.action] ?? entry.action;
                      const actionIcon = (() => {
                        switch (entry.action) {
                          case 'created':
                            return <PlayCircle className="h-6 w-6 text-white" />;
                          case 'passed':
                            return <Share2 className="h-6 w-6 text-white" />;
                          case 'status_changed':
                            return <RefreshCcw className="h-6 w-6 text-white" />;
                          case 'updated':
                            return <Pencil className="h-6 w-6 text-white" />;
                          default:
                            return <Clock className="h-6 w-6 text-white" />;
                        }
                      })();

                      const gradientClass = (() => {
                        switch (entry.action) {
                          case 'created':
                            return 'from-blue-500 to-indigo-600';
                          case 'passed':
                            return 'from-violet-500 to-purple-600';
                          case 'status_changed':
                            return 'from-amber-500 to-orange-600';
                          case 'updated':
                            return 'from-emerald-500 to-teal-600';
                          default:
                            return 'from-slate-500 to-gray-600';
                        }
                      })();

                      return (
                        <div
                          key={entry.id}
                          className="flex items-start gap-4 p-4 rounded-lg border bg-white dark:bg-gray-950 hover:shadow-md transition-all"
                        >
                          <div className={`h-12 w-12 rounded-xl bg-gradient-to-br ${gradientClass} flex items-center justify-center shadow-lg flex-shrink-0`}>
                            {actionIcon}
                          </div>
                          <div className="flex-1 space-y-2">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                              <p className="font-semibold text-lg">{actionLabel}</p>
                              <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <User className="h-3.5 w-3.5" />
                                {actorName}
                              </p>
                            </div>
                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                              <Clock className="h-3 w-3" />
                              {entryTime}
                            </p>
                            {renderDetails()}
                          </div>
                        </div>
                      );
                    })
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

      {/* Export Dialog */}
      <Dialog open={isExportDialogOpen} onOpenChange={setIsExportDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto border-2 shadow-2xl">
          <DialogHeader className="pb-4 border-b bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950 -m-6 mb-0 p-6 rounded-t-lg">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg">
                <Download className="h-6 w-6 text-white" />
              </div>
              <div>
                <DialogTitle className="text-2xl font-bold">Export Task Report</DialogTitle>
                <DialogDescription className="mt-1">
                  Generate and download task reports in various formats
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="space-y-6 mt-6">
            {/* Export Format */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gradient-to-r from-emerald-500 to-teal-600"></div>
                Export Format
              </Label>
              <div className="grid grid-cols-2 gap-3">
                <Button
                  variant={exportFormat === 'pdf' ? 'default' : 'outline'}
                  onClick={() => setExportFormat('pdf')}
                  className="gap-2 h-12 border-2"
                >
                  <FileDown className="h-4 w-4" />
                  PDF Report
                </Button>
                <Button
                  variant={exportFormat === 'csv' ? 'default' : 'outline'}
                  onClick={() => setExportFormat('csv')}
                  className="gap-2 h-12 border-2"
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  CSV Data
                </Button>
              </div>
            </div>

            {/* Date Range */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <Calendar className="h-4 w-4 text-emerald-600" />
                Date Range
              </Label>
              <Select value={exportDateRange} onValueChange={(value: any) => setExportDateRange(value)}>
                <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border-2 shadow-xl">
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="1month">Last 1 Month</SelectItem>
                  <SelectItem value="3months">Last 3 Months</SelectItem>
                  <SelectItem value="6months">Last 6 Months</SelectItem>
                  <SelectItem value="custom">Custom Range</SelectItem>
                </SelectContent>
              </Select>

              {exportDateRange === 'custom' && (
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div>
                    <Label htmlFor="start-date" className="text-xs font-medium">Start Date</Label>
                    <Input
                      id="start-date"
                      type="date"
                      value={exportStartDate}
                      onChange={(e) => setExportStartDate(e.target.value)}
                      className="h-10 border-2 mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="end-date" className="text-xs font-medium">End Date</Label>
                    <Input
                      id="end-date"
                      type="date"
                      value={exportEndDate}
                      onChange={(e) => setExportEndDate(e.target.value)}
                      className="h-10 border-2 mt-1"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* User Filter */}
            <div className="space-y-3">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <User className="h-4 w-4 text-emerald-600" />
                User Filter
              </Label>
              <Select value={exportUserFilter} onValueChange={setExportUserFilter}>
                <SelectTrigger className="h-11 border-2 bg-white dark:bg-gray-950">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border-2 shadow-xl max-h-72 overflow-auto">
                  <SelectItem value="all">All Users</SelectItem>
                  {extendedEmployees.map((emp) => (
                    <SelectItem key={emp.userId} value={emp.userId} className="cursor-pointer">
                      {emp.name}
                      {emp.department ? ` • ${emp.department}` : ''}
                      {emp.employeeId ? ` (${emp.employeeId})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Export Summary */}
            <div className="p-4 rounded-lg bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950 border">
              <h4 className="font-semibold mb-2">Export Summary</h4>
              <div className="text-sm text-muted-foreground space-y-1">
                <p>• Format: <span className="font-medium text-foreground">{exportFormat.toUpperCase()}</span></p>
                <p>• Date Range: <span className="font-medium text-foreground">
                  {exportDateRange === 'all' ? 'All Time' : 
                   exportDateRange === 'custom' ? `${exportStartDate || 'Not set'} - ${exportEndDate || 'Not set'}` :
                   `Last ${exportDateRange.replace('months', ' Months').replace('1month', '1 Month')}`}
                </span></p>
                <p>• User Filter: <span className="font-medium text-foreground">
                  {exportUserFilter === 'all' ? 'All Users' : 
                   employeesById.get(exportUserFilter)?.name || 'Unknown User'}
                </span></p>
                <p>• Total Tasks: <span className="font-medium text-foreground">{getFilteredTasksForExport().length}</span></p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-6 border-t">
              <Button
                variant="outline"
                onClick={() => setIsExportDialogOpen(false)}
                className="h-11 px-6 border-2 hover:bg-slate-50 dark:hover:bg-slate-900"
              >
                Cancel
              </Button>
              <Button
                onClick={handleExport}
                disabled={isExporting || getFilteredTasksForExport().length === 0}
                className="h-11 px-6 gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isExporting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    Export {exportFormat.toUpperCase()}
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TaskManagement;