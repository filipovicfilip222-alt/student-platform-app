/**
 * requests-inbox.tsx — Professor / assistant inbox of incoming appointment
 * requests.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Shows a status filter (PENDING by
 * default) and a table of requests with per-row actions (Approve /
 * Reject / Delegate). All three actions fire mutations from
 * `use-requests-inbox`.
 *
 * Backend endpoints exist only as stubs today (ROADMAP 3.7). We still
 * render the full UX so the wiring is ready the moment the backend ships.
 */

"use client"

import { useState } from "react"
import { Inbox } from "lucide-react"

import { EmptyState } from "@/components/shared/empty-state"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  useApproveRequest,
  useCancelRequest,
  useDelegateRequest,
  useRejectRequest,
  useRequestsInbox,
} from "@/lib/hooks/use-requests-inbox"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AppointmentResponse, Uuid } from "@/types"

import { RequestApproveDialog } from "./request-approve-dialog"
import { RequestDelegateDialog } from "./request-delegate-dialog"
import { RequestInboxRow } from "./request-inbox-row"
import { RequestRejectDialog } from "./request-reject-dialog"

type InboxFilter = "PENDING" | "ALL"

export function RequestsInbox() {
  const [filter, setFilter] = useState<InboxFilter>("PENDING")
  const [toApprove, setToApprove] = useState<AppointmentResponse | null>(null)
  const [toReject, setToReject] = useState<AppointmentResponse | null>(null)
  const [toDelegate, setToDelegate] = useState<AppointmentResponse | null>(null)
  const [toCancel, setToCancel] = useState<AppointmentResponse | null>(null)

  const inboxQuery = useRequestsInbox(filter)
  const approveMutation = useApproveRequest()
  const rejectMutation = useRejectRequest()
  const delegateMutation = useDelegateRequest()
  const cancelMutation = useCancelRequest()

  const requests = inboxQuery.data ?? []

  function handleApprove() {
    if (!toApprove) return
    approveMutation.mutate(toApprove.id, {
      onSuccess: () => {
        toastSuccess("Termin je odobren.")
        setToApprove(null)
      },
      onError: (err) => toastApiError(err, "Greška pri odobravanju termina."),
    })
  }

  function handleReject(reason: string) {
    if (!toReject) return
    rejectMutation.mutate(
      { id: toReject.id, reason },
      {
        onSuccess: () => {
          toastSuccess("Termin je odbijen.")
          setToReject(null)
        },
        onError: (err) => toastApiError(err, "Greška pri odbijanju termina."),
      }
    )
  }

  function handleDelegate(assistantId: Uuid) {
    if (!toDelegate) return
    delegateMutation.mutate(
      { id: toDelegate.id, assistantId },
      {
        onSuccess: () => {
          toastSuccess("Zahtev je delegiran asistentu.")
          setToDelegate(null)
        },
        onError: (err) => toastApiError(err, "Greška pri delegiranju."),
      }
    )
  }

  function handleCancel(reason: string) {
    if (!toCancel) return
    cancelMutation.mutate(
      { id: toCancel.id, reason },
      {
        onSuccess: () => {
          toastSuccess("Termin je otkazan i student je obavešten.")
          setToCancel(null)
        },
        onError: (err) => toastApiError(err, "Greška pri otkazivanju termina."),
      }
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h2 className="text-base font-semibold">Dolazeći zahtevi</h2>
          <p className="text-sm text-muted-foreground">
            Odobrite, odbijte ili delegirajte zahteve studenata.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="inbox-filter" className="text-xs text-muted-foreground">
            Filter
          </label>
          <Select
            value={filter}
            onValueChange={(v) => setFilter(v as InboxFilter)}
          >
            <SelectTrigger id="inbox-filter" className="w-40" size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="PENDING">Na čekanju</SelectItem>
              <SelectItem value="ALL">Svi zahtevi</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {inboxQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full rounded-lg" />
          <Skeleton className="h-10 w-full rounded-lg" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>
      ) : inboxQuery.isError ? (
        <EmptyState
          icon={Inbox}
          title="Nije dostupno"
          description="Inbox endpoint još nije aktivan (backend u izradi)."
        />
      ) : requests.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nema zahteva"
          description={
            filter === "PENDING"
              ? "Nemate zahteva koji čekaju odgovor."
              : "Inbox je prazan."
          }
        />
      ) : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Termin</TableHead>
                <TableHead>Student</TableHead>
                <TableHead>Tema</TableHead>
                <TableHead>Opis</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[60px] text-right">Akcije</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((r) => (
                <RequestInboxRow
                  key={r.id}
                  appointment={r}
                  onApprove={() => setToApprove(r)}
                  onReject={() => setToReject(r)}
                  onDelegate={() => setToDelegate(r)}
                  onCancel={() => setToCancel(r)}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <RequestApproveDialog
        open={toApprove !== null}
        onOpenChange={(open) => !open && setToApprove(null)}
        appointment={toApprove}
        onConfirm={handleApprove}
        isPending={approveMutation.isPending}
      />
      <RequestRejectDialog
        open={toReject !== null}
        onOpenChange={(open) => !open && setToReject(null)}
        appointment={toReject}
        onConfirm={handleReject}
        isPending={rejectMutation.isPending}
      />
      <RequestDelegateDialog
        open={toDelegate !== null}
        onOpenChange={(open) => !open && setToDelegate(null)}
        appointment={toDelegate}
        onConfirm={handleDelegate}
        isPending={delegateMutation.isPending}
      />
      {/* Cancel reuses the reject dialog — same UX (mandatory reason that
          ends up in rejection_reason and is forwarded to the student). */}
      <RequestRejectDialog
        open={toCancel !== null}
        onOpenChange={(open) => !open && setToCancel(null)}
        appointment={toCancel}
        onConfirm={handleCancel}
        isPending={cancelMutation.isPending}
        title="Otkaži odobreni termin"
        description="Student će dobiti obaveštenje sa razlogom otkazivanja. Obavezno unesite kratko obrazloženje."
        confirmLabel="Otkaži termin"
        reasonLabel="Razlog otkazivanja"
      />
    </div>
  )
}
