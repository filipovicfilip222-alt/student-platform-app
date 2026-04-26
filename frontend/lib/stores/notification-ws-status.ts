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
 * Tri-state model:
 *   - `isConnected = true`               → WS is delivering, REST polling off.
 *   - `isConnected = false, isUnavailable = false`
 *                                        → WS still trying, REST polling on
 *                                          at the normal cadence.
 *   - `isConnected = false, isUnavailable = true`
 *                                        → WS has exhausted reconnects this
 *                                          session (notification-socket.ts
 *                                          gave up after 3 failures). REST
 *                                          polling is the sole transport
 *                                          and use-notifications.ts further
 *                                          slows it down to 5 min once the
 *                                          REST endpoint also returns 404.
 *                                          The flag is cleared on token
 *                                          swap / logout via `reset()`.
 *
 * Not persisted — purely in-memory session state.
 */

import { create } from "zustand"

interface NotificationWsStatusState {
  /** True while the notification WS is in the `open` state. */
  isConnected: boolean
  /**
   * True after the socket exhausted its reconnect schedule (3 attempts).
   * The UI can use this to show a discrete "nedostupno" affordance instead
   * of a spinner that pretends the connection is still being retried.
   */
  isUnavailable: boolean
  setConnected: (next: boolean) => void
  /** Called by notification-socket.ts when reconnect attempts are exhausted. */
  markUnavailable: () => void
  /** Clear both flags — called on logout / access-token swap. */
  reset: () => void
}

export const useNotificationWsStatus = create<NotificationWsStatusState>(
  (set) => ({
    isConnected: false,
    isUnavailable: false,
    setConnected: (next) =>
      set((prev) =>
        next
          ? { isConnected: true, isUnavailable: false }
          : { ...prev, isConnected: false }
      ),
    markUnavailable: () =>
      set({ isConnected: false, isUnavailable: true }),
    reset: () => set({ isConnected: false, isUnavailable: false }),
  })
)
