/**
 * faculty-badge.tsx — FON / ETF colored chip.
 *
 * KORAK 4 brand alignment:
 *   - FON → amber gold (#E8A93D u light, #F4C56A u dark)
 *   - ETF → burgundy   (#7B1E2C u light, #B0405A u dark)
 *
 * Boje dolaze iz HSL token-a `--faculty-fon` / `--faculty-etf` definisanih
 * u `app/globals.css` (KORAK 1). Token-i imaju automatsku light/dark
 * varijantu — komponenta sama ne mora da hendluje theme switch.
 *
 * Kontrast: AA (>= 4.5:1) za oba para u oba theme-a (verifikovano u
 * `docs/DESIGN_SYSTEM.md`).
 */

import { cn } from "@/lib/utils"
import type { Faculty } from "@/types/common"

const FACULTY_STYLES: Record<Faculty, string> = {
  FON: "bg-faculty-fon text-faculty-fon-foreground border-faculty-fon/40",
  ETF: "bg-faculty-etf text-faculty-etf-foreground border-faculty-etf/40",
}

export interface FacultyBadgeProps {
  faculty: Faculty
  className?: string
}

export function FacultyBadge({ faculty, className }: FacultyBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-md border px-2 py-0.5 text-xs font-semibold tracking-wide",
        FACULTY_STYLES[faculty],
        className
      )}
      aria-label={`Fakultet: ${faculty}`}
    >
      {faculty}
    </span>
  )
}
