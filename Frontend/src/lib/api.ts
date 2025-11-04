const API_BASE_URL = 'http://localhost:8000';

interface EmployeeData {
  name: string;
  email: string;
  employee_id: string;
  department?: string;
  designation?: string;
  phone?: string;
  address?: string;
  role?: string;
  gender?: string;
  resignation_date?: string;
  pan_card?: string;
  aadhar_card?: string;
  shift_type?: string;
  employee_type?: string;  // ✅ Added
  profile_photo?: File | string;
  is_verified?: boolean;
  created_at?: string;
  user_id?: number;
}

interface Employee {
  id: string;
  employee_id: string;
  name: string;
  email: string;
  department?: string;
  designation?: string;
  role: string;
  phone?: string;
  address?: string;
  status: string;
  created_at: string;
  updated_at: string;
  photo_url?: string;
  resignation_date?: string;
  gender?: string;
  employee_type?: string;
  pan_card?: string;
  aadhar_card?: string;
  shift_type?: string;
}

interface LeaveRequestData {
  employee_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string;
}

interface LeaveRequestResponse {
  id: string;
  employee_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  created_at: string;
  updated_at: string;
}

class ApiService {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseURL}${endpoint}`;

    // Get auth token from localStorage
    const token = localStorage.getItem('token');
    
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}), // ✅ Add auth token
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new Error('Not authenticated');
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Get all employees
  async getEmployees() {
    return this.request('/employees');
  }

  // Dashboard endpoints
  async getAdminDashboard() {
    return this.request('/dashboard/admin');
  }

  async getHRDashboard() {
    return this.request('/dashboard/hr');
  }

  async getManagerDashboard() {
    return this.request('/dashboard/manager');
  }

  async getTeamLeadDashboard() {
    return this.request('/dashboard/team-lead');
  }

  async getEmployeeDashboard() {
    return this.request('/dashboard/employee');
  }

  // User tasks
  async getMyTasks() {
    return this.request('/tasks');
  }

  // Create a new employee
  async createEmployee(employeeData: EmployeeData): Promise<Employee> {
    const formData = new FormData();

    // Add all fields to FormData
    Object.entries(employeeData).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (key === 'profile_photo' && value instanceof File) {
          formData.append(key, value);
        } else {
          formData.append(key, String(value));
        }
      }
    });

    const response = await fetch(`${this.baseURL}/employees/register`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  // Update an employee - Updated to use user_id instead of employee_id
  async updateEmployee(userId: string, employeeData: Partial<EmployeeData>): Promise<Employee> {
    // Prepare the request body as JSON
    const requestBody: Record<string, unknown> = {
      name: employeeData.name,
      email: employeeData.email,
      employee_id: employeeData.employee_id,
      department: employeeData.department || null,
      designation: employeeData.designation || null,
      phone: employeeData.phone || null,
      address: employeeData.address || null,
      role: employeeData.role || 'Employee',
      gender: employeeData.gender || null,
      resignation_date: employeeData.resignation_date || null,
      pan_card: employeeData.pan_card || null,
      aadhar_card: employeeData.aadhar_card || null,
      shift_type: employeeData.shift_type || null,
      employee_type: employeeData.employee_type || null,  // ✅ Added
      is_verified: employeeData.is_verified !== undefined ? employeeData.is_verified : true,
      profile_photo: employeeData.profile_photo || null,
      created_at: employeeData.created_at || new Date().toISOString()
    };

    // Remove undefined/null values
    Object.keys(requestBody).forEach(key => {
      if (requestBody[key] === undefined) {
        delete requestBody[key];
      }
    });

    // Get auth token from localStorage
    const token = localStorage.getItem('token');
    
    const response = await fetch(`${this.baseURL}/employees/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}), // ✅ Add auth token
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  // Delete an employee
  async deleteEmployee(userId: string): Promise<void> {
    // Get auth token from localStorage
    const token = localStorage.getItem('token');
    
    const response = await fetch(`${this.baseURL}/employees/${userId}`, {
      method: 'DELETE',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
  }

  // Update employee status (activate/deactivate)
  async updateEmployeeStatus(userId: string, isActive: boolean): Promise<Employee> {
    const token = localStorage.getItem('token');
    
    const response = await fetch(`${this.baseURL}/employees/${userId}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ is_active: isActive }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  // Submit a leave request
  async submitLeaveRequest(leaveData: LeaveRequestData): Promise<LeaveRequestResponse> {
    return this.request('/leave/', {
      method: 'POST',
      body: JSON.stringify(leaveData),
    });
  }

  // Get all leave requests
  async getLeaveRequests(): Promise<LeaveRequestResponse[]> {
    return this.request('/leave/');
  }

  // Get leave requests by employee
  async getLeaveRequestsByEmployee(employeeId: string): Promise<LeaveRequestResponse[]> {
    return this.request(`/leave/employee/${employeeId}`);
  }

  // Approve or reject a leave request
  async approveLeaveRequest(leaveId: string, approved: boolean): Promise<LeaveRequestResponse> {
    return this.request(`/leave/${leaveId}/approve`, {
      method: 'PUT',
      body: JSON.stringify({ approved }),
    });
  }

  // Export employees as CSV
  async exportEmployeesCSV(): Promise<Blob> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${this.baseURL}/employees/export/csv`, {
      method: 'GET',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.blob();
  }

  // Export employees as PDF
  async exportEmployeesPDF(): Promise<Blob> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${this.baseURL}/employees/export/pdf`, {
      method: 'GET',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.blob();
  }
}

export const apiService = new ApiService(API_BASE_URL);
export type { Employee, EmployeeData, LeaveRequestData, LeaveRequestResponse };
