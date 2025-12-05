from enum import Enum

class RoleEnum(str, Enum):
    ADMIN = "Admin"
    HR = "HR"
    MANAGER = "Manager"
    TEAM_LEAD = "TeamLead"
    EMPLOYEE = "Employee"

class TaskStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"

class TaskAction(str, Enum):
    CREATED = "created"
    PASSED = "passed"
    STATUS_CHANGED = "status_changed"
    UPDATED = "updated"

class LeaveStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class GenderEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"

    @classmethod
    def _missing_(cls, value):
        """Allow case-insensitive gender inputs (value or name)."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value.lower() == normalized or member.name.lower() == normalized:
                    return member
        return None