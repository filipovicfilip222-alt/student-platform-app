/**
 * (student)/appointments/[id]/page.tsx — Full appointment detail.
 *
 * ROADMAP 3.6 / Faza 3.6.
 *
 * Layout:
 *   - Left column (lg:col-span-2):
 *       · Header (status + topic + description + rejection reason)
 *       · Participant list (visible only when `is_group=true`)
 *       · File list (view + upload for non-terminal statuses)
 *   - Right column (lg:col-span-1):
 *       · TicketChat (polling fallback until ROADMAP 4.1 WS)
 *       · Cancel button (only for upcoming PENDING/APPROVED)
 *
 * The detail endpoint (`GET /appointments/{id}`) is ROADMAP 3.6 — so we
 * gracefully show a placeholder when the backend returns 404.
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
import { EmptyState } from "@/components/shared/empty-state"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ROUTES } from "@/lib/constants/routes"
import {
  useAppointmentDetail,
  useCancelAppointment,
} from "@/lib/hooks/use-appointments"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AppointmentResponse, AppointmentStatus } from "@/types"

const TERMINAL: AppointmentStatus[] = ["REJECTED", "CANCELLED", "COMPLETED"]

export default function AppointmentDetailPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const appointmentId = params?.id ?? null

  const detailQuery = useAppointmentDetail(appointmentId)
  const cancelMutation = useCancelAppointment()
  const [showCancel, setShowCancel] = useState(false)

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
              <Link href={ROUTES.myAppointments}>Moji termini</Link>
            </Button>
          </div>
        }
      />
    )
  }

  const appointment = detailQuery.data
  const isTerminal = TERMINAL.includes(appointment.status)
  const canCancel = !isTerminal

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

  function handleConfirmCancel() {
    cancelMutation.mutate(appointment.id, {
      onSuccess: () => {
        toastSuccess("Termin je otkazan.")
        setShowCancel(false)
      },
      onError: (err) => toastApiError(err, "Greška pri otkazivanju termina."),
    })
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
        {canCancel && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowCancel(true)}
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
        open={showCancel}
        onOpenChange={setShowCancel}
        appointment={showCancel ? simpleAppointment : null}
        onConfirm={handleConfirmCancel}
        isPending={cancelMutation.isPending}
      />
    </div>
  )
}
