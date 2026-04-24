/**
 * professor.ts — Professor / availability / FAQ / CRM types.
 *
 * 1:1 mapping with backend/app/schemas/professor.py (and the professor-facing
 * slices of student.py). Types not yet present in backend schemas are marked
 * `// TODO: sync with backend when schema is implemented`.
 */

import type {
  ConsultationType,
  Faculty,
  IsoDate,
  IsoDateTime,
  Uuid,
} from "./common"

// ── Availability slots ───────────────────────────────────────────────────────
// Source: backend/app/schemas/professor.py::SlotCreate/SlotUpdate/SlotResponse

export interface SlotCreateRequest {
  slot_datetime: IsoDateTime
  duration_minutes: number
  consultation_type: ConsultationType
  max_students?: number
  online_link?: string | null
  is_available?: boolean
  recurring_rule?: Record<string, unknown> | null
  valid_from?: IsoDate | null
  valid_until?: IsoDate | null
}

export type SlotUpdateRequest = Partial<SlotCreateRequest>

export interface SlotResponse {
  id: Uuid
  professor_id: Uuid
  slot_datetime: IsoDateTime
  duration_minutes: number
  consultation_type: ConsultationType
  max_students: number
  online_link: string | null
  is_available: boolean
  recurring_rule: Record<string, unknown> | null
  valid_from: IsoDate | null
  valid_until: IsoDate | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

// ── Blackout periods ──────────────────────────────────────────────────────────
// Source: backend/app/schemas/professor.py::BlackoutCreate/BlackoutResponse

export interface BlackoutCreateRequest {
  start_date: IsoDate
  end_date: IsoDate
  reason?: string | null
}

export interface BlackoutResponse {
  id: Uuid
  professor_id: Uuid
  start_date: IsoDate
  end_date: IsoDate
  reason: string | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

// ── Search + profile (student-facing views) ──────────────────────────────────
// Source: backend/app/schemas/student.py

export interface ProfessorSearchResponse {
  id: Uuid
  full_name: string
  title: string
  department: string
  faculty: Faculty
  subjects: string[]
  consultation_types: ConsultationType[]
}

export interface FaqResponse {
  id: Uuid
  question: string
  answer: string
  sort_order: number
}

export interface AvailableSlotResponse {
  id: Uuid
  slot_datetime: IsoDateTime
  duration_minutes: number
  consultation_type: ConsultationType
  max_students: number
  online_link: string | null
}

export interface ProfessorProfileResponse {
  id: Uuid
  full_name: string
  title: string
  department: string
  office: string | null
  office_description: string | null
  faculty: Faculty
  areas_of_interest: string[]
  subjects: string[]
  faq: FaqResponse[]
  available_slots: AvailableSlotResponse[]
}

// ── Professor settings (ROADMAP 3.7) ─────────────────────────────────────────
// TODO: sync with backend when schema is implemented (schemas/professor.py
//       does not yet expose ProfileUpdate / FaqCreate / CannedResponse / CrmNote).

export interface ProfessorProfileUpdate {
  title?: string
  department?: string
  office?: string | null
  office_description?: string | null
  areas_of_interest?: string[]
  auto_approve_recurring?: boolean
  auto_approve_special?: boolean
  buffer_minutes?: number
}

export interface FaqCreate {
  question: string
  answer: string
  sort_order?: number
}

export type FaqUpdate = Partial<FaqCreate>

export interface CannedResponseCreate {
  title: string
  content: string
}

export type CannedResponseUpdate = Partial<CannedResponseCreate>

export interface CannedResponseResponse {
  id: Uuid
  professor_id: Uuid
  title: string
  content: string
  created_at: IsoDateTime
}

export interface CrmNoteCreate {
  student_id: Uuid
  content: string
}

export interface CrmNoteResponse {
  id: Uuid
  professor_id: Uuid
  student_id: Uuid
  content: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

// ── Subject (for dropdowns / assistant assignment) ───────────────────────────
// TODO: sync with backend when schema is implemented (schemas/subject.py missing).

export interface SubjectResponse {
  id: Uuid
  name: string
  code: string | null
  faculty: Faculty
  professor_id: Uuid | null
}
