from .user import User
from .attendance import Attendance
from .office_timing import OfficeTiming
from .leave import Leave
from .leave_config import LeaveAllocationConfig
from .task import Task
from .notification import LeaveNotification, TaskNotification
from .hiring import Vacancy, Candidate
from .shift import Shift, ShiftAssignment, ShiftNotification
from .online_status import OnlineStatus

# Base import
from app.db.database import Base
