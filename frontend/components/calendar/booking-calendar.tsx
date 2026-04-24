/**
 * booking-calendar.tsx — Student-facing FullCalendar wrapper.
 *
 * ROADMAP 3.5 / Faza 3.5.
 *
 * Read-only view over a professor's availability. Clicking a slot that
 * is still available fires `onSelectSlot(slot)`; the parent handles
 * opening the <AppointmentRequestForm /> dialog.
 *
 * Implementation notes:
 *   - Uses `timeGridWeek` as default (PRD §2.2) with day/month options.
 *   - Calendar locale is "sr" — date-fns + FullCalendar both support
 *     Serbian latin via lowercase tag.
 *   - Slot range is pushed to the hook via `datesSet` so only slots
 *     inside the visible window are fetched.
 */

"use client"

import { useMemo, useRef, useState } from "react"
import FullCalendar from "@fullcalendar/react"
import dayGridPlugin from "@fullcalendar/daygrid"
import timeGridPlugin from "@fullcalendar/timegrid"
import interactionPlugin from "@fullcalendar/interaction"
import type {
  DatesSetArg,
  EventClickArg,
  EventInput,
} from "@fullcalendar/core"

import { CalendarLegend } from "@/components/calendar/calendar-legend"
import { Skeleton } from "@/components/ui/skeleton"
import { useProfessorSlots } from "@/lib/hooks/use-professors"
import type { AvailableSlotResponse, Uuid } from "@/types"

export interface BookingCalendarProps {
  professorId: Uuid
  onSelectSlot: (slot: AvailableSlotResponse) => void
  className?: string
}

function toYmd(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

export function BookingCalendar({
  professorId,
  onSelectSlot,
  className,
}: BookingCalendarProps) {
  const calendarRef = useRef<FullCalendar | null>(null)
  const [range, setRange] = useState<{
    start_date?: string
    end_date?: string
  }>({})

  const slotsQuery = useProfessorSlots(professorId, range)

  const events: EventInput[] = useMemo(() => {
    const slots = slotsQuery.data ?? []
    return slots.map((slot) => {
      const start = new Date(slot.slot_datetime)
      const end = new Date(
        start.getTime() + slot.duration_minutes * 60 * 1000
      )
      return {
        id: slot.id,
        title:
          slot.consultation_type === "ONLINE" ? "Online slot" : "Slot (uživo)",
        start,
        end,
        backgroundColor: "rgb(16 185 129)", // emerald-500
        borderColor: "rgb(16 185 129)",
        extendedProps: { slot },
      }
    })
  }, [slotsQuery.data])

  function handleDatesSet(arg: DatesSetArg) {
    setRange({
      start_date: toYmd(arg.start),
      end_date: toYmd(arg.end),
    })
  }

  function handleEventClick(arg: EventClickArg) {
    const slot = arg.event.extendedProps.slot as
      | AvailableSlotResponse
      | undefined
    if (slot) onSelectSlot(slot)
  }

  return (
    <div className={className}>
      <CalendarLegend className="mb-3" />

      {slotsQuery.isLoading ? (
        <Skeleton className="h-[560px] w-full rounded-lg" />
      ) : (
        <div className="rounded-lg border bg-card p-2">
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView="timeGridWeek"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "timeGridWeek,dayGridMonth,timeGridDay",
            }}
            firstDay={1}
            locale="sr"
            allDaySlot={false}
            slotMinTime="07:00:00"
            slotMaxTime="22:00:00"
            height="auto"
            nowIndicator
            events={events}
            eventClick={handleEventClick}
            datesSet={handleDatesSet}
            buttonText={{
              today: "Danas",
              month: "Mesec",
              week: "Nedelja",
              day: "Dan",
            }}
            noEventsText="Nema dostupnih slotova u ovom periodu."
          />
        </div>
      )}

      {slotsQuery.isError && (
        <p className="mt-2 text-xs text-destructive">
          Greška pri učitavanju slotova. Osvežite stranicu za par sekundi.
        </p>
      )}
    </div>
  )
}
