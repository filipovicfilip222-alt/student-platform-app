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
import listPlugin from "@fullcalendar/list"
import type {
  DateSelectArg,
  EventClickArg,
  EventContentArg,
  EventDropArg,
  EventInput,
} from "@fullcalendar/core"
import type { EventResizeDoneArg } from "@fullcalendar/interaction"
import { Loader2, Repeat, Trash2 } from "lucide-react"

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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { CalendarLegend } from "@/components/calendar/calendar-legend"
import { CalendarSkeleton } from "@/components/calendar/calendar-skeleton"
import { RecurringRuleModal } from "@/components/calendar/recurring-rule-modal"
import { srLatnLocale } from "@/lib/utils/fullcalendar-locale"
import {
  useBlackouts,
  useCreateSlot,
  useDeleteSlot,
  useMySlots,
  useUpdateSlot,
} from "@/lib/hooks/use-availability"
import { cn } from "@/lib/utils"
import { formatDate, formatDateTime } from "@/lib/utils/date"
import { toastApiError, toastSuccess, toastWarning } from "@/lib/utils/errors"
import type { BlackoutResponse, SlotResponse } from "@/types"

export interface AvailabilityCalendarProps {
  /** ASISTENT view: disable creating/updating/deleting slots. */
  readOnly?: boolean
  className?: string
}

/**
 * Vraća prvi blackout period (ako postoji) u koji upada ISO datetime
 * slota. Poređenje se radi u UTC datumu jer backend
 * (`search_service._available_slots_query`) takođe filtrira slotove
 * preko `func.date(slot_datetime)` u UTC sesiji — moramo da pratimo isti
 * pravac, inače "slot van blackout-a" lokalno može biti "u blackout-u"
 * na serveru.
 */
function findOverlappingBlackout(
  slotIso: string,
  blackouts: BlackoutResponse[]
): BlackoutResponse | null {
  const ymd = slotIso.slice(0, 10)
  return (
    blackouts.find((b) => b.start_date <= ymd && ymd <= b.end_date) ?? null
  )
}

