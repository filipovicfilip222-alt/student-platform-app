/**
 * notifications.ts — Notification list / read state REST wrapper.
 *
 * All mutations go through REST (websocket-schema.md §4.3). The WS channel
 * is push-only server→client; the client never sends notification events
 * other than `system.pong` heartbeats.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.2 — notifications
 * REST router + WebSocket stream). The shape below follows the contract in
 * websocket-schema.md §4 and is ready to go live without further changes.
 */

import api from "@/lib/api"
import type {
  MessageResponse,
  NotificationResponse,
  UnreadCountResponse,
  Uuid,
} from "@/types"

export const notificationsApi = {
  // TODO: backend endpoint not yet implemented (ROADMAP 4.2)
  list: (params: { limit?: number; unread_only?: boolean } = {}) =>
    api
      .get<NotificationResponse[]>("/notifications", { params })
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.2)
  unreadCount: () =>
    api
      .get<UnreadCountResponse>("/notifications/unread-count")
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.2)
  markRead: (id: Uuid) =>
    api
      .post<MessageResponse>(`/notifications/${id}/read`)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.2)
  markAllRead: () =>
    api
      .post<MessageResponse>("/notifications/read-all")
      .then((r) => r.data),
}
