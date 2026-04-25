from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, DocumentType


class DocumentRequestCreate(BaseModel):
    document_type: DocumentType
    note: str | None = Field(default=None, max_length=2000)


class DocumentRequestApproveRequest(BaseModel):
    pickup_date: date
    admin_note: str | None = Field(default=None, max_length=2000)


class DocumentRequestRejectRequest(BaseModel):
    admin_note: str = Field(min_length=1, max_length=2000)


class DocumentRequestResponse(BaseModel):
    id: UUID
    student_id: UUID
    document_type: DocumentType
    note: str | None
    status: DocumentStatus
    admin_note: str | None
    pickup_date: date | None
    processed_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
