from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional, List

from pydantic import BaseModel, field_validator, model_validator

RuleType = Literal["FIXED", "PERCENTAGE"]
SpecialType = Literal["FIXED", "BALANCING"]


class CompanySalaryStructureCreate(BaseModel):
    structure_name: str
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False

    basic_type: RuleType
    basic_value: Decimal
    hra_percentage_of_basic: Decimal
    special_allowance_type: SpecialType = "BALANCING"
    special_allowance_value: Optional[Decimal] = None
    conveyance_allowance: Decimal = Decimal("0")
    medical_allowance: Decimal = Decimal("0")
    other_allowance: Decimal = Decimal("0")

    pf_type: RuleType
    pf_value: Decimal
    esic_type: RuleType = "FIXED"
    esic_value: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    tds_type: RuleType = "FIXED"
    tds_value: Decimal = Decimal("0")
    other_deduction: Decimal = Decimal("0")

    @field_validator("structure_name")
    @classmethod
    def validate_structure_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Structure name cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        return value or None

    @field_validator(
        "basic_value",
        "hra_percentage_of_basic",
        "conveyance_allowance",
        "medical_allowance",
        "other_allowance",
        "pf_value",
        "esic_value",
        "professional_tax",
        "tds_value",
        "other_deduction",
        "special_allowance_value",
    )
    @classmethod
    def validate_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        if v < 0:
            raise ValueError("Value must be greater than or equal to 0")
        return v

    @model_validator(mode="after")
    def validate_percentage_logic(self):
        if self.basic_type == "PERCENTAGE" and self.basic_value > 100:
            raise ValueError("basic_value cannot exceed 100 when basic_type is PERCENTAGE")
        if self.hra_percentage_of_basic > 100:
            raise ValueError("hra_percentage_of_basic cannot exceed 100")
        if self.pf_type == "PERCENTAGE" and self.pf_value > 100:
            raise ValueError("pf_value cannot exceed 100 when pf_type is PERCENTAGE")
        if self.esic_type == "PERCENTAGE" and self.esic_value > 100:
            raise ValueError("esic_value cannot exceed 100 when esic_type is PERCENTAGE")
        if self.tds_type == "PERCENTAGE" and self.tds_value > 100:
            raise ValueError("tds_value cannot exceed 100 when tds_type is PERCENTAGE")

        if self.special_allowance_type == "FIXED" and self.special_allowance_value is None:
            raise ValueError("special_allowance_value is required when special_allowance_type is FIXED")
        if self.special_allowance_type == "BALANCING":
            self.special_allowance_value = None
        return self


class CompanySalaryStructureUpdate(CompanySalaryStructureCreate):
    pass


class CompanySalaryStructurePatch(BaseModel):
    structure_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

    basic_type: Optional[RuleType] = None
    basic_value: Optional[Decimal] = None
    hra_percentage_of_basic: Optional[Decimal] = None
    special_allowance_type: Optional[SpecialType] = None
    special_allowance_value: Optional[Decimal] = None
    conveyance_allowance: Optional[Decimal] = None
    medical_allowance: Optional[Decimal] = None
    other_allowance: Optional[Decimal] = None

    pf_type: Optional[RuleType] = None
    pf_value: Optional[Decimal] = None
    esic_type: Optional[RuleType] = None
    esic_value: Optional[Decimal] = None
    professional_tax: Optional[Decimal] = None
    tds_type: Optional[RuleType] = None
    tds_value: Optional[Decimal] = None
    other_deduction: Optional[Decimal] = None

    @field_validator("structure_name")
    @classmethod
    def validate_structure_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        if not value:
            raise ValueError("Structure name cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        return value or None

    @field_validator(
        "basic_value",
        "hra_percentage_of_basic",
        "conveyance_allowance",
        "medical_allowance",
        "other_allowance",
        "pf_value",
        "esic_value",
        "professional_tax",
        "tds_value",
        "other_deduction",
        "special_allowance_value",
    )
    @classmethod
    def validate_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        if v < 0:
            raise ValueError("Value must be greater than or equal to 0")
        return v


class CompanySalaryStructureStatusUpdate(BaseModel):
    is_active: bool


class CompanySalaryStructureDefaultUpdate(BaseModel):
    is_default: bool


class CompanySalaryStructureBulkStatusUpdate(BaseModel):
    structure_ids: List[int]
    is_active: bool

    @field_validator("structure_ids")
    @classmethod
    def validate_structure_ids(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("structure_ids must contain at least one id")
        if len(set(v)) != len(v):
            raise ValueError("structure_ids must not contain duplicates")
        if any(item <= 0 for item in v):
            raise ValueError("Each structure id must be a positive integer")
        return v


class CompanySalaryStructureOut(CompanySalaryStructureCreate):
    structure_id: int
    company_id: int
    created_at: datetime
    created_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True
