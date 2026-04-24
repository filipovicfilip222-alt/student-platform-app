/**
 * strike-display.tsx — Student strike-points indicator.
 *
 * ROADMAP 3.2 / Faza 3.2. Rendered on the student dashboard and (later)
 * inside the profile dropdown.
 *
 * NB: the backend `/auth/me` response does NOT yet expose the
 * `total_strike_points` or `blocked_until` fields (see
 * FRONTEND_STRUKTURA.md § 7.3 — open question). Until the backend
 * patch lands we read from `window.__STRIKE_DATA__` if the ADMIN sets
 * it for debugging; otherwise we fall back to 0 with a TODO marker.
 *
 * The component already renders the final three-state UI (safe /
 * warning / blocked) so swapping the data source is a one-liner.
 */

"use client"

import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/utils/date"

export interface StrikeDisplayProps {
  /**
   * Total strike points for the current student.
   * TODO: replace hard-coded 0 with `/auth/me` field once the backend
   * Pydantic UserResponse adds `total_strike_points` (ROADMAP 3.4 —
   * open question).
   */
  points?: number
  /** ISO date for when the current block expires (null = not blocked). */
  blockedUntil?: string | null
  className?: string
}

const BLOCK_THRESHOLD = 3

export function StrikeDisplay({
  points = 0,
  blockedUntil = null,
  className,
}: StrikeDisplayProps) {
  const isBlocked = blockedUntil !== null && new Date(blockedUntil) > new Date()
  const state = isBlocked
    ? "blocked"
    : points >= BLOCK_THRESHOLD
      ? "blocked"
      : points > 0
        ? "warning"
        : "safe"

  const palette = {
    safe: {
      Icon: CheckCircle2,
      wrapper: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
      title: "Bez kazni",
      description: "Nemate strike poena. Zakazivanje je dostupno kao i obično.",
    },
    warning: {
      Icon: AlertTriangle,
      wrapper: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
      title: `${points} ${points === 1 ? "strike poen" : "strike poena"}`,
      description:
        "Još jedan propust znači privremenu blokadu zakazivanja. Budite oprezni sa otkazivanjima.",
    },
    blocked: {
      Icon: ShieldAlert,
      wrapper: "border-destructive/30 bg-destructive/10 text-destructive",
      title: "Zakazivanje privremeno blokirano",
      description: blockedUntil
        ? `Blokada aktivna do ${formatDate(blockedUntil)}.`
        : "Kontaktirajte studentsku službu.",
    },
  }[state]

  const { Icon } = palette

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3",
        palette.wrapper,
        className
      )}
      role="status"
      data-state={state}
    >
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-semibold">{palette.title}</p>
        <p className="text-xs leading-relaxed opacity-90">
          {palette.description}
        </p>
      </div>
    </div>
  )
}
