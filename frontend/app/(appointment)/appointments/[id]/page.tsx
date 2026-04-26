/**
 * (appointment)/appointments/[id]/page.tsx — Shared appointment detail.
 *
 * Renders the same full detail view (status + topic + description, optional
 * participants list, file list with upload, ticket chat) for every
 * authenticated party of an appointment:
 *
 *   - The lead student who booked the slot (sees "Otkaži termin" while
 *     status is PENDING or APPROVED — same flow as before, calls the
 *     student-side cancel endpoint that adds a strike for late cancels).
 *   - The professor who owns the slot, or the asistent the request was
 *     delegated to (sees a separate "Otkaži termin" path that calls the
 *     professor portal cancel endpoint, only available on APPROVED).
 *
 * Backend RBAC on `/appointments/{id}` ensures only the parties involved
 * can fetch the detail, so a foreign user landing on the URL gets a 404
 * which we render as a soft empty state.
 */

"use client"

import { useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, CalendarX, X } from "lucide-react"

import { AppointmentCancelDialog } from "@/components/appointments/appointment-cancel-dialog"
import { AppointmentDetailHeader } from "@/components/appointments/appointment-detail-header"
import { FileList } from "@/components/appointments/file-list"
import { ParticipantList } from "@/components/appointments/participant-list"
import { TicketChat } from "@/components/chat/ticket-chat"
import { RequestRejectDialog } from "@/components/professor/request-reject-dialog"
import { EmptyState } from "@/components/shared/empty-state"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ROUTES } from "@/lib/constants/routes"
import {
  useAppointmentDetail,
  useCancelAppointment,
} from "@/lib/hooks/use-appointments"
import { useCancelRequest } from "@/lib/hooks/use-requests-inbox"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AppointmentResponse, AppointmentStatus } from "@/types"

const TERMINAL: AppointmentStatus[] = ["REJECTED", "CANCELLED", "COMPLETED"]

export default function AppointmentDetailPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const appointmentId = params?.id ?? null

  const role = useAuthStore((s) => s.user?.role)
  const isStudent = role === "STUDENT"
  const isStaff = role === "PROFESOR" || role === "ASISTENT"

  const detailQuery = useAppointmentDetail(appointmentId)
  const studentCancel = useCancelAppointment()
  const staffCancel = useCancelRequest()

  const [showStudentCancel, setShowStudentCancel] = useState(false)
  const [showStaffCancel, setShowStaffCancel] = useState(false)

  if (detailQuery.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Skeleton className="h-52 rounded-lg" />
          <Skeleton className="h-40 rounded-lg" />
        </div>
        <Skeleton className="h-[520px] rounded-lg" />
      </div>
    )
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <EmptyState
        icon={CalendarX}
        title="Termin nije dostupan"
        description="Detaljan prikaz termina još nije aktivan (backend ROADMAP 3.6) ili termin ne postoji."
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.back()}>
              <ArrowLeft aria-hidden />
              Nazad
            </Button>
            <Button asChild>
              <Link href={isStaff ? ROUTES.professorDashboard : ROUTES.myAppointments}>
                {isStaff ? "Profesor dashboard" : "Moji termini"}
              </Link>
            </Button>
          </div>
        }
      />
    )
  }

  const appointment = detailQuery.data
  const isTerminal = TERMINAL.includes(appointment.status)

  // Student can cancel anything not yet terminal (PENDING or APPROVED) —
  // late-cancel strike logic lives on the backend.
  const canStudentCancel = isStudent && !isTerminal

  // Staff can cancel only an already-confirmed slot (APPROVED). Rejecting
  // a PENDING request goes through the inbox row dropdown, not here.
  const canStaffCancel = isStaff && appointment.status === "APPROVED"

  const simpleAppointment: AppointmentResponse = {
    id: appointment.id,
    slot_id: appointment.slot_id,
    professor_id: appointment.professor_id,
    lead_student_id: appointment.lead_student_id,
    subject_id: appointment.subject_id,
    topic_category: appointment.topic_category,
    description: appointment.description,
    status: appointment.status,
    consultation_type: appointment.consultation_type,
    slot_datetime: appointment.slot_datetime,
    created_at: appointment.created_at,
  }

  function handleStudentConfirmCancel() {
    studentCancel.mutate(appointment.id, {
      onSuccess: () => {
        toastSuccess("Termin je otkazan.")
        setShowStudentCancel(false)
      },
      onError: (err) => toastApiError(err, "Greška pri otkazivanju termina."),
    })
  }

  function handleStaffConfirmCancel(reason: string) {
    staffCancel.mutate(
      { id: appointment.id, reason },
      {
        onSuccess: () => {
          toastSuccess("Termin je otkazan i student je obavešten.")
          setShowStaffCancel(false)
        },
        onError: (err) => toastApiError(err, "Greška pri otkazivanju termina."),
      }
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
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
        {canStudentCancel && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowStudentCancel(true)}
          >
            <X aria-hidden />
            Otkaži termin
          </Button>
        )}
        {canStaffCancel && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowStaffCancel(true)}
          >
            <X aria-hidden />
            Otkaži termin
          </Button>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <AppointmentDetailHeader appointment={appointment} />

          {appointment.is_group && (
            <ParticipantList appointmentId={appointment.id} />
          )}

          <FileList
            appointmentId={appointment.id}
            canUpload={!isTerminal}
          />
        </div>

        <div className="lg:col-span-1">
          <TicketChat
            appointmentId={appointment.id}
            appointmentStatus={appointment.status}
          />
        </div>
      </div>

      <AppointmentCancelDialog
        open={showStudentCancel}
        onOpenChange={setShowStudentCancel}
        appointment={showStudentCancel ? simpleAppointment : null}
        onConfirm={handleStudentConfirmCancel}
        isPending={studentCancel.isPending}
      />

      {/* Staff cancel — reuses the reject dialog because the UX is identical:
          mandatory reason that ends up in the rejection_reason column and
          is forwarded to the student via the existing notification template. */}
      <RequestRejectDialog
        open={showStaffCancel}
        onOpenChange={setShowStaffCancel}
        appointment={showStaffCancel ? simpleAppointment : null}
        onConfirm={handleStaffConfirmCancel}
        isPending={staffCancel.isPending}
        title="Otkaži odobreni termin"
        description="Student će dobiti obaveštenje sa razlogom otkazivanja. Obavezno unesite kratko obrazloženje."
        confirmLabel="Otkaži termin"
        reasonLabel="Razlog otkazivanja"
      />
    </div>
  )
}
