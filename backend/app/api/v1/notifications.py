"""Notifications router (Faza 4.2).

REST endpoint inventory poklapa se 1:1 sa ``frontend/lib/api/notifications.ts``:

    GET    /api/v1/notifications              → list[NotificationResponse]
    GET    /api/v1/notifications/unread-count → UnreadCountResponse
    POST   /api/v1/notifications/{id}/read    → MessageResponse
    POST   /api/v1/notifications/read-all     → MessageResponse

WebSocket endpoint (handler u ``websocket_handlers/`` modulu zbog veličine —
stiže u I-4.2.4):

    WS     /api/v1/notifications/stream       → push-only server→client

> ⚠️ ``CURSOR_PROMPT_1_BACKEND_COMPLETION.md §4.2`` pominje ``POST /mark-read``
> i ``POST /mark-all-read`` — to je interna omaška u prompt dokumentu.
> ``frontend/lib/api/notifications.ts`` (``markRead``, ``markAllRead``) zove
> ``POST /{id}/read`` odnosno ``POST /read-all``. Frontend je zaključan,
> backend prati frontend (CLAUDE.md §17, ROADMAP §6.5).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.dependencies import CurrentUser, DBSession, RedisClient, get_redis
from app.core.ws_deps import decode_ws_token
from app.schemas.auth import MessageResponse
from app.schemas.notification import (
    NotificationResponse,
    PushSubscribeRequest,
    PushSubscriptionResponse,
    PushUnsubscribeRequest,
    UnreadCountResponse,
    VapidPublicKeyResponse,
)
from app.services import notification_service, push_service

_log = logging.getLogger(__name__)

router = APIRouter()


# ── WS heartbeat constants (must match chat WS so frontend uses one config) ──
WS_HEARTBEAT_INTERVAL_SECONDS = 25  # schema §3.1 — server ping cadence
WS_HEARTBEAT_TIMEOUT_SECONDS = 60   # schema §3.1 — close 1001 if no pong


# ── List ─────────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="Lista notifikacija (najnovije prvo, max 50)",
)
async def list_notifications(
    db: DBSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
) -> list[NotificationResponse]:
    """Vraća sopstvene notifikacije sortirane DESC po ``created_at``.

    ``limit`` je hard-cap-ovan na 100 — frontend dropdown trenutno
    prikazuje top 10 a hooks default-uju na 50, paginated wrapper nije
    deo V1 ugovora (vidi ``schemas/notification.py`` JSDoc).
    """
    return await notification_service.list_recent(
        db, current_user.id, limit=limit, unread_only=unread_only
    )


# ── Unread counter ────────────────────────────────────────────────────────────


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Broj nepročitanih notifikacija (Redis cache + DB fallback)",
)
async def get_unread_count(
    db: DBSession,
    redis: RedisClient,
    current_user: CurrentUser,
) -> UnreadCountResponse:
    count = await notification_service.get_unread_count(db, redis, current_user.id)
    return UnreadCountResponse(count=count)


# ── Mark read ─────────────────────────────────────────────────────────────────


@router.post(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Markiraj jednu notifikaciju kao pročitanu",
)
async def mark_notification_read(
    notification_id: UUID,
    db: DBSession,
    redis: RedisClient,
    current_user: CurrentUser,
) -> MessageResponse:
    """Idempotent: ako je notif već pročitan ili ne pripada korisniku,
    vraćamo 404. Counter se DECR-uje samo pri stvarnoj promeni stanja.

    RBAC je u service sloju (``WHERE user_id = current_user.id`` u UPDATE-u),
    pa pokušaj da se pročita tuđa notifikacija završava sa 404 — namerno
    isto ponašanje kao "ne postoji", da ne curimo informaciju o tuđim ID-jevima.
    """
    ok = await notification_service.mark_read(
        db, redis, user_id=current_user.id, notification_id=notification_id
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notifikacija nije pronađena ili je već pročitana.",
        )
    return MessageResponse(message="Notifikacija je markirana kao pročitana.")


@router.post(
    "/read-all",
    response_model=MessageResponse,
    summary="Markiraj sve notifikacije kao pročitane",
)
async def mark_all_notifications_read(
    db: DBSession,
    redis: RedisClient,
    current_user: CurrentUser,
) -> MessageResponse:
    affected = await notification_service.mark_all_read(
        db, redis, user_id=current_user.id
    )
    return MessageResponse(
        message=f"Markirano kao pročitano: {affected} notifikacija."
    )


# ── Web Push (KORAK 1 Prompta 2 / PRD §5.3) ──────────────────────────────────


@router.get(
    "/vapid-public-key",
    response_model=VapidPublicKeyResponse,
    summary="VAPID javni ključ za PushManager.subscribe",
)
async def get_vapid_public_key(
    current_user: CurrentUser,
) -> VapidPublicKeyResponse:
    """Vraća VAPID javni ključ koji frontend prosleđuje u
    ``pushManager.subscribe({applicationServerKey})``.

    Auth ostaje obavezan iako je javni ključ tehnički nije tajna —
    fettuje ga samo prijavljen korisnik koji namerava da pretplati uređaj.
    Tako sprečavamo casual scraping i log-ujemo ko je pokušavao da
    pretplati push.

    503 ako VAPID nije konfigurisan (developer još nije pokrenuo
    ``scripts/generate_vapid_keys.py``) — frontend toggle će prikazati
    tooltip "Push trenutno nedostupan" umesto crash-a.
    """
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "VAPID nije konfigurisan na serveru — kontaktirajte "
                "administratora."
            ),
        )
    return VapidPublicKeyResponse(public_key=settings.VAPID_PUBLIC_KEY)


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pretplati ovaj uređaj na push notifikacije (UPSERT)",
)
async def subscribe_push(
    payload: PushSubscribeRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> PushSubscriptionResponse:
    """UPSERT pretplata za ``(current_user.id, payload.endpoint)``.

    Idempotent: drugi POST sa istim endpoint-om ne kreira drugi red, već
    osvežava ključeve i ``last_used_at`` (browser je možda re-subscribe-ovao
    posle VAPID rotation-a). Status code je 201 da bi semantika bila
    konzistentna sa REST CRUD-om — frontend hook ne razlikuje 201 od 200
    pa nije lomljiv.

    Ne dodaje se u audit log jer je per-user self-service akcija (isto
    kao mark_read pattern); push subscribe nije security-critical.
    """
    sub = await push_service.subscribe(
        db,
        user_id=current_user.id,
        endpoint=payload.endpoint,
        p256dh_key=payload.keys.p256dh,
        auth_key=payload.keys.auth,
        user_agent=payload.user_agent,
    )
    _log.info(
        "push.subscribe user=%s endpoint=%s…",
        current_user.id, payload.endpoint[:48],
    )
    return PushSubscriptionResponse.model_validate(sub)


@router.post(
    "/unsubscribe",
    response_model=MessageResponse,
    summary="Otkazi pretplatu ovog uređaja na push notifikacije",
)
async def unsubscribe_push(
    payload: PushUnsubscribeRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> MessageResponse:
    """DELETE pretplata po ``(current_user.id, endpoint)``.

    Idempotent: ako pretplata ne postoji (već obrisana, npr. browser je
    pozvao ``subscription.unsubscribe()`` paralelno sa našim cleanup-om
    posle 410 Gone), ipak vraćamo 200 OK — frontend ne mora da prati
    razliku između "obrisano sad" i "već nije bilo".
    """
    deleted = await push_service.unsubscribe(
        db,
        user_id=current_user.id,
        endpoint=payload.endpoint,
    )
    _log.info(
        "push.unsubscribe user=%s endpoint=%s… deleted=%s",
        current_user.id, payload.endpoint[:48], deleted,
    )
    return MessageResponse(
        message=(
            "Pretplata uklonjena." if deleted else "Pretplata već nije postojala."
        )
    )


# ── WebSocket: per-user notifications stream ─────────────────────────────────


@router.websocket("/stream")
async def notifications_websocket(websocket: WebSocket) -> None:
    """Per-user notifications stream (push-only server → client).

    Lifecycle (mirrors ``docs/websocket-schema.md §4`` + chat WS pattern):

        1. accept()
        2. JWT iz ``?token=...`` → ``decode_ws_token``; failure → close 4401.
           Kanal je iz ``user.id`` (sub claim) — nema URL parametra za user
           ID, što daje **implicitnu RBAC** (klijent ne može da pretplati
           tuđi kanal čak i da želi).
        3. Subscribe na ``notif:pub:{user.id}`` PRE inicijalnog send-a tako
           da se ništa publish-ovano u handshake prozoru ne izgubi.
        4. Send ``notification.unread_count`` snapshot (frontend popunjava
           bell badge bez čekanja na prvi REST GET).
        5. Tri concurrent task-a:
              recv_loop      — parsira ``system.pong`` (jedini dozvoljen
                               event sa klijenta), sve ostalo → ``system.error``
                               (ne zatvara socket).
              fanout_loop    — Redis pubsub → ``ws.send_text`` verbatim
                               (publisher već šalje frontend-shaped
                               envelope; nema re-serializacije).
              heartbeat_loop — ``system.ping`` svakih 25s; close 1001 ako
                               nema pong-a 60s.

    Push-only kanal: nema ``notification.send`` (kreiranje ide isključivo
    preko Celery taskova / admin REST-a — schema §4.1 napomena). Klijent
    šalje SAMO ``system.pong``; bilo koji drugi event tip je validacijska
    greška.
    """
    redis: aioredis.Redis = await get_redis()

    await websocket.accept()

    token = websocket.query_params.get("token", "")

    pubsub: aioredis.client.PubSub | None = None
    channel: str | None = None

    try:
        # ── Step 2: token + identify user ────────────────────────────────
        async with AsyncSessionLocal() as db:
            user = await decode_ws_token(token, db)
            if user is None:
                await websocket.close(code=4401, reason="Invalid or expired token")
                return

            # ── Step 3: subscribe FIRST ──────────────────────────────────
            channel = notification_service.notif_pub_channel(user.id)
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            # ── Step 4: initial unread snapshot ──────────────────────────
            initial_count = await notification_service.get_unread_count(
                db, redis, user.id
            )
            await websocket.send_text(
                notification_service.build_unread_count_envelope(initial_count)
            )

        # ── Step 5: three concurrent loops ───────────────────────────────
        last_pong_ts = time.monotonic()
        sent_ping_seq = 0

        async def heartbeat_loop() -> None:
            nonlocal sent_ping_seq, last_pong_ts
            while True:
                await asyncio.sleep(WS_HEARTBEAT_INTERVAL_SECONDS)
                if time.monotonic() - last_pong_ts > WS_HEARTBEAT_TIMEOUT_SECONDS:
                    await websocket.close(code=1001, reason="Heartbeat timeout")
                    return
                sent_ping_seq += 1
                try:
                    await websocket.send_text(
                        notification_service.build_system_ping_envelope(
                            seq=sent_ping_seq
                        )
                    )
                except Exception:
                    return

        async def fanout_loop() -> None:
            assert pubsub is not None
            async for raw in pubsub.listen():
                if raw is None:
                    continue
                if raw.get("type") != "message":
                    continue
                payload = raw.get("data")
                if payload is None:
                    continue
                try:
                    await websocket.send_text(
                        payload if isinstance(payload, str) else payload.decode()
                    )
                except Exception:
                    return

        async def recv_loop() -> None:
            nonlocal last_pong_ts
            while True:
                try:
                    raw = await websocket.receive_text()
                except WebSocketDisconnect:
                    return

                try:
                    envelope = json.loads(raw)
                    event_name = envelope.get("event")
                except (ValueError, AttributeError):
                    await _safe_send(
                        websocket,
                        notification_service.build_system_error_envelope(
                            code="VALIDATION_FAILED",
                            message="Neispravan format envelope-a.",
                        ),
                    )
                    continue

                if event_name == "system.pong":
                    last_pong_ts = time.monotonic()
                    continue

                # Push-only stream — sve ostalo je validacijska greška,
                # ali ne zatvaramo socket (klijent može da pošalje
                # nepoznat event tokom rolling deploy-a, npr. stari tab).
                await _safe_send(
                    websocket,
                    notification_service.build_system_error_envelope(
                        code="VALIDATION_FAILED",
                        message=f"Nepoznat event: {event_name!r}.",
                    ),
                )

        tasks = {
            asyncio.create_task(recv_loop(), name="ws-notif-recv"),
            asyncio.create_task(fanout_loop(), name="ws-notif-fanout"),
            asyncio.create_task(heartbeat_loop(), name="ws-notif-heartbeat"),
        }

        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for t in done:
            if not t.cancelled() and t.exception() is not None:
                _log.warning(
                    "notif_ws: task %s raised %s",
                    t.get_name(),
                    t.exception(),
                )
        for t in pending:
            t.cancel()
        for t in pending:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    except Exception as exc:  # noqa: BLE001
        _log.exception("notif_ws: unhandled error err=%s", exc)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=4500, reason="Internal error")
            except Exception:
                pass

    finally:
        if pubsub is not None and channel is not None:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass
            try:
                await pubsub.aclose()
            except Exception:
                pass
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass


async def _safe_send(websocket: WebSocket, payload: str) -> None:
    """``ws.send_text`` koji guta greške posle disconnect-a — recv_loop
    je možda već prijavio disconnect dok se error envelope formira."""
    try:
        await websocket.send_text(payload)
    except Exception:
        pass
