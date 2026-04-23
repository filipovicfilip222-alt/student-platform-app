import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.professor import Professor
    from app.models.user import User


class CrmNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_notes"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    professor: Mapped["Professor"] = relationship("Professor", back_populates="crm_notes")
    student: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<CrmNote id={self.id} professor={self.professor_id} student={self.student_id}>"
