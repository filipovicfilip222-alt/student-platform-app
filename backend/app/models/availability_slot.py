import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConsultationType

if TYPE_CHECKING:
    from app.models.professor import Professor
    from app.models.appointment import Appointment
    from app.models.appointment import Waitlist


class AvailabilitySlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "availability_slots"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    consultation_type: Mapped[ConsultationType] = mapped_column(
        Enum(ConsultationType, name="consultationtype"), nullable=False
    )
    max_students: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    online_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    recurring_rule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    professor: Mapped["Professor"] = relationship(
        "Professor", back_populates="availability_slots"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="slot"
    )
    waitlist_entries: Mapped[list["Waitlist"]] = relationship(
        "Waitlist", back_populates="slot"
    )

    def __repr__(self) -> str:
        return f"<AvailabilitySlot id={self.id} datetime={self.slot_datetime}>"


class BlackoutDate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "blackout_dates"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    professor: Mapped["Professor"] = relationship("Professor", back_populates="blackout_dates")

    def __repr__(self) -> str:
        return f"<BlackoutDate id={self.id} {self.start_date}–{self.end_date}>"
