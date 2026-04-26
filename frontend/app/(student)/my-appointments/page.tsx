/**
 * (student)/my-appointments/page.tsx — Upcoming / history tabs.
 *
 * ROADMAP 3.3 / Faza 3.3.
 *
 * Tabs:
 *   - "Predstojeći"  → useMyAppointments('upcoming')
 *   - "Istorija"     → useMyAppointments('history')
 *
 * Cancel action is available only on upcoming + non-terminal statuses
 * (PENDING or APPROVED). Terminal statuses (REJECTED, CANCELLED,
 * COMPLETED) render the card without the cancel button.
 */

"use client"

import { useState } from "react"
import Link from "next/link"
import { CalendarPlus, CalendarRange, X } from "lucide-react"

import { AppointmentCancelDialog } from "@/components/appointments/appointment-cancel-dialog"
import { AppointmentCard } from "@/components/appointments/appointment-card"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { PageHeader } from "@/components/shared/page-header"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useCancelAppointment,
  useMyAppointments,
} from "@/lib/hooks/use-appointments"
import { ROUTES } from "@/lib/constants/routes"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AppointmentResponse } from "@/types"

type ViewTab = "upcoming" | "history"

const CANCELLABLE_STATUSES = new Set<AppointmentResponse["status"]>([
  "PENDING",
  "APPROVED",
])

export default function MyAppointmentsPage() {
  const [view, setView] = useState<ViewTab>("upcoming")
  const [toCancel, setToCancel] = useState<AppointmentResponse | null>(null)

  const upcomingQuery = useMyAppointments("upcoming")
  const historyQuery = useMyAppointments("history")
  const cancelMutation = useCancelAppointment()

  function handleConfirmCancel() {
    if (!toCancel) return
    cancelMutation.mutate(toCancel.id, {
      onSuccess: () => {
        toastSuccess("Termin je otkazan.")
        setToCancel(null)
      },
      onError: (err) => toastApiError(err, "Greška pri otkazivanju termina."),
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Moji termini"
        description="Pregled predstojećih i prošlih konsultacija."
      >
        <Button asChild>
          <Link href={ROUTES.search}>
            <CalendarPlus aria-hidden />
            Zakaži novi termin
          </Link>
        </Button>
      </PageHeader>

      <Tabs value={view} onValueChange={(v) => setView(v as ViewTab)}>
        <TabsList className="w-full max-w-xs">
          <TabsTrigger value="upcoming" className="flex-1">
            Predstojeći
          </TabsTrigger>
          <TabsTrigger value="history" className="flex-1">
            Istorija
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming" className="pt-4">
          <AppointmentList
            data={upcomingQuery.data ?? []}
            isLoading={upcomingQuery.isLoading}
            isError={upcomingQuery.isError}
            emptyTitle="Nemate zakazane termine"
            emptyDescription="Pronađite profesora i rezervišite prvi slot."
            onRequestCancel={setToCancel}
            renderCancel
          />
        </TabsContent>

        <TabsContent value="history" className="pt-4">
          <AppointmentList
            data={historyQuery.data ?? []}
            isLoading={historyQuery.isLoading}
            isError={historyQuery.isError}
            emptyTitle="Nema prošlih termina"
            emptyDescription="Kad završite prvi termin, pojaviće se ovde."
            onRequestCancel={() => undefined}
            renderCancel={false}
          />
        </TabsContent>
      </Tabs>

      <AppointmentCancelDialog
        open={toCancel !== null}
        onOpenChange={(open) => !open && setToCancel(null)}
        appointment={toCancel}
        onConfirm={handleConfirmCancel}
        isPending={cancelMutation.isPending}
      />
    </div>
  )
}

interface AppointmentListProps {
  data: AppointmentResponse[]
  isLoading: boolean
  isError: boolean
  emptyTitle: string
  emptyDescription: string
  onRequestCancel: (appointment: AppointmentResponse) => void
  renderCancel: boolean
}

function AppointmentList({
  data,
  isLoading,
  isError,
  emptyTitle,
  emptyDescription,
  onRequestCancel,
  renderCancel,
}: AppointmentListProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-[88px] w-full rounded-lg" />
        <Skeleton className="h-[88px] w-full rounded-lg" />
        <Skeleton className="h-[88px] w-full rounded-lg" />
      </div>
    )
  }
  if (isError) {
    return (
      <ErrorState
        title="Termini trenutno nisu dostupni"
        description="Osvežite stranicu ili pokušajte ponovo za par sekundi."
      />
    )
  }
  if (data.length === 0) {
    return (
      <EmptyState
        icon={CalendarRange}
        title={emptyTitle}
        description={emptyDescription}
      />
    )
  }

  return (
    <div className="space-y-2">
      {data.map((appointment) => {
        const canCancel =
          renderCancel && CANCELLABLE_STATUSES.has(appointment.status)
        return (
          <AppointmentCard
            key={appointment.id}
            appointment={appointment}
            // Card is always interactive so the student can open the
            // detail page (chat + files). The Cancel button stops
            // propagation so it doesn't trigger the wrapping <Link>.
            interactive
            actions={
              canCancel ? (
                <CancelButton onClick={() => onRequestCancel(appointment)} />
              ) : undefined
            }
          />
        )
      })}
    </div>
  )
}

function CancelButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onClick()
      }}
    >
      <X aria-hidden />
      Otkaži
    </Button>
  )
}
