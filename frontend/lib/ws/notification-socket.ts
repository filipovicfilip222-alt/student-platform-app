/**
 * notification-socket.ts — Native WebSocket client for the per-user
 * notifications stream defined in docs/websocket-schema.md §4.
 *
 * Uses the browser's native `WebSocket` API (not socket.io — that library
 * was removed from package.json for V1 per schema §1 / §10.3).
 *
 * Responsibilities:
 *  - Open `wss://…/api/v1/notifications/stream?token=<access_jwt>` because
 *    browsers forbid a custom Authorization header on WebSocket handshakes
 *    (schema §2.1).
 *  - Parse every incoming message against the WsEnvelope shape and dispatch
 *    to the provided event handler.
 *  - Auto-answer `system.ping` with `system.pong` so the server does not
 *    force-close us at 60 s of silence (schema §7.1).
 *  - Reconnect with the standard schema §7.2 schedule: 1 s → 2 s → 4 s →
 *    8 s → 30 s, ±20% jitter, hard cap 5 attempts. After the cap we declare
 *    the stream "permanently unavailable" for this session and the consumer
 *    falls back to REST polling. The schedule is intentionally identical to
 *    chat-socket.ts so a single-page app with both channels exhibits the
 *    same reconnect cadence — easier to reason about under flaky networks.
 *    Terminal close codes (4401 / 4403 / 4404 / 4430) skip the schedule and
 *    immediately surface to the consumer.
 *  - Surface open / close / error / unavailable lifecycle hooks to the
 *    component owner so it can render fallback UI (e.g. keep REST polling
 *    alive, flip the WS status store to `isUnavailable`).
 *
 * NB: this module is transport-only — it does NOT touch the React Query
 * cache or auth store. `components/notifications/notification-stream.tsx`
 * wires it up to those side effects.
 */

import type {
  NotificationWsEvent,
  SystemPingEvent,
  WsCloseCode,
} from "@/types/ws"
import { WS_CLOSE_CODES } from "@/types/ws"

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost"

/**
 * Reconnect backoff schedule in ms (schema §7.2).
 *
 * Mirrors chat-socket.ts so the two channels share one mental model. The
 * ±20% jitter shifts retries off the wall clock, smoothing thundering-herd
 * reconnects after a backend restart. Five attempts (≈45 s wall-clock with
 * jitter) is enough to ride out a typical container restart without
 * spamming the server during a longer outage.
 */
const BACKOFF_BASE_MS = [1_000, 2_000, 4_000, 8_000, 30_000]
const BACKOFF_JITTER = 0.2 // ±20%
const MAX_RECONNECT_ATTEMPTS = BACKOFF_BASE_MS.length

export type NotificationSocketStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed"
  | "unavailable"

export interface NotificationSocketCallbacks {
  onEvent: (event: NotificationWsEvent) => void
  /** Called every time the connection state changes. */
  onStatusChange?: (status: NotificationSocketStatus) => void
  /** Called when the server closes with a terminal code (no reconnect). */
  onTerminalClose?: (code: WsCloseCode | number, reason: string) => void
  /**
   * Called when the server closes with 4401 (token expired). Consumer is
   * expected to refresh the token and call `.reconnect(newToken)` — the
   * socket does NOT call /auth/refresh on its own.
   */
  onUnauthorized?: () => void
  /**
   * Called exactly once per session when we exhaust the reconnect schedule.
   * Consumer should flip its UI to a "stream nedostupan" affordance and
   * keep relying on REST polling. Recovery requires a page reload.
   */
  onPermanentlyUnavailable?: () => void
}

export interface NotificationSocketHandle {
  /** Close the socket and stop reconnecting. */
  close(): void
  /**
   * Close the current socket and reopen with a new token (used after a
   * successful /auth/refresh or after an admin impersonation token swap).
   */
  reconnect(nextToken: string): void
  /** Current lifecycle state. */
  status(): NotificationSocketStatus
}

