/**
 * notification.ts — Notification types.
 *
 * Source of truth: docs/websocket-schema.md §4.4 (catalog of notification types)
 * and §8.2 (TypeScript contract). Backend Pydantic shape will land in
 * backend/app/schemas/notification.py (ROADMAP 4.2) and must match 1:1.
 *
 * Do NOT invent alternative type names or extra fields without updating
 * websocket-schema.md first.
 */

import type { IsoDateTime, Uuid } from "./common"

/**
 * The 16 notification `type` values enumerated in websocket-schema.md §4.4.
 * Ordered exactly as the schema table to keep code review diffs tidy.
 */
export type NotificationType =
  | "APPOINTMENT_CONFIRMED"
  | "APPOINTMENT_REJECTED"
  | "APPOINTMENT_CANCELLED"
  | "APPOINTMENT_DELEGATED"
  | "APPOINTMENT_REMINDER_24H"
  | "APPOINTMENT_REMINDER_1H"
  | "NEW_APPOINTMENT_REQUEST"
  | "NEW_CHAT_MESSAGE"
  | "WAITLIST_OFFER"
  | "STRIKE_ADDED"
  | "BLOCK_ACTIVATED"
  | "BLOCK_LIFTED"
  | "DOCUMENT_REQUEST_APPROVED"
  | "DOCUMENT_REQUEST_REJECTED"
  | "DOCUMENT_REQUEST_COMPLETED"
  | "BROADCAST"

/**
 * NotificationResponse — mirrors the Pydantic shape from
 * websocket-schema.md §8.1 (`schemas/notification.py::NotificationResponse`).
 *
 * NB: the schema includes `data: dict | None` — a free-form payload whose
 * keys depend on `type` (see §4.4 table). We preserve this as
 * `Record<string, unknown> | null`; consumers that need a specific field
 * (e.g. `appointment_id`) should narrow locally.
 */
export interface NotificationResponse {
  id: Uuid
  type: NotificationType
  title: string
  body: string
  data: Record<string, unknown> | null
  is_read: boolean
  created_at: IsoDateTime
}

/**
 * Response for GET /api/v1/notifications/unread-count (REST fallback while
 * WS is unavailable). The WS channel also publishes this payload as
 * `notification.unread_count` events (schema §4.2).
 */
export interface UnreadCountResponse {
  count: number
}

/**
 * Notification types that should surface as a toast in addition to the bell
 * badge update. Derived directly from the "Kritičan (toast)" column in
 * websocket-schema.md §4.4 — keep in sync.
 */
export const TOAST_NOTIFICATION_TYPES: ReadonlySet<NotificationType> = new Set([
  "APPOINTMENT_CONFIRMED",
  "APPOINTMENT_REJECTED",
  "APPOINTMENT_CANCELLED",
  "APPOINTMENT_REMINDER_1H",
  "WAITLIST_OFFER",
  "STRIKE_ADDED",
  "BLOCK_ACTIVATED",
  "BLOCK_LIFTED",
  "DOCUMENT_REQUEST_APPROVED",
  "DOCUMENT_REQUEST_REJECTED",
  "BROADCAST",
])

export function shouldShowToast(type: NotificationType): boolean {
  return TOAST_NOTIFICATION_TYPES.has(type)
}
