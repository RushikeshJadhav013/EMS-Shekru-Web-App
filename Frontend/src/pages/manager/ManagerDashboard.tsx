import React from 'react';
import { useEffect, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Users,
  Clock,
  CalendarDays,
  ClipboardList,
  TrendingUp,
  AlertCircle,
  ChevronRight,
  Activity,
  Target,
  CheckCircle2,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '@/lib/api';

interface TeamMemberStatus {
  name: string;
  status: 'present' | 'on-leave' | 'absent';
  task: string;
  progress: number;
  userId: string;
}

const ManagerDashboard: React.FC = () => {
  const { t } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] = useState({
    teamMembers: 0,
    presentToday: 0,
    onLeave: 0,
    activeTasks: 0,
    completedTasks: 0,
    pendingApprovals: 0,
    teamPerformancePercent: 0,
    overdueItems: 0,
  });

  const [teamActivities, setTeamActivities] = useState<{id: string; type: string; user: string; time: string; description: string; status: string;}[]>([]);
  const [teamPerformance, setTeamPerformance] = useState<{team: string; lead: string; members: number; completion: number;}[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMemberStatus[]>([]);
  const [isLoadingTeamMembers, setIsLoadingTeamMembers] = useState(false);

  useEffect(() => {
    apiService.getManagerDashboard()
      .then((data) => {
        setStats({
          teamMembers: data.teamMembers || 0,
          presentToday: data.presentToday || 0,
          onLeave: data.onLeave || 0,
          activeTasks: data.activeTasks || 0,
          completedTasks: data.completedTasks || 0,
          pendingApprovals: data.pendingApprovals || 0,
          teamPerformancePercent: data.teamPerformancePercent || 0,
          overdueItems: data.overdueItems || 0,
        });
        setTeamActivities(data.teamActivities || []);
        setTeamPerformance(data.teamPerformance || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fetchTeamMembersWithStatus = async () => {
      if (!user?.department) return;
      
      setIsLoadingTeamMembers(true);
      try {
        // Fetch all employees
        const employees = await apiService.getEmployees();
        
        // Filter by department and exclude managers/admins
        const departmentEmployees = employees.filter((emp: any) => 
          emp.department === user.department && 
          emp.role?.toLowerCase() !== 'manager' && 
          emp.role?.toLowerCase() !== 'admin' &&
          emp.is_active !== false
        );

        // Fetch all tasks
        const tasks = await apiService.getMyTasks();
        
        // Process team members with their status and tasks
        const teamMembersData: TeamMemberStatus[] = await Promise.all(
          departmentEmployees.map(async (emp: any) => {
            const userId = String(emp.id || emp.user_id || '');
            
            // Get tasks assigned to this employee
            const employeeTasks = tasks.filter((task: any) => {
              const assignedTo = Array.isArray(task.assignedTo) ? task.assignedTo : [task.assignedTo];
              return assignedTo.includes(userId);
            });

            // Get active tasks (not completed)
            const activeTasks = employeeTasks.filter((task: any) => 
              task.status !== 'completed' && task.status !== 'cancelled'
            );

            // Calculate progress based on completed vs total tasks
            const totalTasks = employeeTasks.length;
            const completedTasks = employeeTasks.filter((task: any) => task.status === 'completed').length;
            const progress = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

            // Get the most recent active task title
            const currentTask = activeTasks.length > 0 
              ? activeTasks[0].title || 'No active task'
              : completedTasks > 0 
                ? 'All tasks completed'
                : 'No tasks assigned';

            // Determine status (simplified - we'll assume present if they have tasks)
            let status: 'present' | 'on-leave' | 'absent' = 'present';
            if (activeTasks.length === 0 && completedTasks === 0) {
              status = 'absent';
            }

            return {
              name: emp.name || 'Unknown',
              status,
              task: currentTask,
              progress,
              userId,
            };
          })
        );

        setTeamMembers(teamMembersData);
      } catch (error) {
        console.error('Failed to fetch team members:', error);
      } finally {
        setIsLoadingTeamMembers(false);
      }
    };

    fetchTeamMembersWithStatus();
  }, [user?.department]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 p-6 rounded-2xl bg-gradient-to-r from-teal-600 via-cyan-700 to-blue-800 text-white shadow-xl">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <div className="h-12 w-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Target className="h-7 w-7 text-white" />
            </div>
            {t.common.welcome}, Manager!
          </h1>
          <p className="text-teal-100 mt-2 ml-15">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <Button onClick={() => navigate('/manager/tasks')} className="gap-2 bg-white text-teal-700 hover:bg-teal-50">
          <ClipboardList className="h-4 w-4" />
          Assign Task
        </Button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="card-hover border-0 bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-blue-50">
              Team Members
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Users className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.teamMembers}</div>
            <div className="flex items-center gap-1 mt-2">
              <CheckCircle2 className="h-4 w-4 text-blue-100" />
              <span className="text-sm text-blue-100">{stats.presentToday} present today</span>
            </div>
          </CardContent>
        </Card>

        <Card className="card-hover border-0 bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-green-50">
              Team Performance
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Target className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.teamPerformancePercent}%</div>
            <Progress value={stats.teamPerformancePercent} className="mt-2 h-2 bg-white/30" />
          </CardContent>
        </Card>

        <Card className="card-hover border-0 bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-cyan-50">
              Active Tasks
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <ClipboardList className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.activeTasks}</div>
            <Button variant="link" className="p-0 h-auto mt-2 text-white hover:text-cyan-100" onClick={() => navigate('/manager/tasks')}>
              <span className="text-sm">Manage tasks</span>
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </CardContent>
        </Card>

        <Card className="card-hover border-0 bg-gradient-to-br from-amber-500 to-orange-600 text-white shadow-lg hover:shadow-xl transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-amber-50">
              Pending Approvals
            </CardTitle>
            <div className="h-10 w-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-white" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.pendingApprovals}</div>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-sm text-amber-100">{stats.overdueItems} overdue</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Team Activities */}
        <Card className="lg:col-span-2 border-0 shadow-lg bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center">
                <Activity className="h-5 w-5 text-white" />
              </div>
              Team Activities
            </CardTitle>
            <CardDescription className="text-base">Recent updates from your team</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {teamActivities.length > 0 ? teamActivities.map((activity) => (
              <div key={activity.id} className="flex items-start gap-3 p-3 rounded-lg border hover:bg-white/50 dark:hover:bg-gray-800/50 transition-colors">
                <div className={`h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm ${
                  activity.type === 'task' ? 'bg-gradient-to-br from-blue-400 to-indigo-500' :
                  activity.type === 'leave' ? 'bg-gradient-to-br from-amber-400 to-orange-500' :
                  'bg-gradient-to-br from-green-400 to-emerald-500'
                }`}>
                  {activity.type === 'task' && <ClipboardList className="h-5 w-5 text-white" />}
                  {activity.type === 'leave' && <CalendarDays className="h-5 w-5 text-white" />}
                  {activity.type === 'check-in' && <Clock className="h-5 w-5 text-white" />}
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium">{activity.user}</p>
                  <p className="text-xs text-muted-foreground">
                    {activity.description || ''}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">
                    {new Date(activity.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <Badge 
                    variant={
                      activity.status === 'completed' || activity.status === 'on-time' ? 'default' :
                      activity.status === 'pending' ? 'secondary' :
                      'outline'
                    }
                    className="text-xs mt-1"
                  >
                    {activity.status}
                  </Badge>
                </div>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No recent activities</p>
            )}
          </CardContent>
        </Card>

        {/* Team Leads Performance */}
        <Card className="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                <Target className="h-5 w-5 text-white" />
              </div>
              Team Performance
            </CardTitle>
            <CardDescription className="text-base">Task completion by team</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {teamPerformance.length > 0 ? teamPerformance.map((team) => (
              <div key={`${team.team}-${team.lead}`} className="space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-sm">{team.team}</p>
                    <p className="text-xs text-muted-foreground">{team.lead} • {team.members} members</p>
                  </div>
                  <span className="text-sm font-semibold">{team.completion}%</span>
                </div>
                <Progress value={team.completion} className="h-2" />
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No performance data available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Team Members Current Status */}
      <Card className="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-900 dark:to-gray-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center">
              <Users className="h-5 w-5 text-white" />
            </div>
            Team Members Current Status
          </CardTitle>
          <CardDescription className="text-base">Current status and task progress</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoadingTeamMembers ? (
            <p className="text-sm text-muted-foreground text-center py-4">Loading team members...</p>
          ) : teamMembers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No team members found</p>
          ) : (
            teamMembers.map((member) => (
              <div key={member.userId} className="p-3 rounded-lg border space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`h-2 w-2 rounded-full ${
                      member.status === 'present' ? 'bg-green-500' : 
                      member.status === 'on-leave' ? 'bg-amber-500' : 
                      'bg-gray-400'
                    }`} />
                    <div>
                      <p className="font-medium text-sm">{member.name}</p>
                      <p className="text-xs text-muted-foreground">{member.task}</p>
                    </div>
                  </div>
                  <Badge variant={
                    member.status === 'present' ? 'default' : 
                    member.status === 'on-leave' ? 'secondary' : 
                    'outline'
                  }>
                    {member.status === 'present' ? 'Active' : 
                     member.status === 'on-leave' ? 'On Leave' : 
                     'Absent'}
                  </Badge>
                </div>
                {member.status === 'present' && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">Progress</span>
                      <span className="font-medium">{member.progress}%</span>
                    </div>
                    <Progress value={member.progress} className="h-1" />
                  </div>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.quickActions}</CardTitle>
          <CardDescription>Frequently used manager actions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Button variant="outline" className="h-auto py-3 flex-col gap-2" onClick={() => navigate('/manager/shift-schedule')}>
              <Clock className="h-5 w-5" />
              <span className="text-xs">Shift Schedule</span>
            </Button>
            <Button variant="outline" className="h-auto py-3 flex-col gap-2" onClick={() => navigate('/manager/teams')}>
              <Users className="h-5 w-5" />
              <span className="text-xs">View Team</span>
            </Button>
            <Button variant="outline" className="h-auto py-3 flex-col gap-2" onClick={() => navigate('/manager/attendance')}>
              <Clock className="h-5 w-5" />
              <span className="text-xs">Team Attendance</span>
            </Button>
            <Button variant="outline" className="h-auto py-3 flex-col gap-2" onClick={() => navigate('/manager/leaves')}>
              <CalendarDays className="h-5 w-5" />
              <span className="text-xs">Approve Leaves</span>
            </Button>
            <Button variant="outline" className="h-auto py-3 flex-col gap-2" onClick={() => navigate('/manager/tasks')}>
              <ClipboardList className="h-5 w-5" />
              <span className="text-xs">Manage Tasks</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ManagerDashboard;