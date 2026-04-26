/**
 * booking-calendar.tsx — Student-facing FullCalendar wrapper.
 *
 * KORAK 5 (StudentPlus polish):
 *   - Event boje sada idu kroz `eventClassNames` (`.fc-event--available` /
 *     `.fc-event--past`) i CSS varijable iz globals.css → automatski prelazi
 *     u dark mode bez JS recompute-a.
 *   - Custom `eventContent` renderuje kratak title + clock ikonu (umesto
 *     default-nog FullCalendar markupa). Cleaner u tight slotovima.
 *   - Mobile (<md) automatski prebacuje na `listWeek` view — čitljivije
 *     na uskim ekranima nego scaling timeGrid-a.
 *   - Skeleton placeholder je sada `<CalendarSkeleton />` umesto golog
 *     Skeleton blob-a.
 *   - Hover preko slot-a otvara `<SlotPopover />` sa quick-info i
 *     "Zakaži termin" CTA — ne moramo da otvaramo modal samo da bismo
 *     videli detalje.
 */

"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import FullCalendar from "@fullcalendar/react"
import dayGridPlugin from "@fullcalendar/daygrid"
import timeGridPlugin from "@fullcalendar/timegrid"
import interactionPlugin from "@fullcalendar/interaction"
import listPlugin from "@fullcalendar/list"
import type {
  DatesSetArg,
  EventClickArg,
  EventContentArg,
  EventInput,
} from "@fullcalendar/core"
import { Clock } from "lucide-react"

import { CalendarLegend } from "@/components/calendar/calendar-legend"
import { CalendarSkeleton } from "@/components/calendar/calendar-skeleton"
import { SlotPopover } from "@/components/calendar/slot-popover"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { useProfessorSlots } from "@/lib/hooks/use-professors"
import type { AvailableSlotResponse, Uuid } from "@/types"

export interface BookingCalendarProps {
  professorId: Uuid
  professorName?: string
  onSelectSlot: (slot: AvailableSlotResponse) => void
  className?: string
}

function toYmd(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

/**
 * Watch viewport width so we can swap timeGrid → list view on small screens.
 * 768px matches Tailwind `md` breakpoint.
 */
function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
    setIsMobile(mql.matches)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mql.addEventListener("change", handler)
    return () => mql.removeEventListener("change", handler)
  }, [breakpoint])

  return isMobile
}

export function BookingCalendar({
  professorId,
  professorName,
  onSelectSlot,
  className,
}: BookingCalendarProps) {
  const calendarRef = useRef<FullCalendar | null>(null)
  const isMobile = useIsMobile()
  const [range, setRange] = useState<{
    start_date?: string
    end_date?: string
  }>({})

  const slotsQuery = useProfessorSlots(professorId, range)

  const events: EventInput[] = useMemo(() => {
    const slots = slotsQuery.data ?? []
    const now = Date.now()
    return slots.map((slot) => {
      const start = new Date(slot.slot_datetime)
      const end = new Date(
        start.getTime() + slot.duration_minutes * 60 * 1000
      )
      const isPast = end.getTime() < now
      return {
        id: slot.id,
        title:
          slot.consultation_type === "ONLINE" ? "Online slot" : "Slot (uživo)",
        start,
        end,
        classNames: isPast
          ? ["fc-event--available", "fc-event--past"]
          : ["fc-event--available"],
        extendedProps: { slot, isPast },
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
    const { slot, isPast } = arg.event.extendedProps as {
      slot?: AvailableSlotResponse
      isPast?: boolean
    }
    if (slot && !isPast) onSelectSlot(slot)
  }

  function renderEventContent(arg: EventContentArg) {
    const { slot } = arg.event.extendedProps as {
      slot?: AvailableSlotResponse
    }
    if (!slot) return null
    return (
      <HoverCard>
        <HoverCardTrigger asChild>
          <div className="flex h-full w-full items-center gap-1 px-1.5 py-1 leading-tight">
            <Clock className="size-3 shrink-0" aria-hidden />
            <span className="truncate text-[0.7rem] font-medium">
              {arg.timeText}
            </span>
          </div>
        </HoverCardTrigger>
        <HoverCardContent align="center" sideOffset={8}>
          <SlotPopover
            slot={slot}
            professorName={professorName}
            bookable={!arg.event.extendedProps.isPast}
            onBook={onSelectSlot}
          />
        </HoverCardContent>
      </HoverCard>
    )
  }

  return (
    <div className={className}>
      <CalendarLegend className="mb-3" mode="student" />

      {slotsQuery.isLoading ? (
        <CalendarSkeleton />
      ) : (
        <div className="rounded-lg border border-border bg-card p-2 transition-colors">
          <FullCalendar
            ref={calendarRef}
            plugins={[
              dayGridPlugin,
              timeGridPlugin,
              interactionPlugin,
              listPlugin,
            ]}
            initialView={isMobile ? "listWeek" : "timeGridWeek"}
            key={isMobile ? "mobile" : "desktop"}
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: isMobile
                ? "listWeek,dayGridMonth"
                : "timeGridWeek,dayGridMonth,timeGridDay",
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
            eventContent={renderEventContent}
            datesSet={handleDatesSet}
            buttonText={{
              today: "Danas",
              month: "Mesec",
              week: "Nedelja",
              day: "Dan",
              list: "Lista",
            }}
            noEventsText="Nema dostupnih slotova u ovom periodu."
          />
        </div>
      )}

      {slotsQuery.isError && (
        <p className="mt-2 text-xs text-destructive" role="alert">
          Greška pri učitavanju slotova. Osvežite stranicu za par sekundi.
        </p>
      )}
    </div>
  )
}