export function createNotificationSocket(
  initialToken: string,
  callbacks: NotificationSocketCallbacks
): NotificationSocketHandle {
  let token = initialToken
  let ws: WebSocket | null = null
  let status: NotificationSocketStatus = "idle"
  let attempt = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function setStatus(next: NotificationSocketStatus) {
    if (status === next) return
    status = next
    callbacks.onStatusChange?.(next)
  }

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function buildUrl(): string {
    return `${WS_BASE_URL}/api/v1/notifications/stream?token=${encodeURIComponent(token)}`
  }

  function nextDelayMs(): number {
    const base = BACKOFF_BASE_MS[attempt]
    // ±20% jitter — Math.random gives [0,1); shift to [-1,1).
    const jitter = (Math.random() * 2 - 1) * BACKOFF_JITTER
    return Math.max(0, Math.round(base * (1 + jitter)))
  }

  function scheduleReconnect() {
    if (disposed) return

    if (attempt >= MAX_RECONNECT_ATTEMPTS) {
      if (typeof window !== "undefined") {
        // eslint-disable-next-line no-console
        console.warn(
          "[notifications] WebSocket nedostupan posle 5 pokušaja. Prebačen na REST polling."
        )
      }
      callbacks.onPermanentlyUnavailable?.()
      setStatus("unavailable")
      return
    }

    const delay = nextDelayMs()
    attempt += 1
    setStatus("reconnecting")

    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function connect() {
    if (disposed) return
    if (typeof window === "undefined") return // SSR guard

    clearReconnectTimer()
    setStatus("connecting")

    let socket: WebSocket
    try {
      socket = new WebSocket(buildUrl())
    } catch {
      // URL build / browser refused — treat as transient failure.
      scheduleReconnect()
      return
    }

    ws = socket

    socket.addEventListener("open", () => {
      if (disposed) {
        socket.close(WS_CLOSE_CODES.NORMAL)
        return
      }
      attempt = 0
      setStatus("open")
    })

    socket.addEventListener("message", (evt: MessageEvent<string>) => {
      let parsed: NotificationWsEvent
      try {
        parsed = JSON.parse(evt.data) as NotificationWsEvent
      } catch {
        return // forward-compat: ignore malformed frames.
      }

      // Auto-answer heartbeats. The server drops us at ~60s of silence
      // (schema §7.1).
      if (parsed.event === "system.ping") {
        const ping = parsed as SystemPingEvent
        try {
          socket.send(
            JSON.stringify({
              event: "system.pong",
              data: { seq: ping.data.seq },
            })
          )
        } catch {
          // send() may throw if we're mid-close; swallow safely.
        }
        return
      }

      callbacks.onEvent(parsed)
    })

    socket.addEventListener("error", () => {
      // Don't log-spam: onerror fires alongside onclose. The onclose
      // handler owns the reconnect decision.
    })

    socket.addEventListener("close", (evt: CloseEvent) => {
      ws = null
      if (disposed) {
        setStatus("closed")
        return
      }

      const code = evt.code
      const reason = evt.reason ?? ""

      // 4401: token refresh path — hand off to the consumer.
      if (code === WS_CLOSE_CODES.UNAUTHORIZED) {
        callbacks.onTerminalClose?.(code, reason)
        callbacks.onUnauthorized?.()
        setStatus("closed")
        return
      }

      // Other terminal codes (4403 / 4404 / 4430) — stop entirely.
      if (
        code === WS_CLOSE_CODES.FORBIDDEN ||
        code === WS_CLOSE_CODES.NOT_FOUND ||
        code === WS_CLOSE_CODES.CHAT_WINDOW_CLOSED
      ) {
        callbacks.onTerminalClose?.(code, reason)
        setStatus("closed")
        return
      }

      // Normal client-initiated close — final state.
      if (code === WS_CLOSE_CODES.NORMAL) {
        setStatus("closed")
        return
      }

      // Everything else: schedule a reconnect (server restart, network
      // flap, 1001 going-away, 4429 rate-limit, 4500 internal error).
      scheduleReconnect()
    })
  }

  connect()

  return {
    close() {
      disposed = true
      clearReconnectTimer()
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.close(WS_CLOSE_CODES.NORMAL)
        } catch {
          /* noop */
        }
      }
      ws = null
      setStatus("closed")
    },

    reconnect(nextToken: string) {
      if (disposed) return
      token = nextToken
      attempt = 0
      clearReconnectTimer()
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.close(WS_CLOSE_CODES.NORMAL)
        } catch {
          /* noop */
        }
      }
      ws = null
      // Small gap so the server sees the close before the re-open.
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        connect()
      }, 50)
    },

    status() {
      return status
    },
  }
}
