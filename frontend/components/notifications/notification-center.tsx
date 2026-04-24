/**
 * notification-center.tsx — Bell button in the top-bar (placeholder shell).
 *
 * ROADMAP 2.2 — shared shell primitives (visual only).
 * ROADMAP 4.1 / 4.8 — real dropdown, list + WS streaming.
 *
 * For Phase 2 this renders just the bell with an unread counter shell so
 * the top-bar layout is complete. The real dropdown (last 10 items, mark
 * read, navigate to source) lands in Phase 5 together with the
 * `<NotificationStream />` WebSocket client already in `providers.tsx`.
 */

"use client"

import { Bell } from "lucide-react"

import { Button } from "@/components/ui/button"

export function NotificationCenter() {
  const unreadCount = 0

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className="relative"
      aria-label={`Notifikacije${unreadCount > 0 ? ` (${unreadCount} nepročitanih)` : ""}`}
      disabled
    >
      <Bell aria-hidden />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 flex size-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground"
          aria-hidden
        >
          {unreadCount > 9 ? "9+" : unreadCount}
        </span>
      )}
    </Button>
  )
}
