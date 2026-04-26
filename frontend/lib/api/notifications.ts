/**
 * notifications.ts — Notification list / read state + Web Push REST wrapper.
 *
 * All mutations go through REST (websocket-schema.md §4.3). The WS channel
 * is push-only server→client; the client never sends notification events
 * other than `system.pong` heartbeats.
 *
 * Web Push wiring (KORAK 1 Prompta 2):
 *   - getVapidPublicKey() → backend serves the base64url-encoded raw EC
 *     P-256 public key; consumed by `urlBase64ToUint8Array` in the
 *     push-subscription hook before being passed to
 *     `pushManager.subscribe({ applicationServerKey })`.
 *   - subscribeToPush(payload) → UPSERT (status 201 even when an existing
 *     row was just refreshed; backend uses `ON CONFLICT DO UPDATE`).
 *   - unsubscribeFromPush(endpoint) → idempotent (returns 200 whether or
 *     not the row existed).
 */

import api from "@/lib/api"
import type {
  MessageResponse,
  NotificationResponse,
  PushSubscribeRequest,
  PushSubscriptionResponse,
  PushUnsubscribeRequest,
  UnreadCountResponse,
  Uuid,
  VapidPublicKeyResponse,
} from "@/types"

export const notificationsApi = {
  list: (params: { limit?: number; unread_only?: boolean } = {}) =>
    api
      .get<NotificationResponse[]>("/notifications", { params })
      .then((r) => r.data),

  unreadCount: () =>
    api
      .get<UnreadCountResponse>("/notifications/unread-count")
      .then((r) => r.data),

  markRead: (id: Uuid) =>
    api
      .post<MessageResponse>(`/notifications/${id}/read`)
      .then((r) => r.data),

  markAllRead: () =>
    api
      .post<MessageResponse>("/notifications/read-all")
      .then((r) => r.data),

  // ── Web Push (KORAK 1 Prompta 2) ──────────────────────────────────────────

  getVapidPublicKey: () =>
    api
      .get<VapidPublicKeyResponse>("/notifications/vapid-public-key")
      .then((r) => r.data),

  subscribeToPush: (payload: PushSubscribeRequest) =>
    api
      .post<PushSubscriptionResponse>("/notifications/subscribe", payload)
      .then((r) => r.data),

  unsubscribeFromPush: (payload: PushUnsubscribeRequest) =>
    api
      .post<MessageResponse>("/notifications/unsubscribe", payload)
      .then((r) => r.data),
}
