/**
 * use-chat.ts — Per-appointment chat data hooks (Faza 4.1 — WS migration).
 *
 * Switched from 2-5 s REST polling to a real-time WebSocket subscription
 * (docs/websocket-schema.md §5). The TanStack Query cache key
 * `["appointment", id, "messages"]` is preserved so existing consumers
 * (`<TicketChat />`) keep working with no markup changes.
 *
 * Read path:
 *  - On mount we open a `chat-socket.ts` WebSocket to
 *    `/api/v1/appointments/{id}/chat?token=…`.
 *  - The server's first frame is `chat.history` — we replace the cache with
 *    its message list (normalized to the REST `ChatMessageResponse` shape
 *    for parity with the existing UI).
 *  - Each `chat.message` envelope appends to the cache (dedup by id, so
 *    REST optimistic updates and WS echoes don't duplicate).
 *  - REST polling stays as a graceful fallback: while the WS is not OPEN
 *    we keep `refetchInterval = 5 s`. Once the WS reaches OPEN we set it
 *    to `false`. If the reconnect schedule is exhausted
 *    (`onPermanentlyUnavailable`) we switch back on automatically.
 *
 * Write path:
 *  - We deliberately keep REST `POST /messages` for the send mutation:
 *      1. The 201 response gives us the persisted message synchronously
 *         for an instant optimistic append.
 *      2. The backend POST handler ALSO publishes to `chat:pub:{id}`, so
 *         the OTHER browser's WS subscriber sees the message in real time.
 *      3. The sender's own WS subscriber receives the same echo and dedups
 *         by id (no double-render).
 *    So the WS chat.send envelope is exercised only by the integration
 *    test; the UI stays on REST POST and gains real-time receive for free.
 *
 * Closed-chat handling:
 *  - The 24-hour window and APPOINTMENT_CANCELLED reasons emit a
 *    `chat.closed` envelope before the server closes with 4430. We surface
 *    `wsClosedReason` so `<TicketChat />` could render
 *    `<ChatClosedNotice />` based on the WS reason in the future. For
 *    Faza 4.1 the existing local logic in TicketChat (status + count)
 *    is retained — the WS reason is informational only.
 */

"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { appointmentsApi } from "@/lib/api/appointments"
import { useAuthStore } from "@/lib/stores/auth"
import {
  createChatSocket,
  type ChatSocketHandle,
  type ChatSocketStatus,
} from "@/lib/ws/chat-socket"
import type {
  AppointmentStatus,
  ChatMessageCreate,
  ChatMessageResponse,
  Uuid,
} from "@/types"
import type { ChatClosedReason } from "@/types/ws"
import type { WsChatMessage } from "@/types/chat"

const REST_POLL_INTERVAL_MS = 5_000

/** Same key TicketChat reads from; KEEP STABLE. */
const makeKey = (appointmentId: Uuid) =>
  ["appointment", appointmentId, "messages"] as const

const TERMINAL_STATUSES: AppointmentStatus[] = [
  "REJECTED",
  "CANCELLED",
  "COMPLETED",
]

/**
 * Lossily normalise the WS-shape (`WsChatMessage`, nested sender) to the
 * REST shape (`ChatMessageResponse`, flat sender_id) so the cache contract
 * stays the same as the polling era. We discard `sender.full_name` /
 * `sender.role` here — the existing UI looks them up via the
 * `participantNames` prop, so nothing visibly changes.
 */
function normaliseWsMessage(
  appointmentId: Uuid,
  m: WsChatMessage
): ChatMessageResponse {
  return {
    id: m.id,
    appointment_id: appointmentId,
    sender_id: m.sender.id,
    content: m.content,
    created_at: m.created_at,
  }
}

