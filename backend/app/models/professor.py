import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.subject import Subject
    from app.models.availability_slot import AvailabilitySlot, BlackoutDate
    from app.models.crm_note import CrmNote
    from app.models.faq import FaqItem
    from app.models.canned_response import CannedResponse


class Professor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "professors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    office: Mapped[str | None] = mapped_column(String(100), nullable=True)
    office_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    areas_of_interest: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    auto_approve_recurring: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    auto_approve_special: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    buffer_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="professor_profile")
    subjects: Mapped[list["Subject"]] = relationship("Subject", back_populates="professor")
    availability_slots: Mapped[list["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot", back_populates="professor"
    )
    blackout_dates: Mapped[list["BlackoutDate"]] = relationship(
        "BlackoutDate", back_populates="professor"
    )
    crm_notes: Mapped[list["CrmNote"]] = relationship("CrmNote", back_populates="professor")
    faq_items: Mapped[list["FaqItem"]] = relationship("FaqItem", back_populates="professor")
    canned_responses: Mapped[list["CannedResponse"]] = relationship(
        "CannedResponse", back_populates="professor"
    )

    def __repr__(self) -> str:
        return f"<Professor id={self.id} user_id={self.user_id}>"
