/**
 * notification-item.tsx — One row inside the bell dropdown / full list.
 *
 * Source of truth: docs/websocket-schema.md §4.4. The `type` drives the
 * icon + accent color. Unknown types render with a generic bell icon.
 *
 * Clicking an unread item calls `onMarkRead` (handled by the parent).
 * Navigation from the `data` payload (e.g. jumping to the appointment
 * page) is a Phase 6 polish item — left as a TODO below.
 */

"use client"

import {
  AlertTriangle,
  Bell,
  Calendar,
  CalendarCheck2,
  CalendarX2,
  Clock,
  FileCheck2,
  FileX2,
  Megaphone,
  MessageSquare,
  ShieldAlert,
  ShieldCheck,
  UserPlus,
  type LucideIcon,
} from "lucide-react"

import { formatRelative } from "@/lib/utils/date"
import { cn } from "@/lib/utils"
import type { NotificationResponse, NotificationType } from "@/types/notification"

const TYPE_ICON: Record<NotificationType, LucideIcon> = {
  APPOINTMENT_CONFIRMED: CalendarCheck2,
  APPOINTMENT_REJECTED: CalendarX2,
  APPOINTMENT_CANCELLED: CalendarX2,
  APPOINTMENT_DELEGATED: Calendar,
  APPOINTMENT_REMINDER_24H: Clock,
  APPOINTMENT_REMINDER_1H: Clock,
  NEW_APPOINTMENT_REQUEST: UserPlus,
  NEW_CHAT_MESSAGE: MessageSquare,
  WAITLIST_OFFER: Calendar,
  STRIKE_ADDED: AlertTriangle,
  BLOCK_ACTIVATED: ShieldAlert,
  BLOCK_LIFTED: ShieldCheck,
  DOCUMENT_REQUEST_APPROVED: FileCheck2,
  DOCUMENT_REQUEST_REJECTED: FileX2,
  DOCUMENT_REQUEST_COMPLETED: FileCheck2,
  BROADCAST: Megaphone,
}

const TYPE_ACCENT: Partial<Record<NotificationType, string>> = {
  APPOINTMENT_CONFIRMED: "text-emerald-600",
  APPOINTMENT_REJECTED: "text-red-600",
  APPOINTMENT_CANCELLED: "text-red-600",
  APPOINTMENT_REMINDER_24H: "text-amber-600",
  APPOINTMENT_REMINDER_1H: "text-amber-600",
  WAITLIST_OFFER: "text-blue-600",
  STRIKE_ADDED: "text-red-600",
  BLOCK_ACTIVATED: "text-red-700",
  BLOCK_LIFTED: "text-emerald-600",
  DOCUMENT_REQUEST_APPROVED: "text-emerald-600",
  DOCUMENT_REQUEST_REJECTED: "text-red-600",
  DOCUMENT_REQUEST_COMPLETED: "text-emerald-600",
  BROADCAST: "text-violet-600",
}

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
  const Icon = TYPE_ICON[notification.type as NotificationType] ?? Bell
  const accent = TYPE_ACCENT[notification.type as NotificationType] ?? "text-muted-foreground"

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
        "flex w-full items-start gap-3 rounded-md px-3 py-2 text-left transition-colors hover:bg-muted",
        !notification.is_read && "bg-primary/5",
        className
      )}
      aria-label={
        notification.is_read
          ? notification.title
          : `Nepročitano: ${notification.title}`
      }
    >
      <div
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted",
          accent
        )}
        aria-hidden
      >
        <Icon className="size-4" />
      </div>

      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex items-start justify-between gap-2">
          <p
            className={cn(
              "truncate text-sm",
              notification.is_read ? "text-foreground" : "font-semibold text-foreground"
            )}
          >
            {notification.title}
          </p>
          {!notification.is_read && (
            <span
              className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
              aria-label="Nepročitano"
            />
          )}
        </div>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {notification.body}
        </p>
        <p className="text-[10px] text-muted-foreground">
          {formatRelative(notification.created_at)}
        </p>
      </div>
    </button>
  )
}
