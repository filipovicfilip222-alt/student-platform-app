"""PushSubscription ORM (KORAK 1 Prompta 2 — Web Push, PRD §5.3).

Per-uređaj zapis o Web Push subscription-u jednog korisnika. Browser
PushManager.subscribe() vraća JSON sa 3 polja (endpoint + 2 javna
ključa); ovde ih čuvamo kako bi backend mogao da pošalje signed
Web Push poruku preko ``pywebpush`` (ili ručnog VAPID JWT-a u fallback
scenariju).

Zašto ``UNIQUE (user_id, endpoint)`` umesto samo ``UNIQUE (endpoint)``:

  - Endpoint je generisan od strane push servisa (FCM / Mozilla / Apple)
    i u praksi je globalno jedinstven, ali ne želimo da se oslanjamo na
    to. Ako bi se 2 različita korisnika nekako probudila sa istim
    endpoint-om (npr. preuzeli isti uređaj), želimo per-user zapis bez
    cross-account leakage-a.
  - UPSERT pattern u ``push_service.subscribe`` koristi ovaj par kao
    on-conflict target.

Zašto ``ON DELETE CASCADE`` na ``user_id``:
  - Kad admin deaktivira ili briše korisnika, sve njegove push
    pretplate su besmislene — push servis bi vraćao 410 Gone i
    cleanup posao bi ih ionako obrisao. CASCADE je čistiji od TTL-a.

Polja koja NISU u ovom modelu (svesno):
  - ``device_label`` (npr. „Chrome na Windows") — over-engineering za V1
    i ne bi se popunilo na frontend strani jer browser ne izlaže to.
    Umesto toga, ``user_agent`` pruža isti signal sa jednim DB hop-om.
  - ``encryption_padding`` / ``content_encoding`` — pywebpush bira
    ``aes128gcm`` po defaultu, ne treba dodatna konfiguracija.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class PushSubscription(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_push_subscriptions_user_endpoint"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="push_subscriptions")

    def __repr__(self) -> str:
        return (
            f"<PushSubscription id={self.id} user={self.user_id} "
            f"endpoint={self.endpoint[:48]}…>"
        )
