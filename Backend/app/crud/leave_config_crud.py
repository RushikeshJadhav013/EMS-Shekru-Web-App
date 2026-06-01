from sqlalchemy.orm import Session
from typing import Optional
from app.db.models.leave_config import LeaveAllocationConfig


def get_active_leave_config(
    db: Session,
    company_id: int,
) -> Optional[LeaveAllocationConfig]:
    """Get the active leave allocation configuration for a company."""
    return (
        db.query(LeaveAllocationConfig)
        .filter(
            LeaveAllocationConfig.company_id == int(company_id),
            LeaveAllocationConfig.is_active.is_(True),
        )
        .order_by(LeaveAllocationConfig.updated_at.desc())
        .first()
    )


def get_leave_config_or_default(db: Session, company_id: int | None = None) -> dict:
    """
    Get active leave configuration for a company or return default values.
    Returns a dict with leave allocations.
    Annual leave is calculated as sick + casual (not stored separately).
    """
    if company_id is not None:
        config = get_active_leave_config(db, int(company_id))
        if config:
            annual_calculated = config.sick_leave_allocation + config.casual_leave_allocation
            return {
                "annual": annual_calculated,
                "sick": config.sick_leave_allocation,
                "casual": config.casual_leave_allocation,
                "other": config.other_leave_allocation,
            }

    return {
        "annual": 15,
        "sick": 10,
        "casual": 5,
        "other": 0,
    }


def get_leave_config_by_id(
    db: Session,
    config_id: int,
    company_id: int | None = None,
) -> Optional[LeaveAllocationConfig]:
    q = db.query(LeaveAllocationConfig).filter(LeaveAllocationConfig.id == config_id)
    if company_id is not None:
        q = q.filter(LeaveAllocationConfig.company_id == int(company_id))
    return q.first()


def create_leave_config(
    db: Session,
    company_id: int,
    total_annual_leave: int,
    sick_leave_allocation: int,
    casual_leave_allocation: int,
    other_leave_allocation: int,
    updated_by: int,
) -> LeaveAllocationConfig:
    """
    Create a new leave allocation configuration for a company.
    Deactivates previous configurations for that company only.
    Note: total_annual_leave is stored but annual bucket = sick + casual in calculations.
    """
    db.query(LeaveAllocationConfig).filter(
        LeaveAllocationConfig.company_id == int(company_id),
    ).update({"is_active": False})

    derived_total = (sick_leave_allocation or 0) + (casual_leave_allocation or 0)
    config = LeaveAllocationConfig(
        company_id=int(company_id),
        total_annual_leave=derived_total,
        sick_leave_allocation=sick_leave_allocation,
        casual_leave_allocation=casual_leave_allocation,
        other_leave_allocation=other_leave_allocation,
        is_active=True,
        updated_by=updated_by,
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return config


def update_leave_config(
    db: Session,
    config_id: int,
    company_id: int,
    total_annual_leave: Optional[int] = None,
    sick_leave_allocation: Optional[int] = None,
    casual_leave_allocation: Optional[int] = None,
    other_leave_allocation: Optional[int] = None,
    updated_by: Optional[int] = None,
) -> Optional[LeaveAllocationConfig]:
    """Update an existing leave allocation configuration for a company."""
    config = get_leave_config_by_id(db, config_id, company_id=company_id)

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

    config.total_annual_leave = (config.sick_leave_allocation or 0) + (
        config.casual_leave_allocation or 0
    )

    db.commit()
    db.refresh(config)

    return config
