/**
 * request-approve-dialog.tsx — Confirmation before approving a request.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Keeps the approval flow explicit so
 * accidental clicks on the row Action menu don't immediately auto-approve.
 */

"use client"

import { CheckCircle2, Loader2 } from "lucide-react"

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

export interface RequestApproveDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment: AppointmentResponse | null
  onConfirm: () => void
  isPending: boolean
}

export function RequestApproveDialog({
  open,
  onOpenChange,
  appointment,
  onConfirm,
  isPending,
}: RequestApproveDialogProps) {
  if (!appointment) return null

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia>
            <CheckCircle2 className="text-emerald-500" aria-hidden />
          </AlertDialogMedia>
          <AlertDialogTitle>Odobriti zahtev?</AlertDialogTitle>
          <AlertDialogDescription>
            Termin zakazan za{" "}
            <strong className="font-semibold text-foreground">
              {formatDateTime(appointment.slot_datetime)}
            </strong>
            . Student će dobiti email i in-app notifikaciju.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isPending}>Odustani</AlertDialogCancel>
          <AlertDialogAction
            disabled={isPending}
            onClick={(e) => {
              e.preventDefault()
              onConfirm()
            }}
          >
            {isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Odobravam...
              </>
            ) : (
              "Odobri termin"
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
