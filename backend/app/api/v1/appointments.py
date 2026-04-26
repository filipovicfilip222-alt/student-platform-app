"""Appointment detail / chat / files / participants router (Faza 3.3 + 4.1).

REST endpoint inventory mirrors ``frontend/lib/api/appointments.ts`` 1:1:

    GET    /{id}                                        → AppointmentDetailResponse
    GET    /{id}/messages                               → list[ChatMessageResponse]
    POST   /{id}/messages                               → ChatMessageResponse
    GET    /{id}/files                                  → list[FileResponse]
    POST   /{id}/files                          (multipart "file") → FileResponse
    DELETE /{id}/files/{file_id}                        → MessageResponse
    GET    /{id}/participants                           → list[ParticipantResponse]
    POST   /{id}/participants/{participant_id}/confirm  → ParticipantResponse
    POST   /{id}/participants/{participant_id}/decline  → ParticipantResponse

WebSocket endpoint (Faza 4.1):

    WS     /{id}/chat                                   → real-time chat fan-out

All REST endpoints depend on ``CurrentUser`` (any authenticated, active user).
RBAC is enforced inside the service layer
(``appointment_detail_service.load_appointment_for_user``) so the same rules
apply to REST and WS uniformly. The WS handler runs that check **once** at
handshake (CLAUDE.md §12) and then trusts the connection.
"""

import asyncio
import json
import logging
import time
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.websockets import WebSocketState

from app.core.database import AsyncSessionLocal
from app.core.dependencies import CurrentUser, DBSession, RedisClient, get_redis
from app.core.ws_deps import decode_ws_token
from app.schemas.appointment import (
    AppointmentDetailResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    FileResponse,
    ParticipantResponse,
)
from app.schemas.auth import MessageResponse
from app.schemas.chat import ChatSendData
from app.services import appointment_detail_service, chat_service

_log = logging.getLogger(__name__)

router = APIRouter()


# ── Detail ───────────────────────────────────────────────────────────────────


