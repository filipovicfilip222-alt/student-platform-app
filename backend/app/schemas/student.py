from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AppointmentStatus,
    ConsultationType,
    Faculty,
    TopicCategory,
)


class AvailableSlotResponse(BaseModel):
    id: UUID
    slot_datetime: datetime
    duration_minutes: int
    consultation_type: ConsultationType
    max_students: int
    online_link: str | None

    model_config = {"from_attributes": True}


class FaqResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    sort_order: int

    model_config = {"from_attributes": True}


class ProfessorSearchResponse(BaseModel):
    id: UUID
    full_name: str
    title: str
    department: str
    faculty: Faculty
    subjects: list[str]
    consultation_types: list[ConsultationType]


class ProfessorProfileResponse(BaseModel):
    id: UUID
    full_name: str
    title: str
    department: str
    office: str | None
    office_description: str | None
    faculty: Faculty
    areas_of_interest: list[str]
    subjects: list[str]
    faq: list[FaqResponse]
    available_slots: list[AvailableSlotResponse]


class SlotRangeFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class AppointmentCreateRequest(BaseModel):
    slot_id: UUID
    topic_category: TopicCategory
    description: str = Field(min_length=10, max_length=4000)
    subject_id: UUID | None = None


class AppointmentResponse(BaseModel):
    id: UUID
    slot_id: UUID
    professor_id: UUID
    lead_student_id: UUID
    subject_id: UUID | None
    topic_category: TopicCategory
    description: str
    status: AppointmentStatus
    consultation_type: ConsultationType
    slot_datetime: datetime
    created_at: datetime


class AppointmentCancelResponse(BaseModel):
    id: UUID
    status: AppointmentStatus
