/**
 * chat-message-counter.tsx — "X / 20" indicator for TicketChat.
 *
 * ROADMAP 3.6 / Faza 3.6. Switches to a warning color when fewer than
 * 5 messages remain and to destructive when the cap is reached.
 */

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
  const tone =
    remaining === 0
      ? "text-destructive"
      : remaining <= 5
        ? "text-amber-600 dark:text-amber-400"
        : "text-muted-foreground"

  return (
    <span
      className={cn("text-xs font-medium tabular-nums", tone, className)}
      aria-live="polite"
    >
      {current} / {max} poruka
    </span>
  )
}
