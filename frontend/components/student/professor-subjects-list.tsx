/**
 * professor-subjects-list.tsx — Compact subject chips list.
 *
 * ROADMAP 3.5 / Faza 3.5. Shown on the student-facing professor
 * profile between the header and the FAQ accordion.
 */

import { BookOpen } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export interface ProfessorSubjectsListProps {
  subjects: string[]
}

export function ProfessorSubjectsList({ subjects }: ProfessorSubjectsListProps) {
  if (subjects.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="p-5 pb-2">
        <CardTitle className="inline-flex items-center gap-2 text-base font-semibold">
          <BookOpen className="size-4 text-muted-foreground" aria-hidden />
          Predmeti
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5 pt-2">
        <div className="flex flex-wrap gap-1.5">
          {subjects.map((subject) => (
            <Badge key={subject} variant="outline" className="text-xs">
              {subject}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
