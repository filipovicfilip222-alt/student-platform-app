/**
 * recent-notifications-card.tsx — "Poslednjih N notifikacija" kartica
 * za dashboard.
 *
 * Renders a card sa naslovom "Poslednje notifikacije" i listom od max 5
 * notif-a. Svaka stavka koristi `<NotificationItem />` da bude vizuelno
 * konzistentna sa NotificationCenter dropdown-om.
 *
 * Empty/loading/error stanja:
 *   - loading → 3 Skeleton stavke
 *   - error   → diskretna poruka u footer-u kartice
 *   - empty   → friendly "Nema novih obaveštenja" + ikona
 *
 * Footer ima link „Sve notifikacije" — Phase 6 polish doda dedicirani
 * `/notifications` page; do tada smo spremni sa konstantom u routes.
 */

"use client"

import { ArrowRight, BellOff } from "lucide-react"
import Link from "next/link"

import { NotificationItem } from "@/components/notifications/notification-item"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMarkRead, useNotifications } from "@/lib/hooks/use-notifications"
import { cn } from "@/lib/utils"

export interface RecentNotificationsCardProps {
  limit?: number
  className?: string
  /** Optional href for the "see all" link; rendered only if provided. */
  seeAllHref?: string
}

export function RecentNotificationsCard({
  limit = 5,
  className,
  seeAllHref,
}: RecentNotificationsCardProps) {
  const query = useNotifications({ limit })
  const markRead = useMarkRead()

  const items = query.data ?? []

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-base font-semibold">Notifikacije</CardTitle>
        {seeAllHref && items.length > 0 && (
          <Link
            href={seeAllHref}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
          >
            Sve
            <ArrowRight className="size-3" aria-hidden />
          </Link>
        )}
      </CardHeader>

      <CardContent className="flex-1 space-y-1 px-2 pb-3">
        {query.isLoading ? (
          <div className="space-y-2 px-2">
            {Array.from({ length: 3 }).map((_, idx) => (
              <div key={idx} className="flex items-start gap-3 rounded-md py-2">
                <Skeleton className="size-8 shrink-0 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : query.isError ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">
            Notifikacije trenutno nisu dostupne.
          </p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-2 py-8 text-center">
            <BellOff
              className="size-8 text-muted-foreground/60"
              aria-hidden
            />
            <p className="text-sm font-medium text-foreground">
              Nema novih obaveštenja
            </p>
            <p className="text-xs text-muted-foreground">
              Bićete obavešteni kad stigne novi termin ili poruka.
            </p>
          </div>
        ) : (
          items
            .slice(0, limit)
            .map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onMarkRead={(id) => markRead.mutate(id)}
              />
            ))
        )}
      </CardContent>
    </Card>
  )
}
