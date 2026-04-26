/**
 * calendar-skeleton.tsx — Smarter loading placeholder za FullCalendar.
 *
 * KORAK 5 — zamena za sirov `<Skeleton className="h-[560px]" />` koji se
 * prikazivao tokom prvog fetch-a. Sada renderujemo grid 7 dana × 12 slotova
 * sa shimmer efektom (Tailwind `animate-pulse`), uz fake header toolbar.
 *
 * Reduced-motion: shimmer je ugušen globalno (vidi `@media reduced-motion`
 * u globals.css), pa nije potrebno specijalno baratanje ovde.
 *
 * Visina (`h-[560px]`) namerno odgovara default-noj visini timeGridWeek-a
 * sa slotMinTime=07:00 / slotMaxTime=22:00.
 */

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export interface CalendarSkeletonProps {
  className?: string
  /** Number of "day" columns to render. Default 7 (week view). */
  days?: number
  /** Number of slot rows. Default 12 (07:00 → 19:00, hourly). */
  slots?: number
}

export function CalendarSkeleton({
  className,
  days = 7,
  slots = 12,
}: CalendarSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Učitavam kalendar"
      aria-busy="true"
      className={cn(
        "rounded-lg border border-border bg-card p-3",
        className
      )}
    >
      {/* Toolbar skeleton */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Skeleton className="h-7 w-12 rounded-md" />
          <Skeleton className="h-7 w-12 rounded-md" />
          <Skeleton className="h-7 w-16 rounded-md" />
        </div>
        <Skeleton className="h-6 w-44 rounded-md" />
        <div className="flex items-center gap-1">
          <Skeleton className="h-7 w-16 rounded-md" />
          <Skeleton className="h-7 w-16 rounded-md" />
          <Skeleton className="h-7 w-12 rounded-md" />
        </div>
      </div>

      {/* Day header row */}
      <div
        className="grid gap-px border-b border-border pb-2"
        style={{ gridTemplateColumns: `48px repeat(${days}, 1fr)` }}
      >
        <div />
        {Array.from({ length: days }).map((_, i) => (
          <div key={`hdr-${i}`} className="px-1 py-1">
            <Skeleton className="h-3 w-12 rounded" />
            <Skeleton className="mt-1.5 h-4 w-6 rounded" />
          </div>
        ))}
      </div>

      {/* Slot rows */}
      <div
        className="mt-2 grid gap-px"
        style={{ gridTemplateColumns: `48px repeat(${days}, 1fr)` }}
      >
        {Array.from({ length: slots }).map((_, rowIdx) => (
          <div
            key={`row-${rowIdx}`}
            className="contents"
            aria-hidden
          >
            <div className="flex h-12 items-start pt-0.5 pr-1.5">
              <Skeleton className="ml-auto h-2.5 w-7 rounded" />
            </div>
            {Array.from({ length: days }).map((_, colIdx) => (
              <div
                key={`cell-${rowIdx}-${colIdx}`}
                className="h-12 border-t border-border/40"
              >
                {/* Sprinkle a few "events" for visual rhythm */}
                {(rowIdx + colIdx) % 5 === 2 && (
                  <Skeleton className="m-1 h-10 rounded-sm" />
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      <span className="sr-only">Učitavam kalendar…</span>
    </div>
  )
}
