/**
 * notification.ts — Notification types.
 *
 * TODO: sync with backend when schema is implemented.
 *       backend/app/schemas/notification.py does not exist yet (ROADMAP 4.1).
 *       The SQLAlchemy model `Notification` exposes `type` as `String(50)`
 *       — we narrow it below to a documented set until the backend enforces
 *       an enum.
 */

import type { IsoDateTime, Uuid } from "./common"

/**
 * Known notification types dispatched by the backend. Non-exhaustive —
 * unknown strings are tolerated by widening to `string` at the boundary.
 */
export type NotificationType =
  | "APPOINTMENT_REQUESTED"
  | "APPOINTMENT_APPROVED"
  | "APPOINTMENT_REJECTED"
  | "APPOINTMENT_CANCELLED"
  | "APPOINTMENT_REMINDER"
  | "APPOINTMENT_DELEGATED"
  | "PARTICIPANT_INVITED"
  | "WAITLIST_SLOT_OPENED"
  | "DOCUMENT_REQUEST_APPROVED"
  | "DOCUMENT_REQUEST_REJECTED"
  | "DOCUMENT_REQUEST_READY"
  | "STRIKE_ISSUED"
  | "BLOCK_APPLIED"
  | "BLOCK_REMOVED"
  | "BROADCAST"
  | "CHAT_MESSAGE"

export interface NotificationResponse {
  id: Uuid
  user_id: Uuid
  type: NotificationType | string
  title: string
  body: string
  data: Record<string, unknown> | null
  is_read: boolean
  created_at: IsoDateTime
}

export interface UnreadCountResponse {
  count: number
}
