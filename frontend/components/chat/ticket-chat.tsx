/**
 * ticket-chat.tsx — Per-appointment mini-chat with 20-message cap.
 *
 * ROADMAP 3.6 / Faza 3.6.
 *
 * Polling fallback strategy (WebSocket arrives with ROADMAP 4.1):
 *   - Poll `/appointments/{id}/messages` every 5 s while the tab is
 *     active and the chat is not closed.
 *   - `refetchOnWindowFocus: true` handles tab-switch staleness.
 *
 * Closed chat conditions:
 *   - appointmentStatus ∈ {REJECTED, CANCELLED, COMPLETED} → "status"
 *   - messages.length ≥ MAX_MESSAGES → "limit"
 */

"use client"

import { useEffect, useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ChatClosedNotice } from "./chat-closed-notice"
import { ChatInput } from "./chat-input"
import { ChatMessage } from "./chat-message"
import { ChatMessageCounter } from "./chat-message-counter"
import { appointmentsApi } from "@/lib/api/appointments"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError } from "@/lib/utils/errors"
import type { AppointmentStatus, ChatMessageResponse, Uuid } from "@/types"

const MAX_MESSAGES = 20
const POLL_INTERVAL_MS = 5_000

export interface TicketChatProps {
  appointmentId: Uuid
  appointmentStatus: AppointmentStatus
  participantNames?: Record<Uuid, string>
}

const TERMINAL_STATUSES: AppointmentStatus[] = [
  "REJECTED",
  "CANCELLED",
  "COMPLETED",
]

export function TicketChat({
  appointmentId,
  appointmentStatus,
  participantNames = {},
}: TicketChatProps) {
  const currentUserId = useAuthStore((s) => s.user?.id ?? null)
  const qc = useQueryClient()
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const isStatusClosed = TERMINAL_STATUSES.includes(appointmentStatus)

  const messagesQuery = useQuery({
    queryKey: ["appointment", appointmentId, "messages"] as const,
    queryFn: () => appointmentsApi.listMessages(appointmentId),
    refetchInterval: isStatusClosed ? false : POLL_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })

  const messages: ChatMessageResponse[] = messagesQuery.data ?? []
  const isLimitReached = messages.length >= MAX_MESSAGES
  const isClosed = isStatusClosed || isLimitReached

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      appointmentsApi.sendMessage(appointmentId, { content }),
    onSuccess: (newMessage) => {
      qc.setQueryData<ChatMessageResponse[]>(
        ["appointment", appointmentId, "messages"],
        (prev) => {
          if (!prev) return [newMessage]
          if (prev.some((m) => m.id === newMessage.id)) return prev
          return [...prev, newMessage]
        }
      )
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
    },
    onError: (err) => toastApiError(err, "Greška pri slanju poruke."),
  })

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages.length])

  function handleSend(content: string) {
    if (isClosed) return
    sendMutation.mutate(content)
  }

  const closedReason: "status" | "limit" | null = isStatusClosed
    ? "status"
    : isLimitReached
      ? "limit"
      : null

  return (
    <Card className="flex h-[520px] flex-col">
      <CardHeader className="flex flex-row items-center justify-between border-b p-4">
        <CardTitle className="text-base font-semibold">Chat</CardTitle>
        <ChatMessageCounter current={messages.length} max={MAX_MESSAGES} />
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 p-0">
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-y-auto px-4 py-3"
        >
          {messagesQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-2/3 rounded-xl" />
              <Skeleton className="h-10 w-1/2 rounded-xl" />
              <Skeleton className="h-10 w-3/4 rounded-xl" />
            </div>
          ) : messagesQuery.isError ? (
            <p className="text-center text-xs text-muted-foreground">
              Chat stream trenutno nedostupan (očekuje se backend ROADMAP 3.6).
            </p>
          ) : messages.length === 0 ? (
            <p className="text-center text-xs text-muted-foreground">
              Još uvek nema poruka. Započnite razgovor.
            </p>
          ) : (
            <ul className="space-y-2">
              {messages.map((m) => (
                <ChatMessage
                  key={m.id}
                  message={m}
                  isOwn={m.sender_id === currentUserId}
                  senderName={
                    m.sender_id === currentUserId
                      ? undefined
                      : participantNames[m.sender_id]
                  }
                />
              ))}
            </ul>
          )}
        </div>

        <div className="border-t p-3 space-y-2">
          {closedReason && <ChatClosedNotice reason={closedReason} />}
          <ChatInput
            onSend={handleSend}
            isSending={sendMutation.isPending}
            disabled={isClosed}
            placeholder={
              isClosed ? "Chat je zatvoren" : "Napišite poruku..."
            }
          />
        </div>
      </CardContent>
    </Card>
  )
}
