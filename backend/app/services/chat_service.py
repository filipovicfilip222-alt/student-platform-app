"""Per-appointment chat service.

Faza 3.3 (REST polling fallback) and Faza 4.1 (WebSocket + Redis Pub/Sub)
both consume this module — there is exactly one ``send_message`` implementation
so REST and WS callers cannot drift. The only difference between transports
is whether the caller passes a Redis client; if it does, a fan-out envelope
is published to ``chat:pub:{appointment_id}`` so any open WebSocket sees the
new message in real time.

Business rules (PRD §3.4 + ``docs/websocket-schema.md §5``):
    - Maximum **20 messages** per appointment (hard cap; 21st send → 409).
    - Chat closes 24h after ``slot.slot_datetime`` OR if the appointment is
      not in ``APPROVED`` state. Distinct error messages so the UI can render
      the correct empty-state copy.
    - All participants of the appointment (RBAC delegated to
      ``appointment_detail_service.load_appointment_for_user``) may read and
      send. Admins without impersonation are blocked one layer above.

The WS-shaped helpers (``list_messages_ws``, ``build_chat_message_envelope``)
return ``WsChatMessageData`` instances mirroring
``frontend/types/chat.ts::WsChatMessage`` (nested ``sender``,
``message_number`` ordinal). They are deliberately separate from the flat
``ChatMessageResponse`` REST shape so neither contract bleeds into the other.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.chat import TicketChatMessage
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import ChatMessageResponse
from app.schemas.chat import (
    ChatClosedReason,
    ChatSenderData,
    WsChatMessageData,
)
from app.services.appointment_detail_service import load_appointment_for_user


# ── Constants ────────────────────────────────────────────────────────────────

MAX_MESSAGES_PER_APPOINTMENT = 20  # PRD §3.4
CHAT_WINDOW_AFTER_SLOT = timedelta(hours=24)  # PRD §3.4

ChatCloseReason = Literal["NOT_APPROVED", "WINDOW_EXPIRED"]


def chat_pub_channel(appointment_id: UUID) -> str:
    """Redis Pub/Sub channel name. Centralised so the WS handler and the
    publisher cannot disagree on the format."""
    return f"chat:pub:{appointment_id}"


# ── Pure helpers ─────────────────────────────────────────────────────────────


def chat_close_reason(appointment: Appointment) -> ChatCloseReason | None:
    """Return why the chat is closed, or ``None`` if it is open.

    Reused by the REST layer (which raises 410 GONE) and the WebSocket layer
    (which maps it to a ``chat.closed`` envelope + close 4430). The WS-side
    mapping lives in :func:`chat_closed_ws_reason` below.
    """
    if appointment.status != AppointmentStatus.APPROVED:
        return "NOT_APPROVED"

    now_utc = datetime.now(timezone.utc)
    if appointment.slot.slot_datetime + CHAT_WINDOW_AFTER_SLOT <= now_utc:
        return "WINDOW_EXPIRED"

    return None


def chat_closed_ws_reason(appointment: Appointment) -> ChatClosedReason | None:
    """Map :func:`chat_close_reason` to the frontend-facing close reason
    (``frontend/types/ws.ts::ChatClosedReason``).

    Both ``NOT_APPROVED`` (PENDING / REJECTED / CANCELLED / COMPLETED) and any
    state where the 24h window has expired terminate the WS with close-code
    4430. The reason string drives the copy in ``<ChatClosedNotice />``.
    """
    reason = chat_close_reason(appointment)
    if reason is None:
        return None
    if reason == "WINDOW_EXPIRED":
        return "WINDOW_EXPIRED"
    return "APPOINTMENT_CANCELLED"


def _close_reason_to_message(reason: ChatCloseReason) -> str:
    if reason == "NOT_APPROVED":
        return "Chat nije dostupan za ovaj termin."
    return "Chat je zatvoren."


def chat_closes_at(appointment: Appointment) -> datetime:
    """Absolute timestamp at which the chat window closes for this
    appointment. Used by the WS handler in the ``chat.history`` payload so
    the frontend can render a countdown."""
    return appointment.slot.slot_datetime + CHAT_WINDOW_AFTER_SLOT


# ── Reads ────────────────────────────────────────────────────────────────────


async def count_messages(db: AsyncSession, appointment_id: UUID) -> int:
    total = await db.scalar(
        select(func.count(TicketChatMessage.id)).where(
            TicketChatMessage.appointment_id == appointment_id
        )
    )
    return int(total or 0)


async def list_messages(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> list[ChatMessageResponse]:
    """REST polling shape — flat ``sender_id``. ASC chronological.

    The 20-message cap means we can safely return the full history without
    pagination; the frontend renders top-down.
    """
    await load_appointment_for_user(db, current_user, appointment_id)

    result = await db.execute(
        select(TicketChatMessage)
        .where(TicketChatMessage.appointment_id == appointment_id)
        .order_by(TicketChatMessage.created_at.asc())
    )
    rows = list(result.scalars().all())
    return [_to_response(m) for m in rows]


async def list_messages_ws(
    db: AsyncSession,
    appointment_id: UUID,
) -> list[WsChatMessageData]:
    """WS-shaped history: nested sender + 1..20 ``message_number`` ordinal.

    RBAC is **not** enforced here — the WS handler validates the user once at
    handshake (``CLAUDE.md §12``) and only then calls this helper to build the
    initial ``chat.history`` payload.
    """
    result = await db.execute(
        select(TicketChatMessage)
        .options(selectinload(TicketChatMessage.sender))
        .where(TicketChatMessage.appointment_id == appointment_id)
        .order_by(TicketChatMessage.created_at.asc())
    )
    rows = list(result.scalars().all())
    return [_to_ws_payload(m, idx + 1) for idx, m in enumerate(rows)]


# ── Write ────────────────────────────────────────────────────────────────────


async def send_message(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    content: str,
    *,
    redis: aioredis.Redis | None = None,
    skip_rbac: bool = False,
) -> ChatMessageResponse:
    """Persist a chat message after enforcing all business rules.

    Pydantic enforces ``content`` length (1..1000); the only additional check
    here is non-empty after ``.strip()``. When ``redis`` is provided, a
    ``chat.message`` envelope is published to ``chat:pub:{appointment_id}``
    after the row is committed — so any open WebSocket fan-out task picks it
    up. Publish failures are logged and swallowed: the message is durably in
    the database, and any reconnecting client will re-fetch it via
    ``chat.history`` (schema §7.3).

    ``skip_rbac=True`` is used by the WS handler — it has already validated
    the user once at handshake and re-validating per-message would re-load
    the appointment and waste a round-trip (CLAUDE.md §12).
    """
    if skip_rbac:
        appointment = await _load_appointment_no_rbac(db, appointment_id)
    else:
        appointment = await load_appointment_for_user(
            db, current_user, appointment_id
        )

    reason = chat_close_reason(appointment)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_close_reason_to_message(reason),
        )

    stripped = content.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Poruka ne sme biti prazna.",
        )

    current_count = await count_messages(db, appointment_id)
    if current_count >= MAX_MESSAGES_PER_APPOINTMENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limit od {MAX_MESSAGES_PER_APPOINTMENT} poruka po terminu je dostignut.",
        )

    message = TicketChatMessage(
        appointment_id=appointment_id,
        sender_id=current_user.id,
        content=stripped,
    )
    db.add(message)
    await db.flush()
    # Eager-commit so a parallel WS subscriber loading chat.history (or a REST
    # poller hitting GET /messages) sees the row immediately. Pattern matches
    # ``booking_service.book_slot`` which also commits explicitly.
    await db.commit()
    await db.refresh(message)

    # Fire-and-forget Redis publish for live WS fan-out. Failure here MUST NOT
    # roll back the persisted row — clients will see the message via
    # chat.history on reconnect (schema §7.3) or via the REST polling fallback
    # in ``frontend/components/chat/ticket-chat.tsx``.
    if redis is not None:
        message_number = current_count + 1
        ws_payload = _to_ws_payload_with_user(message, current_user, message_number)
        envelope = build_chat_message_envelope(
            ws_payload,
            remaining=MAX_MESSAGES_PER_APPOINTMENT - message_number,
        )
        try:
            await redis.publish(chat_pub_channel(appointment_id), envelope)
        except Exception as exc:  # noqa: BLE001 — defensive; details captured in log
            import logging

            logging.getLogger(__name__).warning(
                "chat_service: Redis publish failed for appointment=%s message=%s err=%s",
                appointment_id,
                message.id,
                exc,
            )

    return _to_response(message)


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _load_appointment_no_rbac(
    db: AsyncSession, appointment_id: UUID
) -> Appointment:
    """Fetch an appointment with the ``slot`` relation loaded (needed for the
    24h window check) — without re-running RBAC. Used by the WS recv loop
    after the per-connection handshake check has already passed.
    """
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        # Should be unreachable: handshake already validated existence. We
        # surface 404 so the caller can map to close 4404 if it ever happens
        # (e.g. appointment deleted mid-session).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin nije pronađen.",
        )
    return appointment


def _to_response(row: TicketChatMessage) -> ChatMessageResponse:
    """Flat REST shape (``schemas/appointment.py::ChatMessageResponse``)."""
    return ChatMessageResponse(
        id=row.id,
        appointment_id=row.appointment_id,
        sender_id=row.sender_id,
        content=row.content,
        created_at=row.created_at,
    )


def _to_ws_payload(
    row: TicketChatMessage, message_number: int
) -> WsChatMessageData:
    """Build the WS-shaped payload from a row whose ``sender`` relation has
    been eagerly loaded (e.g. via ``selectinload``)."""
    return WsChatMessageData(
        id=row.id,
        sender=ChatSenderData(
            id=row.sender.id,
            full_name=row.sender.full_name,
            role=row.sender.role,
        ),
        content=row.content,
        created_at=row.created_at,
        message_number=message_number,
    )


def _to_ws_payload_with_user(
    row: TicketChatMessage, sender: User, message_number: int
) -> WsChatMessageData:
    """Same as :func:`_to_ws_payload` but uses an explicit ``User`` arg —
    avoids triggering an async lazy-load when we already have the sender in
    hand (e.g. ``current_user`` inside ``send_message``)."""
    return WsChatMessageData(
        id=row.id,
        sender=ChatSenderData(
            id=sender.id,
            full_name=sender.full_name,
            role=sender.role,
        ),
        content=row.content,
        created_at=row.created_at,
        message_number=message_number,
    )


# ── Envelope builders (single source of truth for JSON payloads) ─────────────


def _envelope(event: str, data: dict) -> str:
    """JSON-encode a WS envelope ``{event, ts, data}`` per schema §3.

    Centralised so handler code stays declarative — the publisher and the
    WS subscriber emit identical bytes."""
    return json.dumps(
        {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": data,
        }
    )


def build_chat_message_envelope(
    payload: WsChatMessageData, *, remaining: int
) -> str:
    """``chat.message`` — broadcast a single message to all subscribers
    (including the sender, for echo + persist confirmation).
    """
    data = payload.model_dump(mode="json")
    data["remaining"] = remaining
    return _envelope("chat.message", data)


def build_chat_history_envelope(
    messages: list[WsChatMessageData], *, closes_at: datetime
) -> str:
    """``chat.history`` — initial snapshot sent once on accept()."""
    total = len(messages)
    return _envelope(
        "chat.history",
        {
            "messages": [m.model_dump(mode="json") for m in messages],
            "total": total,
            "remaining": MAX_MESSAGES_PER_APPOINTMENT - total,
            "closes_at": closes_at.isoformat(),
        },
    )


def build_chat_limit_reached_envelope(*, total: int) -> str:
    """``chat.limit_reached`` — sent right before close 4409 on the 21st
    attempt or when the cap is hit naturally."""
    return _envelope("chat.limit_reached", {"total": total})


def build_chat_closed_envelope(reason: ChatClosedReason) -> str:
    """``chat.closed`` — emitted before close 4430 to give the frontend a
    structured reason for ``<ChatClosedNotice />``."""
    return _envelope("chat.closed", {"reason": reason})


def build_system_error_envelope(*, code: str, message: str) -> str:
    """Non-fatal error frame (does not close the socket)."""
    return _envelope("system.error", {"code": code, "message": message})


def build_system_ping_envelope(*, seq: int) -> str:
    """25s heartbeat ping per schema §3.1 + §7.1."""
    return _envelope("system.ping", {"seq": seq})
