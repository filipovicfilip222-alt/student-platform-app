/**
 * professor-search-card.tsx — Search result card for a single professor.
 *
 * ROADMAP 3.4 / Faza 3.4. Clicking the card navigates to /professor/[id].
 * Shows: full name, title, department, faculty badge, subjects and
 * supported consultation types.
 */

import Link from "next/link"
import { ArrowRight, Video } from "lucide-react"

import { FacultyBadge } from "@/components/shared/faculty-badge"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ROUTES } from "@/lib/constants/routes"
import type { ProfessorSearchResponse } from "@/types"

const MAX_VISIBLE_SUBJECTS = 4

export interface ProfessorSearchCardProps {
  professor: ProfessorSearchResponse
}

export function ProfessorSearchCard({ professor }: ProfessorSearchCardProps) {
  const {
    id,
    full_name,
    title,
    department,
    faculty,
    subjects,
    consultation_types,
  } = professor

  const visibleSubjects = subjects.slice(0, MAX_VISIBLE_SUBJECTS)
  const hiddenCount = Math.max(0, subjects.length - visibleSubjects.length)
  const supportsOnline = consultation_types.includes("ONLINE")
  const supportsInPerson = consultation_types.includes("UZIVO")

  return (
    <Card className="group border-border/70 shadow-none transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm">
      <Link
        href={ROUTES.professor(id)}
        className="block rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
      >
        <CardContent className="flex h-full flex-col gap-3 p-5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 space-y-1">
              <h3 className="text-base font-semibold tracking-tight text-foreground">
                {full_name}
              </h3>
              <p className="truncate text-xs text-muted-foreground">
                {title}
                {title && department ? " · " : ""}
                {department}
              </p>
            </div>
            <FacultyBadge faculty={faculty} />
          </div>

          {visibleSubjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {visibleSubjects.map((subject) => (
                <Badge key={subject} variant="secondary" className="text-[10px]">
                  {subject}
                </Badge>
              ))}
              {hiddenCount > 0 && (
                <Badge variant="outline" className="text-[10px]">
                  +{hiddenCount}
                </Badge>
              )}
            </div>
          )}

          <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              {supportsInPerson && <span>Uživo</span>}
              {supportsInPerson && supportsOnline && (
                <span className="opacity-40">·</span>
              )}
              {supportsOnline && (
                <span className="inline-flex items-center gap-1">
                  <Video className="size-3" aria-hidden />
                  Online
                </span>
              )}
              {!supportsInPerson && !supportsOnline && (
                <span>Tip konsultacija nije definisan</span>
              )}
            </div>
            <span className="inline-flex items-center gap-1 text-primary group-hover:translate-x-0.5 transition-transform">
              Otvori profil
              <ArrowRight className="size-3" aria-hidden />
            </span>
          </div>
        </CardContent>
      </Link>
    </Card>
  )
}
