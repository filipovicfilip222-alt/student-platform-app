/**
 * calendar-legend.tsx — Color legend for BookingCalendar / AvailabilityCalendar.
 *
 * KORAK 5 — usklađeno sa StudentPlus paletom (burgundy primary + amber
 * accent). Svatch klase replikuju izgled `.fc-event--*` modifikatora iz
 * globals.css, tako da legend tačno odražava prave kalendar boje.
 *
 * Komponenta prima `mode="student" | "professor"` da prikaže relevantne
 * varijante:
 *   - student vidi: Slobodno / Moj termin / Zauzeto / Prošao
 *   - profesor vidi: Slobodno / Rekurentno / Rezervisan / Blackout
 */

import { cn } from "@/lib/utils"

interface LegendItem {
  key: string
  label: string
  swatchClass: string
}

const STUDENT_ITEMS: LegendItem[] = [
  {
    key: "available",
    label: "Slobodno",
    swatchClass: "border-2 border-primary/55 bg-primary/10",
  },
  {
    key: "mine",
    label: "Moj termin",
    swatchClass: "bg-primary",
  },
  {
    key: "reserved",
    label: "Zauzeto",
    swatchClass: "border border-accent bg-accent/25",
  },
  {
    key: "past",
    label: "Prošao",
    swatchClass: "bg-muted opacity-50",
  },
]

const PROFESSOR_ITEMS: LegendItem[] = [
  {
    key: "available",
    label: "Slobodan",
    swatchClass: "border-2 border-primary/55 bg-primary/10",
  },
  {
    key: "recurring",
    label: "Rekurentan",
    swatchClass: "border-2 border-dashed border-accent bg-accent/20",
  },
  {
    key: "reserved",
    label: "Rezervisan",
    swatchClass: "border border-accent bg-accent/25",
  },
  {
    key: "blocked",
    label: "Blackout",
    swatchClass: "bg-muted",
  },
]

export interface CalendarLegendProps {
  className?: string
  mode?: "student" | "professor"
}

export function CalendarLegend({
  className,
  mode = "student",
}: CalendarLegendProps) {
  const items = mode === "professor" ? PROFESSOR_ITEMS : STUDENT_ITEMS

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground",
        className
      )}
      aria-label="Legenda kalendara"
    >
      {items.map((item) => (
        <span key={item.key} className="inline-flex items-center gap-1.5">
          <span
            className={cn("size-3 rounded-sm", item.swatchClass)}
            aria-hidden
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}
