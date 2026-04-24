/**
 * availability-calendar.tsx — Professor-facing editable availability calendar.
 *
 * ROADMAP 3.7 / Faza 4 (frontend).
 *
 * Differences from BookingCalendar:
 *   - Reads slots from /professors/slots (useMySlots), not per-professor student view.
 *   - `selectable` on the grid: dragging out a range opens <RecurringRuleModal>.
 *   - Events are `editable` so professor can drag existing slot to a new time
 *     (triggers useUpdateSlot). eventResize also triggers update with new duration.
 *   - Click on an existing slot opens an AlertDialog to delete it.
 *
 * The backend endpoints for create/update/delete already exist (ROADMAP 3.1);
 * recurring rule expansion lives in ROADMAP 3.8 — until then every recurring
 * rule creates a single slot record with the rule stored in JSONB.
 *
 * PROFESOR only: inside <AvailabilityCalendar /> we hide the "new slot" flow
 * from ASISTENT via <RoleGate>, but passing just the `readOnly` prop is
 * sufficient when the page already knows the viewer role.
 */

"use client"

import { useMemo, useRef, useState } from "react"
import FullCalendar from "@fullcalendar/react"
import dayGridPlugin from "@fullcalendar/daygrid"
import timeGridPlugin from "@fullcalendar/timegrid"
import interactionPlugin from "@fullcalendar/interaction"
import type {
  DateSelectArg,
  EventClickArg,
  EventDropArg,
  EventInput,
} from "@fullcalendar/core"
import type { EventResizeDoneArg } from "@fullcalendar/interaction"
import { Loader2, Trash2 } from "lucide-react"

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
import { Skeleton } from "@/components/ui/skeleton"
import { CalendarLegend } from "@/components/calendar/calendar-legend"
import { RecurringRuleModal } from "@/components/calendar/recurring-rule-modal"
import {
  useCreateSlot,
  useDeleteSlot,
  useMySlots,
  useUpdateSlot,
} from "@/lib/hooks/use-availability"
import { cn } from "@/lib/utils"
import { formatDateTime } from "@/lib/utils/date"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { SlotResponse } from "@/types"

export interface AvailabilityCalendarProps {
  /** ASISTENT view: disable creating/updating/deleting slots. */
  readOnly?: boolean
  className?: string
}

