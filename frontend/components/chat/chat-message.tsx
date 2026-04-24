/**
 * chat-message.tsx — Single message bubble inside TicketChat.
 *
 * ROADMAP 3.6 / Faza 3.6. Differentiates the current viewer's own
 * messages (right-aligned, primary background) from others' (left,
 * muted). Shows the sender name + timestamp under the bubble.
 */

import { cn } from "@/lib/utils"
import { formatTime } from "@/lib/utils/date"
import type { ChatMessageResponse } from "@/types"

export interface ChatMessageProps {
  message: ChatMessageResponse
  isOwn: boolean
  senderName?: string
}

export function ChatMessage({ message, isOwn, senderName }: ChatMessageProps) {
  return (
    <li
      className={cn(
        "flex flex-col gap-1",
        isOwn ? "items-end" : "items-start"
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-3 py-2 text-sm",
          isOwn
            ? "rounded-tr-sm bg-primary text-primary-foreground"
            : "rounded-tl-sm bg-muted text-foreground"
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
      <span className="px-1 text-[10px] text-muted-foreground">
        {senderName ? `${senderName} · ` : ""}
        {formatTime(message.created_at)}
      </span>
    </li>
  )
}
