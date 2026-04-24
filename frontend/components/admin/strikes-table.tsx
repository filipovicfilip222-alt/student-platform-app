/**
 * strikes-table.tsx — Admin overview of students with strike points.
 *
 * ROADMAP 4.7 / FRONTEND_STRUKTURA §3.6. Shows active blocks first so
 * admins can triage unblock requests. Unblock action requires a written
 * `removal_reason` which ends up in the audit log + strike history.
 */

"use client"

import { useMemo, useState } from "react"
import { Loader2, ShieldCheck, ShieldOff, ShieldAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/shared/empty-state"
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

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>Fakultet</TableHead>
              <TableHead>Poeni</TableHead>
              <TableHead>Blokiran do</TableHead>
              <TableHead>Poslednji strike</TableHead>
              <TableHead className="text-right">Akcije</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.isLoading ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <TableRow key={idx}>
                  <TableCell colSpan={6}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : query.isError ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8">
                  <EmptyState
                    icon={ShieldAlert}
                    title="Strike registar nije dostupan"
                    description="Backend endpoint /admin/strikes još nije aktivan (ROADMAP 4.7)."
                  />
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8">
                  <EmptyState
                    icon={ShieldCheck}
                    title="Nema aktivnih strike-ova"
                    description="Svi studenti trenutno imaju čist registar — nema potrebe za intervencijom."
                  />
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.student_id}>
                  <TableCell>
                    <div className="font-medium">{row.student_full_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {row.email}
                    </div>
                  </TableCell>
                  <TableCell>
                    <FacultyBadge faculty={row.faculty} />
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={row.total_points >= 3 ? "destructive" : "secondary"}
                    >
                      {row.total_points} / 3
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {row.blocked_until ? (
                      <span className="font-semibold text-red-600">
                        {formatDateTime(row.blocked_until)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.last_strike_at
                      ? formatRelative(row.last_strike_at)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setTarget(row)}
                      disabled={!row.blocked_until && row.total_points === 0}
                    >
                      <ShieldOff aria-hidden />
                      Odblokiraj
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

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
