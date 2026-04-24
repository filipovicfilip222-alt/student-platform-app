/**
 * (admin)/admin/broadcast/page.tsx — Platform-wide broadcast.
 *
 * ROADMAP 4.7 / 4.2. Form to send, plus recent history below for audit.
 */

"use client"

import { Megaphone } from "lucide-react"

import { BroadcastForm } from "@/components/admin/broadcast-form"
import { EmptyState } from "@/components/shared/empty-state"
import { PageHeader } from "@/components/shared/page-header"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useBroadcastHistory } from "@/lib/hooks/use-broadcast"
import { formatDateTime } from "@/lib/utils/date"

export default function AdminBroadcastPage() {
  const history = useBroadcastHistory()

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Obaveštenja"
        description="Slanje poruka svim korisnicima, studentima, osoblju ili po fakultetu."
      />

      <BroadcastForm />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Istorija
        </h2>

        {history.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, idx) => (
              <Skeleton key={idx} className="h-20 w-full" />
            ))}
          </div>
        ) : history.isError ? (
          <EmptyState
            icon={Megaphone}
            title="Istorija nije dostupna"
            description="Backend endpoint /admin/broadcast još nije aktivan (ROADMAP 4.7)."
          />
        ) : (history.data ?? []).length === 0 ? (
          <EmptyState
            icon={Megaphone}
            title="Još nije poslato obaveštenje"
            description="Poslate poruke će se pojaviti ovde sa brojem primalaca."
          />
        ) : (
          <ul className="space-y-2">
            {history.data!.map((item) => (
              <li
                key={item.id}
                className="rounded-lg border border-border bg-background p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong className="text-sm">{item.title}</strong>
                  <div className="flex items-center gap-1 text-xs">
                    <Badge variant="outline">{item.target}</Badge>
                    {item.channels.map((c) => (
                      <Badge key={c} variant="secondary">
                        {c}
                      </Badge>
                    ))}
                  </div>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                  {item.body}
                </p>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  {formatDateTime(item.sent_at)} · {item.recipient_count}{" "}
                  primalaca
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