export function AvailabilityCalendar({
  readOnly = false,
  className,
}: AvailabilityCalendarProps) {
  const calendarRef = useRef<FullCalendar | null>(null)
  const slotsQuery = useMySlots()
  const createMutation = useCreateSlot()
  const updateMutation = useUpdateSlot()
  const deleteMutation = useDeleteSlot()

  const [modalOpen, setModalOpen] = useState(false)
  const [draftStart, setDraftStart] = useState<Date | null>(null)
  const [draftEnd, setDraftEnd] = useState<Date | null>(null)
  const [toDelete, setToDelete] = useState<SlotResponse | null>(null)

  const events: EventInput[] = useMemo(() => {
    const slots = slotsQuery.data ?? []
    return slots.map((slot) => {
      const start = new Date(slot.slot_datetime)
      const end = new Date(start.getTime() + slot.duration_minutes * 60 * 1000)
      const isRecurring = Boolean(slot.recurring_rule)
      return {
        id: slot.id,
        title:
          slot.consultation_type === "ONLINE" ? "Online slot" : "Slot (uživo)",
        start,
        end,
        backgroundColor: isRecurring ? "rgb(14 165 233)" : "rgb(16 185 129)",
        borderColor: isRecurring ? "rgb(14 165 233)" : "rgb(16 185 129)",
        editable: !readOnly && !isRecurring,
        extendedProps: { slot },
      }
    })
  }, [slotsQuery.data, readOnly])

  function handleSelect(arg: DateSelectArg) {
    if (readOnly) return
    setDraftStart(arg.start)
    setDraftEnd(arg.end)
    setModalOpen(true)
    arg.view.calendar.unselect()
  }

  function handleEventClick(arg: EventClickArg) {
    const slot = arg.event.extendedProps.slot as SlotResponse | undefined
    if (!slot || readOnly) return
    setToDelete(slot)
  }

  async function handleEventDrop(arg: EventDropArg) {
    const slot = arg.event.extendedProps.slot as SlotResponse | undefined
    if (!slot || !arg.event.start) {
      arg.revert()
      return
    }
    try {
      await updateMutation.mutateAsync({
        id: slot.id,
        data: { slot_datetime: arg.event.start.toISOString() },
      })
      toastSuccess("Slot pomeren.")
    } catch (err) {
      arg.revert()
      toastApiError(err, "Greška pri pomeranju slota.")
    }
  }

  async function handleEventResize(arg: EventResizeDoneArg) {
    const slot = arg.event.extendedProps.slot as SlotResponse | undefined
    if (!slot || !arg.event.start || !arg.event.end) {
      arg.revert()
      return
    }
    const durationMinutes = Math.round(
      (arg.event.end.getTime() - arg.event.start.getTime()) / 60000
    )
    try {
      await updateMutation.mutateAsync({
        id: slot.id,
        data: { duration_minutes: durationMinutes },
      })
      toastSuccess("Trajanje slota ažurirano.")
    } catch (err) {
      arg.revert()
      toastApiError(err, "Greška pri promeni trajanja.")
    }
  }

  async function handleCreate(payload: Parameters<typeof createMutation.mutateAsync>[0]) {
    try {
      await createMutation.mutateAsync(payload)
      toastSuccess(
        payload.recurring_rule
          ? "Rekurentni slot je kreiran."
          : "Slot je kreiran."
      )
      setModalOpen(false)
    } catch (err) {
      toastApiError(err, "Greška pri kreiranju slota.")
    }
  }

  async function handleConfirmDelete() {
    if (!toDelete) return
    try {
      await deleteMutation.mutateAsync(toDelete.id)
      toastSuccess("Slot je obrisan.")
      setToDelete(null)
    } catch (err) {
      toastApiError(err, "Greška pri brisanju slota.")
    }
  }

  const isLoading = slotsQuery.isLoading
  const isMutating =
    createMutation.isPending || updateMutation.isPending

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CalendarLegend />
        {isMutating && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Čuvam izmene...
          </span>
        )}
      </div>

      {isLoading ? (
        <Skeleton className="h-[600px] w-full rounded-lg" />
      ) : (
        <div className="rounded-lg border bg-card p-2">
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView="timeGridWeek"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "timeGridWeek,dayGridMonth,timeGridDay",
            }}
            firstDay={1}
            locale="sr"
            allDaySlot={false}
            slotMinTime="07:00:00"
            slotMaxTime="22:00:00"
            height="auto"
            nowIndicator
            selectable={!readOnly}
            selectMirror
            editable={!readOnly}
            events={events}
            select={handleSelect}
            eventClick={handleEventClick}
            eventDrop={handleEventDrop}
            eventResize={handleEventResize}
            buttonText={{
              today: "Danas",
              month: "Mesec",
              week: "Nedelja",
              day: "Dan",
            }}
            noEventsText="Nemate definisane slotove u ovom periodu."
          />
        </div>
      )}

      {slotsQuery.isError && (
        <p className="text-xs text-destructive">
          Greška pri učitavanju slotova.
        </p>
      )}

      {!readOnly && (
        <p className="text-xs text-muted-foreground">
          Prevucite izbor na praznom polju da dodate novi slot. Kliknite na
          postojeći slot da ga obrišete, ili ga prevucite da ga pomerite.
        </p>
      )}

      <RecurringRuleModal
        open={modalOpen}
        onOpenChange={(v) => {
          setModalOpen(v)
          if (!v) {
            setDraftStart(null)
            setDraftEnd(null)
          }
        }}
        defaultStart={draftStart}
        defaultEnd={draftEnd}
        onSubmit={handleCreate}
        isSubmitting={createMutation.isPending}
      />

      <AlertDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia>
              <Trash2 className="text-destructive" aria-hidden />
            </AlertDialogMedia>
            <AlertDialogTitle>Obrisati slot?</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete && (
                <>
                  Slot zakazan za{" "}
                  <strong className="font-semibold text-foreground">
                    {formatDateTime(toDelete.slot_datetime)}
                  </strong>
                  . Ova akcija se ne može opozvati.
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
                handleConfirmDelete()
              }}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Brišem...
                </>
              ) : (
                "Obriši slot"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
