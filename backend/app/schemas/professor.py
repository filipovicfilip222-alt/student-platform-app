from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ConsultationType


class SlotCreate(BaseModel):
    slot_datetime: datetime
    duration_minutes: int = Field(ge=5, le=480)
    consultation_type: ConsultationType
    max_students: int = Field(default=1, ge=1, le=50)
    online_link: str | None = Field(default=None, max_length=2000)
    is_available: bool = True
    recurring_rule: dict | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "SlotCreate":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until ne može biti pre valid_from.")
        return self


class SlotUpdate(BaseModel):
    slot_datetime: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    consultation_type: ConsultationType | None = None
    max_students: int | None = Field(default=None, ge=1, le=50)
    online_link: str | None = Field(default=None, max_length=2000)
    is_available: bool | None = None
    recurring_rule: dict | None = None
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
    valid_from: date | None
    valid_until: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
