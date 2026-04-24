/**
 * faculty-badge.tsx — FON / ETF colored chip.
 *
 * ROADMAP 2.2 — shared shell primitives.
 * Used wherever a professor/student's faculty needs to be surfaced (search
 * results, professor header, admin tables).
 */

import { cn } from "@/lib/utils"
import type { Faculty } from "@/types/common"

const FACULTY_STYLES: Record<Faculty, string> = {
  FON: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-500/10 dark:text-blue-200 dark:border-blue-400/30",
  ETF: "bg-red-100 text-red-800 border-red-200 dark:bg-red-500/10 dark:text-red-200 dark:border-red-400/30",
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
