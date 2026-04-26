/**
 * chat-socket.ts — Native WebSocket client for the per-appointment chat
 * channel defined in docs/websocket-schema.md §5.
 *
 * Pairs with backend handler `app/api/v1/appointments.py::chat_websocket`
 * (Faza 4.1). Uses the browser's native `WebSocket` API — no socket.io.
 *
 * Responsibilities:
 *  - Open `wss://…/api/v1/appointments/{id}/chat?token=<access_jwt>` because
 *    browsers forbid a custom Authorization header on WebSocket handshakes
 *    (schema §2.1).
 *  - Parse every incoming envelope (`WsEnvelope`) and dispatch to the
 *    consumer's `onEvent` callback.
 *  - Auto-answer `system.ping` with `system.pong` so the server does NOT
 *    force-close at 60 s of silence (schema §3.1 + §7.1).
 *  - Outbound queue: any `send()` issued before the socket reaches `OPEN`
 *    is queued and flushed on connect (schema §5.4 — frontend may queue,
 *    server does not).
 *  - Reconnect with the standard schema §7.2 schedule: 1 s → 2 s → 4 s →
 *    8 s → 30 s, ±20% jitter, hard cap 5 attempts. After the cap we declare
 *    the channel "permanently unavailable" so the consumer can fall back
 *    to REST polling. Chat differs from the notifications stream here —
 *    notifications uses a tighter [1, 5, 30] schedule because its endpoint
 *    historically did not exist; the chat endpoint exists and a real
 *    network blip is the more likely cause of disconnect.
 *  - Terminal close codes (no reconnect): 4401, 4403, 4404, 4409, 4430.
 *    4429 is NOT in the chat path (server uses `system.error RATE_LIMITED`
 *    instead — see backend recv_loop) so we do not list it here.
 *
 * NB: this module is transport-only — it does NOT touch TanStack Query
 * cache or the auth store. The cache wiring lives in
 * `lib/hooks/use-chat.ts`.
 */

import type {
  ChatSendEvent,
  ChatWsEvent,
  SystemPingEvent,
  WsCloseCode,
} from "@/types/ws"
import { WS_CLOSE_CODES } from "@/types/ws"
import type { Uuid } from "@/types/common"

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost"

/**
 * Reconnect backoff schedule in ms — schema §7.2.
 *
 * Hard cap (5) keeps a permanently-down backend from looping forever. After
 * the cap fires, `onPermanentlyUnavailable` is called and the consumer is
 * expected to surface the REST-polling fallback (or a "re-open" button).
 */
const BACKOFF_BASE_MS = [1_000, 2_000, 4_000, 8_000, 30_000]
const BACKOFF_JITTER = 0.2 // ±20%
const MAX_RECONNECT_ATTEMPTS = BACKOFF_BASE_MS.length

/**
 * Close codes after which the chat MUST NOT reconnect — see schema §2.3.
 * 4401 is treated specially: the consumer is asked to refresh the token,
 * then call `reconnect(newToken)` manually; we do NOT auto-loop.
 */
const TERMINAL_CHAT_CLOSE_CODES: ReadonlySet<number> = new Set<number>([
  WS_CLOSE_CODES.UNAUTHORIZED,
  WS_CLOSE_CODES.FORBIDDEN,
  WS_CLOSE_CODES.NOT_FOUND,
  WS_CLOSE_CODES.CONFLICT, // 4409 — chat limit reached
  WS_CLOSE_CODES.CHAT_WINDOW_CLOSED,
])

export type ChatSocketStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed"
  | "unavailable"

export interface ChatSocketCallbacks {
  /** Every parsed envelope (excluding system.ping which we auto-answer). */
  onEvent: (event: ChatWsEvent) => void
  /** Called every time the connection state changes. */
  onStatusChange?: (status: ChatSocketStatus) => void
  /** Called once when a terminal close code lands. */
  onTerminalClose?: (code: WsCloseCode | number, reason: string) => void
  /** Called on close 4401 — consumer should refresh token + reconnect(). */
  onUnauthorized?: () => void
  /** Called once when the reconnect schedule is exhausted. */
  onPermanentlyUnavailable?: () => void
}

export interface ChatSocketHandle {
  /** Send a `chat.send` envelope. Queued if the socket is not OPEN. */
  send(content: string): void
  /** Close the socket and stop reconnecting. */
  close(): void
  /** Close the current socket and reopen with a fresh access token. */
  reconnect(nextToken: string): void
  /** Current lifecycle state. */
  status(): ChatSocketStatus
}

/**
 * @param appointmentId scoping the WS handshake URL.
 * @param initialToken access JWT for query-string transport.
 */
export function createChatSocket(
  appointmentId: Uuid,
  initialToken: string,
  callbacks: ChatSocketCallbacks
): ChatSocketHandle {
  let token = initialToken
  let ws: WebSocket | null = null
  let status: ChatSocketStatus = "idle"
  let attempt = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false
  /** Buffer for chat.send payloads issued before OPEN. */
  const outboundQueue: ChatSendEvent[] = []

  function setStatus(next: ChatSocketStatus) {
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
    return `${WS_BASE_URL}/api/v1/appointments/${appointmentId}/chat?token=${encodeURIComponent(token)}`
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
          "[chat] WebSocket nedostupan posle 5 pokušaja. Prebačen na REST polling."
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

  function flushQueue() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    while (outboundQueue.length > 0) {
      const env = outboundQueue.shift()!
      try {
        ws.send(JSON.stringify(env))
      } catch {
        // Re-queue and stop — the close handler will reopen us.
        outboundQueue.unshift(env)
        return
      }
    }
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
      flushQueue()
    })

    socket.addEventListener("message", (evt: MessageEvent<string>) => {
      let parsed: ChatWsEvent
      try {
        parsed = JSON.parse(evt.data) as ChatWsEvent
      } catch {
        return // ignore malformed frames (forward-compat).
      }

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
          // mid-close; swallow.
        }
        return
      }

      callbacks.onEvent(parsed)
    })

    socket.addEventListener("error", () => {
      // onerror fires alongside onclose. The close handler owns reconnects.
    })

    socket.addEventListener("close", (evt: CloseEvent) => {
      ws = null
      if (disposed) {
        setStatus("closed")
        return
      }

      const code = evt.code
      const reason = evt.reason ?? ""

      if (code === WS_CLOSE_CODES.UNAUTHORIZED) {
        callbacks.onTerminalClose?.(code, reason)
        callbacks.onUnauthorized?.()
        setStatus("closed")
        return
      }

      if (TERMINAL_CHAT_CLOSE_CODES.has(code)) {
        callbacks.onTerminalClose?.(code, reason)
        setStatus("closed")
        return
      }

      if (code === WS_CLOSE_CODES.NORMAL) {
        setStatus("closed")
        return
      }

      // 1001 (heartbeat timeout / server going away), 4500 (server error),
      // network flap → reconnect with backoff.
      scheduleReconnect()
    })
  }

  connect()

  return {
    send(content: string) {
      const env: ChatSendEvent = {
        event: "chat.send",
        data: { content },
      }
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify(env))
          return
        } catch {
          // fall through to queue
        }
      }
      outboundQueue.push(env)
    },

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

export { WS_BASE_URL }
