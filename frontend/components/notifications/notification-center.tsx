/**
 * notification-center.tsx — Bell button u top-bar-u sa popover dropdown-om.
 *
 * KORAK 7 (StudentPlus polish):
 *   - Bell + count koristi `<NotificationBadge />` sa pulse animacijom.
 *   - Header: "Notifikacije" + "{N} nepročitanih" / "Sve je pročitano".
 *   - Footer: "Označi sve kao pročitano" (samo ako ima unread)
 *     + "Pogledaj sve" link (deep link na /notifikacije ako postoji,
 *     inače je sakriven do Phase 6).
 *   - Empty state: friendly poruka + Bell ikona, ne goli text.
 *   - Skeleton: 3 reda sa grid-style placeholder-ima koji liče na prave
 *     items (ne goli pravougaonici).
 */

"use client"

import { Bell, BellOff, CheckCheck } from "lucide-react"

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/hooks/use-notifications"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError } from "@/lib/utils/errors"

import { NotificationBadge } from "./notification-badge"
import { NotificationItem } from "./notification-item"

const DROPDOWN_LIMIT = 10

export function NotificationCenter() {
  const isAuthenticated = useAuthStore((s) => s.accessToken !== null)

  const listQuery = useNotifications({ limit: DROPDOWN_LIMIT })
  const unreadQuery = useUnreadCount()
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  const unreadCount = unreadQuery.data ?? 0
  const notifications = listQuery.data ?? []
  const hasUnread = unreadCount > 0

  function handleMarkRead(id: string) {
    markRead.mutate(id, {
      onError: (err) =>
        toastApiError(err, "Neuspešno označavanje notifikacije."),
    })
  }

  function handleMarkAllRead() {
    markAllRead.mutate(undefined, {
      onError: (err) =>
        toastApiError(err, "Neuspešno označavanje svih notifikacija."),
    })
  }

  if (!isAuthenticated) {
    return (
      <Button
        variant="ghost"
        size="icon-sm"
        className="relative"
        aria-label="Notifikacije"
        disabled
      >
        <Bell aria-hidden />
      </Button>
    )
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          className="relative"
          aria-label={
            hasUnread
              ? `Notifikacije (${unreadCount} nepročitanih)`
              : "Notifikacije"
          }
        >
          <NotificationBadge count={unreadCount} />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={8}
        className="w-[380px] overflow-hidden p-0"
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-2 px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold">Notifikacije</p>
            <p className="text-xs text-muted-foreground">
              {hasUnread
                ? `${unreadCount} ${unreadCount === 1 ? "nepročitana" : "nepročitanih"}`
                : "Sve je pročitano"}
            </p>
          </div>
        </div>

        <Separator />

        {/* Body */}
        <ScrollArea className="max-h-[420px]">
          <div className="p-1.5">
            {listQuery.isLoading ? (
              <SkeletonList />
            ) : listQuery.isError ? (
              <ErrorState />
            ) : notifications.length === 0 ? (
              <EmptyState />
            ) : (
              <ul className="space-y-0.5">
                {notifications.map((n) => (
                  <li key={n.id}>
                    <NotificationItem
                      notification={n}
                      onMarkRead={handleMarkRead}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </ScrollArea>

        {/* Footer */}
        {hasUnread && (
          <>
            <Separator />
            <div className="px-2 py-1.5">
              <Button
                size="sm"
                variant="ghost"
                className="w-full justify-center"
                onClick={handleMarkAllRead}
                disabled={markAllRead.isPending}
              >
                <CheckCheck aria-hidden />
                Označi sve kao pročitano
              </Button>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function SkeletonList() {
  return (
    <ul className="space-y-1.5 p-2">
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="flex items-start gap-3 rounded-md px-3 py-2.5"
          aria-hidden
        >
          <div className="size-9 shrink-0 animate-pulse rounded-full bg-muted" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 w-3/5 animate-pulse rounded bg-muted" />
            <div className="h-2.5 w-4/5 animate-pulse rounded bg-muted" />
          </div>
          <div className="h-2 w-10 animate-pulse rounded bg-muted" />
        </li>
      ))}
    </ul>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <div
        aria-hidden
        className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
      >
        <Bell className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        Trenutno nema notifikacija
      </p>
      <p className="max-w-[28ch] text-xs text-muted-foreground">
        Ovde ćemo vam javiti za nove zahteve, podsetnike i ažuriranja.
      </p>
    </div>
  )
}

function ErrorState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <div
        aria-hidden
        className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground"
      >
        <BellOff className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        Notifikacije trenutno nisu dostupne
      </p>
      <p className="max-w-[30ch] text-xs text-muted-foreground">
        Pokušaćemo ponovo kroz par sekundi.
      </p>
    </div>
  )
}
