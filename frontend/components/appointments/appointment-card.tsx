/**
 * appointment-card.tsx — Compact card for a student's appointment.
 *
 * ROADMAP 3.2 (student dashboard) + 3.3 (my-appointments). Renders a
 * status badge, slot datetime, consultation type, topic category, a
 * short description excerpt and optional action slots (Cancel on
 * upcoming, View on history).
 *
 * Data source: AppointmentResponse from the list endpoints in
 * studentsApi.listMyAppointments. Professor name is not part of that
 * payload today — we surface the professor ID until the backend joins
 * in a ProfessorPublicSummary (tracked in ROADMAP 3.1 as a follow-up).
 */

import Link from "next/link"
import { CalendarClock, ChevronRight, Video } from "lucide-react"
import type { ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { formatDateTime } from "@/lib/utils/date"
import { topicCategoryLabel } from "@/lib/constants/topic-categories"
import { ROUTES } from "@/lib/constants/routes"
import type { AppointmentResponse } from "@/types"

import { AppointmentStatusBadge } from "./appointment-status-badge"

export interface AppointmentCardProps {
  appointment: AppointmentResponse
  /** Slot for action buttons rendered on the right side. */
  actions?: ReactNode
  /** When true, the entire card links to /appointments/[id]. */
  interactive?: boolean
  className?: string
}

export function AppointmentCard({
  appointment,
  actions,
  interactive = true,
  className,
}: AppointmentCardProps) {
  const {
    id,
    status,
    slot_datetime,
    consultation_type,
    topic_category,
    description,
  } = appointment

  const isOnline = consultation_type === "ONLINE"

  const body = (
    <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <AppointmentStatusBadge status={status} />
          <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
            {isOnline ? (
              <>
                <Video className="size-3.5" aria-hidden />
                Online
              </>
            ) : (
              <>
                <CalendarClock className="size-3.5" aria-hidden />
                Uživo
              </>
            )}
          </span>
          <span className="text-xs text-muted-foreground">
            {topicCategoryLabel(topic_category)}
          </span>
        </div>

        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">
            {formatDateTime(slot_datetime)}
          </p>
          {description && (
            <p className="line-clamp-2 text-xs text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </div>

      {actions || interactive ? (
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          {interactive && (
            <ChevronRight
              className="hidden size-5 shrink-0 text-muted-foreground sm:block"
              aria-hidden
            />
          )}
        </div>
      ) : null}
    </CardContent>
  )

  if (!interactive) {
    return (
      <Card className={cn("border-border/70 shadow-none", className)}>
        {body}
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        "border-border/70 shadow-none transition-colors hover:border-primary/40 hover:bg-muted/30",
        className
      )}
    >
      <Link
        href={ROUTES.appointment(id)}
        className="block rounded-xl focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Detalji termina ${formatDateTime(slot_datetime)}`}
      >
        {body}
      </Link>
    </Card>
  )
}
