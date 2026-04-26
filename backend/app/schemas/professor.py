from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AppointmentStatus, ConsultationType, Faculty, TopicCategory


# ── Recurring rule (ROADMAP §3.8) ─────────────────────────────────────────────
# Wire format identical to what `frontend/components/calendar/recurring-rule-modal.tsx`
# emits (see SlotCreateRequest.recurring_rule). Weekday integers follow the
# JavaScript Date.getDay() convention: 0 = Sunday, 1 = Monday, …, 6 = Saturday.
# Service layer translates these to dateutil.rrule weekday constants when
# expanding the rule into concrete slot timestamps.
class RecurringRule(BaseModel):
    freq: Literal["WEEKLY", "MONTHLY"] = "WEEKLY"
    by_weekday: list[int] | None = Field(default=None, min_length=1, max_length=7)
    interval: int = Field(default=1, ge=1, le=52)
    count: int | None = Field(default=None, ge=1, le=100)
    until: date | None = None

    @model_validator(mode="after")
    def validate_termination_and_weekdays(self) -> "RecurringRule":
        if self.by_weekday is not None:
            for d in self.by_weekday:
                if d < 0 or d > 6:
                    raise ValueError(
                        "by_weekday vrednosti moraju biti 0..6 (0=nedelja, 6=subota)."
                    )
            if len(set(self.by_weekday)) != len(self.by_weekday):
                raise ValueError("by_weekday ne sme imati duplikate.")
        # Mora postojati način da serija stane: ili `count`, ili `until`,
        # nikad oba istovremeno (sprečava nejasne slučajeve).
        if self.count is not None and self.until is not None:
            raise ValueError(
                "RecurringRule mora imati ILI count ILI until, ne oba."
            )
        if self.count is None and self.until is None:
            raise ValueError(
                "RecurringRule mora definisati kraj (count ili until)."
            )
        if self.freq == "WEEKLY" and not self.by_weekday:
            raise ValueError("Za WEEKLY freq, by_weekday je obavezan.")
        return self


class SlotCreate(BaseModel):
    slot_datetime: datetime
    duration_minutes: int = Field(ge=5, le=480)
    consultation_type: ConsultationType
    max_students: int = Field(default=1, ge=1, le=50)
    online_link: str | None = Field(default=None, max_length=2000)
    is_available: bool = True
    recurring_rule: RecurringRule | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "SlotCreate":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until ne može biti pre valid_from.")
        if self.recurring_rule is not None and self.valid_from is None:
            raise ValueError(
                "Kada je `recurring_rule` postavljen, `valid_from` je obavezan."
            )
        return self


class SlotUpdate(BaseModel):
    slot_datetime: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    consultation_type: ConsultationType | None = None
    max_students: int | None = Field(default=None, ge=1, le=50)
    online_link: str | None = Field(default=None, max_length=2000)
    is_available: bool | None = None
    recurring_rule: RecurringRule | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "SlotUpdate":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until ne može biti pre valid_from.")
        return self


class SlotResponse(BaseModel):
    id: UUID
    professor_id: UUID
    slot_datetime: datetime
    duration_minutes: int
    consultation_type: ConsultationType
    max_students: int
    online_link: str | None
    is_available: bool
    recurring_rule: dict | None
    recurring_group_id: UUID | None
    valid_from: date | None
    valid_until: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecurringConflict(BaseModel):
    """
    Vraća se u 422 telu kada `create_slot` (ili DELETE recurring grupe)
    detektuje sudar sa već odobrenim ili rezervisanim terminom.
    """
    slot_datetime: datetime
    appointment_id: UUID | None = None
    reason: str


class BlackoutCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_date_range(self) -> "BlackoutCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date ne može biti pre start_date.")
        return self


class BlackoutResponse(BaseModel):
    id: UUID
    professor_id: UUID
    start_date: date
    end_date: date
    reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfessorMeResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    title: str
    department: str
    office: str | None
    office_description: str | None
    faculty: Faculty
    areas_of_interest: list[str]
    auto_approve_recurring: bool
    auto_approve_special: bool
    buffer_minutes: int
    faq: list["FaqResponse"] = []


class ProfessorProfileUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=100)
    department: str | None = Field(default=None, min_length=2, max_length=200)
    office: str | None = Field(default=None, max_length=100)
    office_description: str | None = Field(default=None, max_length=2000)
    areas_of_interest: list[str] | None = Field(default=None, max_length=20)
    auto_approve_recurring: bool | None = None
    auto_approve_special: bool | None = None
    buffer_minutes: int | None = Field(default=None, ge=0, le=60)


class RequestInboxFilter(BaseModel):
    status: Literal["PENDING", "ALL"] = "PENDING"


class RequestInboxRow(BaseModel):
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
    rejection_reason: str | None
    delegated_to: UUID | None
    lead_student_name: str | None = None


class RequestRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RequestCancelRequest(BaseModel):
    """Profesor / asistent otkazuje već odobren termin."""
    reason: str = Field(min_length=1, max_length=2000)


class RequestDelegateRequest(BaseModel):
    assistant_id: UUID


class CannedResponseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class CannedResponseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=2000)


class CannedResponseResponse(BaseModel):
    id: UUID
    professor_id: UUID
    title: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FaqCreate(BaseModel):
    question: str = Field(min_length=5, max_length=300)
    answer: str = Field(min_length=5, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=10000)


class FaqUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=5, max_length=300)
    answer: str | None = Field(default=None, min_length=5, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class FaqResponse(BaseModel):
    id: UUID
    question: str
    answer: str
    sort_order: int

    model_config = {"from_attributes": True}


class CrmNoteCreate(BaseModel):
    student_id: UUID
    content: str = Field(min_length=1, max_length=4000)


class CrmNoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class CrmNoteResponse(BaseModel):
    id: UUID
    professor_id: UUID
    student_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssistantOptionResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    subjects: list[str]
