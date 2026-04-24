/**
 * chat.ts — Chat WebSocket contract types.
 *
 * Source of truth: docs/websocket-schema.md §5 + §8.2. The native WebSocket
 * replaces the polling shape once ROADMAP 4.1 ships the chat WS endpoint.
 *
 * The REST polling shape (ChatMessageResponse-as-row used by Phase 3's
 * ticket-chat) is declared in types/appointment.ts and remains valid until
 * the WS migration.
 */

import type { IsoDateTime, Uuid } from "./common"

/**
 * Trimmed sender view sent with every chat event. The backend computes
 * `full_name` by joining first + last name so the frontend does not need a
 * separate user lookup.
 */
export interface ChatSender {
  id: Uuid
  full_name: string
  role: "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN"
}

/**
 * WS-format chat message (distinct from the REST polling
 * `ChatMessageResponse` which exposes only `sender_id`).
 */
export interface WsChatMessage {
  id: Uuid
  sender: ChatSender
  content: string
  created_at: IsoDateTime
  /** 1..20 — drives the "X/20" counter. */
  message_number: number
}
