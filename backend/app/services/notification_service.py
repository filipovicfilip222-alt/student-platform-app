"""Per-user notification service (Faza 4.2).

Single source of truth za in-app notifikacije: REST handler-i, Celery
taskovi i bilo koji budući background job moraju ići kroz ``create()``,
``mark_read()`` i ``mark_all_read()`` ovde — tako da:

  1. Insert u ``notifications`` tabelu uvek prati Redis publish na
     ``notif:pub:{user_id}`` (per-user kanal iz schema §4),
  2. Counter u ``notif:unread:{user_id}`` ostaje konzistentan sa stanjem
     u bazi (Redis je *cache*, ne autoritativan izvor — ako padne, fallback
     na ``COUNT(*) WHERE is_read=false``),
  3. Cross-tab sync radi: ``mark_read`` publish-uje novi
     ``notification.unread_count`` event tako da svi otvoreni tabovi istog
     korisnika dobijaju isti counter (schema §10.1, otvoreno pitanje #1 —
     odgovor: da, publish-ujemo).

Pattern fan-out-a je identičan ``chat_service.send_message`` (Faza 4.1):
INSERT → flush+commit → ``redis.publish(channel, envelope)``. Publish je
fire-and-forget; ako Redis padne između INSERT-a i PUBLISH-a, poruka je
durably u DB-u i klijent će je videti pri reconnect-u kroz REST GET-ove
(``schema §7.3``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.services import push_service

_log = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────


def notif_pub_channel(user_id: UUID) -> str:
    """Redis Pub/Sub channel name. Centralised so the WS handler and the
    publisher cannot disagree on the format (schema §4.1)."""
    return f"notif:pub:{user_id}"


def notif_unread_key(user_id: UUID) -> str:
    """Redis counter ključ. Set/INCR/DECR-ovan na pisanje, GET-ovan na
    inicijalni unread sync u WS handshake-u i u REST ``unread-count``
    endpoint-u sa DB fallback-om."""
    return f"notif:unread:{user_id}"


# ── Envelope builders (single source of truth za WS payload bytes) ──────────


def _envelope(event: str, data: dict[str, Any]) -> str:
    """Encode a WS envelope ``{event, ts, data}`` per schema §3.

    ``ts`` je ISO-8601 UTC sa ``Z`` suffix-om — isti format kao chat_service
    iz 4.1. WS subscriber prosleđuje verbatim (no re-serialization), zato
    je publisher autoritativan za format.
    """
    return json.dumps(
        {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": data,
        }
    )


def build_notification_created_envelope(notif: Notification) -> str:
    """``notification.created`` — broadcast novog reda na ``notif:pub:{user_id}``.

    Payload je identičan ``NotificationResponse`` shape-u — frontend
    ``<NotificationStream />`` ga direktno injection-uje u TanStack Query
    cache (``setQueriesData``).
    """
    return _envelope(
        "notification.created",
        {
            "id": str(notif.id),
            "type": notif.type,
            "title": notif.title,
            "body": notif.body,
            "data": notif.data,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat(),
        },
    )


def build_unread_count_envelope(count: int) -> str:
    """``notification.unread_count`` — sync svih otvorenih tabova istog
    korisnika posle bilo koje read-state mutacije (schema §4.2)."""
    return _envelope("notification.unread_count", {"count": int(count)})


def build_system_ping_envelope(*, seq: int) -> str:
    """25s heartbeat ping (schema §3.1 + §7.1). Identičan format kao chat."""
    return _envelope("system.ping", {"seq": seq})


def build_system_error_envelope(*, code: str, message: str) -> str:
    """Non-fatal error frame (ne zatvara socket). Korišćen pri
    malformed envelope-ovima u recv loop-u."""
    return _envelope("system.error", {"code": code, "message": message})


# ── Reads ────────────────────────────────────────────────────────────────────


async def list_recent(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 50,
    unread_only: bool = False,
) -> list[NotificationResponse]:
    """Vraća poslednjih ``limit`` notifikacija za korisnika, najnovije prvo.

    Frontend ``useNotifications`` zove ovo bez paginacije — limit je
    dovoljan jer dropdown prikazuje top 10, a "Vidi sve" stranica nije
    deo V1 (frontend trenutno render-uje sve što stigne).
    """
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return [NotificationResponse.model_validate(row) for row in rows]


async def get_unread_count(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: UUID,
) -> int:
    """Vraća broj nepročitanih notifikacija. Redis-first sa DB fallback-om.

    Redis ključ ``notif:unread:{user_id}`` je *cache*; DB je autoritativan.
    Ako Redis-u nedostaje ključ (cold start, eviction) → izračunavamo iz
    DB-a i upišemo nazad (lazy backfill). Ako Redis padne potpuno →
    ignorišemo grešku, vraćamo DB count direktno.
    """
    try:
        cached = await redis.get(notif_unread_key(user_id))
        if cached is not None:
            return int(cached)
    except Exception as exc:  # noqa: BLE001 — defensive (Redis flap)
        _log.warning(
            "notification_service.get_unread_count: Redis GET failed user=%s err=%s",
            user_id, exc,
        )

    # Fallback: DB count + lazy cache write.
    db_count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    db_count = int(db_count or 0)

    try:
        await redis.set(notif_unread_key(user_id), db_count)
    except Exception:
        pass  # cache miss next time je OK

    return db_count


# ── Writes ───────────────────────────────────────────────────────────────────


async def create(
    db: AsyncSession,
    redis: aioredis.Redis,
    *,
    user_id: UUID,
    type: NotificationType,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    dispatch_push_in_background: bool = True,
) -> Notification:
    """Kreira notifikaciju + INCR counter + publish ``notification.created``.

    Redosled:
        1. INSERT u ``notifications`` tabelu (commit eksplicitno — drugi
           browser tab istog korisnika koji već ima WS otvoren mora videti
           red ako po sledećem REST GET-u ode na DB).
        2. ``INCR notif:unread:{user_id}`` da counter ostane konzistentan
           sa Redis cache-om (``get_unread_count`` Redis-first).
        3. ``redis.publish(notif:pub:{user_id}, envelope)`` — fan-out na
           sve otvorene WS-ove istog korisnika; svaki dobija
           ``notification.created`` event.
        4. Bonus publish ``notification.unread_count`` da counter na bell
           ikonici skoči odmah (frontend ``setQueryData`` direktno).

    Greške na nivou Redis-a su LOG-ovane i swallow-ovane: notifikacija je
    perzistentna u DB-u i klijent će je videti na sledećem reconnect-u
    (schema §7.3 — "publish je fire-and-forget").
    """
    notif = Notification(
        user_id=user_id,
        type=type.value,
        title=title,
        body=body,
        data=data,
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    # Eager commit kao u chat_service.send_message — drugi worker / drugi
    # tab istog korisnika koji ode na ``GET /notifications`` mora odmah
    # videti red.
    await db.commit()
    await db.refresh(notif)

    # Redis side-effects: INCR + 2 publish-a. Sve u try/except — DB row je
    # kanonski izvor, Redis je cache + push transport.
    try:
        new_count = await redis.incr(notif_unread_key(user_id))
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "notification_service.create: Redis INCR failed user=%s notif=%s err=%s",
            user_id, notif.id, exc,
        )
        new_count = None

    try:
        await redis.publish(
            notif_pub_channel(user_id),
            build_notification_created_envelope(notif),
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "notification_service.create: Redis publish (created) failed user=%s notif=%s err=%s",
            user_id, notif.id, exc,
        )

    if new_count is not None:
        try:
            await redis.publish(
                notif_pub_channel(user_id),
                build_unread_count_envelope(int(new_count)),
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "notification_service.create: Redis publish (unread_count) failed user=%s err=%s",
                user_id, exc,
            )

    # ── Web Push fan-out (KORAK 1 Prompta 2) ────────────────────────────────
    #
    # Dva režima zavisno od poziva:
    #
    # (A) ``dispatch_push_in_background=True`` (default, FastAPI request):
    #     Fire-and-forget kroz ``asyncio.create_task``. Korisnik koji čita
    #     POST response dobija < 100ms (in-app + Redis publish je gotov),
    #     push se isporučuje u pozadini sa do 5s budgeta. Ako padne
    #     (timeout, push servis 503, mrtve pretplate), in-app i email i
    #     dalje rade — push je nice-to-have.
    #
    # (B) ``dispatch_push_in_background=False`` (Celery task wrapper):
    #     Await push DIREKTNO. Razlog: Celery taskovi pokreću
    #     ``asyncio.run(_run())`` koji na cleanup-u zove ``_cancel_all_tasks``
    #     (Python 3.11+ standardno ponašanje) — to bi cancel-ovalo background
    #     ``_safe_push()`` task PRE nego što HTTP roundtrip ka FCM/Mozilla
    #     servisu završi. Pošto Celery task ionako traje 1-3s, dodatnih
    #     200-500ms za push ne smeta; bitno je da push uopšte stigne.
    #     90% notifikacija dolazi iz Celery taskova (appointment_confirmed,
    #     cancelled, reminder, strike, block, waitlist_offer, document_*),
    #     pa je ovaj branch kritičan za demo.
    #
    # Background task u režimu (A) otvara NEZAVISNU DB sesiju iz
    # AsyncSessionLocal — ``db`` iz request handler-a će biti zatvoren čim
    # FastAPI završi response. Glavni engine (ne NullPool) je OK ovde jer
    # smo u jednom istom FastAPI event loop-u, nema cross-loop rizika kao
    # u Celery taskovima (Faza 4.5 pattern).

    async def _safe_push(use_independent_session: bool) -> None:
        try:
            if use_independent_session:
                async with AsyncSessionLocal() as bg_db:
                    await push_service.send_push(
                        bg_db,
                        user_id=user_id,
                        notification_type=type.value,
                        title=title,
                        body=body,
                        data=data,
                    )
            else:
                await push_service.send_push(
                    db,
                    user_id=user_id,
                    notification_type=type.value,
                    title=title,
                    body=body,
                    data=data,
                )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "notification_service.create: push dispatch failed user=%s notif=%s err=%s",
                user_id, notif.id, exc,
            )

    if dispatch_push_in_background:
        try:
            asyncio.create_task(_safe_push(use_independent_session=True))
        except RuntimeError as exc:
            _log.warning(
                "notification_service.create: cannot dispatch push (no running loop) user=%s err=%s",
                user_id, exc,
            )
    else:
        await _safe_push(use_independent_session=False)

    return notif


async def mark_read(
    db: AsyncSession,
    redis: aioredis.Redis,
    *,
    user_id: UUID,
    notification_id: UUID,
) -> bool:
    """Markira pojedinačnu notifikaciju kao pročitanu.

    Idempotent: ako je već ``is_read=True``, vraća ``False`` i ne menja
    counter (sprečava se under-flow ispod 0). Vraća ``True`` ako je promena
    izvršena. RBAC: ``WHERE user_id = :user_id`` u UPDATE-u — pokušaj da
    se pročita tuđa notifikacija završava sa ``False`` (no-op).

    Posle uspešne promene publish-uje novi ``notification.unread_count``
    na ``notif:pub:{user_id}`` da svi otvoreni tabovi istog korisnika
    sinhronizuju badge.
    """
    stmt = (
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .returning(Notification.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    await db.commit()

    if row is None:
        return False  # not found, not yours, or already read

    # Counter sync — DECR a ne SET (drugi tab je možda upravo INCR-ovao
    # zbog nove notifikacije). Ako Redis padne, lazy backfill u
    # get_unread_count će sledeći put ispraviti vrednost iz DB-a.
    try:
        new_count = await redis.decr(notif_unread_key(user_id))
        # Defenzivno: ako je counter pao ispod 0 (cache drift), ispravi.
        if int(new_count) < 0:
            await redis.set(notif_unread_key(user_id), 0)
            new_count = 0
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "notification_service.mark_read: Redis DECR failed user=%s notif=%s err=%s",
            user_id, notification_id, exc,
        )
        new_count = None

    if new_count is not None:
        try:
            await redis.publish(
                notif_pub_channel(user_id),
                build_unread_count_envelope(int(new_count)),
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "notification_service.mark_read: Redis publish (unread_count) failed user=%s err=%s",
                user_id, exc,
            )

    return True


async def mark_all_read(
    db: AsyncSession,
    redis: aioredis.Redis,
    *,
    user_id: UUID,
) -> int:
    """Markira sve nepročitane notifikacije kao pročitane.

    Vraća broj ažuriranih redova. Posle uspeha resetuje counter na 0 i
    publish-uje ``notification.unread_count{count: 0}`` za cross-tab sync.
    """
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .returning(Notification.id)
    )
    result = await db.execute(stmt)
    affected = len(list(result.scalars().all()))
    await db.commit()

    try:
        await redis.set(notif_unread_key(user_id), 0)
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "notification_service.mark_all_read: Redis SET 0 failed user=%s err=%s",
            user_id, exc,
        )

    try:
        await redis.publish(
            notif_pub_channel(user_id),
            build_unread_count_envelope(0),
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "notification_service.mark_all_read: Redis publish failed user=%s err=%s",
            user_id, exc,
        )

    return affected
