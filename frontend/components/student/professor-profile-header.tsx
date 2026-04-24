/**
 * professor-profile-header.tsx — Header block for /professor/[id].
 *
 * ROADMAP 3.5 / Faza 3.5. Shows avatar placeholder + name + title +
 * department + faculty badge + office info. Areas of interest are
 * rendered below the main row as a chip cloud.
 */

import { MapPin } from "lucide-react"

import { FacultyBadge } from "@/components/shared/faculty-badge"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { ProfessorProfileResponse } from "@/types"

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("")
}

export interface ProfessorProfileHeaderProps {
  professor: ProfessorProfileResponse
}

export function ProfessorProfileHeader({
  professor,
}: ProfessorProfileHeaderProps) {
  const {
    full_name,
    title,
    department,
    faculty,
    office,
    office_description,
    areas_of_interest,
  } = professor

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          <div className="flex size-20 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xl font-semibold tracking-wide text-primary">
            {getInitials(full_name) || "?"}
          </div>

          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                {full_name}
              </h1>
              <FacultyBadge faculty={faculty} />
            </div>
            <p className="text-sm text-muted-foreground">
              {title}
              {title && department ? " · " : ""}
              {department}
            </p>

            {(office || office_description) && (
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />
                <div className="space-y-0.5">
                  {office && (
                    <p className="font-medium text-foreground">{office}</p>
                  )}
                  {office_description && (
                    <p className="text-xs">{office_description}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {areas_of_interest.length > 0 && (
          <div className="mt-5 space-y-2 border-t pt-4">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Oblasti interesovanja
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {areas_of_interest.map((area) => (
                <Badge key={area} variant="secondary">
                  {area}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