export function AvailabilityCalendar({
  readOnly = false,
  className,
}: AvailabilityCalendarProps) {
  const calendarRef = useRef<FullCalendar | null>(null)
  const slotsQuery = useMySlots()
  const blackoutsQuery = useBlackouts()
  const createMutation = useCreateSlot()
  const updateMutation = useUpdateSlot()
  const deleteMutation = useDeleteSlot()

  const [modalOpen, setModalOpen] = useState(false)
  const [draftStart, setDraftStart] = useState<Date | null>(null)
  const [draftEnd, setDraftEnd] = useState<Date | null>(null)
  const [toDelete, setToDelete] = useState<SlotResponse | null>(null)
  // Personalizovana poruka izvinjenja za studente koji su zakazali termin
  // u slotu koji se otkazuje. Reset-uje se kad se dialog zatvori.
  const [cancelMessage, setCancelMessage] = useState("")

  const events: EventInput[] = useMemo(() => {
    const slots = slotsQuery.data ?? []
    const blackouts = blackoutsQuery.data ?? []
    const now = Date.now()

    const slotEvents: EventInput[] = slots.map((slot) => {
      const start = new Date(slot.slot_datetime)
      const end = new Date(start.getTime() + slot.duration_minutes * 60 * 1000)
      const isRecurring = Boolean(slot.recurring_rule)
      const isPast = end.getTime() < now
      const classes = [
        isRecurring ? "fc-event--recurring" : "fc-event--available",
      ]
      if (isPast) classes.push("fc-event--past")
      return {
        id: slot.id,
        title:
          slot.consultation_type === "ONLINE" ? "Online slot" : "Slot (uživo)",
        start,
        end,
        classNames: classes,
        editable: !readOnly && !isRecurring && !isPast,
        extendedProps: { slot, isRecurring, isPast },
      }
    })

    // Blackout periodi se renderuju kao FullCalendar background eventi —
    // ne mogu se selektovati ni klikati, ali pokrivaju ceo dan i jasno
    // pokazuju profesoru da su tu studenti slepi za njegove slotove.
    // `end_date` je INCLUSIVE u našoj backend semantici, a FullCalendar
    // tretira `end` kao EXCLUSIVE, pa dodajemo +1 dan na end.
    const blackoutEvents: EventInput[] = blackouts.map((b) => {
      const endExclusive = new Date(`${b.end_date}T00:00:00`)
      endExclusive.setDate(endExclusive.getDate() + 1)
      return {
        id: `blackout-${b.id}`,
        start: `${b.start_date}T00:00:00`,
        end: endExclusive.toISOString().slice(0, 10),
        display: "background",
        classNames: ["fc-event--blackout"],
        title: b.reason ? `Blackout: ${b.reason}` : "Blackout",
      }
    })

    return [...blackoutEvents, ...slotEvents]
  }, [slotsQuery.data, blackoutsQuery.data, readOnly])

  function renderEventContent(arg: EventContentArg) {
    const { isRecurring } = arg.event.extendedProps as { isRecurring?: boolean }
    return (
      <div className="flex h-full w-full items-center gap-1 px-1.5 py-1 leading-tight">
        {isRecurring && (
          <Repeat className="size-3 shrink-0" aria-hidden />
        )}
        <span className="truncate text-[0.7rem] font-medium">
          {arg.timeText}
        </span>
      </div>
    )
  }

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

      // Profesor možda nije svestan da slot upada u njegov vlastiti
      // blackout period — backend taj slot uredno krije od studenata
      // (`search_service._available_slots_query` filtrira preko
      // `overlaps_blackout`), pa bez ovog toasta deluje kao da je nešto
      // polomljeno: profesor vidi slot na svom kalendaru, student ga
      // ne vidi. Proveru radimo samo na single-slot kreiranju — za
      // rekurentne serije uradićemo opštu napomenu jer ne znamo sve
      // generisane datume na klijentu.
      const blackouts = blackoutsQuery.data ?? []
      if (!payload.recurring_rule && blackouts.length > 0) {
        const overlap = findOverlappingBlackout(payload.slot_datetime, blackouts)
        if (overlap) {
          toastWarning(
            "Slot upada u blackout period",
            `Studenti neće videti ovaj termin dok je blackout ${formatDate(
              overlap.start_date
            )} – ${formatDate(overlap.end_date)} aktivan. ` +
              `Obrišite blackout ako želite da slot bude vidljiv.`
          )
        }
      } else if (payload.recurring_rule && blackouts.length > 0) {
        toastWarning(
          "Proverite blackout periode",
          "Pojedini termini iz rekurentne serije možda upadaju u tvoj blackout period i neće biti vidljivi studentima."
        )
      }

      setModalOpen(false)
    } catch (err) {
      toastApiError(err, "Greška pri kreiranju slota.")
    }
  }

  async function handleConfirmDelete() {
    if (!toDelete) return
    const trimmed = cancelMessage.trim()
    try {
      const result = await deleteMutation.mutateAsync({
        id: toDelete.id,
        data: trimmed ? { cancellation_message: trimmed } : undefined,
      })
      if (result.cancelled_count > 0) {
        const word =
          result.cancelled_count === 1
            ? "termin je otkazan i student je obavešten"
            : `termina je otkazano i studenti su obavešteni`
        toastSuccess(`${result.cancelled_count} ${word}.`)
      } else {
        toastSuccess("Slot je obrisan.")
      }
      setToDelete(null)
      setCancelMessage("")
    } catch (err) {
      toastApiError(err, "Greška pri otkazivanju slota.")
    }
  }

  const isLoading = slotsQuery.isLoading
  const isMutating =
    createMutation.isPending || updateMutation.isPending

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CalendarLegend mode="professor" />
        {isMutating && (
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Čuvam izmene...
          </span>
        )}
      </div>

      {isLoading ? (
        <CalendarSkeleton />
      ) : (
        <div className="rounded-lg border border-border bg-card p-2 transition-colors">
          <FullCalendar
            ref={calendarRef}
            plugins={[
              dayGridPlugin,
              timeGridPlugin,
              interactionPlugin,
              listPlugin,
            ]}
            initialView="timeGridWeek"
            headerToolbar={{
              left: "prev,next today",
              center: "title",
              right: "timeGridWeek,dayGridMonth,timeGridDay,listWeek",
            }}
            firstDay={1}
            locale={srLatnLocale}
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
            eventContent={renderEventContent}
            buttonText={{
              today: "Danas",
              month: "Mesec",
              week: "Nedelja",
              day: "Dan",
              list: "Lista",
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
        onOpenChange={(open) => {
          if (!open) {
            setToDelete(null)
            setCancelMessage("")
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia>
              <Trash2 className="text-destructive" aria-hidden />
            </AlertDialogMedia>
            <AlertDialogTitle>Otkazati slot?</AlertDialogTitle>
            <AlertDialogDescription>
              {toDelete && (
                <>
                  Slot zakazan za{" "}
                  <strong className="font-semibold text-foreground">
                    {formatDateTime(toDelete.slot_datetime)}
                  </strong>
                  . Ako su studenti zakazali termin u ovom slotu, biće
                  obavešteni o otkazivanju (in-app, email i push).
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-1.5 px-1">
            <Label htmlFor="cancel-message" className="text-xs font-medium">
              Poruka izvinjenja (opciono)
            </Label>
            <Textarea
              id="cancel-message"
              value={cancelMessage}
              onChange={(e) => setCancelMessage(e.target.value)}
              placeholder="Izvinjavam se zbog neprijatnosti, javiću novi termin u toku dana…"
              maxLength={500}
              rows={3}
              disabled={deleteMutation.isPending}
              className="resize-none"
            />
            <p className="text-[0.7rem] text-muted-foreground">
              Ako ostavite prazno, šaljemo standardnu izvinjavajuću poruku.
              ({cancelMessage.length}/500)
            </p>
          </div>

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
                  Otkazujem...
                </>
              ) : (
                "Otkaži slot"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
