from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.db.models.company_salary_structure import (
    CompanySalaryStructure,
    CompanySalaryStructureComponent,
)
from app.schemas.company_salary_structure_schema import (
    CompanySalaryStructureCreate,
    CompanySalaryStructureOut,
    CompanySalaryStructureUpdate,
)


def _to_component_rows(payload: CompanySalaryStructureCreate | CompanySalaryStructureUpdate) -> list[dict]:
    return [
        {
            "component_code": "BASIC",
            "category": "EARNING",
            "calculation_type": payload.basic_type,
            "percentage_base": "CTC" if payload.basic_type == "PERCENTAGE" else "NONE",
            "percentage_value": payload.basic_value if payload.basic_type == "PERCENTAGE" else None,
            "fixed_value": payload.basic_value if payload.basic_type == "FIXED" else None,
            "is_enabled": True,
            "sort_order": 1,
        },
        {
            "component_code": "HRA",
            "category": "EARNING",
            "calculation_type": "PERCENTAGE",
            "percentage_base": "BASIC",
            "percentage_value": payload.hra_percentage_of_basic,
            "fixed_value": None,
            "is_enabled": True,
            "sort_order": 2,
        },
        {
            "component_code": "SPECIAL_ALLOWANCE",
            "category": "EARNING",
            "calculation_type": payload.special_allowance_type,
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.special_allowance_value if payload.special_allowance_type == "FIXED" else None,
            "is_enabled": True,
            "sort_order": 3,
        },
        {
            "component_code": "CONVEYANCE_ALLOWANCE",
            "category": "EARNING",
            "calculation_type": "FIXED",
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.conveyance_allowance,
            "is_enabled": True,
            "sort_order": 4,
        },
        {
            "component_code": "MEDICAL_ALLOWANCE",
            "category": "EARNING",
            "calculation_type": "FIXED",
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.medical_allowance,
            "is_enabled": True,
            "sort_order": 5,
        },
        {
            "component_code": "OTHER_ALLOWANCE",
            "category": "EARNING",
            "calculation_type": "FIXED",
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.other_allowance,
            "is_enabled": True,
            "sort_order": 6,
        },
        {
            "component_code": "PF",
            "category": "DEDUCTION",
            "calculation_type": payload.pf_type,
            "percentage_base": "BASIC" if payload.pf_type == "PERCENTAGE" else "NONE",
            "percentage_value": payload.pf_value if payload.pf_type == "PERCENTAGE" else None,
            "fixed_value": payload.pf_value if payload.pf_type == "FIXED" else None,
            "is_enabled": True,
            "sort_order": 7,
        },
        {
            "component_code": "ESIC",
            "category": "DEDUCTION",
            "calculation_type": payload.esic_type,
            "percentage_base": "GROSS" if payload.esic_type == "PERCENTAGE" else "NONE",
            "percentage_value": payload.esic_value if payload.esic_type == "PERCENTAGE" else None,
            "fixed_value": payload.esic_value if payload.esic_type == "FIXED" else None,
            "is_enabled": True,
            "sort_order": 8,
        },
        {
            "component_code": "PROFESSIONAL_TAX",
            "category": "DEDUCTION",
            "calculation_type": "FIXED",
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.professional_tax,
            "is_enabled": True,
            "sort_order": 9,
        },
        {
            "component_code": "TDS",
            "category": "DEDUCTION",
            "calculation_type": payload.tds_type,
            "percentage_base": "GROSS" if payload.tds_type == "PERCENTAGE" else "NONE",
            "percentage_value": payload.tds_value if payload.tds_type == "PERCENTAGE" else None,
            "fixed_value": payload.tds_value if payload.tds_type == "FIXED" else None,
            "is_enabled": True,
            "sort_order": 10,
        },
        {
            "component_code": "OTHER_DEDUCTION",
            "category": "DEDUCTION",
            "calculation_type": "FIXED",
            "percentage_base": "NONE",
            "percentage_value": None,
            "fixed_value": payload.other_deduction,
            "is_enabled": True,
            "sort_order": 11,
        },
    ]


