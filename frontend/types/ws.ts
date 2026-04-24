/**
 * ws.ts — WebSocket message contracts (chat + notifications).
 *
 * TODO: sync with backend when docs/websocket-schema.md lands (ROADMAP 4.1).
 *       Shapes below are the frontend's best-guess until Stefan confirms the
 *       wire format — do NOT treat them as authoritative.
 */

import type { NotificationResponse } from "./notification"
import type { ChatMessageResponse } from "./appointment"
import type { Uuid } from "./common"

// ── Chat socket (socket.io, per-appointment room) ────────────────────────────

export type ChatSocketEvent =
  | { type: "message"; payload: ChatMessageResponse }
  | { type: "message_counter"; payload: { appointment_id: Uuid; count: number } }
  | { type: "chat_closed"; payload: { appointment_id: Uuid; closed_at: string } }
  | { type: "error"; payload: { code: string; message: string } }

export interface ChatSendEnvelope {
  type: "send_message"
  payload: { appointment_id: Uuid; content: string }
}

// ── Notification stream (native WS, per-user) ────────────────────────────────

export type NotificationSocketEvent =
  | { type: "notification"; payload: NotificationResponse }
  | { type: "unread_count"; payload: { count: number } }
  | { type: "ping" }
