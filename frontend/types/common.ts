/**
 * common.ts — Shared primitive types + enums that mirror the backend.
 *
 * Source of truth: backend/app/models/enums.py.
 * Each string-literal union must match the Python enum **values** (not names).
 *
 * NB: a few types are also declared in types/auth.ts (UserRole, Faculty) from
 * an earlier scaffolding pass. They are structurally identical, so they
 * remain assignable. Consolidation is a scheduled cleanup (see ROADMAP report).
 */

// ── Enum-backed unions ────────────────────────────────────────────────────────

export type Role = "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN"
export type Faculty = "FON" | "ETF"
export type ConsultationType = "UZIVO" | "ONLINE"
export type AppointmentStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "CANCELLED"
  | "COMPLETED"
export type TopicCategory =
  | "SEMINARSKI"
  | "PREDAVANJA"
  | "ISPIT"
  | "PROJEKAT"
  | "OSTALO"
export type ParticipantStatus = "PENDING" | "CONFIRMED" | "DECLINED"
export type StrikeReason = "LATE_CANCEL" | "NO_SHOW"
export type DocumentType =
  | "POTVRDA_STATUSA"
  | "UVERENJE_ISPITI"
  | "UVERENJE_PROSEK"
  | "PREPIS_OCENA"
  | "POTVRDA_SKOLARINE"
  | "OSTALO"
export type DocumentStatus = "PENDING" | "APPROVED" | "REJECTED" | "COMPLETED"

// ── Generic envelopes ─────────────────────────────────────────────────────────

/**
 * Pagination envelope.
 *
 * NB: as of April 2026 the backend list endpoints (students/appointments,
 * professors/search) still return bare `list[T]`. `Paginated<T>` is declared
 * here so the frontend is ready when the backend switches over (ROADMAP 1.6).
 * Existing API wrappers use `T[]` until that migration happens.
 */
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** FastAPI shape for a generic confirmation response. */
export interface MessageResponse {
  message: string
}

/**
 * All backend timestamps are ISO 8601 strings (datetime / date), transported
 * as JSON. Use these aliases to make intent explicit in type signatures.
 */
export type IsoDateTime = string
export type IsoDate = string
export type Uuid = string
