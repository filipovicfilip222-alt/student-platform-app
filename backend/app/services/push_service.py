"""Web Push fan-out servis (KORAK 1 Prompta 2 / PRD §5.3).

Single source of truth za sva 3 push aspekta:
  1. ``subscribe()``    — UPSERT u ``push_subscriptions`` na osnovu
     ``(user_id, endpoint)`` UNIQUE-a; ako endpoint već postoji za istog
     korisnika (npr. browser je pozvan ``subscribe()`` po drugi put posle
     novog VAPID rolla), update-uje ključeve i ``last_used_at``.
  2. ``unsubscribe()``  — DELETE po ``(user_id, endpoint)``; idempotent
     (vraća True/False bez 404 grešaka — frontend ne mora da prati).
  3. ``send_push()``    — fan-out preko ``pywebpush.webpush`` na sve
     aktivne pretplate korisnika; 410 Gone → cleanup; quiet hours filter
     22:00-07:00 CET za non-urgent tipove.

Zašto pywebpush poziv ide kroz ``asyncio.to_thread``:
  - ``pywebpush.webpush()`` je sinhroni (interno koristi ``requests``,
    blokira event loop). Kad bi se zvalo direktno, FastAPI worker bi se
    blokirao 200-1500ms po HTTP roundtrip-u prema FCM-u — što je upravo
    razlog zbog kog notification_service zove ovaj servis kao fire-and-forget
    background task (``asyncio.create_task``). Ali čak i unutar tog
    background task-a, blokirajući poziv bi sprečio druge background
    task-ove da napreduju. ``asyncio.to_thread`` razrešava oba problema.

Zašto NE pravimo zaseban Celery task za push:
  - In-app + Redis pub/sub deo notification.create() ostaje sub-100ms.
  - Push se šalje fire-and-forget unutar request task-a, sa 5s budgetom.
    Ako padne (timeout, 503), nije fatalno — in-app i email i dalje rade.
  - Celery task bi dodao 50-200ms task dispatch latency + komplikaciju
    (NullPool engine za task DB sesiju, retry budget) bez stvarnog gain-a.
  - Re-evaluacija u Promptu 3 ako otkrijemo da puštanje preko event loop-a
    ne skalira (tipično tek na 1000+ push/sec, što ovaj projekat neće
    videti u demo-u).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dtime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.push_subscription import PushSubscription

_log = logging.getLogger(__name__)

_BELGRADE_TZ = ZoneInfo("Europe/Belgrade")
_QUIET_HOURS_START = dtime(22, 0)
_QUIET_HOURS_END = dtime(7, 0)

# Notification tipovi koji probijaju quiet hours (vremenski osetljivi —
# studentu treba da stigne čak i u 23:30 ako mu je termin za 1h ili
# je profesor otkazao zakazan razgovor preko noći).
_URGENT_PUSH_TYPES: frozenset[str] = frozenset({
    "APPOINTMENT_REMINDER_1H",
    "APPOINTMENT_CANCELLED",
    "APPOINTMENT_CONFIRMED",
    "WAITLIST_OFFER",
})


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_quiet_hours(now_utc: datetime | None = None) -> bool:
    """True ako je trenutno između 22:00 i 07:00 po beogradskom vremenu.

    Belgrade je CET (+01:00) zimi i CEST (+02:00) leti — ZoneInfo to
    automatski razrešava preko tzdata-e (Python 3.12 baseline).
    """
    now = now_utc or datetime.now(timezone.utc)
    local = now.astimezone(_BELGRADE_TZ).time()
    # Window prelazi ponoć: ili je posle 22:00 ili pre 07:00.
    return local >= _QUIET_HOURS_START or local < _QUIET_HOURS_END


def _build_deep_link(notification_type: str, data: dict[str, Any] | None) -> str:
    """Vraća apsolutni URL koji SW ``notificationclick`` handler otvara.

    Mapping je centralizovan ovde a ne u SW-u jer:
      - ``settings.FRONTEND_URL`` je server config (može se razlikovati
        po environment-u, demo vs prod);
      - SW radi nad trimovanim payload-om i nema pristup ``NotificationType``
        konstantama — dovoljno mu je da otvori URL.

    Default fallback je ``/dashboard`` ako nemamo dovoljno konteksta —
    bolje neki ekran nego ``about:blank``.
    """
    base = settings.FRONTEND_URL.rstrip("/")
    if not data:
        return f"{base}/dashboard"

    if notification_type.startswith("APPOINTMENT_"):
        appt_id = data.get("appointment_id")
        if appt_id:
            return f"{base}/appointments/{appt_id}"
    elif notification_type.startswith("DOCUMENT_REQUEST_"):
        req_id = data.get("request_id")
        if req_id:
            return f"{base}/requests/{req_id}"
    elif notification_type == "NEW_CHAT_MESSAGE":
        appt_id = data.get("appointment_id")
        if appt_id:
            return f"{base}/messages/{appt_id}"
    elif notification_type == "WAITLIST_OFFER":
        return f"{base}/appointments"
    elif notification_type in {"STRIKE_ADDED", "BLOCK_ACTIVATED", "BLOCK_LIFTED"}:
        return f"{base}/profile"

    return f"{base}/dashboard"


def _build_tag(notification_type: str, data: dict[str, Any] | None) -> str:
    """Vraća Web Push ``tag`` koji u OS notification tray-u zamenjuje stariju
    poruku istog taga (sprečava reminder spam: 24h reminder + 1h reminder
    za isti termin → vidi se samo poslednji)."""
    if data:
        if "appointment_id" in data:
            return f"appointment:{data['appointment_id']}"
        if "request_id" in data:
            return f"request:{data['request_id']}"
    return f"type:{notification_type.lower()}"


def _trim(text: str, limit: int) -> str:
    """Skrati string sa Unicode-friendly elipsom — payload mora ispod 4KB.

    Pravilo: ``title`` ≤ 80 chars, ``body`` ≤ 140 chars (Slack/Discord
    pattern). Frontend in-app stream ima pun tekst, push je samo trigger.
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ── Subscribe / Unsubscribe (REST flow) ──────────────────────────────────────


