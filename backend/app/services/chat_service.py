"""Per-appointment chat service (Faza 3.3 — REST polling fallback).

Business rules (PRD §3.4):
    - Maximum **20 messages** per appointment (hard cap; 21st send → 409).
    - Chat closes 24h after ``slot.slot_datetime`` OR if the appointment is
      not in ``APPROVED`` state. Distinct error messages so the UI can render
      the correct empty-state copy.
    - All participants of the appointment (RBAC delegated to
      ``appointment_detail_service.load_appointment_for_user``) may read and
      send. Admins without impersonation are blocked one layer above.

Faza 4.1 (WebSocket chat) reuses ``send_message`` and ``list_messages``
verbatim and adds Redis Pub/Sub fan-out on top — no logic should be
duplicated in the WS endpoint.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.chat import TicketChatMessage
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import ChatMessageResponse
from app.services.appointment_detail_service import load_appointment_for_user


# ── Constants ────────────────────────────────────────────────────────────────

MAX_MESSAGES_PER_APPOINTMENT = 20  # PRD §3.4
CHAT_WINDOW_AFTER_SLOT = timedelta(hours=24)  # PRD §3.4

ChatCloseReason = Literal["NOT_APPROVED", "WINDOW_EXPIRED"]


# ── Pure helpers ─────────────────────────────────────────────────────────────


def chat_close_reason(appointment: Appointment) -> ChatCloseReason | None:
    """Return why the chat is closed, or ``None`` if it is open.

    Reused by the WebSocket layer (Faza 4.1) to choose close codes 4403 vs
    4410 per ``docs/websocket-schema.md §5``.
    """
    if appointment.status != AppointmentStatus.APPROVED:
        return "NOT_APPROVED"

    now_utc = datetime.now(timezone.utc)
    if appointment.slot.slot_datetime + CHAT_WINDOW_AFTER_SLOT <= now_utc:
        return "WINDOW_EXPIRED"

    return None


def _close_reason_to_message(reason: ChatCloseReason) -> str:
    if reason == "NOT_APPROVED":
        return "Chat nije dostupan za ovaj termin."
    return "Chat je zatvoren."


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
    """Return all messages for an appointment in ASC chronological order.

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


# ── Write ────────────────────────────────────────────────────────────────────


async def send_message(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    content: str,
) -> ChatMessageResponse:
    """Persist a chat message after enforcing all business rules.

    Pydantic already enforces ``content`` length (1..1000); the only
    additional check here is that the post-strip content is non-empty.
    Faza 4.1 will add a Redis Pub/Sub publish call after the flush.
    """
    appointment = await load_appointment_for_user(db, current_user, appointment_id)

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
    await db.refresh(message)

    return _to_response(message)


def _to_response(row: TicketChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=row.id,
        appointment_id=row.appointment_id,
        sender_id=row.sender_id,
        content=row.content,
        created_at=row.created_at,
    )
