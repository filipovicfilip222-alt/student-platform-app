/**
 * notification-stream.tsx — Invisible client component that owns the
 * per-user notification WebSocket connection.
 *
 * Mounts once in app/providers.tsx so the socket outlives individual
 * pages. Responsibilities (websocket-schema.md §4):
 *  1. Open the socket when a user + access token are available in the
 *     auth store. Close it on logout.
 *  2. Flip `useNotificationWsStatus.isConnected` so the notification
 *     hooks turn their REST polling fallback off while the WS is live
 *     (Phase 5 Izmena 4).
 *  3. On `notification.created`:
 *       - write the new item into the list cache.
 *       - invalidate list queries (defensive — covers filter variants).
 *       - show a toast for types flagged `show_toast` in schema §4.4.
 *  4. On `notification.unread_count`: patch the counter cache directly
 *     (no refetch needed).
 *  5. Re-open the socket whenever the access token changes (login,
 *     /auth/refresh, impersonation start / end).
 *  6. Gracefully tolerate ECONNREFUSED / 404 while backend ROADMAP 4.2
 *     is not deployed — the socket logs nothing, the hooks keep
 *     polling; once the backend goes live the socket connects on the
 *     next reconnect cycle (≤ 30 s).
 *
 * Renders nothing.
 */

"use client"

import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  NOTIFICATION_LIST_KEY,
  NOTIFICATION_UNREAD_KEY,
} from "@/lib/hooks/use-notifications"
import { getToastTitle } from "@/lib/notifications/messages"
import { useAuthStore } from "@/lib/stores/auth"
import { useNotificationWsStatus } from "@/lib/stores/notification-ws-status"
import { createNotificationSocket } from "@/lib/ws/notification-socket"
import type {
  NotificationSocketHandle,
  NotificationSocketStatus,
} from "@/lib/ws/notification-socket"
import type { NotificationResponse } from "@/types/notification"
import { shouldShowToast } from "@/types/notification"
import type { NotificationWsEvent } from "@/types/ws"

export function NotificationStream(): null {
  const accessToken = useAuthStore((s) => s.accessToken)
  const userId = useAuthStore((s) => s.user?.id ?? null)
  const qc = useQueryClient()
  const setConnected = useNotificationWsStatus((s) => s.setConnected)
  const markUnavailable = useNotificationWsStatus((s) => s.markUnavailable)
  const resetWsStatus = useNotificationWsStatus((s) => s.reset)
  const handleRef = useRef<NotificationSocketHandle | null>(null)

  useEffect(() => {
    // No auth → tear down any existing socket and bail. Reset the store too
    // so a fresh login isn't poisoned by a previous session's "unavailable"
    // marker.
    if (!accessToken || !userId) {
      handleRef.current?.close()
      handleRef.current = null
      resetWsStatus()
      return
    }

    function handleEvent(event: NotificationWsEvent) {
      if (event.event === "notification.created") {
        const notif = event.data as NotificationResponse

        // Patch every cached list query (filters may vary) — prepend and dedupe.
        qc.setQueriesData<NotificationResponse[]>(
          { queryKey: NOTIFICATION_LIST_KEY },
          (prev) => {
            if (!prev) return prev
            if (prev.some((n) => n.id === notif.id)) return prev
            return [notif, ...prev]
          }
        )
        // Still invalidate — the server may filter differently (unread_only etc.).
        qc.invalidateQueries({ queryKey: NOTIFICATION_LIST_KEY })

        // Toast for critical types per schema §4.4 — naslov iz centralne
        // copy mape (lib/notifications/messages.ts), body je pun text iz
        // backenda. KORAK 7 polish: dodajemo `action` koja vodi na
        // /notifikacije (ako bude implementirano) ili u tihom no-op.
        if (shouldShowToast(notif.type)) {
          toast.message(getToastTitle(notif.type), { description: notif.body })
        }
        return
      }

      if (event.event === "notification.unread_count") {
        const count = event.data.count
        qc.setQueryData<number>(NOTIFICATION_UNREAD_KEY, count)
        return
      }

      // system.ping is auto-answered inside the socket wrapper.
      // system.error is advisory — nothing to do client-side in V1.
    }

    const handle = createNotificationSocket(accessToken, {
      onEvent: handleEvent,
      onStatusChange: (next: NotificationSocketStatus) => {
        // `unavailable` is reported separately via onPermanentlyUnavailable;
        // here we only flip the boolean isConnected for the polling-handoff
        // hook in use-notifications.ts.
        setConnected(next === "open")
      },
      onTerminalClose: () => {
        // 4403 / 4404 / 4430 on the notifications stream are unexpected
        // (those codes are more chat-specific). Leaving polling enabled
        // via `setConnected(false)` is the safe default.
        setConnected(false)
      },
      onUnauthorized: () => {
        // The axios interceptor already handles 401 → refresh → retry.
        // If the backend closed our WS with 4401, the access token is
        // about to change — the auth-token effect below will reopen us
        // with the new token. Nothing to do here.
        setConnected(false)
      },
      onPermanentlyUnavailable: () => {
        // Three transient handshakes failed back-to-back (typically because
        // ROADMAP 4.2 is not yet deployed). Flip the discrete `unavailable`
        // flag so the UI can render a non-spinning affordance, and let the
        // REST polling layer take over (it self-throttles to 5 min on 404).
        markUnavailable()
      },
    })

    handleRef.current = handle

    return () => {
      handle.close()
      if (handleRef.current === handle) handleRef.current = null
      // Wipe both isConnected and isUnavailable so the next session starts
      // from a clean slate (e.g. token swap after /auth/refresh).
      resetWsStatus()
    }
  }, [accessToken, userId, qc, setConnected, markUnavailable, resetWsStatus])

  return null
}
