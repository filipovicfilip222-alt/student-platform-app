/**
 * strikes-table.tsx — Admin overview studenata sa strike poenima.
 *
 * KORAK 4 — refaktor sa generic `<DataTable />`. Sortiranje po
 * blocked_until + total_points je sada kolona-driven (server-side sort
 * nije podržan; client sort radi za <=1k redova bez probleme).
 *
 * Default sort: blocked_until DESC (blokirani prvi), pa total_points DESC.
 */

"use client"

import { useMemo, useState } from "react"
import {
  Loader2,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
} from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { FacultyBadge } from "@/components/shared/faculty-badge"
import { useStrikes, useUnblockStudent } from "@/lib/hooks/use-strikes"
import { formatDateTime, formatRelative } from "@/lib/utils/date"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { StrikeRow } from "@/types"

export function StrikesTable() {
  const query = useStrikes()
  const [target, setTarget] = useState<StrikeRow | null>(null)

  const rows = useMemo(() => {
    const data = query.data ?? []
    return [...data].sort((a, b) => {
      const aBlocked = a.blocked_until ? 1 : 0
      const bBlocked = b.blocked_until ? 1 : 0
      if (aBlocked !== bBlocked) return bBlocked - aBlocked
      return b.total_points - a.total_points
    })
  }, [query.data])

  const columns = useMemo<ColumnDef<StrikeRow>[]>(
    () => [
      {
        id: "student",
        header: "Student",
        accessorFn: (r) => r.student_full_name,
        cell: ({ row }) => (
          <div className="space-y-0.5">
            <div className="font-medium">{row.original.student_full_name}</div>
            <div className="text-xs text-muted-foreground">
              {row.original.email}
            </div>
          </div>
        ),
      },
      {
        accessorKey: "faculty",
        header: "Fakultet",
        cell: ({ row }) => <FacultyBadge faculty={row.original.faculty} />,
      },
      {
        accessorKey: "total_points",
        header: "Poeni",
        cell: ({ row }) => (
          <Badge
            variant={row.original.total_points >= 3 ? "destructive" : "secondary"}
          >
            {row.original.total_points} / 3
          </Badge>
        ),
      },
      {
        accessorKey: "blocked_until",
        header: "Blokiran do",
        cell: ({ row }) =>
          row.original.blocked_until ? (
            <span className="text-xs font-semibold text-destructive">
              {formatDateTime(row.original.blocked_until)}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          ),
      },
      {
        accessorKey: "last_strike_at",
        header: "Poslednji strike",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {row.original.last_strike_at
              ? formatRelative(row.original.last_strike_at)
              : "—"}
          </span>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Akcije</span>,
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setTarget(row.original)}
              disabled={
                !row.original.blocked_until && row.original.total_points === 0
              }
            >
              <ShieldOff aria-hidden />
              Odblokiraj
            </Button>
          </div>
        ),
      },
    ],
    []
  )

  return (
    <div className="space-y-4">
      <DataTable<StrikeRow, unknown>
        data={rows}
        columns={columns}
        isLoading={query.isLoading}
        isError={query.isError}
        ariaLabel="Strike registar"
        getRowId={(row) => row.student_id}
        emptyState={{
          icon: ShieldCheck,
          title: "Nema aktivnih strike-ova",
          description:
            "Svi studenti trenutno imaju čist registar — nema potrebe za intervencijom.",
        }}
        errorState={{
          icon: ShieldAlert,
          title: "Strike registar nije dostupan",
          description:
            "Backend endpoint /admin/strikes još nije aktivan (ROADMAP 4.7).",
        }}
      />

      <UnblockDialog
        target={target}
        onOpenChange={(open) => !open && setTarget(null)}
      />
    </div>
  )
}

function UnblockDialog({
  target,
  onOpenChange,
}: {
  target: StrikeRow | null
  onOpenChange: (open: boolean) => void
}) {
  const [reason, setReason] = useState("")
  const mutation = useUnblockStudent()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!target || reason.trim().length < 10) return
    try {
      await mutation.mutateAsync({
        studentId: target.student_id,
        data: { removal_reason: reason.trim() },
      })
      toastSuccess(
        "Student odblokiran",
        `${target.student_full_name} ponovo može da zakazuje termine.`
      )
      setReason("")
      onOpenChange(false)
    } catch (err) {
      toastApiError(err, "Odblokiranje nije uspelo.")
    }
  }

  return (
    <Dialog
      open={Boolean(target)}
      onOpenChange={(next) => {
        if (!next) setReason("")
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Odblokiraj studenta</DialogTitle>
          <DialogDescription>
            Resetovaćete strike poene i ukloniti blokadu za{" "}
            <strong>{target?.student_full_name}</strong>. Razlog se upisuje u
            audit log.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="unblock-reason">Razlog (min 10 karaktera)</Label>
            <Textarea
              id="unblock-reason"
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              minLength={10}
              placeholder="Npr. Student je priložio medicinsku dokumentaciju…"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Otkaži
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending || reason.trim().length < 10}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Odblokiram…
                </>
              ) : (
                "Odblokiraj"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
