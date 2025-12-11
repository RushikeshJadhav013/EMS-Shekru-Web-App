from sqlalchemy.orm import Session
from typing import Optional
from app.db.models.leave_config import LeaveAllocationConfig

def get_active_leave_config(db: Session) -> Optional[LeaveAllocationConfig]:
    """Get the active leave allocation configuration"""
    return db.query(LeaveAllocationConfig).filter(
        LeaveAllocationConfig.is_active == True
    ).order_by(LeaveAllocationConfig.updated_at.desc()).first()

def get_leave_config_or_default(db: Session) -> dict:
    """
    Get active leave configuration or return default values.
    Returns a dict with leave allocations.
    """
    config = get_active_leave_config(db)
    
    if config:
        return {
            "annual": config.total_annual_leave,
            "sick": config.sick_leave_allocation,
            "casual": config.casual_leave_allocation,
            "other": config.other_leave_allocation,
        }
    
    # Default values if no configuration exists
    return {
        "annual": 15,
        "sick": 10,
        "casual": 5,
        "other": 0,
    }

def create_leave_config(
    db: Session,
    total_annual_leave: int,
    sick_leave_allocation: int,
    casual_leave_allocation: int,
    other_leave_allocation: int,
    updated_by: int
) -> LeaveAllocationConfig:
    """
    Create a new leave allocation configuration.
    Deactivates all previous configurations.
    """
    # Deactivate all existing configurations
    db.query(LeaveAllocationConfig).update({"is_active": False})
    
    # Create new configuration
    config = LeaveAllocationConfig(
        total_annual_leave=total_annual_leave,
        sick_leave_allocation=sick_leave_allocation,
        casual_leave_allocation=casual_leave_allocation,
        other_leave_allocation=other_leave_allocation,
        is_active=True,
        updated_by=updated_by
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return config

def update_leave_config(
    db: Session,
    config_id: int,
    total_annual_leave: Optional[int] = None,
    sick_leave_allocation: Optional[int] = None,
    casual_leave_allocation: Optional[int] = None,
    other_leave_allocation: Optional[int] = None,
    updated_by: Optional[int] = None
) -> Optional[LeaveAllocationConfig]:
    """Update an existing leave allocation configuration"""
    config = db.query(LeaveAllocationConfig).filter(
        LeaveAllocationConfig.id == config_id
    ).first()
    
    if not config:
        return None
    
    if total_annual_leave is not None:
        config.total_annual_leave = total_annual_leave
    if sick_leave_allocation is not None:
        config.sick_leave_allocation = sick_leave_allocation
    if casual_leave_allocation is not None:
        config.casual_leave_allocation = casual_leave_allocation
    if other_leave_allocation is not None:
        config.other_leave_allocation = other_leave_allocation
    if updated_by is not None:
        config.updated_by = updated_by
    
    db.commit()
    db.refresh(config)
    
    return config
