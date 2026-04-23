import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DocumentStatus, DocumentType

if TYPE_CHECKING:
    from app.models.user import User


class DocumentRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="documenttype"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus"),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default="PENDING",
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    processor: Mapped["User | None"] = relationship("User", foreign_keys=[processed_by])

    def __repr__(self) -> str:
        return f"<DocumentRequest id={self.id} type={self.document_type} status={self.status}>"
