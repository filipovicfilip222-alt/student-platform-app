/**
 * appointment-status-badge.tsx — Coloured pill for an AppointmentStatus.
 *
 * ROADMAP 3.3 / Faza 3.3. Used by appointment list cards and the detail
 * header. Kept in a dedicated file so both the dashboard (3.2) and
 * /my-appointments (3.3) render identical badges.
 *
 * Colour palette follows PRD §2.3 (lifecycle) — greens for success,
 * amber for pending approval, red for rejections, muted for terminal
 * neutrals (cancelled/completed).
 */

import { cn } from "@/lib/utils"
import type { AppointmentStatus } from "@/types"

const STATUS_LABELS: Record<AppointmentStatus, string> = {
  PENDING: "Čeka odobrenje",
  APPROVED: "Odobren",
  REJECTED: "Odbijen",
  CANCELLED: "Otkazan",
  COMPLETED: "Završen",
}

const STATUS_STYLES: Record<AppointmentStatus, string> = {
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  APPROVED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  REJECTED: "bg-destructive/15 text-destructive",
  CANCELLED: "bg-muted text-muted-foreground",
  COMPLETED: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
}

export interface AppointmentStatusBadgeProps {
  status: AppointmentStatus
  className?: string
}

export function AppointmentStatusBadge({
  status,
  className,
}: AppointmentStatusBadgeProps) {
  const label = STATUS_LABELS[status] ?? status
  const style = STATUS_STYLES[status] ?? "bg-muted text-muted-foreground"

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        style,
        className
      )}
      data-status={status}
    >
      {label}
    </span>
  )
}
