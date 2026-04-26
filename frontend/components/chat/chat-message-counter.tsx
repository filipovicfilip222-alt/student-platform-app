/**
 * chat-message-counter.tsx — "X / 20" indikator za TicketChat.
 *
 * KORAK 6 (StudentPlus polish):
 *   - Skala boja:
 *       0–14 → success (zelena, "imate prostora")
 *       15–18 → warning (amber, "blizu kraja")
 *       19 → primary-ish (poslednja poruka)
 *       20 → destructive (limit dostignut)
 *   - Ikona drugačija po fazi: MessageSquare → AlertTriangle → Lock.
 *   - Live region (`aria-live="polite"`) saopštava promenu broja
 *     screen-reader-ima.
 */

import { AlertTriangle, Lock, MessageSquare } from "lucide-react"

import { cn } from "@/lib/utils"

export interface ChatMessageCounterProps {
  current: number
  max: number
  className?: string
}

export function ChatMessageCounter({
  current,
  max,
  className,
}: ChatMessageCounterProps) {
  const remaining = Math.max(0, max - current)
  const reachedLimit = remaining === 0
  const nearLimit = remaining > 0 && remaining <= 5

  const tone = reachedLimit
    ? "text-destructive bg-destructive/10"
    : nearLimit
      ? "text-amber-700 bg-amber-500/15 dark:text-amber-300"
      : "text-success bg-success/10 dark:text-emerald-300"

  const Icon = reachedLimit
    ? Lock
    : nearLimit
      ? AlertTriangle
      : MessageSquare

  const label = reachedLimit
    ? "Dostigao si limit poruka."
    : nearLimit
      ? `Još ${remaining} ${remaining === 1 ? "poruka" : "poruke"} pre limita.`
      : `${remaining} poruka preostalo.`

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums transition-colors",
        tone,
        className
      )}
      aria-live="polite"
      aria-label={label}
    >
      <Icon className="size-3" aria-hidden />
      {current} / {max}
    </span>
  )
}
