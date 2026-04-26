"""Broadcast ORM model (Faza 4.5).

Tabela ``broadcasts`` čuva istoriju globalnih obaveštenja koje admin
šalje preko ``POST /api/v1/admin/broadcast``. Frontend hook
``useBroadcastHistory`` (``frontend/lib/hooks/use-broadcast.ts``) zove
``GET /api/v1/admin/broadcast`` koji vraća poslednjih N redova ove
tabele kao ``BroadcastResponse[]``.

Šemu kreira migracija ``20260427_0003_broadcasts.py``:

- ``id`` UUID PK
- ``admin_id`` FK ``users.id`` ON DELETE RESTRICT (admin koji je
  poslao broadcast — ne brišemo ga dok god ima broadcast-ova; SET NULL
  bi gubio audit trag)
- ``title`` VARCHAR(120), ``body`` TEXT (mirror frontend max constraints)
- ``target`` VARCHAR(20) — vrednosti su iz ``BroadcastTarget`` Literal
  union-a u ``schemas/admin.py`` (ALL/STUDENTS/STAFF/BY_FACULTY).
- ``faculty`` VARCHAR(10) NULL — popunjen samo kad je target=BY_FACULTY.
- ``channels`` VARCHAR(50)[] — PG array sa vrednostima ``IN_APP``/``EMAIL``.
- ``recipient_count`` INTEGER — broj resolve-ovanih primaoca u trenutku
  dispatch-a (NIJE delivered_count; ako fan-out task pukne za 5 od 200
  user-a, recipient_count ostaje 200 i greške se gledaju u Celery logu).
- ``sent_at`` TIMESTAMPTZ DEFAULT now().

Ne koristimo ``TimestampMixin`` — nema potrebe za ``updated_at`` (broadcast
je immutable nakon dispatch-a; admin ne edituje istoriju).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Broadcast(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "broadcasts"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    faculty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    channels: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False
    )
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    admin: Mapped["User"] = relationship("User", foreign_keys=[admin_id])

    def __repr__(self) -> str:
        return (
            f"<Broadcast id={self.id} admin={self.admin_id} "
            f"target={self.target} recipients={self.recipient_count}>"
        )
