"""Pydantic V2 schemas for the appointment detail / chat / files / participants
flow (Faza 3.3).

Each schema is paired 1:1 with the locked frontend contract in
``frontend/types/appointment.ts``. Fields use snake_case on both sides
(see CLAUDE.md §17 + CURRENT_STATE2.md §7).

Note on construction:
    The existing project convention (``backend/app/api/v1/students.py``) builds
    ``AppointmentResponse`` manually because ``slot_datetime`` requires a join
    on ``appointment.slot.slot_datetime``. We follow the same pattern here —
    services hydrate these schemas explicitly rather than relying on
    ``from_attributes`` traversing relationships.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AppointmentStatus,
    ConsultationType,
    ParticipantStatus,
    TopicCategory,
)


# ── Detail ────────────────────────────────────────────────────────────────────


class AppointmentDetailResponse(BaseModel):
    """Mirrors ``frontend/types/appointment.ts::AppointmentDetailResponse``.

    Flat shape — files / participants / messages live behind separate endpoints
    (``GET /{id}/files``, ``GET /{id}/participants``, ``GET /{id}/messages``).
    Counts here drive UI badges (e.g. "X/20" chat counter, file tab badge).
    """

    id: UUID
    slot_id: UUID
    professor_id: UUID
    lead_student_id: UUID
    subject_id: UUID | None
    topic_category: TopicCategory
    description: str
    status: AppointmentStatus
    consultation_type: ConsultationType
    slot_datetime: datetime
    created_at: datetime
    is_group: bool
    delegated_to: UUID | None
    rejection_reason: str | None
    chat_message_count: int
    file_count: int


# ── Chat (REST polling fallback; WS upgrade in Faza 4.1) ──────────────────────


class ChatMessageResponse(BaseModel):
    """Mirrors ``frontend/types/appointment.ts::ChatMessageResponse``.

    Flat REST shape (sender_id only). The WS chat envelope from
    ``docs/websocket-schema.md §5`` uses a nested ``sender`` object — that is a
    separate contract delivered with Faza 4.1 and intentionally not collapsed
    into this REST schema.
    """

    id: UUID
    appointment_id: UUID
    sender_id: UUID
    content: str
    created_at: datetime


class ChatMessageCreate(BaseModel):
    """Mirrors ``frontend/types/appointment.ts::ChatMessageCreate``.

    ``content`` is bounded by Pydantic; whitespace-only strings are rejected
    in the service layer (after ``.strip()``).
    """

    content: str = Field(min_length=1, max_length=1000)


# ── Files ─────────────────────────────────────────────────────────────────────


class FileResponse(BaseModel):
    """Mirrors ``frontend/types/appointment.ts::FileResponse``.

    ``download_url`` is a presigned MinIO GET URL with a 1h TTL. It is
    populated on list / upload responses and absent on bare DB reads.
    """

    id: UUID
    appointment_id: UUID
    uploaded_by: UUID
    filename: str
    mime_type: str
    file_size_bytes: int
    created_at: datetime
    download_url: str | None = None


# ── Participants (group consultations) ────────────────────────────────────────


class ParticipantResponse(BaseModel):
    """Mirrors ``frontend/types/appointment.ts::ParticipantResponse``.

    ``student_full_name`` is an optional convenience field hydrated via a join
    on ``users`` so the UI can render the participant list without a second
    round-trip.
    """

    id: UUID
    appointment_id: UUID
    student_id: UUID
    status: ParticipantStatus
    is_lead: bool
    confirmed_at: datetime | None
    student_full_name: str | None = None
