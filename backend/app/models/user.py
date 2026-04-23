import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Faculty, UserRole

if TYPE_CHECKING:
    from app.models.professor import Professor
    from app.models.appointment import Appointment, AppointmentParticipant
    from app.models.notification import Notification
    from app.models.strike import StrikeRecord, StudentBlock
    from app.models.document_request import DocumentRequest
    from app.models.audit_log import AuditLog
    from app.models.password_reset_token import PasswordResetToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), nullable=False)
    faculty: Mapped[Faculty] = mapped_column(Enum(Faculty, name="faculty"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    professor_profile: Mapped["Professor | None"] = relationship(
        "Professor", back_populates="user", uselist=False
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", lazy="dynamic"
    )
    strike_records: Mapped[list["StrikeRecord"]] = relationship(
        "StrikeRecord", back_populates="student", foreign_keys="StrikeRecord.student_id"
    )
    student_block: Mapped["StudentBlock | None"] = relationship(
        "StudentBlock", back_populates="student", foreign_keys="StudentBlock.student_id", uselist=False
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
