/**
 * appointment.ts — Appointment, chat, file and participant types.
 *
 * 1:1 mapping with backend/app/schemas/student.py where available.
 * Chat / file / participant / detail responses are not yet shipped by the
 * backend (ROADMAP 3.6) and are marked with explicit TODOs.
 */

import type {
  AppointmentStatus,
  ConsultationType,
  IsoDateTime,
  ParticipantStatus,
  TopicCategory,
  Uuid,
} from "./common"

// ── Request/response: booking flow ───────────────────────────────────────────
// Source: backend/app/schemas/student.py

export interface AppointmentCreateRequest {
  slot_id: Uuid
  topic_category: TopicCategory
  description: string
  subject_id?: Uuid | null
}

export interface AppointmentResponse {
  id: Uuid
  slot_id: Uuid
  professor_id: Uuid
  lead_student_id: Uuid
  subject_id: Uuid | null
  topic_category: TopicCategory
  description: string
  status: AppointmentStatus
  consultation_type: ConsultationType
  slot_datetime: IsoDateTime
  created_at: IsoDateTime
}

export interface AppointmentCancelResponse {
  id: Uuid
  status: AppointmentStatus
}

// ── Appointment detail + chat + files + participants ─────────────────────────
// TODO: sync with backend when schema is implemented (ROADMAP 3.6 introduces
//       /appointments/{id} detail + chat/messages + file + participant endpoints).

export interface AppointmentDetailResponse extends AppointmentResponse {
  /** Flag from models/appointment.py: true when slot.max_students > 1. */
  is_group: boolean
  /** Populated when professor delegates approval to an assistant. */
  delegated_to: Uuid | null
  /** Populated when professor rejects the appointment. */
  rejection_reason: string | null
  /** Count of chat messages — drives "X/20" counter. */
  chat_message_count: number
  /** Count of uploaded files. */
  file_count: number
}

export interface ChatMessageResponse {
  id: Uuid
  appointment_id: Uuid
  sender_id: Uuid
  content: string
  created_at: IsoDateTime
}

export interface ChatMessageCreate {
  content: string
}

export interface FileResponse {
  id: Uuid
  appointment_id: Uuid
  uploaded_by: Uuid
  filename: string
  mime_type: string
  file_size_bytes: number
  created_at: IsoDateTime
  /** Presigned MinIO download URL (time-limited). Populated on GET detail. */
  download_url?: string
}

export interface ParticipantResponse {
  id: Uuid
  appointment_id: Uuid
  student_id: Uuid
  status: ParticipantStatus
  is_lead: boolean
  confirmed_at: IsoDateTime | null
  /** Convenience: student full name (backend may expose via join). */
  student_full_name?: string
}

// ── Waitlist (student) ────────────────────────────────────────────────────────
// Source: backend/app/api/v1/students.py — POST/DELETE /waitlist/{slot_id}
// Backend returns MessageResponse with "Pozicija: N" in the text; we parse
// that on the client if needed. A dedicated response shape is not yet exposed.

export interface WaitlistPosition {
  slot_id: Uuid
  position: number
}
