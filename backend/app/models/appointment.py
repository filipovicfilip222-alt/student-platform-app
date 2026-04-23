import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    AppointmentStatus,
    ConsultationType,
    ParticipantStatus,
    TopicCategory,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.professor import Professor
    from app.models.subject import Subject
    from app.models.availability_slot import AvailabilitySlot
    from app.models.file import File
    from app.models.chat import TicketChatMessage
    from app.models.strike import StrikeRecord


class Appointment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointments"

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lead_student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_category: Mapped[TopicCategory] = mapped_column(
        Enum(TopicCategory, name="topiccategory"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointmentstatus"),
        nullable=False,
        default=AppointmentStatus.PENDING,
        server_default="PENDING",
    )
    consultation_type: Mapped[ConsultationType] = mapped_column(
        Enum(ConsultationType, name="consultationtype"), nullable=False
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    delegated_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_group: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    slot: Mapped["AvailabilitySlot"] = relationship("AvailabilitySlot", back_populates="appointments")
    professor: Mapped["Professor"] = relationship("Professor")
    lead_student: Mapped["User"] = relationship("User", foreign_keys=[lead_student_id])
    delegated_user: Mapped["User | None"] = relationship("User", foreign_keys=[delegated_to])
    subject: Mapped["Subject | None"] = relationship("Subject")
    participants: Mapped[list["AppointmentParticipant"]] = relationship(
        "AppointmentParticipant", back_populates="appointment"
    )
    files: Mapped[list["File"]] = relationship("File", back_populates="appointment")
    chat_messages: Mapped[list["TicketChatMessage"]] = relationship(
        "TicketChatMessage", back_populates="appointment"
    )
    strike_records: Mapped[list["StrikeRecord"]] = relationship(
        "StrikeRecord", back_populates="appointment"
    )

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} status={self.status}>"


class AppointmentParticipant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "appointment_participants"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ParticipantStatus] = mapped_column(
        Enum(ParticipantStatus, name="participantstatus"),
        nullable=False,
        default=ParticipantStatus.PENDING,
        server_default="PENDING",
    )
    is_lead: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="participants")
    student: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<AppointmentParticipant appointment={self.appointment_id} student={self.student_id}>"


class Waitlist(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "waitlist"
    __table_args__ = (UniqueConstraint("slot_id", "student_id", name="uq_waitlist_slot_student"),)

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    slot: Mapped["AvailabilitySlot"] = relationship("AvailabilitySlot", back_populates="waitlist_entries")
    student: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Waitlist slot={self.slot_id} student={self.student_id}>"