async def subscribe(
    db: AsyncSession,
    *,
    user_id: UUID,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: str | None,
) -> PushSubscription:
    """UPSERT pretplata za ``(user_id, endpoint)``.

    Idempotent: ako je par već u tabeli, ažurira ključeve i ``last_used_at``
    bez kreiranja drugog reda (browser je možda pozvao ``subscribe()`` posle
    VAPID rotation-a — endpoint isti, ključevi novi).

    UPSERT se radi PostgreSQL-specific ``INSERT ... ON CONFLICT`` jer
    SQLAlchemy generic insert nema portable ON CONFLICT API. Vraća pun ORM
    objekat (RETURNING clause) — frontend hook ga parsira u dijagnostičku
    ``PushSubscriptionResponse`` šemu.
    """
    stmt = (
        pg_insert(PushSubscription)
        .values(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            user_agent=user_agent,
        )
        .on_conflict_do_update(
            constraint="uq_push_subscriptions_user_endpoint",
            set_={
                "p256dh_key": p256dh_key,
                "auth_key": auth_key,
                "user_agent": user_agent,
                # ``last_used_at`` ažuriramo tek na uspešan ``send_push``;
                # ovde stavljamo ``now()`` na re-subscribe samo da nemamo
                # stale vrednost iz prošlog inkarnata pretplate.
                "last_used_at": datetime.now(timezone.utc),
            },
        )
        .returning(PushSubscription)
    )
    result = await db.execute(stmt)
    row = result.scalar_one()
    await db.commit()
    await db.refresh(row)
    return row


async def unsubscribe(
    db: AsyncSession,
    *,
    user_id: UUID,
    endpoint: str,
) -> bool:
    """Briše pretplatu po ``(user_id, endpoint)``. Vraća True ako je nešto
    obrisano, False ako nije bilo reda — frontend hook to ignoriše."""
    stmt = (
        delete(PushSubscription)
        .where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        .returning(PushSubscription.id)
    )
    result = await db.execute(stmt)
    deleted = result.first() is not None
    await db.commit()
    return deleted


# ── Send (notification fan-out hook) ─────────────────────────────────────────


def _send_one_blocking(
    *,
    subscription_info: dict[str, Any],
    payload: bytes,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
) -> None:
    """Sinhroni omotač oko ``pywebpush.webpush`` — zove se kroz
    ``asyncio.to_thread`` da ne blokira event loop.

    Greške propagira (WebPushException sa response.status_code) — caller
    razlikuje 410 (cleanup) od ostalih (warning log).
    """
    webpush(
        subscription_info=subscription_info,
        data=payload,
        vapid_private_key=vapid_private_key,
        vapid_claims=vapid_claims,
        ttl=600,  # poruka ima 10 min budget na push servisu, pa propada
    )


