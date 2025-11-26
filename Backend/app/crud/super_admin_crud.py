from sqlalchemy.orm import Session
from app.db.models.super_admin import SuperAdmin
from app.schemas.super_admin_schema import SuperAdminCreate, SuperAdminUpdate


def create_super_admin(db: Session, super_admin: SuperAdminCreate):
    db_super_admin = SuperAdmin(**super_admin.dict())
    db.add(db_super_admin)
    db.commit()
    db.refresh(db_super_admin)
    return db_super_admin


def update_super_admin(db: Session, super_admin_id: int, super_admin: SuperAdminUpdate):
    db_super_admin = db.query(SuperAdmin).filter(SuperAdmin.id == super_admin_id).first()
    if not db_super_admin:
        return None
    for key, value in super_admin.dict(exclude_unset=True).items():
        setattr(db_super_admin, key, value)
    db.commit()
    db.refresh(db_super_admin)
    return db_super_admin


def delete_super_admin(db: Session, super_admin_id: int):
    db_super_admin = db.query(SuperAdmin).filter(SuperAdmin.id == super_admin_id).first()
    if not db_super_admin:
        return None
    db.delete(db_super_admin)
    db.commit()
    return db_super_admin


def get_super_admin(db: Session, super_admin_id: int):
    return db.query(SuperAdmin).filter(SuperAdmin.id == super_admin_id).first()


def list_super_admins(db: Session):
    return db.query(SuperAdmin).all()
