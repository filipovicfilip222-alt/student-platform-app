/**
 * calendar-legend.tsx — Color legend for BookingCalendar / AvailabilityCalendar.
 *
 * ROADMAP 3.5 / Faza 3.5. Shared between student and professor views.
 * Colors must match the event backgrounds set in booking-calendar.tsx
 * and availability-calendar.tsx.
 */

import { cn } from "@/lib/utils"

const ITEMS: Array<{
  key: string
  label: string
  swatchClass: string
}> = [
  { key: "available", label: "Slobodno", swatchClass: "bg-emerald-500" },
  { key: "full", label: "Popunjeno", swatchClass: "bg-amber-500" },
  { key: "mine", label: "Moj termin", swatchClass: "bg-sky-500" },
  { key: "blocked", label: "Blackout", swatchClass: "bg-muted-foreground/50" },
]

export interface CalendarLegendProps {
  className?: string
}

export function CalendarLegend({ className }: CalendarLegendProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground",
        className
      )}
      aria-label="Legenda kalendara"
    >
      {ITEMS.map((item) => (
        <span key={item.key} className="inline-flex items-center gap-1.5">
          <span
            className={cn("size-2.5 rounded-full", item.swatchClass)}
            aria-hidden
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}
