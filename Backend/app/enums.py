from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "Admin"
    HR = "HR"
    MANAGER = "Manager"
    TEAM_LEAD = "TeamLead"
    EMPLOYEE = "Employee"


class ChatMemberRoleEnum(str, Enum):
    MEMBER = "member"
    ADMIN = "admin"


class TaskStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    OVERDUE = "Overdue"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

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

class ExpenseCategoryEnum(str, Enum):
    TRAVEL_AND_CONVEYANCE = "Travel & Conveyance"
    FOOD_AND_REFRESHMENTS = "Food & Refreshments"
    OFFICE_SUPPLIES = "Office Supplies"
    STATIONERY = "Stationery"
    ELECTRICITY = "Electricity"
    INTERNET_AND_TELEPHONE = "Internet & Telephone"
    RENT_AND_MAINTENANCE = "Rent & Maintenance"
    SOFTWARE_SUBSCRIPTION = "Software / Subscription"
    EMPLOYEE_WELFARE = "Employee Welfare"
    CLIENT_MEETING = "Client Meeting"
    MARKETING = "Marketing"
    COURIER = "Courier"
    REPAIRS_AND_MAINTENANCE = "Repairs & Maintenance"
    MISCELLANEOUS = "Miscellaneous"