export function useChatMessages(
  appointmentId: Uuid | null | undefined,
  appointmentStatus?: AppointmentStatus
) {
  const accessToken = useAuthStore((s) => s.accessToken)
  const qc = useQueryClient()
  const socketRef = useRef<ChatSocketHandle | null>(null)
  const [wsStatus, setWsStatus] = useState<ChatSocketStatus>("idle")
  const [wsClosedReason, setWsClosedReason] = useState<ChatClosedReason | null>(
    null
  )
  const [permanentlyUnavailable, setPermanentlyUnavailable] = useState(false)

  const isStatusClosed = appointmentStatus
    ? TERMINAL_STATUSES.includes(appointmentStatus)
    : false

  // Polling stays on while the WS is not the active source of truth, OR
  // when the chat itself is closed (so the existing read keeps working
  // even though no further messages are expected).
  const restPollingActive =
    wsStatus !== "open" && !isStatusClosed

  const messagesQuery = useQuery({
    queryKey: makeKey(appointmentId as Uuid),
    queryFn: () => appointmentsApi.listMessages(appointmentId as Uuid),
    enabled: Boolean(appointmentId) && Boolean(accessToken),
    refetchInterval: restPollingActive ? REST_POLL_INTERVAL_MS : false,
    refetchOnWindowFocus: restPollingActive,
  })

  useEffect(() => {
    if (!appointmentId) return
    if (!accessToken) return
    if (isStatusClosed) return // no point connecting to a closed chat
    if (permanentlyUnavailable) return // give up — REST polling owns it now

    const handle = createChatSocket(appointmentId, accessToken, {
      onStatusChange: setWsStatus,
      onEvent: (evt) => {
        switch (evt.event) {
          case "chat.history": {
            const next = evt.data.messages.map((m) =>
              normaliseWsMessage(appointmentId, m)
            )
            qc.setQueryData<ChatMessageResponse[]>(makeKey(appointmentId), next)
            break
          }
          case "chat.message": {
            const incoming = normaliseWsMessage(appointmentId, evt.data)
            qc.setQueryData<ChatMessageResponse[]>(
              makeKey(appointmentId),
              (prev) => {
                if (!prev) return [incoming]
                if (prev.some((m) => m.id === incoming.id)) return prev
                return [...prev, incoming]
              }
            )
            break
          }
          case "chat.closed": {
            setWsClosedReason(evt.data.reason)
            break
          }
          case "chat.limit_reached":
          case "system.error":
          case "system.ping":
          default:
            // limit/error are informational here — TicketChat's local logic
            // (count vs cap, appointmentStatus) is the rendering driver.
            break
        }
      },
      onTerminalClose: () => {
        // 4401/4403/4404/4409/4430 all stop reconnects; cache stays.
      },
      onPermanentlyUnavailable: () => setPermanentlyUnavailable(true),
    })
    socketRef.current = handle

    return () => {
      handle.close()
      socketRef.current = null
    }
  }, [
    appointmentId,
    accessToken,
    isStatusClosed,
    permanentlyUnavailable,
    qc,
  ])

  return useMemo(
    () => ({
      ...messagesQuery,
      wsStatus,
      wsClosedReason,
      isWsPermanentlyUnavailable: permanentlyUnavailable,
    }),
    [messagesQuery, wsStatus, wsClosedReason, permanentlyUnavailable]
  )
}

export function useSendMessage(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ChatMessageCreate) =>
      appointmentsApi.sendMessage(appointmentId, data),
    // Optimistic append so the sender sees their own message instantly even
    // if their WS echo is delayed by a few ms. The WS pubsub fanout will
    // arrive shortly after — we dedup by id in the WS handler above.
    onSuccess: (newMessage) => {
      qc.setQueryData<ChatMessageResponse[]>(
        makeKey(appointmentId),
        (prev) => {
          if (!prev) return [newMessage]
          if (prev.some((m) => m.id === newMessage.id)) return prev
          return [...prev, newMessage]
        }
      )
      // Side effect: appointment detail counters depend on message count.
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
    },
  })
}
