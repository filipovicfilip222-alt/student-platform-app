/**
 * notifications.ts — Notification list / read state.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.1 — notifications
 * router + WebSocket stream).
 */

import api from "@/lib/api"
import type {
  MessageResponse,
  NotificationResponse,
  UnreadCountResponse,
  Uuid,
} from "@/types"

export const notificationsApi = {
  // TODO: backend endpoint not yet implemented (ROADMAP 4.1)
  list: (params: { limit?: number; unread_only?: boolean } = {}) =>
    api
      .get<NotificationResponse[]>("/notifications", { params })
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.1)
  unreadCount: () =>
    api
      .get<UnreadCountResponse>("/notifications/unread-count")
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.1)
  markRead: (id: Uuid) =>
    api
      .post<MessageResponse>(`/notifications/${id}/read`)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.1)
  markAllRead: () =>
    api
      .post<MessageResponse>("/notifications/mark-all-read")
      .then((r) => r.data),
}
