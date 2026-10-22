
from sqlalchemy.orm import Session

from app.db.models.vendor import Vendor


def create_vendor(
    db: Session,
    company_id: int,
    vendor_name: str,
    contact_person: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
):
    vendor = Vendor(
        company_id=company_id,
        vendor_name=vendor_name,
        contact_person=contact_person,
        email=email,
        phone=phone,
        address=address,
    )

    try:
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor
    except Exception:
        db.rollback()
        raise


def get_vendors(db: Session, company_id: int):
    return (
        db.query(Vendor)
        .filter(Vendor.company_id == company_id)
        .order_by(Vendor.vendor_id.desc())
        .all()
    )


def get_vendor(
    db: Session,
    vendor_id: int,
    company_id: int,
):
    return (
        db.query(Vendor)
        .filter(
            Vendor.vendor_id == vendor_id,
            Vendor.company_id == company_id,
        )
        .first()
    )


def update_vendor(
    db: Session,
    vendor: Vendor,
    vendor_name: str | None = None,
    contact_person: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
):
    if vendor_name is not None:
        vendor.vendor_name = vendor_name

    if contact_person is not None:
        vendor.contact_person = contact_person

    if email is not None:
        vendor.email = email

    if phone is not None:
        vendor.phone = phone

    if address is not None:
        vendor.address = address

    try:
        db.commit()
        db.refresh(vendor)
        return vendor
    except Exception:
        db.rollback()
        raise


def delete_vendor(db: Session, vendor: Vendor):
    try:
        db.delete(vendor)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
