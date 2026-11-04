
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.db.models.vendor import Vendor


def check_duplicate_vendor(
    db: Session,
    company_id: int,
    email: str | None = None,
    phone: str | None = None,
    exclude_vendor_id: int | None = None,
):
    query = db.query(Vendor).filter(
        Vendor.company_id == company_id,
        Vendor.is_deleted.is_(False),
    )

    if exclude_vendor_id is not None:
        query = query.filter(
            Vendor.vendor_id != exclude_vendor_id
        )

    if email is not None:
        existing_email = query.filter(
            Vendor.email.isnot(None)
        ).all()

        normalized_email = email.strip().casefold()

        for existing in existing_email:
            if (
                existing.email
                and existing.email.strip().casefold()
                == normalized_email
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A vendor with this email already exists.",
                )

    if phone is not None:
        existing_phone = query.filter(
            Vendor.phone == phone.strip()
        ).first()

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A vendor with this phone number already exists.",
            )


def create_vendor(
    db: Session,
    company_id: int,
    vendor_name: str,
    contact_person: str,
    email: str,
    phone: str,
    address: str,
):
    check_duplicate_vendor(
        db=db,
        company_id=company_id,
        email=email,
        phone=phone,
    )

    vendor = Vendor(
        company_id=company_id,
        vendor_name=vendor_name,
        contact_person=contact_person,
        email=email,
        phone=phone,
        address=address,
        is_deleted=False,
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
        .filter(
            Vendor.company_id == company_id,
            Vendor.is_deleted.is_(False),
        )
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
            Vendor.is_deleted.is_(False),
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
    if vendor.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found.",
        )

    check_duplicate_vendor(
        db=db,
        company_id=vendor.company_id,
        email=email if email is not None else None,
        phone=phone if phone is not None else None,
        exclude_vendor_id=vendor.vendor_id,
    )

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
    if vendor.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found.",
        )

    try:
        vendor.is_deleted = True
        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
