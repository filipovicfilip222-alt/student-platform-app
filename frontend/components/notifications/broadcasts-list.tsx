/**
 * broadcasts-list.tsx — Shared listing svih BROADCAST notifikacija koje
 * su targetirale trenutno prijavljenog korisnika.
 *
 * Backend ne čuva poseban "broadcasts received by user" view; svaki
 * broadcast koji admin pošalje fan-out task (`broadcast_tasks.fanout_broadcast`)
 * insert-uje u `notifications` sa `type=BROADCAST`. Komponenta zato
 * radi: `GET /notifications?type=BROADCAST&limit=100`.
 *
 * Jedna komponenta servira tri stranice (student/professor/asistent) —
 * sadržaj je 1:1 isti, samo se layout (sidebar) razlikuje između route
 * grupa. Centralizacija ovde znači: jedna izmena UX-a → tri rola.
 */

"use client"

import { CheckCheck, Megaphone } from "lucide-react"

import { NotificationItem } from "@/components/notifications/notification-item"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { PageHeader } from "@/components/shared/page-header"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
} from "@/lib/hooks/use-notifications"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"

export interface BroadcastsListProps {
  /** Tekst opisa ispod naslova — varira po roli (npr. studentu se kaže
   * "od studentske službe", profesoru "vama, vašem fakultetu ili svim
   * profesorima"). */
  description: string
}

export function BroadcastsList({ description }: BroadcastsListProps) {
  const query = useNotifications({ type: "BROADCAST", limit: 100 })
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  const items = query.data ?? []
  const unreadCount = items.filter((n) => !n.is_read).length

  function handleMarkAllRead() {
    if (unreadCount === 0) return
    markAllRead.mutate(undefined, {
      onSuccess: () =>
        toastSuccess(`Označeno kao pročitano: ${unreadCount} obaveštenja.`),
      onError: (err) =>
        toastApiError(err, "Greška pri obeležavanju kao pročitano."),
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Obaveštenja" description={description}>
        {unreadCount > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={markAllRead.isPending}
          >
            <CheckCheck aria-hidden />
            {markAllRead.isPending
              ? "Obeležavam…"
              : `Označi sve kao pročitano (${unreadCount})`}
          </Button>
        )}
      </PageHeader>

      {query.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, idx) => (
            <Skeleton key={idx} className="h-[72px] w-full rounded-lg" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState
          title="Obaveštenja trenutno nisu dostupna"
          description="Osvežite stranicu ili pokušajte ponovo za par sekundi."
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title="Još nemate obaveštenja"
          description="Ovde će se pojaviti poruke koje vam pošalje studentska služba (admin)."
        />
      ) : (
        <ul className="space-y-1 rounded-lg border border-border bg-background p-2">
          {items.map((notification) => (
            <li key={notification.id}>
              <NotificationItem
                notification={notification}
                onMarkRead={(id) => markRead.mutate(id)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
