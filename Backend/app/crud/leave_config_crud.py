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
    Annual leave is calculated as sick + casual (not stored separately).
    """
    config = get_active_leave_config(db)
    
    if config:
        # Calculate annual as sick + casual
        annual_calculated = config.sick_leave_allocation + config.casual_leave_allocation
        return {
            "annual": annual_calculated,
            "sick": config.sick_leave_allocation,
            "casual": config.casual_leave_allocation,
            "other": config.other_leave_allocation,
        }
    
    # Default values if no configuration exists
    # Annual = sick (10) + casual (5) = 15
    return {
        "annual": 15,  # Calculated as sick (10) + casual (5)
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
    Note: total_annual_leave is stored but annual bucket = sick + casual in calculations.
    """
    # Deactivate all existing configurations
    db.query(LeaveAllocationConfig).update({"is_active": False})
    
    # Create new configuration
    # Enforce: annual bucket = sick + casual (total_annual_leave is derived)
    derived_total = (sick_leave_allocation or 0) + (casual_leave_allocation or 0)
    config = LeaveAllocationConfig(
        total_annual_leave=derived_total,
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
    
    if sick_leave_allocation is not None:
        config.sick_leave_allocation = sick_leave_allocation
    if casual_leave_allocation is not None:
        config.casual_leave_allocation = casual_leave_allocation
    if other_leave_allocation is not None:
        config.other_leave_allocation = other_leave_allocation
    if updated_by is not None:
        config.updated_by = updated_by

    # Enforce: annual bucket = sick + casual (ignore any provided total_annual_leave)
    config.total_annual_leave = (config.sick_leave_allocation or 0) + (config.casual_leave_allocation or 0)
    
    db.commit()
    db.refresh(config)
    
    return config
