"""Pydantic V2 schemas for the WebSocket chat layer (Faza 4.1).

These schemas are **distinct** from ``schemas/appointment.py::ChatMessageResponse``
which mirrors the REST polling contract (flat ``sender_id`` field). The WS
contract in ``frontend/types/chat.ts::WsChatMessage`` requires a nested
``sender`` object with ``full_name`` + ``role`` (so the UI can render bubbles
without a second user lookup) and a 1..20 ``message_number`` ordinal that
drives the "X/20" counter.

Both contracts coexist because the REST endpoint cannot expose the WS shape
without breaking the polling fallback (``frontend/components/chat/ticket-chat.tsx``
still uses it). The WS handler builds these payloads explicitly via
``chat_service.list_messages_ws`` / ``_to_ws_payload``.

Source of truth:
    - ``docs/websocket-schema.md §5`` (chat namespace)
    - ``docs/websocket-schema.md §3`` (envelope)
    - ``frontend/types/chat.ts`` (TS contract — paired field-by-field)
    - ``frontend/types/ws.ts`` (WsEnvelope, ChatWsEvent, WS_CLOSE_CODES)
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import UserRole


# ── Sender (nested in every chat WS message) ─────────────────────────────────


class ChatSenderData(BaseModel):
    """Nested sender object — see ``frontend/types/chat.ts::ChatSender``.

    The frontend role union is the four ``UserRole`` values as plain strings;
    we let Pydantic serialize the enum via its value (``UserRole.STUDENT.value
    == "STUDENT"``) by typing the field as the enum itself with the JSON dump
    using ``mode="json"`` semantics that Pydantic V2 applies automatically.
    """

    id: UUID
    full_name: str
    role: UserRole


# ── Message payloads ─────────────────────────────────────────────────────────


class WsChatMessageData(BaseModel):
    """Mirrors ``frontend/types/chat.ts::WsChatMessage``.

    Used as the ``data`` of three envelopes:
      - ``chat.history``   → list of these
      - ``chat.message``   → single one + ``remaining`` field grafted on
      - (server-side only — never deserialized from clients)
    """

    id: UUID
    sender: ChatSenderData
    content: str
    created_at: datetime
    message_number: int = Field(ge=1, le=20)


# ── Inbound (client → server) ────────────────────────────────────────────────


class ChatSendData(BaseModel):
    """Mirrors ``frontend/types/ws.ts::ChatSendEvent`` ``data`` shape.

    Length bounds match REST ``ChatMessageCreate`` (1..1000) so both transports
    enforce the same payload constraints. Whitespace-only content is rejected
    in the service layer (after ``.strip()``).
    """

    content: str = Field(min_length=1, max_length=1000)


# ── Closure reasons ──────────────────────────────────────────────────────────

# WS close-payload reason — must match
# ``frontend/types/ws.ts::ChatClosedReason`` exactly.
ChatClosedReason = Literal[
    "APPOINTMENT_CANCELLED",
    "WINDOW_EXPIRED",
    "ADMIN_ACTION",
]


# ── Server-side error codes (system.error.data.code) ─────────────────────────

# Subset of ``frontend/types/ws.ts::SystemErrorCode`` actually emitted by the
# chat handler. Re-declared here as a Literal to keep the contract tight.
ChatSystemErrorCode = Literal[
    "VALIDATION_FAILED",
    "RATE_LIMITED",
    "CHAT_LIMIT_REACHED",
    "CHAT_CLOSED",
    "INTERNAL_ERROR",
]
