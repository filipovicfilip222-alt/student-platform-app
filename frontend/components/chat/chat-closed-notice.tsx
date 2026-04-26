/**
 * chat-closed-notice.tsx — Banner kada je chat zatvoren.
 *
 * KORAK 6 (StudentPlus polish):
 *   - Ikona po razlogu: Lock (status) ili MessagesSquare (limit).
 *   - Naslov + body — naslov je glavna poruka, body je objašnjenje.
 *   - Soft burgundy outline + muted bg → ne deluje kao greška, već kao
 *     informativno stanje.
 *
 * Razlozi:
 *   - "status": termin je REJECTED / CANCELLED / COMPLETED
 *   - "limit":  dostignut je 20-poruka cap
 */

import { Lock, MessagesSquare } from "lucide-react"

interface NoticeContent {
  Icon: typeof Lock
  title: string
  body: string
}

const CONTENT: Record<"status" | "limit", NoticeContent> = {
  status: {
    Icon: Lock,
    title: "Chat je zatvoren",
    body: "Termin je završen ili otkazan, pa nove poruke nisu moguće. Istorija poruka ostaje vidljiva.",
  },
  limit: {
    Icon: MessagesSquare,
    title: "Dostignut limit od 20 poruka",
    body: "Nastavite razgovor uživo na samom terminu — ovde nećete moći da pošaljete dodatne poruke.",
  },
}

export interface ChatClosedNoticeProps {
  reason: "status" | "limit"
}

export function ChatClosedNotice({ reason }: ChatClosedNoticeProps) {
  const { Icon, title, body } = CONTENT[reason]

  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2.5 text-xs"
      role="status"
    >
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="size-3.5" aria-hidden />
      </div>
      <div className="space-y-0.5">
        <p className="font-semibold text-foreground">{title}</p>
        <p className="text-muted-foreground">{body}</p>
      </div>
    </div>
  )
}
