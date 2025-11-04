import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/hooks/use-toast';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Building2,
  Users,
  Search,
  ChevronRight
} from 'lucide-react';
import { Department } from '@/types';
import { useLanguage } from '@/contexts/LanguageContext';

interface ExtendedDepartment extends Department {
  employeeCount?: number;
  budget?: number;
  location?: string;
}

export default function DepartmentManagement() {
  const { t } = useLanguage();
  const [departments, setDepartments] = useState<ExtendedDepartment[]>([
    {
      id: '1',
      name: 'Engineering',
      code: 'ENG',
      managerId: 'manager1',
      description: 'Software development and technical operations',
      status: 'active',
      employeeCount: 45,
      budget: 5000000,
      location: 'Building A, Floor 3',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    },
    {
      id: '2',
      name: 'Marketing',
      code: 'MKT',
      managerId: 'manager2',
      description: 'Marketing, branding, and communications',
      status: 'active',
      employeeCount: 20,
      budget: 2000000,
      location: 'Building B, Floor 2',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    },
    {
      id: '3',
      name: 'Human Resources',
      code: 'HR',
      managerId: 'manager3',
      description: 'Employee management and organizational development',
      status: 'active',
      employeeCount: 12,
      budget: 1500000,
      location: 'Building A, Floor 1',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    },
    {
      id: '4',
      name: 'Sales',
      code: 'SLS',
      managerId: 'manager4',
      description: 'Sales operations and customer acquisition',
      status: 'active',
      employeeCount: 35,
      budget: 3000000,
      location: 'Building B, Floor 3',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
  ]);

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedDepartment, setSelectedDepartment] = useState<ExtendedDepartment | null>(null);
  const [formData, setFormData] = useState<Partial<ExtendedDepartment>>({
    name: '',
    code: '',
    managerId: '',
    description: '',
    status: 'active',
    employeeCount: 0,
    budget: 0,
    location: ''
  });

  const managers = [
    { id: 'manager1', name: 'John Smith' },
    { id: 'manager2', name: 'Sarah Johnson' },
    { id: 'manager3', name: 'Michael Chen' },
    { id: 'manager4', name: 'Emily Davis' },
    { id: 'manager5', name: 'Robert Wilson' }
  ];

  const filteredDepartments = departments.filter(dept => {
    const matchesSearch = dept.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         dept.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         dept.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = selectedStatus === 'all' || dept.status === selectedStatus;
    return matchesSearch && matchesStatus;
  });

  const handleCreateDepartment = () => {
    if (!formData.name || !formData.code || !formData.managerId) {
      toast({
        title: 'Error',
        description: 'Please fill in all required fields',
        variant: 'destructive'
      });
      return;
    }

    const newDepartment: ExtendedDepartment = {
      ...formData as ExtendedDepartment,
      id: Date.now().toString(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    setDepartments([...departments, newDepartment]);
    setIsCreateDialogOpen(false);
    resetForm();
    toast({
      title: 'Success',
      description: 'Department created successfully'
    });
  };

  const handleUpdateDepartment = () => {
    if (!selectedDepartment) return;

    const updatedDepartments = departments.map(dept => 
      dept.id === selectedDepartment.id 
        ? {
            ...dept,
            ...formData,
            updatedAt: new Date().toISOString()
          }
        : dept
    );

    setDepartments(updatedDepartments);
    setIsEditDialogOpen(false);
    resetForm();
    toast({
      title: 'Success',
      description: 'Department updated successfully'
    });
  };

  const handleDeleteDepartment = (id: string) => {
    const dept = departments.find(d => d.id === id);
    if (dept && dept.employeeCount && dept.employeeCount > 0) {
      toast({
        title: 'Error',
        description: 'Cannot delete department with active employees',
        variant: 'destructive'
      });
      return;
    }

    setDepartments(departments.filter(dept => dept.id !== id));
    toast({
      title: 'Success',
      description: 'Department deleted successfully'
    });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      code: '',
      managerId: '',
      description: '',
      status: 'active',
      employeeCount: 0,
      budget: 0,
      location: ''
    });
    setSelectedDepartment(null);
  };

  const openEditDialog = (department: ExtendedDepartment) => {
    setSelectedDepartment(department);
    setFormData(department);
    setIsEditDialogOpen(true);
  };

  const totalEmployees = departments.reduce((sum, dept) => sum + (dept.employeeCount || 0), 0);
  const totalBudget = departments.reduce((sum, dept) => sum + (dept.budget || 0), 0);
  const activeDepartments = departments.filter(dept => dept.status === 'active').length;

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Departments</p>
                <p className="text-2xl font-bold">{departments.length}</p>
              </div>
              <Building2 className="h-8 w-8 text-primary opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Active Departments</p>
                <p className="text-2xl font-bold">{activeDepartments}</p>
              </div>
              <Building2 className="h-8 w-8 text-green-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Employees</p>
                <p className="text-2xl font-bold">{totalEmployees}</p>
              </div>
              <Users className="h-8 w-8 text-blue-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Budget</p>
                <p className="text-2xl font-bold">₹{(totalBudget / 100000).toFixed(1)}L</p>
              </div>
              <ChevronRight className="h-8 w-8 text-purple-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl flex items-center gap-2">
              <Building2 className="h-6 w-6" />
              Department Management
            </CardTitle>
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Department
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Create New Department</DialogTitle>
                </DialogHeader>
                <DepartmentForm />
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-6">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name, code, or description..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger className="w-200">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Department Name</TableHead>
                  <TableHead>Manager</TableHead>
                  <TableHead>Employees</TableHead>
                  <TableHead>Budget</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredDepartments.map((department) => {
                  const manager = managers.find(m => m.id === department.managerId);
                  return (
                    <TableRow key={department.id}>
                      <TableCell className="font-medium">{department.code}</TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{department.name}</p>
                          <p className="text-sm text-muted-foreground">{department.description}</p>
                        </div>
                      </TableCell>
                      <TableCell>{manager?.name || '-'}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {department.employeeCount || 0}
                        </Badge>
                      </TableCell>
                      <TableCell>₹{((department.budget || 0) / 100000).toFixed(1)}L</TableCell>
                      <TableCell>{department.location || '-'}</TableCell>
                      <TableCell>
                        <Badge variant={department.status === 'active' ? 'default' : 'secondary'}>
                          {department.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEditDialog(department)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDeleteDepartment(department.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Department</DialogTitle>
          </DialogHeader>
          <DepartmentForm />
        </DialogContent>
      </Dialog>
    </div>
  );

  function DepartmentForm() {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="name">Department Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              required
            />
          </div>
          <div>
            <Label htmlFor="code">Department Code *</Label>
            <Input
              id="code"
              value={formData.code}
              onChange={(e) => setFormData({...formData, code: e.target.value.toUpperCase()})}
              placeholder="e.g., ENG, MKT, HR"
              maxLength={5}
              required
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="manager">Department Manager *</Label>
            <Select 
              value={formData.managerId} 
              onValueChange={(value) => setFormData({...formData, managerId: value})}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select Manager" />
              </SelectTrigger>
              <SelectContent>
                {managers.map(manager => (
                  <SelectItem key={manager.id} value={manager.id}>
                    {manager.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="status">Status</Label>
            <Select 
              value={formData.status} 
              onValueChange={(value) => setFormData({...formData, status: value as 'active' | 'inactive'})}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="employeeCount">Number of Employees</Label>
            <Input
              id="employeeCount"
              type="number"
              value={formData.employeeCount}
              onChange={(e) => setFormData({...formData, employeeCount: parseInt(e.target.value) || 0})}
              min="0"
            />
          </div>
          <div>
            <Label htmlFor="budget">Annual Budget (₹)</Label>
            <Input
              id="budget"
              type="number"
              value={formData.budget}
              onChange={(e) => setFormData({...formData, budget: parseInt(e.target.value) || 0})}
              min="0"
              placeholder="e.g., 5000000"
            />
          </div>
        </div>
        <div>
          <Label htmlFor="location">Location</Label>
          <Input
            id="location"
            value={formData.location}
            onChange={(e) => setFormData({...formData, location: e.target.value})}
            placeholder="e.g., Building A, Floor 3"
          />
        </div>
        <div>
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData({...formData, description: e.target.value})}
            placeholder="Brief description of the department's responsibilities..."
            rows={3}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => {
            isCreateDialogOpen ? setIsCreateDialogOpen(false) : setIsEditDialogOpen(false);
            resetForm();
          }}>
            Cancel
          </Button>
          <Button onClick={isCreateDialogOpen ? handleCreateDepartment : handleUpdateDepartment}>
            {isCreateDialogOpen ? 'Create' : 'Update'} Department
          </Button>
        </DialogFooter>
      </div>
    );
  }
}