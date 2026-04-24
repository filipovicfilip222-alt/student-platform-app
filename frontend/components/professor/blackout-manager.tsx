/**
 * blackout-manager.tsx — Blackout-period CRUD (settings → Blackout tab).
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Lets the professor pick a date range
 * through the shadcn Calendar (mode="range") and an optional reason.
 * Lists active blackouts with a delete action. Once a blackout is
 * persisted, the professor's availability for that range is hidden from
 * students (backend filter).
 */

"use client"

import { useMemo, useState } from "react"
import { CalendarOff, Loader2, Trash2 } from "lucide-react"
import type { DateRange } from "react-day-picker"
import { sr } from "date-fns/locale"
import { format, isSameDay } from "date-fns"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/shared/empty-state"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useBlackouts,
  useCreateBlackout,
  useDeleteBlackout,
} from "@/lib/hooks/use-availability"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import { formatDate } from "@/lib/utils/date"
import type { BlackoutResponse } from "@/types"

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd")
}

export function BlackoutManager() {
  const listQuery = useBlackouts()
  const createMutation = useCreateBlackout()
  const deleteMutation = useDeleteBlackout()

  const [range, setRange] = useState<DateRange | undefined>(undefined)
  const [reason, setReason] = useState("")
  const [toDelete, setToDelete] = useState<BlackoutResponse | null>(null)

  const sorted = useMemo(
    () =>
      [...(listQuery.data ?? [])].sort((a, b) =>
        a.start_date.localeCompare(b.start_date)
      ),
    [listQuery.data]
  )

  const canSubmit =
    range?.from !== undefined && range.to !== undefined && !createMutation.isPending

  function handleCreate() {
    if (!range?.from || !range.to) return
    createMutation.mutate(
      {
        start_date: toIsoDate(range.from),
        end_date: toIsoDate(range.to),
        reason: reason.trim() ? reason.trim() : null,
      },
      {
        onSuccess: () => {
          toastSuccess("Blackout dodat.")
          setRange(undefined)
          setReason("")
        },
        onError: (err) => toastApiError(err, "Greška pri dodavanju blackout-a."),
      }
    )
  }

  function handleDelete() {
    if (!toDelete) return
    deleteMutation.mutate(toDelete.id, {
      onSuccess: () => {
        toastSuccess("Blackout obrisan.")
        setToDelete(null)
      },
      onError: (err) => toastApiError(err, "Greška pri brisanju blackout-a."),
    })
  }

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">Novi blackout period</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex justify-center rounded-lg border bg-muted/30 p-2">
            <Calendar
              mode="range"
              selected={range}
              onSelect={setRange}
              locale={sr}
              numberOfMonths={2}
              disabled={{ before: new Date() }}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="blackout-reason">Razlog (opciono)</Label>
            <Input
              id="blackout-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Godišnji odmor, konferencija..."
              maxLength={200}
              disabled={createMutation.isPending}
            />
          </div>

          <div className="flex items-center justify-between gap-3">
            <div className="text-sm text-muted-foreground">
              {range?.from && range.to ? (
                isSameDay(range.from, range.to) ? (
                  <>Izabrano: <strong>{formatDate(range.from)}</strong></>
                ) : (
                  <>
                    <strong>{formatDate(range.from)}</strong> →{" "}
                    <strong>{formatDate(range.to)}</strong>
                  </>
                )
              ) : (
                "Izaberite opseg datuma."
              )}
            </div>
            <Button
              type="button"
              onClick={handleCreate}
              disabled={!canSubmit}
            >
              {createMutation.isPending && (
                <Loader2 className="animate-spin" aria-hidden />
              )}
              Sačuvaj blackout
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Aktivni blackout periodi</CardTitle>
        </CardHeader>
        <CardContent>
          {listQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full rounded-lg" />
              <Skeleton className="h-14 w-full rounded-lg" />
            </div>
          ) : listQuery.isError ? (
            <EmptyState
              icon={CalendarOff}
              title="Lista nije dostupna"
              description="Endpoint je još u izradi (backend ROADMAP 3.7)."
            />
          ) : sorted.length === 0 ? (
            <EmptyState
              icon={CalendarOff}
              title="Nema aktivnih blackout-a"
              description="Dodajte datum da studenti ne mogu da rezervišu termine."
            />
          ) : (
            <ul className="space-y-2">
              {sorted.map((bo) => (
                <li
                  key={bo.id}
                  className="flex items-start justify-between gap-3 rounded-lg border bg-card p-3"
                >
                  <div className="min-w-0 space-y-0.5">
                    <p className="text-sm font-medium text-foreground">
                      {formatDate(bo.start_date)} — {formatDate(bo.end_date)}
                    </p>
                    {bo.reason && (
                      <p className="text-xs text-muted-foreground">
                        {bo.reason}
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Obriši blackout"
                    onClick={() => setToDelete(bo)}
                  >
                    <Trash2 aria-hidden className="text-destructive" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <AlertDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Obrisati blackout?</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete && (
                <>
                  Period{" "}
                  <strong>
                    {formatDate(toDelete.start_date)} —{" "}
                    {formatDate(toDelete.end_date)}
                  </strong>{" "}
                  će biti uklonjen i vaša dostupnost za taj opseg se
                  vraća na podrazumevani raspored.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Odustani
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Brišem...
                </>
              ) : (
                "Obriši"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
