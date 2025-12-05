from sqlalchemy.orm import Session
from app.db.models.super_admin import SuperAdmin
from app.schemas.super_admin_schema import SuperAdminCreate, SuperAdminUpdate


def create_super_admin(db: Session, super_admin: SuperAdminCreate, created_by: int):
    super_admin_dict = super_admin.dict()
    super_admin_dict['created_by'] = created_by
    db_super_admin = SuperAdmin(**super_admin_dict)
    db.add(db_super_admin)
    db.commit()
    db.refresh(db_super_admin)
    return db_super_admin


def update_super_admin(db: Session, super_admin_id: int, super_admin: SuperAdminUpdate, updated_by: int):
    db_super_admin = db.query(SuperAdmin).filter(SuperAdmin.super_admin_id == super_admin_id).first()
    if not db_super_admin:
        return None
    for key, value in super_admin.dict(exclude_unset=True).items():
        setattr(db_super_admin, key, value)
    db_super_admin.updated_by = updated_by
    db.commit()
    db.refresh(db_super_admin)
    return db_super_admin


def delete_super_admin(db: Session, super_admin_id: int):
    db_super_admin = db.query(SuperAdmin).filter(SuperAdmin.super_admin_id == super_admin_id).first()
    if not db_super_admin:
        return None
    db.delete(db_super_admin)
    db.commit()
    return db_super_admin


def get_super_admin(db: Session, super_admin_id: int):
    return db.query(SuperAdmin).filter(SuperAdmin.super_admin_id == super_admin_id).first()


def list_super_admins(db: Session):
    return db.query(SuperAdmin).all()


def set_super_admin_status(db: Session, super_admin_id: int, is_active: bool, updated_by: int):
    db_super_admin = db.query(SuperAdmin).filter(SuperAdmin.super_admin_id == super_admin_id).first()
    if not db_super_admin:
        return None
    db_super_admin.is_active = is_active
    db_super_admin.updated_by = updated_by
    db.commit()
    db.refresh(db_super_admin)
    return db_super_admin