def _to_out(structure: CompanySalaryStructure) -> CompanySalaryStructureOut:
    by_code = {c.component_code: c for c in structure.components}
    basic = by_code["BASIC"]
    pf = by_code["PF"]
    esic = by_code["ESIC"]
    tds = by_code["TDS"]
    special = by_code["SPECIAL_ALLOWANCE"]

    return CompanySalaryStructureOut(
        structure_id=structure.structure_id,
        company_id=structure.company_id,
        structure_name=structure.structure_name,
        description=structure.description,
        is_active=structure.is_active,
        is_default=structure.is_default,
        basic_type=basic.calculation_type,  # type: ignore[arg-type]
        basic_value=Decimal(
            basic.percentage_value if basic.calculation_type == "PERCENTAGE" else basic.fixed_value or 0
        ),
        hra_percentage_of_basic=Decimal(by_code["HRA"].percentage_value or 0),
        special_allowance_type=special.calculation_type,  # type: ignore[arg-type]
        special_allowance_value=Decimal(special.fixed_value) if special.fixed_value is not None else None,
        conveyance_allowance=Decimal(by_code["CONVEYANCE_ALLOWANCE"].fixed_value or 0),
        medical_allowance=Decimal(by_code["MEDICAL_ALLOWANCE"].fixed_value or 0),
        other_allowance=Decimal(by_code["OTHER_ALLOWANCE"].fixed_value or 0),
        pf_type=pf.calculation_type,  # type: ignore[arg-type]
        pf_value=Decimal(pf.percentage_value if pf.calculation_type == "PERCENTAGE" else pf.fixed_value or 0),
        esic_type=esic.calculation_type,  # type: ignore[arg-type]
        esic_value=Decimal(esic.percentage_value if esic.calculation_type == "PERCENTAGE" else esic.fixed_value or 0),
        professional_tax=Decimal(by_code["PROFESSIONAL_TAX"].fixed_value or 0),
        tds_type=tds.calculation_type,  # type: ignore[arg-type]
        tds_value=Decimal(tds.percentage_value if tds.calculation_type == "PERCENTAGE" else tds.fixed_value or 0),
        other_deduction=Decimal(by_code["OTHER_DEDUCTION"].fixed_value or 0),
        created_at=structure.created_at,
        created_by=structure.created_by,
        updated_at=structure.updated_at,
        updated_by=structure.updated_by,
    )


def create_company_salary_structure(
    db: Session,
    company_id: int,
    payload: CompanySalaryStructureCreate,
    created_by: int | None = None,
) -> CompanySalaryStructureOut:
    if payload.is_default:
        db.query(CompanySalaryStructure).filter(CompanySalaryStructure.company_id == company_id).update({"is_default": False})

    structure = CompanySalaryStructure(
        company_id=company_id,
        structure_name=payload.structure_name,
        description=payload.description,
        is_active=payload.is_active,
        is_default=payload.is_default,
        created_by=created_by,
    )
    db.add(structure)
    db.flush()

    for component in _to_component_rows(payload):
        db.add(CompanySalaryStructureComponent(structure_id=structure.structure_id, **component))

    db.commit()
    refreshed = get_company_salary_structure_entity(db, structure.structure_id)
    return _to_out(refreshed)


def list_company_salary_structures(db: Session, company_id: int) -> list[CompanySalaryStructureOut]:
    structures = (
        db.query(CompanySalaryStructure)
        .options(joinedload(CompanySalaryStructure.components))
        .filter(CompanySalaryStructure.company_id == company_id)
        .order_by(CompanySalaryStructure.structure_id.desc())
        .all()
    )
    return [_to_out(s) for s in structures]


def get_company_salary_structure_entity(db: Session, structure_id: int) -> CompanySalaryStructure | None:
    return (
        db.query(CompanySalaryStructure)
        .options(joinedload(CompanySalaryStructure.components))
        .filter(CompanySalaryStructure.structure_id == structure_id)
        .first()
    )


def get_company_salary_structure(db: Session, structure_id: int) -> CompanySalaryStructureOut | None:
    structure = get_company_salary_structure_entity(db, structure_id)
    return _to_out(structure) if structure else None


def get_company_salary_structure_by_name(
    db: Session, company_id: int, structure_name: str, exclude_structure_id: int | None = None
) -> CompanySalaryStructure | None:
    query = db.query(CompanySalaryStructure).filter(
        CompanySalaryStructure.company_id == company_id,
        CompanySalaryStructure.structure_name == structure_name,
    )
    if exclude_structure_id is not None:
        query = query.filter(CompanySalaryStructure.structure_id != exclude_structure_id)
    return query.first()