@router.get(
    "/{id}",
    response_model=AppointmentDetailResponse,
    summary="Detalji termina (flat shape sa countovima)",
)
async def get_appointment_detail(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> AppointmentDetailResponse:
    return await appointment_detail_service.get_detail(db, current_user, id)


# ── Chat (REST polling fallback; WS upgrade in Faza 4.1) ──────────────────────


@router.get(
    "/{id}/messages",
    response_model=list[ChatMessageResponse],
    summary="Lista chat poruka za termin (max 20)",
)
async def list_chat_messages(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[ChatMessageResponse]:
    return await chat_service.list_messages(db, current_user, id)


@router.post(
    "/{id}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
    summary="Slanje chat poruke (REST fallback dok WS ne live-uje)",
)
async def send_chat_message(
    id: UUID,
    data: ChatMessageCreate,
    db: DBSession,
    current_user: CurrentUser,
    redis: RedisClient,
) -> ChatMessageResponse:
    # Publish to chat:pub:{id} so any open WS subscriber sees REST-sent
    # messages live (cross-tab / cross-mode consistency, schema §5.2).
    return await chat_service.send_message(
        db, current_user, id, data.content, redis=redis
    )


# ── Files ────────────────────────────────────────────────────────────────────


@router.get(
    "/{id}/files",
    response_model=list[FileResponse],
    summary="Lista fajlova sa presigned download URL-ovima (TTL 1h)",
)
async def list_appointment_files(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[FileResponse]:
    return await appointment_detail_service.list_files(db, current_user, id)


@router.post(
    "/{id}/files",
    response_model=FileResponse,
    status_code=201,
    summary="Otpremanje fajla (multipart, max 5MB, MIME whitelist)",
)
async def upload_appointment_file(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> FileResponse:
    return await appointment_detail_service.upload_file(db, current_user, id, file)


@router.delete(
    "/{id}/files/{file_id}",
    response_model=MessageResponse,
    summary="Brisanje sopstvenog fajla (uploader-only)",
)
async def delete_appointment_file(
    id: UUID,
    file_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> MessageResponse:
    await appointment_detail_service.delete_file(db, current_user, id, file_id)
    return MessageResponse(message="Fajl je obrisan.")


# ── Participants (group consultations) ───────────────────────────────────────


@router.get(
    "/{id}/participants",
    response_model=list[ParticipantResponse],
    summary="Lista učesnika (sa student_full_name kroz join)",
)
async def list_appointment_participants(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[ParticipantResponse]:
    return await appointment_detail_service.list_participants(db, current_user, id)


@router.post(
    "/{id}/participants/{participant_id}/confirm",
    response_model=ParticipantResponse,
    summary="Potvrda sopstvenog učešća na grupnoj konsultaciji",
)
async def confirm_participation(
    id: UUID,
    participant_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> ParticipantResponse:
    return await appointment_detail_service.confirm_participant(
        db, current_user, id, participant_id
    )


@router.post(
    "/{id}/participants/{participant_id}/decline",
    response_model=ParticipantResponse,
    summary="Odbijanje sopstvenog učešća (lead ne može — neka otkaže termin)",
)
async def decline_participation(
    id: UUID,
    participant_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> ParticipantResponse:
    return await appointment_detail_service.decline_participant(
        db, current_user, id, participant_id
    )


# ── WebSocket chat (Faza 4.1) ────────────────────────────────────────────────

# Heartbeat constants per docs/websocket-schema.md §3.1 + §7.1.
WS_HEARTBEAT_INTERVAL_SECONDS = 25  # 25s per websocket-schema.md §3.1
WS_HEARTBEAT_TIMEOUT_SECONDS = 60   # 60s without pong → close 1001

# Per-sender rate limit per docs/websocket-schema.md §5.4 (1 msg / 500ms).
# Uses Redis SET NX PX so race-free across uvicorn workers.
WS_CHAT_RATE_LIMIT_PX = 500


def _chat_rate_limit_key(user_id: UUID, appointment_id: UUID) -> str:
    return f"chat:rl:{user_id}:{appointment_id}"


@router.websocket("/{id}/chat")
async def chat_websocket(
    websocket: WebSocket,
    id: UUID,
) -> None:
    """Per-appointment chat WebSocket.

    Lifecycle (mirrors docs/websocket-schema.md §5):

        1. accept()
        2. Token from ``?token=`` query param → ``decode_ws_token``;
           failure → close 4401.
        3. ``load_appointment_for_user`` (RBAC + existence) → close 4404 / 4403.
        4. ``chat_close_reason`` → close 4430 with ``chat.closed`` envelope.
        5. Subscribe to Redis channel ``chat:pub:{id}`` BEFORE loading
           history so no message published mid-handshake is lost (frontend
           dedupes by message id).
        6. Send ``chat.history`` snapshot.
        7. Run three concurrent tasks:
              recv_loop      — parse client envelopes (chat.send, system.pong)
              fanout_loop    — pump pubsub messages → ws.send_text
              heartbeat_loop — emit system.ping every 25s, close 1001 if no
                               pong within 60s
           First task to return cancels the other two; all cleanup runs in
           a single ``finally`` block (pubsub.unsubscribe + aclose, ws.close).
    """
    # Pull the Redis client manually — using ``Depends(get_redis)`` works on
    # WS too but mixing it with the DBSession dependency would tie a pool
    # connection to the entire WS lifetime, which is what we are trying to
    # avoid. Each DB op opens its own short session.
    redis: aioredis.Redis = await get_redis()

    await websocket.accept()

    # ── Step 2: token ─────────────────────────────────────────────────────
    token = websocket.query_params.get("token", "")

    pubsub: aioredis.client.PubSub | None = None
    channel = chat_service.chat_pub_channel(id)

    try:
        async with AsyncSessionLocal() as db:
            user = await decode_ws_token(token, db)
            if user is None:
                await websocket.close(code=4401, reason="Invalid or expired token")
                return

            # ── Step 3: RBAC + existence ─────────────────────────────────
            try:
                appointment = await appointment_detail_service.load_appointment_for_user(
                    db, user, id
                )
            except HTTPException as exc:
                if exc.status_code == 404:
                    await websocket.close(code=4404, reason="Appointment not found")
                elif exc.status_code == 403:
                    await websocket.close(code=4403, reason="Forbidden")
                else:
                    _log.warning(
                        "chat_ws: unexpected HTTPException at handshake user=%s appointment=%s status=%s",
                        user.id, id, exc.status_code,
                    )
                    await websocket.close(code=4500, reason="Internal error")
                return

            # ── Step 4: chat lifecycle (status / window) ─────────────────
            ws_reason = chat_service.chat_closed_ws_reason(appointment)
            if ws_reason is not None:
                # Send the structured envelope first so the frontend can
                # render <ChatClosedNotice /> with the right copy, THEN
                # close — both NOT_APPROVED and WINDOW_EXPIRED use 4430
                # for uniform UX (RBAC is the only 4403 case).
                try:
                    await websocket.send_text(
                        chat_service.build_chat_closed_envelope(ws_reason)
                    )
                except Exception:
                    pass
                await websocket.close(code=4430, reason=ws_reason)
                return

            # ── Step 5: subscribe FIRST ──────────────────────────────────
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)

            # ── Step 6: load + send history ──────────────────────────────
            history = await chat_service.list_messages_ws(db, id)
            history_envelope = chat_service.build_chat_history_envelope(
                history,
                closes_at=chat_service.chat_closes_at(appointment),
            )
            await websocket.send_text(history_envelope)

        # DB session closed; ``user`` is detached but its scalar attrs
        # (id, first_name, last_name, role) were eagerly loaded so we can
        # still pass it to send_message. expire_on_commit=False guarantees
        # the attributes survive session close (see core/database.py).

        # ── Step 7: three concurrent tasks ───────────────────────────────
        last_pong_ts = time.monotonic()
        sent_ping_seq = 0

        async def heartbeat_loop() -> None:
            """25s ping per websocket-schema.md §3.1."""
            nonlocal sent_ping_seq, last_pong_ts
            while True:
                await asyncio.sleep(WS_HEARTBEAT_INTERVAL_SECONDS)
                # Window check — if the client never pong-ed within
                # the timeout, we close with 1001 (going away).
                if time.monotonic() - last_pong_ts > WS_HEARTBEAT_TIMEOUT_SECONDS:
                    await websocket.close(code=1001, reason="Heartbeat timeout")
                    return
                sent_ping_seq += 1
                try:
                    await websocket.send_text(
                        chat_service.build_system_ping_envelope(seq=sent_ping_seq)
                    )
                except Exception:
                    return

        async def fanout_loop() -> None:
            """Forward every Redis pubsub message to this connection."""
            assert pubsub is not None
            async for raw in pubsub.listen():
                if raw is None:
                    continue
                if raw.get("type") != "message":
                    continue
                payload = raw.get("data")
                if payload is None:
                    continue
                # The publisher already produced a frontend-shaped envelope
                # (chat_service.build_chat_message_envelope) so we forward
                # bytes verbatim — no re-serialization.
                try:
                    await websocket.send_text(
                        payload if isinstance(payload, str) else payload.decode()
                    )
                except Exception:
                    return

        async def recv_loop() -> None:
            """Parse client → server envelopes."""
            nonlocal last_pong_ts
            while True:
                try:
                    raw = await websocket.receive_text()
                except WebSocketDisconnect:
                    return

                # Envelope parse — anything malformed → system.error
                try:
                    envelope = json.loads(raw)
                    event_name = envelope.get("event")
                    data = envelope.get("data") or {}
                except (ValueError, AttributeError):
                    await _safe_send(
                        websocket,
                        chat_service.build_system_error_envelope(
                            code="VALIDATION_FAILED",
                            message="Neispravan format envelope-a.",
                        ),
                    )
                    continue

                if event_name == "system.pong":
                    last_pong_ts = time.monotonic()
                    continue

                if event_name != "chat.send":
                    await _safe_send(
                        websocket,
                        chat_service.build_system_error_envelope(
                            code="VALIDATION_FAILED",
                            message=f"Nepoznat event: {event_name!r}.",
                        ),
                    )
                    continue

                # Validate the chat.send payload
                try:
                    parsed = ChatSendData.model_validate(data)
                except ValidationError as exc:
                    await _safe_send(
                        websocket,
                        chat_service.build_system_error_envelope(
                            code="VALIDATION_FAILED",
                            message=exc.errors()[0].get("msg", "Neispravan unos."),
                        ),
                    )
                    continue

                # Per-sender rate limit (Redis SET NX PX, lock-free).
                rl_ok = await redis.set(
                    _chat_rate_limit_key(user.id, id),
                    "1",
                    px=WS_CHAT_RATE_LIMIT_PX,
                    nx=True,
                )
                if not rl_ok:
                    await _safe_send(
                        websocket,
                        chat_service.build_system_error_envelope(
                            code="RATE_LIMITED",
                            message="Šaljete poruke prebrzo.",
                        ),
                    )
                    continue

                # Persist (and, via redis= param, fan out to all
                # subscribers — including this connection's fanout_loop,
                # which doubles as the sender's own delivery confirmation).
                try:
                    async with AsyncSessionLocal() as send_db:
                        await chat_service.send_message(
                            send_db,
                            user,
                            id,
                            parsed.content,
                            redis=redis,
                            skip_rbac=True,  # Already validated at handshake.
                        )
                except HTTPException as exc:
                    if exc.status_code == 409:
                        # 21st message — emit chat.limit_reached then
                        # close 4409 (schema §5.3).
                        await _safe_send(
                            websocket,
                            chat_service.build_chat_limit_reached_envelope(
                                total=chat_service.MAX_MESSAGES_PER_APPOINTMENT,
                            ),
                        )
                        await websocket.close(
                            code=4409,
                            reason="Chat message limit reached",
                        )
                        return
                    if exc.status_code == 410:
                        # Window slammed shut between handshake and now
                        # (rare race). Emit chat.closed + close 4430.
                        await _safe_send(
                            websocket,
                            chat_service.build_chat_closed_envelope(
                                "WINDOW_EXPIRED"
                            ),
                        )
                        await websocket.close(
                            code=4430,
                            reason="WINDOW_EXPIRED",
                        )
                        return
                    if exc.status_code == 422:
                        await _safe_send(
                            websocket,
                            chat_service.build_system_error_envelope(
                                code="VALIDATION_FAILED",
                                message=str(exc.detail),
                            ),
                        )
                        continue
                    _log.warning(
                        "chat_ws.recv: unexpected HTTPException status=%s detail=%s",
                        exc.status_code, exc.detail,
                    )
                    await websocket.close(code=4500, reason="Internal error")
                    return
                except Exception as exc:  # noqa: BLE001
                    _log.exception(
                        "chat_ws.recv: unhandled error user=%s appointment=%s err=%s",
                        user.id, id, exc,
                    )
                    await websocket.close(code=4500, reason="Internal error")
                    return

        tasks = {
            asyncio.create_task(recv_loop(), name="ws-chat-recv"),
            asyncio.create_task(fanout_loop(), name="ws-chat-fanout"),
            asyncio.create_task(heartbeat_loop(), name="ws-chat-heartbeat"),
        }

        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        # Surface any non-cancelled exception in the completed task to the
        # log — the WS is going down anyway.
        for t in done:
            if not t.cancelled() and t.exception() is not None:
                _log.warning(
                    "chat_ws: task %s raised %s",
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

    finally:
        # Single cleanup point — runs regardless of which step exited.
        if pubsub is not None:
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
    """``ws.send_text`` that swallows errors after the connection is gone —
    keeps the recv/fanout/heartbeat loops simple."""
    try:
        await websocket.send_text(payload)
    except Exception:
        pass
