/**
 * slot-popover.tsx — Rich popover content za hover/click na slot u BookingCalendar.
 *
 * KORAK 5 — re-design po prompt specu:
 *   - Avatar levo (placeholder ili professor initial)
 *   - Info sredina (datum/vreme, trajanje, tip, status)
 *   - Action dugme dolje ("Zakaži" — burgundy primary, ili "Termin nije dostupan")
 *
 * Komponenta je content-only — koristi se unutar `<Popover />` ili FullCalendar
 * `eventDidMount` hook-a. Za FullCalendar event hover popover (100ms delay
 * iz prompta) koristimo Radix `<HoverCard />` u BookingCalendar-u i ovde
 * pružamo content.
 */

"use client"

import { Calendar, Clock, Globe2, MapPin, Video } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { formatDate, formatTime } from "@/lib/utils/date"
import type { AvailableSlotResponse } from "@/types"

export interface SlotPopoverProps {
  slot: AvailableSlotResponse
  /** Optional professor display name for header. */
  professorName?: string
  /** Optional fallback initial to render in the avatar circle. */
  initials?: string
  /** Click on the primary action. */
  onBook?: (slot: AvailableSlotResponse) => void
  /** When false, the action button is disabled and labeled as unavailable. */
  bookable?: boolean
  className?: string
}

export function SlotPopover({
  slot,
  professorName,
  initials,
  onBook,
  bookable = true,
  className,
}: SlotPopoverProps) {
  const start = new Date(slot.slot_datetime)
  const end = new Date(start.getTime() + slot.duration_minutes * 60 * 1000)
  const isOnline = slot.consultation_type === "ONLINE"
  const initialFallback =
    initials ??
    (professorName
      ? professorName
          .split(/\s+/)
          .map((part) => part[0])
          .filter(Boolean)
          .slice(0, 2)
          .join("")
          .toUpperCase()
      : "PR")

  return (
    <div
      className={cn("flex w-72 flex-col gap-3 p-1", className)}
      role="group"
      aria-label="Detalji slota"
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          aria-hidden
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
        >
          {initialFallback}
        </div>

        <div className="min-w-0 flex-1">
          {professorName && (
            <p className="truncate text-sm font-semibold leading-tight">
              {professorName}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {isOnline ? "Online termin" : "Termin uživo"}
          </p>
        </div>
      </div>

      <dl className="grid gap-1.5 text-xs">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Calendar className="size-3.5" aria-hidden />
          <span className="font-medium text-foreground">
            {formatDate(slot.slot_datetime)}
          </span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Clock className="size-3.5" aria-hidden />
          <span>
            {formatTime(start)} — {formatTime(end)} ({slot.duration_minutes} min)
          </span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          {isOnline ? (
            <Video className="size-3.5" aria-hidden />
          ) : (
            <MapPin className="size-3.5" aria-hidden />
          )}
          <span>
            {isOnline
              ? slot.online_link
                ? "Online sastanak"
                : "Online (link stiže nakon potvrde)"
              : "Kabinet (uživo)"}
          </span>
        </div>
        {slot.max_students > 1 && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Globe2 className="size-3.5" aria-hidden />
            <span>Grupni slot — do {slot.max_students} studenata</span>
          </div>
        )}
      </dl>

      <Button
        size="sm"
        className="w-full"
        disabled={!bookable || !onBook}
        onClick={() => onBook?.(slot)}
      >
        {bookable ? "Zakaži termin" : "Termin nije dostupan"}
      </Button>
    </div>
  )
}
