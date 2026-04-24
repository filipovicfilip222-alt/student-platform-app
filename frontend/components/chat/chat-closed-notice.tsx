/**
 * chat-closed-notice.tsx — Banner displayed when the chat is closed.
 *
 * ROADMAP 3.6 / Faza 3.6. Reasons: appointment status is terminal
 * (REJECTED / CANCELLED / COMPLETED) or the 20-message cap is reached.
 */

import { Lock } from "lucide-react"

export interface ChatClosedNoticeProps {
  reason: "status" | "limit"
}

const MESSAGES: Record<ChatClosedNoticeProps["reason"], string> = {
  status:
    "Chat je zatvoren jer je termin završen ili otkazan. Nije moguće slati nove poruke.",
  limit:
    "Dostignut je limit od 20 poruka. Nastavite komunikaciju uživo na terminu.",
}

export function ChatClosedNotice({ reason }: ChatClosedNoticeProps) {
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-dashed border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
      role="status"
    >
      <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <p>{MESSAGES[reason]}</p>
    </div>
  )
}
