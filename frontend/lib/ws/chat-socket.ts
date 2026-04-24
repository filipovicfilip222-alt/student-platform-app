/**
 * chat-socket.ts — Native WebSocket skeleton for the per-appointment chat
 * channel defined in docs/websocket-schema.md §5.
 *
 * STATUS: SKELETON ONLY — DO NOT WIRE UP YET.
 *
 * Phase 5 explicitly defers the chat WS migration (ROADMAP 4.1 backend
 * endpoint is not implemented). The Phase 3 `<TicketChat />` component
 * continues to use the 2-5 s polling fallback on
 * `GET /appointments/{id}/messages`. This file exists so the module path
 * `@/lib/ws/chat-socket` is reserved and the transport contract is visible
 * on disk for peer review.
 *
 * TODO(chat-ws): when backend 4.1 lands:
 *  1. Replicate the handshake + reconnect + heartbeat behaviour from
 *     notification-socket.ts (identical close-code table per §2.3).
 *  2. Add a small outbound queue so `chat.send` frames issued before the
 *     socket reaches `open` are flushed on connect.
 *  3. Hook `chat.history` into the existing
 *     ['appointment', id, 'messages'] TanStack Query cache so the UI
 *     immediately rehydrates the thread on reconnect (§5.3 / §7.3).
 *  4. Surface `chat.limit_reached` and `chat.closed` to <TicketChat /> so
 *     the input disables + `<ChatClosedNotice />` renders without a
 *     round-trip to REST.
 */

import type { ChatWsEvent } from "@/types/ws"
import type { Uuid } from "@/types/common"

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost"

export interface ChatSocketCallbacks {
  onEvent: (event: ChatWsEvent) => void
  onOpen?: () => void
  onClose?: (code: number, reason: string) => void
}

export interface ChatSocketHandle {
  send(content: string): void
  close(): void
}

/**
 * Placeholder factory — returns a no-op handle so callers can import this
 * module without crashing during the Phase 5 / Phase 4.1-backend gap.
 *
 * @param appointmentId used to build the handshake URL when implemented
 * @param token  access JWT (same transport as notifications — query param
 *               because browsers forbid Authorization headers on WS)
 * @param callbacks event sink
 */
export function createChatSocket(
  appointmentId: Uuid,
  token: string,
  _callbacks: ChatSocketCallbacks
): ChatSocketHandle {
  // TODO(chat-ws): replace the no-op with the real implementation once
  // backend ROADMAP 4.1 is in place. Reference URL shape below so the
  // eventual implementation matches schema §5 exactly.
  void appointmentId
  void token
  void _callbacks
  // Target URL: `${WS_BASE_URL}/api/v1/appointments/${appointmentId}/chat?token=${encodeURIComponent(token)}`

  return {
    send() {
      /* noop until ROADMAP 4.1 backend is live */
    },
    close() {
      /* noop */
    },
  }
}

export { WS_BASE_URL }
