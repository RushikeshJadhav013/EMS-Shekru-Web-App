
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExpenseDocumentCreate(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=255)
    document_path: str = Field(..., min_length=1, max_length=500)
    document_type: str | None = Field(default=None, max_length=50)


class ExpenseDocumentResponse(BaseModel):
    document_id: int
    expense_id: int
    document_name: str
    document_type: str | None = None
    uploaded_by: int | None = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
