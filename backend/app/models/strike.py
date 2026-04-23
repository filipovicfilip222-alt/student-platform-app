import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import StrikeReason

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.appointment import Appointment


class StrikeRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "strike_records"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[StrikeReason] = mapped_column(
        Enum(StrikeReason, name="strikereason"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    student: Mapped["User"] = relationship(
        "User", back_populates="strike_records", foreign_keys=[student_id]
    )
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="strike_records"
    )

    def __repr__(self) -> str:
        return f"<StrikeRecord id={self.id} student={self.student_id} points={self.points}>"


class StudentBlock(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "student_blocks"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    removal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    student: Mapped["User"] = relationship(
        "User", back_populates="student_block", foreign_keys=[student_id]
    )
    removed_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[removed_by])

    def __repr__(self) -> str:
        return f"<StudentBlock id={self.id} student={self.student_id} until={self.blocked_until}>"
