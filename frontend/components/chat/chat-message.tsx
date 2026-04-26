/**
 * chat-message.tsx — Single message bubble inside TicketChat.
 *
 * KORAK 6 (StudentPlus polish):
 *   - Own poruka: desno, burgundy `bg-primary`, sa kvadratnim gornje-desnim
 *     rogljom (vizuelna „strelica" prema autoru).
 *   - Tuđa poruka: levo, `bg-muted`, avatar circle sa inicijalima.
 *   - Header (ime · vreme) je sada IZNAD bubble-a kod tuđih poruka, IZNAD
 *     kod svojih je samo timestamp ispod (tradicionalni messenger pattern).
 *   - Sadržaj prolazi kroz `renderChatMarkdown()` — bold/italic/code/links.
 */

import { cn } from "@/lib/utils"
import { formatTime } from "@/lib/utils/date"
import { renderChatMarkdown } from "@/lib/utils/markdown"
import type { ChatMessageResponse } from "@/types"

export interface ChatMessageProps {
  message: ChatMessageResponse
  isOwn: boolean
  senderName?: string
}

function getInitials(name: string | undefined): string {
  if (!name) return "U"
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0]).join("").toUpperCase()
}

export function ChatMessage({ message, isOwn, senderName }: ChatMessageProps) {
  const initials = getInitials(senderName)

  return (
    <li
      className={cn(
        "flex w-full gap-2",
        isOwn ? "flex-row-reverse" : "flex-row"
      )}
    >
      {!isOwn && (
        <div
          aria-hidden
          className="flex size-7 shrink-0 select-none items-center justify-center rounded-full bg-primary/15 text-[0.65rem] font-semibold text-primary"
        >
          {initials}
        </div>
      )}

      <div
        className={cn(
          "flex max-w-[80%] flex-col gap-1",
          isOwn ? "items-end" : "items-start"
        )}
      >
        {!isOwn && senderName && (
          <span className="px-1 text-[10px] font-medium text-muted-foreground">
            {senderName}
          </span>
        )}

        <div
          className={cn(
            "rounded-2xl px-3 py-2 text-sm leading-relaxed shadow-sm transition-colors",
            isOwn
              ? "rounded-tr-sm bg-primary text-primary-foreground"
              : "rounded-tl-sm bg-muted text-foreground"
          )}
        >
          <p className="whitespace-pre-wrap break-words">
            {renderChatMarkdown(message.content)}
          </p>
        </div>

        <span className="px-1 text-[10px] tabular-nums text-muted-foreground">
          {formatTime(message.created_at)}
        </span>
      </div>
    </li>
  )
}
