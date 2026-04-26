/**
 * strike-status-card.tsx — Wrapper Card oko `<StrikeDisplay />` za dashboard.
 *
 * Vizuelno: kompakt kartica sa naslovom „Strike status", progress
 * indikatorom (0/3 dots) i kratkim opisnim tekstom.
 *
 * `<StrikeDisplay />` već renderuje 3-state UI (safe / warning / blocked),
 * ova komponenta dodaje:
 *   - card chrome (border, padding)
 *   - 3-dot progress (vizuelno počiste konkretan score)
 *   - link „Saznaj više" → /faq#strikes (Phase 6 polish — kreiramo FAQ kasnije)
 *
 * `points` i `blockedUntil` ostaju opcioni — backend `/auth/me` ih još ne
 * vraća (tracked u FRONTEND_STRUKTURA.md § 7.3).
 */

import { StrikeDisplay } from "@/components/shared/strike-display"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export interface StrikeStatusCardProps {
  points?: number
  blockedUntil?: string | null
  className?: string
}

const MAX_POINTS = 3

export function StrikeStatusCard({
  points = 0,
  blockedUntil = null,
  className,
}: StrikeStatusCardProps) {
  const safePoints = Math.max(0, Math.min(points, MAX_POINTS))

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-base font-semibold">Strike status</CardTitle>
        <div
          className="flex items-center gap-1"
          role="img"
          aria-label={`${safePoints} od ${MAX_POINTS} strike poena`}
        >
          {Array.from({ length: MAX_POINTS }).map((_, idx) => {
            const filled = idx < safePoints
            const isOverflow = points > MAX_POINTS && idx === MAX_POINTS - 1
            return (
              <span
                key={idx}
                aria-hidden
                className={cn(
                  "size-2.5 rounded-full transition-colors",
                  !filled && "bg-muted",
                  filled && safePoints === 1 && "bg-warning",
                  filled && safePoints === 2 && "bg-warning",
                  filled && safePoints >= 3 && "bg-destructive",
                  filled && isOverflow && "ring-2 ring-destructive ring-offset-1"
                )}
              />
            )
          })}
        </div>
      </CardHeader>

      <CardContent className="flex-1">
        <StrikeDisplay points={safePoints} blockedUntil={blockedUntil} />
      </CardContent>
    </Card>
  )
}