def update_company_salary_structure(
    db: Session,
    structure_id: int,
    payload: CompanySalaryStructureUpdate,
    updated_by: int | None = None,
) -> CompanySalaryStructureOut | None:
    structure = db.query(CompanySalaryStructure).filter(CompanySalaryStructure.structure_id == structure_id).first()
    if not structure:
        return None

    if payload.is_default:
        db.query(CompanySalaryStructure).filter(
            CompanySalaryStructure.company_id == structure.company_id,
            CompanySalaryStructure.structure_id != structure.structure_id,
        ).update({"is_default": False})

    structure.structure_name = payload.structure_name
    structure.description = payload.description
    structure.is_active = payload.is_active
    structure.is_default = payload.is_default
    structure.updated_by = updated_by

    incoming_components = _to_component_rows(payload)
    existing_components = (
        db.query(CompanySalaryStructureComponent)
        .filter(CompanySalaryStructureComponent.structure_id == structure.structure_id)
        .all()
    )
    existing_by_code = {component.component_code: component for component in existing_components}
    incoming_codes = {component["component_code"] for component in incoming_components}

    for incoming in incoming_components:
        existing = existing_by_code.get(incoming["component_code"])
        if existing:
            existing.category = incoming["category"]
            existing.calculation_type = incoming["calculation_type"]
            existing.percentage_base = incoming["percentage_base"]
            existing.percentage_value = incoming["percentage_value"]
            existing.fixed_value = incoming["fixed_value"]
            existing.is_enabled = incoming["is_enabled"]
            existing.sort_order = incoming["sort_order"]
        else:
            db.add(CompanySalaryStructureComponent(structure_id=structure.structure_id, **incoming))

    for existing in existing_components:
        if existing.component_code not in incoming_codes:
            db.delete(existing)

    db.commit()
    refreshed = get_company_salary_structure_entity(db, structure.structure_id)
    return _to_out(refreshed)


def delete_company_salary_structure(db: Session, structure_id: int) -> bool:
    structure = db.query(CompanySalaryStructure).filter(CompanySalaryStructure.structure_id == structure_id).first()
    if not structure:
        return False
    db.delete(structure)
    db.commit()
    return True


def set_company_salary_structure_active_status(
    db: Session,
    structure_id: int,
    is_active: bool,
    updated_by: int | None = None,
) -> CompanySalaryStructureOut | None:
    structure = db.query(CompanySalaryStructure).filter(CompanySalaryStructure.structure_id == structure_id).first()
    if not structure:
        return None
    structure.is_active = is_active
    structure.updated_by = updated_by
    db.commit()
    refreshed = get_company_salary_structure_entity(db, structure.structure_id)
    return _to_out(refreshed)


def set_company_salary_structure_default_status(
    db: Session,
    company_id: int,
    structure_id: int,
    is_default: bool,
    updated_by: int | None = None,
) -> CompanySalaryStructureOut | None:
    structure = db.query(CompanySalaryStructure).filter(CompanySalaryStructure.structure_id == structure_id).first()
    if not structure or structure.company_id != company_id:
        return None

    if is_default:
        db.query(CompanySalaryStructure).filter(
            CompanySalaryStructure.company_id == company_id,
            CompanySalaryStructure.structure_id != structure_id,
        ).update({"is_default": False})

    structure.is_default = is_default
    structure.updated_by = updated_by
    db.commit()
    refreshed = get_company_salary_structure_entity(db, structure.structure_id)
    return _to_out(refreshed)


def bulk_set_company_salary_structure_active_status(
    db: Session,
    company_id: int,
    structure_ids: list[int],
    is_active: bool,
    updated_by: int | None = None,
) -> list[CompanySalaryStructureOut]:
    structures = (
        db.query(CompanySalaryStructure)
        .filter(
            CompanySalaryStructure.company_id == company_id,
            CompanySalaryStructure.structure_id.in_(structure_ids),
        )
        .all()
    )
    if not structures:
        return []

    for structure in structures:
        structure.is_active = is_active
        structure.updated_by = updated_by

    db.commit()

    refreshed = (
        db.query(CompanySalaryStructure)
        .options(joinedload(CompanySalaryStructure.components))
        .filter(
            CompanySalaryStructure.company_id == company_id,
            CompanySalaryStructure.structure_id.in_(structure_ids),
        )
        .order_by(CompanySalaryStructure.structure_id.desc())
        .all()
    )
    return [_to_out(item) for item in refreshed]
