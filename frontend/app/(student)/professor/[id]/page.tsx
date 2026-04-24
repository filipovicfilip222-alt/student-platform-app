/**
 * (student)/professor/[id]/page.tsx — Professor profile + booking entry.
 *
 * ROADMAP 3.5 / Faza 3.5.
 *
 * Layout (per PRD §2.2):
 *   1. Header  — name, title, department, faculty, office, areas of interest.
 *   2. Subjects chips.
 *   3. FAQ accordion (above calendar — PRD requirement).
 *   4. BookingCalendar.
 *
 * Clicking an available slot opens the <AppointmentRequestForm /> dialog.
 */

"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, CalendarX } from "lucide-react"

import { AppointmentRequestForm } from "@/components/appointments/appointment-request-form"
import { BookingCalendar } from "@/components/calendar/booking-calendar"
import { EmptyState } from "@/components/shared/empty-state"
import { ProfessorFaqAccordion } from "@/components/student/professor-faq-accordion"
import { ProfessorProfileHeader } from "@/components/student/professor-profile-header"
import { ProfessorSubjectsList } from "@/components/student/professor-subjects-list"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useProfessorProfile } from "@/lib/hooks/use-professors"
import type { AvailableSlotResponse } from "@/types"

export default function ProfessorProfilePage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const professorId = params?.id ?? null

  const profileQuery = useProfessorProfile(professorId)
  const [pickedSlot, setPickedSlot] = useState<AvailableSlotResponse | null>(
    null
  )

  if (profileQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-[560px] w-full rounded-lg" />
      </div>
    )
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <EmptyState
        icon={CalendarX}
        title="Profesor nije pronađen"
        description="Proverite link ili se vratite na pretragu."
        action={
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft aria-hidden />
            Nazad
          </Button>
        }
      />
    )
  }

  const professor = profileQuery.data

  return (
    <div className="space-y-5">
      <div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => router.back()}
        >
          <ArrowLeft aria-hidden />
          Nazad
        </Button>
      </div>

      <ProfessorProfileHeader professor={professor} />

      <ProfessorSubjectsList subjects={professor.subjects} />

      <ProfessorFaqAccordion faq={professor.faq} />

      <section className="space-y-2">
        <h2 className="text-lg font-semibold tracking-tight">
          Dostupni termini
        </h2>
        <p className="text-sm text-muted-foreground">
          Kliknite na zeleni slot u kalendaru da pošaljete zahtev.
        </p>
        <BookingCalendar
          professorId={professor.id}
          onSelectSlot={setPickedSlot}
        />
      </section>

      <AppointmentRequestForm
        open={pickedSlot !== null}
        onOpenChange={(open) => !open && setPickedSlot(null)}
        slot={pickedSlot}
      />
    </div>
  )
}
