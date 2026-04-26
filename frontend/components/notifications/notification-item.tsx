/**
 * notification-item.tsx — Jedan red u bell dropdown-u / full list view-u.
 *
 * KORAK 7 (StudentPlus polish):
 *   - Layout: ikona-circle levo, content sredina, time + unread dot desno.
 *   - Boje ikona se sad cita iz `lib/notifications/icons.ts` (jedan izvor).
 *   - Unread vizuelno ima burgundy dot iza kruga + jaču typografiju title-a
 *     + softu burgundy pozadinu (bg-primary/5) celog reda.
 *   - "pre 5 min" / "juče u 14:23" iz `lib/utils/relative-time.ts` umesto
 *     sirovih `formatDistanceToNow` rezultata.
 *   - Klik označava kao pročitano i (TODO phase-6) navigira po `data` payload-u.
 */

"use client"

import { Bell } from "lucide-react"

import {
  getNotificationToneClasses,
  getNotificationVisual,
} from "@/lib/notifications/icons"
import { cn } from "@/lib/utils"
import { formatSmartRelative } from "@/lib/utils/relative-time"
import type { NotificationResponse } from "@/types/notification"

export interface NotificationItemProps {
  notification: NotificationResponse
  onMarkRead?: (id: string) => void
  className?: string
}

export function NotificationItem({
  notification,
  onMarkRead,
  className,
}: NotificationItemProps) {
  const visual = getNotificationVisual(notification.type)
  const Icon = visual.icon ?? Bell
  const toneClasses = getNotificationToneClasses(visual.tone)

  function handleClick() {
    if (!notification.is_read) onMarkRead?.(notification.id)
    // TODO(phase-6): navigate based on `notification.data`
    //   - APPOINTMENT_* → /appointments/{data.appointment_id}
    //   - DOCUMENT_REQUEST_* → /document-requests
    //   - WAITLIST_OFFER → /professor/{data.professor_id}
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "group flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition-colors",
        "hover:bg-muted focus-visible:bg-muted focus-visible:outline-none",
        !notification.is_read && "bg-primary/5",
        className
      )}
      aria-label={
        notification.is_read
          ? notification.title
          : `Nepročitano: ${notification.title}`
      }
    >
      {/* Ikona levo */}
      <div
        className={cn(
          "mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full",
          toneClasses
        )}
        aria-hidden
      >
        <Icon className="size-4" />
      </div>

      {/* Content sredina */}
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "truncate text-sm leading-snug",
            notification.is_read
              ? "text-foreground/80"
              : "font-semibold text-foreground"
          )}
        >
          {notification.title}
        </p>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {notification.body}
        </p>
      </div>

      {/* Time + unread dot desno */}
      <div className="flex shrink-0 flex-col items-end gap-1">
        <time
          className="text-[10px] tabular-nums text-muted-foreground"
          dateTime={notification.created_at}
        >
          {formatSmartRelative(notification.created_at)}
        </time>
        {!notification.is_read && (
          <span
            className="size-2 rounded-full bg-primary"
            aria-label="Nepročitano"
          />
        )}
      </div>
    </button>
  )
}
