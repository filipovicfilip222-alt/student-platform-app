/**
 * admin.ts — Admin-facing types.
 *
 * TODO: sync with backend when schema is implemented.
 *       backend/app/schemas/admin.py does not exist yet (ROADMAP 4.3/4.7).
 *       Shapes below are the frontend's best-guess contract; confirm with
 *       Stefan before wiring real data.
 */

import type {
  Faculty,
  IsoDate,
  IsoDateTime,
  Role,
  StrikeReason,
  Uuid,
} from "./common"
import type { UserResponse } from "./auth"

// ── Users table ──────────────────────────────────────────────────────────────

export interface AdminUserCreate {
  email: string
  password: string
  first_name: string
  last_name: string
  role: Role
  faculty: Faculty
}

export type AdminUserUpdate = Partial<
  Omit<AdminUserCreate, "email" | "password">
> & {
  is_active?: boolean
}

/** Re-export UserResponse as the admin row shape (backend returns UserResponse). */
export type AdminUserResponse = UserResponse

// ── Bulk import (CSV) ────────────────────────────────────────────────────────

export interface BulkImportRow {
  row_number: number
  email: string
  first_name: string
  last_name: string
  role: Role
  faculty: Faculty
  password?: string
  errors: string[]
}

export interface BulkImportPreview {
  valid_rows: BulkImportRow[]
  invalid_rows: BulkImportRow[]
  duplicates: BulkImportRow[]
  total: number
}

export interface BulkImportResult {
  created: number
  skipped: number
  failed: number
}

// ── Strikes ──────────────────────────────────────────────────────────────────

export interface StrikeRow {
  student_id: Uuid
  student_full_name: string
  email: string
  faculty: Faculty
  total_points: number
  blocked_until: IsoDateTime | null
  last_strike_at: IsoDateTime | null
}

export interface StrikeRecord {
  id: Uuid
  student_id: Uuid
  appointment_id: Uuid
  points: number
  reason: StrikeReason
  created_at: IsoDateTime
}

export interface UnblockRequest {
  removal_reason: string
}

// ── Audit log ────────────────────────────────────────────────────────────────

export interface AuditLogRow {
  id: Uuid
  admin_id: Uuid
  admin_full_name: string
  impersonated_user_id: Uuid | null
  impersonated_user_full_name: string | null
  action: string
  ip_address: string
  created_at: IsoDateTime
}

export interface AuditLogFilter {
  admin_id?: Uuid
  action?: string
  from_date?: IsoDate
  to_date?: IsoDate
}

// ── Broadcast ────────────────────────────────────────────────────────────────

export type BroadcastTarget = "ALL" | "STUDENTS" | "STAFF" | "BY_FACULTY"
export type BroadcastChannel = "IN_APP" | "EMAIL"

export interface BroadcastRequest {
  title: string
  body: string
  target: BroadcastTarget
  faculty?: Faculty | null
  channels: BroadcastChannel[]
}

export interface BroadcastResponse {
  id: Uuid
  title: string
  body: string
  target: BroadcastTarget
  faculty: Faculty | null
  channels: BroadcastChannel[]
  sent_by: Uuid
  sent_at: IsoDateTime
  recipient_count: number
}

// ── Impersonation ────────────────────────────────────────────────────────────

export interface ImpersonationStartResponse {
  /** New JWT access token carrying the `imp` claim. */
  access_token: string
  token_type: "bearer"
  user: UserResponse
}

// ── Overview / dashboard metrics ─────────────────────────────────────────────

export interface AdminOverviewMetrics {
  pending_document_requests: number
  active_strikes: number
  blocked_students: number
  total_users: number
  appointments_last_7_days: number
}
