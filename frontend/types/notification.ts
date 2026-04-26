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

// ── Web Push (KORAK 1 Prompta 2 / PRD §5.3) ─────────────────────────────────

/**
 * The two ECDH keys returned by `PushSubscription.toJSON()` in the browser.
 * Both are base64url-encoded strings without padding (Web Push API spec).
 *
 * Field names match the browser-emitted JSON shape verbatim — `p256dh` and
 * `auth`. Backend Pydantic mirror MUST keep the same names so we can pass
 * through `JSON.stringify(subscription)` without remapping.
 */
export interface WebPushKeys {
  p256dh: string
  auth: string
}

/**
 * Body of `POST /api/v1/notifications/subscribe`.
 *
 * The browser yields a `PushSubscription` object whose JSON representation
 * already matches `{ endpoint, keys: { p256dh, auth } }`. We layer one
 * optional `user_agent` field on top for debug diagnostics (which device
 * accepted push); the browser never gives this directly so the frontend
 * sources it from `navigator.userAgent`.
 */
export interface PushSubscribeRequest {
  endpoint: string
  keys: WebPushKeys
  user_agent?: string | null
}

/**
 * Body of `POST /api/v1/notifications/unsubscribe`.
 *
 * Endpoint alone is enough — backend filters by `(user_id, endpoint)`
 * UNIQUE constraint, so we don't need to re-send the keys.
 */
export interface PushUnsubscribeRequest {
  endpoint: string
}

/**
 * Response of `GET /api/v1/notifications/vapid-public-key`.
 *
 * `public_key` is base64url-encoded raw EC P-256 public key (65 bytes
 * uncompressed — `\x04` || X || Y). The browser's
 * `pushManager.subscribe({ applicationServerKey })` expects this exact
 * format after `urlBase64ToUint8Array` decoding.
 */
export interface VapidPublicKeyResponse {
  public_key: string
}

/**
 * Lightweight DB row mirror returned by `subscribe` for diagnostics.
 *
 * The frontend doesn't render this anywhere in V1 — we keep the response
 * non-empty so the hook can detect successful UPSERT vs. error without
 * relying on HTTP-status sniffing.
 */
export interface PushSubscriptionResponse {
  id: Uuid
  endpoint: string
  created_at: IsoDateTime
}

/**
 * Slack/Discord-style trimmed push payload sent by `pywebpush` to the
 * push service and unwrapped inside the service worker `push` event
 * handler. We deliberately keep this small (≤200 bytes typical) to:
 *   - stay well under the 4KB Web Push payload cap,
 *   - avoid leaking the full `body` of sensitive notifications to the
 *     OS notification center (privacy — full text is fetched fresh on
 *     SW `notificationclick` via the in-app stream / REST GET),
 *   - keep over-the-air bandwidth low on metered mobile data.
 *
 * Field semantics:
 *   title — bell title (≤80 chars trimmed by backend if longer).
 *   body  — short summary (≤140 chars trimmed by backend).
 *   url   — absolute deep link the SW opens on `notificationclick`.
 *   type  — `NotificationType` literal; SW uses it for icon/badge selection.
 *   tag   — Web Push `tag` (newer payload with same tag REPLACES older one
 *           in OS notification tray — prevents reminder spam).
 */
export interface PushNotificationPayload {
  title: string
  body: string
  url: string
  type: NotificationType
  tag: string
}
