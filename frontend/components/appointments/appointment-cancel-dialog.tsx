/**
 * appointment-cancel-dialog.tsx — Confirm cancellation of a student
 * appointment, with explicit <24h strike warning (PRD §2.3).
 *
 * ROADMAP 3.3 / Faza 3.3. Renders nothing when `open=false`. Parent
 * passes the target appointment and a mutation instance (created by
 * `useCancelAppointment`) so errors/toasts live outside the dialog.
 */

"use client"

import { AlertTriangle, Loader2 } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { formatDateTime } from "@/lib/utils/date"
import type { AppointmentResponse } from "@/types"

const HOURS_24_MS = 24 * 60 * 60 * 1000

export interface AppointmentCancelDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment: AppointmentResponse | null
  onConfirm: () => void
  isPending: boolean
}

export function AppointmentCancelDialog({
  open,
  onOpenChange,
  appointment,
  onConfirm,
  isPending,
}: AppointmentCancelDialogProps) {
  if (!appointment) return null

  const slotDate = new Date(appointment.slot_datetime)
  const msUntilSlot = slotDate.getTime() - Date.now()
  const isLateCancellation = msUntilSlot > 0 && msUntilSlot < HOURS_24_MS

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia>
            <AlertTriangle className="text-amber-500" aria-hidden />
          </AlertDialogMedia>
          <AlertDialogTitle>Otkazati termin?</AlertDialogTitle>
          <AlertDialogDescription>
            Termin zakazan za{" "}
            <strong className="font-semibold text-foreground">
              {formatDateTime(appointment.slot_datetime)}
            </strong>
            .
          </AlertDialogDescription>
        </AlertDialogHeader>

        {isLateCancellation && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <p className="font-semibold">Otkazivanje u poslednjih 24h</p>
            <p className="mt-1 text-destructive/90">
              Dobićete strike poen. Tri poena u periodu od 6 meseci znače
              privremenu blokadu zakazivanja.
            </p>
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Zadrži termin</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={isPending}
            onClick={(e) => {
              e.preventDefault()
              onConfirm()
            }}
          >
            {isPending ? (
              <>
                <Loader2 className="animate-spin" />
                Otkazujem...
              </>
            ) : (
              "Otkaži termin"
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
