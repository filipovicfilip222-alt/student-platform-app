/**
 * ws.ts — WebSocket envelope + event types.
 *
 * Source of truth: docs/websocket-schema.md §3 (envelope) + §4 (notifications)
 * + §5 (chat) + §8.2 (TypeScript contract). Both channels use native
 * WebSockets (no socket.io) — wrappers live in frontend/lib/ws/.
 */

import type { NotificationResponse } from "./notification"
import type { WsChatMessage } from "./chat"

/**
 * Zajednički envelope za svaku WS poruku (server→client ili client→server).
 * See websocket-schema.md §3.
 */
export interface WsEnvelope<TEvent extends string, TData> {
  event: TEvent
  /** ISO-8601 UTC — set by server; client omits it. */
  ts?: string
  data: TData
}

// ── System / heartbeat events (both channels) ────────────────────────────────

export type SystemPingEvent = WsEnvelope<"system.ping", { seq: number }>
export type SystemPongEvent = WsEnvelope<"system.pong", { seq: number }>

/** Error codes surfaced in data.code — see schema §3.1. */
export type SystemErrorCode =
  | "VALIDATION_FAILED"
  | "RATE_LIMITED"
  | "CHAT_LIMIT_REACHED"
  | "CHAT_CLOSED"
  | "PERMISSION_DENIED"
  | "INTERNAL_ERROR"

export type SystemErrorEvent = WsEnvelope<
  "system.error",
  { code: SystemErrorCode | string; message: string }
>

// ── Notification stream (§4) ─────────────────────────────────────────────────

export type NotificationCreatedEvent = WsEnvelope<
  "notification.created",
  NotificationResponse
>

export type NotificationUnreadCountEvent = WsEnvelope<
  "notification.unread_count",
  { count: number }
>

export type NotificationWsEvent =
  | NotificationCreatedEvent
  | NotificationUnreadCountEvent
  | SystemPingEvent
  | SystemErrorEvent

// ── Chat stream (§5) ─────────────────────────────────────────────────────────

export type ChatHistoryEvent = WsEnvelope<
  "chat.history",
  {
    messages: WsChatMessage[]
    total: number
    remaining: number
    /** slot_datetime + 24h — frontend countdown. */
    closes_at: string
  }
>

export type ChatMessageEvent = WsEnvelope<
  "chat.message",
  WsChatMessage & { remaining: number }
>

export type ChatLimitReachedEvent = WsEnvelope<
  "chat.limit_reached",
  { total: number }
>

export type ChatClosedReason =
  | "APPOINTMENT_CANCELLED"
  | "WINDOW_EXPIRED"
  | "ADMIN_ACTION"

export type ChatClosedEvent = WsEnvelope<
  "chat.closed",
  { reason: ChatClosedReason }
>

export type ChatSendEvent = WsEnvelope<"chat.send", { content: string }>

export type ChatWsEvent =
  | ChatHistoryEvent
  | ChatMessageEvent
  | ChatLimitReachedEvent
  | ChatClosedEvent
  | SystemPingEvent
  | SystemErrorEvent

// ── WebSocket close codes (§2.3) ─────────────────────────────────────────────

export const WS_CLOSE_CODES = {
  /** Normal closure — klijent zatvorio. */
  NORMAL: 1000,
  /** Server restart / heartbeat timeout — reconnect sa backoff-om. */
  GOING_AWAY: 1001,
  /** Invalid/expired JWT — refresh + reconnect. */
  UNAUTHORIZED: 4401,
  /** Forbidden (ne-učesnik / RBAC) — ne reconnect. */
  FORBIDDEN: 4403,
  /** Resurs ne postoji — ne reconnect, redirect. */
  NOT_FOUND: 4404,
  /** Conflict (limit poruka / duplikat) — informativno. */
  CONFLICT: 4409,
  /** Rate limited — backoff, pokušaj kasnije. */
  RATE_LIMITED: 4429,
  /** Chat window closed (24h) — ne reconnect. */
  CHAT_WINDOW_CLOSED: 4430,
  /** Internal server error — reconnect sa backoff-om. */
  INTERNAL_ERROR: 4500,
} as const

export type WsCloseCode = (typeof WS_CLOSE_CODES)[keyof typeof WS_CLOSE_CODES]

/**
 * Close codes after which the client MUST NOT attempt to reconnect.
 * Derived from schema §7.2.
 */
export const WS_TERMINAL_CLOSE_CODES: ReadonlySet<number> = new Set([
  WS_CLOSE_CODES.UNAUTHORIZED, // 4401: will be handled by refresh-then-reconnect, not raw reconnect loop
  WS_CLOSE_CODES.FORBIDDEN,
  WS_CLOSE_CODES.NOT_FOUND,
  WS_CLOSE_CODES.CHAT_WINDOW_CLOSED,
])
