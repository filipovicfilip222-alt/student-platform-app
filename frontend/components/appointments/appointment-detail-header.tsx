/**
 * appointment-detail-header.tsx — Summary block for /appointments/[id].
 *
 * ROADMAP 3.6 / Faza 3.6. Shows status, type, time, topic, description,
 * and the optional rejection_reason surfaced by the backend when a
 * professor declines a request.
 */

import { CalendarClock, MessageSquareX, Users, Video } from "lucide-react"

import { AppointmentStatusBadge } from "./appointment-status-badge"
import { Card, CardContent } from "@/components/ui/card"
import { formatDateTime } from "@/lib/utils/date"
import { topicCategoryLabel } from "@/lib/constants/topic-categories"
import type { AppointmentDetailResponse } from "@/types"

export interface AppointmentDetailHeaderProps {
  appointment: AppointmentDetailResponse
}

export function AppointmentDetailHeader({
  appointment,
}: AppointmentDetailHeaderProps) {
  const {
    status,
    consultation_type,
    slot_datetime,
    topic_category,
    description,
    rejection_reason,
    is_group,
  } = appointment

  const isOnline = consultation_type === "ONLINE"

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <AppointmentStatusBadge status={status} />
          <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
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
          {is_group && (
            <span className="inline-flex items-center gap-1 rounded-md bg-sky-500/15 px-2 py-0.5 text-xs text-sky-700 dark:text-sky-400">
              <Users className="size-3.5" aria-hidden />
              Grupne konsultacije
            </span>
          )}
          <span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {topicCategoryLabel(topic_category)}
          </span>
        </div>

        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {formatDateTime(slot_datetime)}
          </h1>
        </div>

        {description && (
          <div className="space-y-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Opis teme
            </h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {description}
            </p>
          </div>
        )}

        {rejection_reason && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <MessageSquareX className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="space-y-1">
              <p className="font-semibold">Razlog odbijanja</p>
              <p className="whitespace-pre-wrap text-destructive/90">
                {rejection_reason}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
