"""Notifications Pydantic schemas (Faza 4.2).

Source of truth: ``docs/websocket-schema.md §4`` (notifications WS contract)
+ ``frontend/types/notification.ts`` (zaključan TS ugovor). Polja moraju da
se poklope red-za-red — backend je obavezan da prati frontend (CLAUDE.md §17).

REST endpointi (``frontend/lib/api/notifications.ts``):

    GET    /api/v1/notifications              → list[NotificationResponse]
    GET    /api/v1/notifications/unread-count → UnreadCountResponse
    POST   /api/v1/notifications/{id}/read    → MessageResponse  (auth.py)
    POST   /api/v1/notifications/read-all     → MessageResponse  (auth.py)

WS endpoint:

    WS     /api/v1/notifications/stream       → push-only server→client

Frontend list endpoint vraća **goli array** ``NotificationResponse[]``,
NIJE paginated wrapper — provereno protiv ``notificationsApi.list`` u
``lib/api/notifications.ts``. Zato ovde **ne** definišemo
``NotificationListResponse`` pa da ne navodimo budućeg developera u zabludu.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import NotificationType


class NotificationResponse(BaseModel):
    """Mirror of ``frontend/types/notification.ts::NotificationResponse``.

    Polja:
        id          — UUID notifikacije.
        type        — jedan od 16 ``NotificationType`` literala (validira
                      Pydantic; SQLAlchemy kolona je VARCHAR(50)).
        title       — kratak naslov za bell dropdown (max 200 chars u DB-u).
        body        — pun tekst (Text).
        data        — slobodan JSON payload čiji ključevi zavise od ``type``
                      (vidi schema §4.4 tabelu); ``None`` je dozvoljen i NE
                      izostavlja ključ u serijalizaciji.
        is_read     — flag; `mark_read` ga okreće na ``True``.
        created_at  — UTC ISO-8601 (TZ-aware).
    """

    id: UUID
    type: NotificationType
    title: str
    body: str
    data: dict[str, Any] | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    """Mirror of ``frontend/types/notification.ts::UnreadCountResponse``.

    Endpoint ``GET /api/v1/notifications/unread-count`` vraća ovaj objekat;
    WS kanal publish-uje ``{event: "notification.unread_count", data: {count}}``
    sa istim shape-om u ``data`` polju (schema §4.2).
    """

    count: int = Field(ge=0)


# ── Web Push (KORAK 1 Prompta 2 / PRD §5.3) ──────────────────────────────────
#
# TS izvor istine: ``frontend/types/notification.ts`` (definisano PRE backend
# šema u I-50.2 — push stub-ovi nisu postojali, pa je TS strana zaključana
# prva da ostane konzistentno). Polja moraju 1:1 da odgovaraju TS interfejsu;
# imena ``p256dh`` / ``auth`` se ne menjaju jer ih browser ``PushSubscription
# .toJSON()`` proizvodi tako po Web Push spec-u.


class WebPushKeys(BaseModel):
    """Mirror ``WebPushKeys`` iz frontend/types — 2 base64url ključa."""

    p256dh: str = Field(min_length=10, max_length=255)
    auth: str = Field(min_length=10, max_length=255)


class PushSubscribeRequest(BaseModel):
    """Body ``POST /api/v1/notifications/subscribe``.

    Mirror ``PushSubscribeRequest`` iz frontend/types. ``endpoint`` je u
    praksi 200-700 chars (FCM ima ~250, Mozilla ~350); ne stavljamo gornji
    limit jer push servis može da menja format (Apple je upravo to uradio
    2024.).
    """

    endpoint: str = Field(min_length=20)
    keys: WebPushKeys
    user_agent: str | None = Field(default=None, max_length=500)

    @field_validator("endpoint")
    @classmethod
    def _https_only(cls, v: str) -> str:
        if not v.startswith("https://"):
            # Push servisi su uvek HTTPS; bilo šta drugo je validation
            # signal (loš klijent, possible SSRF). Ovo nije security
            # boundary (auth je u JWT-u), nego sanity check.
            raise ValueError("Push endpoint mora da bude HTTPS URL.")
        return v


class PushUnsubscribeRequest(BaseModel):
    """Body ``POST /api/v1/notifications/unsubscribe``.

    Endpoint sam je dovoljan — UNIQUE ``(user_id, endpoint)`` ograničenje
    obezbeđuje da uvek brišemo tačno 1 zapis.
    """

    endpoint: str = Field(min_length=20)


class VapidPublicKeyResponse(BaseModel):
    """Response ``GET /api/v1/notifications/vapid-public-key``.

    Mirror ``VapidPublicKeyResponse`` iz frontend/types. Polje ``public_key``
    se izlaže neautorizovano-friendly (pretpostavlja se da klijent već prošao
    auth dependency u ruti) i sadrži base64url RAW EC P-256 ključ — 87 chars.
    """

    public_key: str = Field(min_length=80, max_length=120)


class PushSubscriptionResponse(BaseModel):
    """Mirror ``PushSubscriptionResponse`` iz frontend/types — diag-only.

    Frontend hook koristi return value samo da potvrdi UPSERT bez sniffing-a
    HTTP statusa; `from_attributes=True` jer ga koristimo direktno nad ORM
    redom.
    """

    id: UUID
    endpoint: str
    created_at: datetime

    model_config = {"from_attributes": True}