async def send_push(
    db: AsyncSession,
    *,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, Any] | None,
) -> int:
    """Fan-out push poruke svim aktivnim pretplatama korisnika.

    Vraća broj uspešno isporučenih push-eva (0 ako nema pretplata, ako su
    quiet hours ublažile non-urgent tip ili ako su svi push-evi pali).
    Pozivni kontekst je fire-and-forget iz ``notification_service.create``,
    pa ne podiže izuzetke nazad — sve se loguje interno.

    Logika:
      1. Ako VAPID_PRIVATE_KEY nije postavljen, log warning + return 0.
         Defenzivni branch — boot ne crash-uje sa praznim vrednostima jer
         demo developer može da pokrene server pre ``generate_vapid_keys.py``.
      2. Quiet hours check — ako je 22:00-07:00 CET i type nije u
         ``_URGENT_PUSH_TYPES``, skip (in-app + email i dalje rade).
      3. Učitaj sve pretplate za user-a.
      4. Pripremi trimovan payload (≤200 bytes total tipično).
      5. Za svaku pretplatu: pošalji preko ``asyncio.to_thread``, pa:
         - 410 Gone → DELETE pretplate (push servis kaže "endpoint mrtav").
         - 404 → DELETE (FCM ponekad vraća umesto 410).
         - drugo → log warning, ne briši (servis možda flap-uje).
      6. Update ``last_used_at`` za one koji su uspeli.
    """
    if not settings.VAPID_PRIVATE_KEY:
        _log.warning(
            "push_service.send_push: VAPID_PRIVATE_KEY not set, skipping. "
            "Run 'python scripts/generate_vapid_keys.py' and set in backend/.env."
        )
        return 0

    if notification_type not in _URGENT_PUSH_TYPES and _is_quiet_hours():
        _log.info(
            "push_service.send_push: quiet hours skip user=%s type=%s",
            user_id, notification_type,
        )
        return 0

    # Učitaj pretplate.
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subs = list(result.scalars().all())
    if not subs:
        return 0

    # Trimovan payload — Slack/Discord pattern, vidi PushNotificationPayload
    # u frontend/types/notification.ts.
    import json as _json
    payload_dict: dict[str, Any] = {
        "title": _trim(title, 80),
        "body": _trim(body, 140),
        "url": _build_deep_link(notification_type, data),
        "type": notification_type,
        "tag": _build_tag(notification_type, data),
    }
    payload_bytes = _json.dumps(payload_dict).encode("utf-8")

    vapid_claims = {"sub": settings.VAPID_SUBJECT}

    delivered = 0
    to_delete: list[UUID] = []
    to_touch: list[UUID] = []

    for sub in subs:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
        }
        try:
            await asyncio.to_thread(
                _send_one_blocking,
                subscription_info=sub_info,
                payload=payload_bytes,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims,
            )
            delivered += 1
            to_touch.append(sub.id)
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (404, 410):
                # Endpoint mrtav — push servis nikad više neće isporučiti.
                to_delete.append(sub.id)
                _log.info(
                    "push_service.send_push: cleaning dead subscription user=%s sub=%s status=%s",
                    user_id, sub.id, status_code,
                )
            else:
                _log.warning(
                    "push_service.send_push: WebPushException user=%s sub=%s status=%s err=%s",
                    user_id, sub.id, status_code, exc,
                )
        except Exception as exc:  # noqa: BLE001 — defensive
            _log.warning(
                "push_service.send_push: unexpected error user=%s sub=%s err=%s",
                user_id, sub.id, exc,
            )

    # Cleanup mrtvih pretplata + last_used_at touch — sve u jednom commit-u.
    if to_delete:
        await db.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(to_delete))
        )
    if to_touch:
        from sqlalchemy import update as sa_update
        await db.execute(
            sa_update(PushSubscription)
            .where(PushSubscription.id.in_(to_touch))
            .values(last_used_at=datetime.now(timezone.utc))
        )
    if to_delete or to_touch:
        await db.commit()

    return delivered
