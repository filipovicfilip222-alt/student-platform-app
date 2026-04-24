/**
 * notification-ws-status.ts — Lightweight Zustand store that tracks whether
 * the notifications WebSocket is currently delivering events.
 *
 * Why it exists: per websocket-schema.md §4 + Phase 5 Izmena 4, while the
 * backend WS endpoint (ROADMAP 4.2) is not yet live, we fall back to REST
 * polling every 30 s for the unread counter. Once the WS opens we turn
 * polling off (set `refetchInterval: false`) so the two transports never
 * race. The `<NotificationStream />` component flips this flag; hooks in
 * use-notifications.ts read it synchronously.
 *
 * Not persisted — purely in-memory session state.
 */

import { create } from "zustand"

interface NotificationWsStatusState {
  /** True while the notification WS is in the `open` state. */
  isConnected: boolean
  setConnected: (next: boolean) => void
}

export const useNotificationWsStatus = create<NotificationWsStatusState>(
  (set) => ({
    isConnected: false,
    setConnected: (next) => set({ isConnected: next }),
  })
)
