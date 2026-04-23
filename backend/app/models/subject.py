import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, Enum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import Faculty

if TYPE_CHECKING:
    from app.models.professor import Professor
    from app.models.user import User

# ── Association table (subject_assistants) ─────────────────────────────────────
subject_assistants = Table(
    "subject_assistants",
    Base.metadata,
    Column(
        "subject_id",
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assistant_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Subject(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    faculty: Mapped[Faculty] = mapped_column(Enum(Faculty, name="faculty"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    professor: Mapped["Professor | None"] = relationship("Professor", back_populates="subjects")
    assistants: Mapped[list["User"]] = relationship(
        "User",
        secondary=subject_assistants,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} code={self.code} name={self.name}>"
