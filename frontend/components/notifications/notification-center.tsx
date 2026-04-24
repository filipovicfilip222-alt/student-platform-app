/**
 * notification-center.tsx — Bell button in the top-bar with a popover
 * dropdown of the last ~10 notifications.
 *
 * ROADMAP 4.2 / 4.7 (Phase 5).
 *
 * Data flow:
 *  - `useUnreadCount()` and `useNotifications({ limit: 10 })` both fall
 *    back to 30 s REST polling until `<NotificationStream />` flips the
 *    WS status flag (see use-notifications.ts + notification-stream.tsx).
 *  - `useMarkRead` / `useMarkAllRead` update the cache optimistically.
 *
 * The bell is disabled (aria-disabled) while the user is unauthenticated
 * so nothing fires before `SessionRestorer` populates the auth store.
 */

"use client"

import { Bell, CheckCheck } from "lucide-react"

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/hooks/use-notifications"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError } from "@/lib/utils/errors"

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
      onError: (err) => toastApiError(err, "Neuspešno označavanje notifikacije."),
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
          <Bell aria-hidden />
          {hasUnread && (
            <span
              className="absolute -right-0.5 -top-0.5 flex size-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground"
              aria-hidden
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" sideOffset={8} className="w-[360px] p-0">
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold">Notifikacije</p>
            <p className="text-xs text-muted-foreground">
              {hasUnread ? `${unreadCount} nepročitanih` : "Sve je pročitano"}
            </p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleMarkAllRead}
            disabled={!hasUnread || markAllRead.isPending}
          >
            <CheckCheck aria-hidden />
            Pročitaj sve
          </Button>
        </div>

        <Separator />

        <ScrollArea className="max-h-[420px]">
          <div className="p-1">
            {listQuery.isLoading ? (
              <div className="space-y-2 p-2">
                <Skeleton className="h-14 w-full rounded-md" />
                <Skeleton className="h-14 w-full rounded-md" />
                <Skeleton className="h-14 w-full rounded-md" />
              </div>
            ) : listQuery.isError ? (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                Notifikacije trenutno nisu dostupne. Pokušajte ponovo kasnije.
              </p>
            ) : notifications.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                Još uvek nemate notifikacije.
              </p>
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

      </PopoverContent>
    </Popover>
  )
}
