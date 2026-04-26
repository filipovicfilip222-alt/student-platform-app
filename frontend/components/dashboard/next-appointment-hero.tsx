/**
 * next-appointment-hero.tsx — Hero kartica za sledeći predstojeći termin.
 *
 * Visual: amber-accent gradient kartica sa countdown-om koji se ažurira
 * svake sekunde, lokacijom, statusom, predmetom i akcionim dugmadima.
 *
 * Countdown precision (svake sekunde):
 *   - „za 2 dana 5h"     ako je 24h+
 *   - „za 5h 23min"      ako je 1h+
 *   - „za 23min 14s"     ako je < 1h
 *   - „uskoro"           ako je < 60s
 *   - „u toku"           ako je u opsegu [start, start+15min]
 *   - „prošao"           ako je istekao (rare — backend bi trebalo da već
 *                         ukloni iz upcoming list-e)
 *
 * Ne ažuriramo countdown ako je tab u background-u (uštedimo CPU); React
 * StrictMode + visibility API pause + resume.
 */

"use client"

import { differenceInSeconds, isAfter, isBefore } from "date-fns"
import { CalendarClock, MapPin, Video } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { ROUTES } from "@/lib/constants/routes"
import { cn } from "@/lib/utils"
import { formatDateTime } from "@/lib/utils/date"
import type { AppointmentResponse } from "@/types"

export interface NextAppointmentHeroProps {
  appointment: AppointmentResponse
  /** Override actions (default: "Detalji" + "Otkaži"). */
  actions?: ReactNode
  /** Override the heading (default: "Sledeći termin"). */
  heading?: string
  className?: string
}

function formatCountdown(seconds: number): string {
  if (seconds < -15 * 60) return "prošao"
  if (seconds <= 0) return "u toku"
  if (seconds < 60) return "za nekoliko trenutaka"

  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remSec = Math.floor(seconds % 60)

  if (days > 0) return `za ${days} ${days === 1 ? "dan" : "dana"} ${hours}h`
  if (hours > 0) return `za ${hours}h ${minutes}min`
  if (minutes > 0) return `za ${minutes}min ${remSec}s`
  return `za ${remSec}s`
}

export function NextAppointmentHero({
  appointment,
  actions,
  heading = "Sledeći termin",
  className,
}: NextAppointmentHeroProps) {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
    const handle = setInterval(() => {
      if (document.visibilityState === "visible") {
        setNow(new Date())
      }
    }, 1000)
    return () => clearInterval(handle)
  }, [])

  const slotDate = new Date(appointment.slot_datetime)
  const isOnline = appointment.consultation_type === "ONLINE"

  const seconds = now ? differenceInSeconds(slotDate, now) : null
  const countdownLabel = seconds !== null ? formatCountdown(seconds) : "—"
  const isImminent = seconds !== null && seconds > 0 && seconds < 60 * 60
  const isLive =
    seconds !== null &&
    isBefore(slotDate, now ?? new Date()) &&
    isAfter(slotDate, new Date(Date.now() - 15 * 60 * 1000))

  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-primary/20 bg-card p-6 shadow-sm sm:p-7",
        className
      )}
    >
      {/* Background flourish — burgundy gradient sweep + amber halo. */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.06] transition-opacity group-hover:opacity-[0.10]"
        style={{
          background:
            "radial-gradient(circle at top right, hsl(var(--accent)) 0%, transparent 55%), linear-gradient(135deg, hsl(var(--primary)) 0%, transparent 60%)",
        }}
      />

      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <CalendarClock className="size-3.5" aria-hidden />
              {heading}
            </span>
            {isLive && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success">
                <span className="size-1.5 animate-pulse rounded-full bg-success" aria-hidden />
                U toku
              </span>
            )}
          </div>

          <div className="space-y-1">
            <p
              className={cn(
                "text-3xl font-bold tracking-tight",
                isImminent ? "text-accent" : "text-foreground"
              )}
              aria-live="polite"
            >
              {countdownLabel}
            </p>
            <p className="text-sm text-muted-foreground">
              {formatDateTime(appointment.slot_datetime)}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              {isOnline ? (
                <>
                  <Video className="size-4" aria-hidden />
                  Online konsultacije
                </>
              ) : (
                <>
                  <MapPin className="size-4" aria-hidden />
                  Uživo na fakultetu
                </>
              )}
            </span>
            {appointment.description && (
              <span className="line-clamp-1 max-w-md text-foreground/80">
                {appointment.description}
              </span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 flex-row gap-2 sm:flex-col">
          {actions ?? (
            <Button asChild size="lg">
              <Link href={ROUTES.appointment(appointment.id)}>Otvori detalje</Link>
            </Button>
          )}
        </div>
      </div>
    </article>
  )
}
