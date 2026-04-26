/**
 * notification-badge.tsx — Bell ikona + count badge sa pulse dot-om.
 *
 * KORAK 7 — wrap-uje Bell + counter dot u jedan reusable element. Pulse
 * animacija (`animate-pulse-dot` — vidi globals.css) signalizira nove
 * nepročitane stavke. Kad je `count` 0, dot se uopšte ne renderuje.
 *
 * Komponenta NE drži state — `count` dolazi iz parent-a (Notifications-
 * Center → useUnreadCount hook).
 */

import { Bell } from "lucide-react"

import { cn } from "@/lib/utils"

export interface NotificationBadgeProps {
  count: number
  className?: string
}

export function NotificationBadge({
  count,
  className,
}: NotificationBadgeProps) {
  const hasUnread = count > 0
  const display = count > 9 ? "9+" : String(count)

  return (
    <span className={cn("relative inline-flex", className)} aria-hidden>
      <Bell className="size-4" />
      {hasUnread && (
        <span
          className={cn(
            "absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold leading-none text-primary-foreground",
            "animate-pulse-dot"
          )}
        >
          {display}
        </span>
      )}
    </span>
  )
}
