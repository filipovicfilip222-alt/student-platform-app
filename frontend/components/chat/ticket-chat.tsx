/**
 * ticket-chat.tsx — Per-appointment mini-chat sa 20-msg cap-om.
 *
 * KORAK 6 (StudentPlus polish):
 *   - Header: naslov + counter + optional 24h countdown badge.
 *   - Lista poruka: smooth scroll na novu poruku (osim prvog load-a),
 *     "Učitavam…" bubble-skeleton-i koji liče na prave bubble redove.
 *   - Empty state: friendly poruka + ikona.
 *   - Footer: ChatClosedNotice (ako zatvoren) + ChatInput sa hintom.
 *
 * Closed conditions (lokalno — WS reason je informativan):
 *   - appointmentStatus ∈ {REJECTED, CANCELLED, COMPLETED} → "status"
 *   - messages.length ≥ MAX_MESSAGES → "limit"
 */

"use client"

import { useEffect, useRef, useState } from "react"
import { Hourglass, MessageCircle } from "lucide-react"
import { formatDistanceToNowStrict, isAfter } from "date-fns"
import { sr } from "date-fns/locale"

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ChatClosedNotice } from "./chat-closed-notice"
import { ChatInput } from "./chat-input"
import { ChatMessage } from "./chat-message"
import { ChatMessageCounter } from "./chat-message-counter"
import { useChatMessages, useSendMessage } from "@/lib/hooks/use-chat"
import { useAuthStore } from "@/lib/stores/auth"
import { cn } from "@/lib/utils"
import { toastApiError } from "@/lib/utils/errors"
import type { AppointmentStatus, ChatMessageResponse, Uuid } from "@/types"

const MAX_MESSAGES = 20

export interface TicketChatProps {
  appointmentId: Uuid
  appointmentStatus: AppointmentStatus
  participantNames?: Record<Uuid, string>
  /**
   * ISO timestamp kada chat treba da se zatvori (24h posle termina, npr.).
   * Ako se ne prosledi, countdown se ne prikazuje.
   */
  chatClosesAt?: string | null
}

const TERMINAL_STATUSES: AppointmentStatus[] = [
  "REJECTED",
  "CANCELLED",
  "COMPLETED",
]

/**
 * Live countdown koji se osvežava svake minute. Vraća { label, isCritical }
 * gde `isCritical` označava preostalo manje od 1 sata (postaje crveno).
 */
function useChatCountdown(closesAt?: string | null) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!closesAt) return
    const interval = setInterval(() => tick((n) => n + 1), 60_000)
    return () => clearInterval(interval)
  }, [closesAt])

  if (!closesAt) return null
  const target = new Date(closesAt)
  if (Number.isNaN(target.getTime())) return null
  const now = new Date()
  if (!isAfter(target, now)) return null

  const diffMs = target.getTime() - now.getTime()
  const isCritical = diffMs < 60 * 60 * 1000
  return {
    label: formatDistanceToNowStrict(target, { locale: sr, addSuffix: false }),
    isCritical,
  }
}

export function TicketChat({
  appointmentId,
  appointmentStatus,
  participantNames = {},
  chatClosesAt = null,
}: TicketChatProps) {
  const currentUserId = useAuthStore((s) => s.user?.id ?? null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const hasScrolledRef = useRef(false)

  const isStatusClosed = TERMINAL_STATUSES.includes(appointmentStatus)
  const messagesQuery = useChatMessages(appointmentId, appointmentStatus)
  const messages: ChatMessageResponse[] = messagesQuery.data ?? []
  const isLimitReached = messages.length >= MAX_MESSAGES
  const isClosed = isStatusClosed || isLimitReached

  const sendMutation = useSendMessage(appointmentId)
  const countdown = useChatCountdown(chatClosesAt)

  // Smooth-scroll na novu poruku; prvi load skroluj instantno (bez animacije).
  useEffect(() => {
    const node = scrollRef.current
    if (!node) return
    if (!hasScrolledRef.current) {
      node.scrollTop = node.scrollHeight
      hasScrolledRef.current = true
    } else {
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" })
    }
  }, [messages.length])

  function handleSend(content: string) {
    if (isClosed) return
    sendMutation.mutate(
      { content },
      { onError: (err) => toastApiError(err, "Greška pri slanju poruke.") }
    )
  }

  const closedReason: "status" | "limit" | null = isStatusClosed
    ? "status"
    : isLimitReached
      ? "limit"
      : null

  return (
    <Card className="flex h-[560px] flex-col overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border bg-muted/30 p-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <MessageCircle className="size-4 text-primary" aria-hidden />
          Razgovor
        </CardTitle>
        <div className="flex items-center gap-2">
          {countdown && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums",
                countdown.isCritical
                  ? "bg-destructive/10 text-destructive"
                  : "bg-muted text-muted-foreground"
              )}
              aria-label={`Chat se zatvara za ${countdown.label}`}
            >
              <Hourglass className="size-3" aria-hidden />
              {countdown.label}
            </span>
          )}
          <ChatMessageCounter current={messages.length} max={MAX_MESSAGES} />
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3 p-0">
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-y-auto px-4 py-4 [scroll-behavior:smooth]"
          role="log"
          aria-live="polite"
          aria-label="Istorija poruka"
        >
          {messagesQuery.isLoading ? (
            <BubbleSkeletons />
          ) : messagesQuery.isError ? (
            <div className="flex h-full items-center justify-center text-center text-xs text-muted-foreground">
              Razgovor trenutno nije dostupan. Pokušajte za par sekundi.
            </div>
          ) : messages.length === 0 ? (
            <EmptyChat />
          ) : (
            <ul className="space-y-3">
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

        <div className="space-y-2 border-t border-border bg-muted/20 p-3">
          {closedReason && <ChatClosedNotice reason={closedReason} />}
          <ChatInput
            onSend={handleSend}
            isSending={sendMutation.isPending}
            disabled={isClosed}
            placeholder={isClosed ? "Chat je zatvoren" : "Napišite poruku…"}
          />
        </div>
      </CardContent>
    </Card>
  )
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function BubbleSkeletons() {
  return (
    <ul className="space-y-3">
      <SkeletonBubble side="left" width="w-[55%]" />
      <SkeletonBubble side="right" width="w-[40%]" />
      <SkeletonBubble side="left" width="w-[70%]" />
    </ul>
  )
}

function SkeletonBubble({
  side,
  width,
}: {
  side: "left" | "right"
  width: string
}) {
  return (
    <li
      className={cn(
        "flex gap-2",
        side === "right" ? "flex-row-reverse" : "flex-row"
      )}
    >
      {side === "left" && (
        <div className="size-7 shrink-0 animate-pulse rounded-full bg-muted" />
      )}
      <div
        className={cn(
          "h-9 animate-pulse rounded-2xl bg-muted",
          width,
          side === "right" ? "rounded-tr-sm" : "rounded-tl-sm"
        )}
      />
    </li>
  )
}

function EmptyChat() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <div
        aria-hidden
        className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
      >
        <MessageCircle className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        Razgovor još nije počeo
      </p>
      <p className="text-xs text-muted-foreground">
        Napišite poruku ispod — limit je 20 poruka, podržan je *bold*, _italic_
        i `code`.
      </p>
    </div>
  )
}
