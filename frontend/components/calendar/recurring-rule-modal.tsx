/**
 * recurring-rule-modal.tsx — Configuration dialog for creating availability slots.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Opened from <AvailabilityCalendar /> when
 * the professor drops a selection on the grid. The dialog collects:
 *   - slot_datetime (prefilled from the calendar selection, editable)
 *   - duration_minutes
 *   - consultation_type (UZIVO / ONLINE)
 *   - max_students (1 for 1-on-1, >1 for group)
 *   - online_link (visible only when ONLINE)
 *   - optional recurring_rule (WEEKLY/MONTHLY, by_weekday, count OR until)
 *
 * Backend: ROADMAP 3.8 will expand recurring rules into N concrete slots
 * on the server side. Until that ships, the frontend still sends the
 * `recurring_rule` JSONB — the backend already accepts the field.
 */

"use client"

import { useEffect, useMemo } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Loader2, Repeat, Video } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Checkbox } from "@/components/ui/checkbox"
import type { ConsultationType, SlotCreateRequest } from "@/types"

const WEEKDAYS: Array<{ value: number; label: string }> = [
  { value: 1, label: "Pon" },
  { value: 2, label: "Uto" },
  { value: 3, label: "Sre" },
  { value: 4, label: "Čet" },
  { value: 5, label: "Pet" },
  { value: 6, label: "Sub" },
  { value: 0, label: "Ned" },
]

const schema = z
  .object({
    slot_datetime: z.string().min(1, "Datum i vreme su obavezni."),
    duration_minutes: z.coerce
      .number()
      .int()
      .min(10, "Minimum 10 minuta.")
      .max(240, "Maksimum 240 minuta."),
    consultation_type: z.enum(["UZIVO", "ONLINE"]),
    online_link: z.string().url("Mora biti validan URL.").or(z.literal("")).optional(),
    max_students: z.coerce
      .number()
      .int()
      .min(1, "Minimum 1.")
      .max(30, "Maksimum 30."),

    is_recurring: z.boolean(),
    freq: z.enum(["WEEKLY", "MONTHLY"]).optional(),
    by_weekday: z.array(z.number().int().min(0).max(6)).optional(),
    ends_mode: z.enum(["count", "until"]).optional(),
    count: z.coerce.number().int().min(1).max(52).optional(),
    until: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.consultation_type === "ONLINE" && !val.online_link) {
      ctx.addIssue({
        path: ["online_link"],
        code: z.ZodIssueCode.custom,
        message: "Online link je obavezan za ONLINE termin.",
      })
    }
    if (val.is_recurring) {
      if (!val.freq) {
        ctx.addIssue({
          path: ["freq"],
          code: z.ZodIssueCode.custom,
          message: "Izaberite učestalost.",
        })
      }
      if (val.freq === "WEEKLY" && (!val.by_weekday || val.by_weekday.length === 0)) {
        ctx.addIssue({
          path: ["by_weekday"],
          code: z.ZodIssueCode.custom,
          message: "Izaberite bar jedan dan u nedelji.",
        })
      }
      if (val.ends_mode === "count" && (!val.count || val.count < 1)) {
        ctx.addIssue({
          path: ["count"],
          code: z.ZodIssueCode.custom,
          message: "Broj ponavljanja mora biti 1 ili više.",
        })
      }
      if (val.ends_mode === "until" && !val.until) {
        ctx.addIssue({
          path: ["until"],
          code: z.ZodIssueCode.custom,
          message: "Izaberite krajnji datum.",
        })
      }
    }
  })

type FormValues = z.infer<typeof schema>

export interface RecurringRuleModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Prefill — datetime comes from the calendar drag/select. */
  defaultStart: Date | null
  defaultEnd: Date | null
  /** Called with the normalized SlotCreateRequest payload. */
  onSubmit: (payload: SlotCreateRequest) => Promise<void> | void
  isSubmitting?: boolean
}

function toLocalInput(date: Date): string {
  // datetime-local needs "YYYY-MM-DDTHH:mm" in the user's local time.
  const pad = (n: number) => String(n).padStart(2, "0")
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

function toIsoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function RecurringRuleModal({
  open,
  onOpenChange,
  defaultStart,
  defaultEnd,
  onSubmit,
  isSubmitting = false,
}: RecurringRuleModalProps) {
  const defaults: FormValues = useMemo(() => {
    const start = defaultStart ?? new Date()
    const durationMs =
      defaultEnd && defaultEnd > start ? defaultEnd.getTime() - start.getTime() : 30 * 60 * 1000
    const durationMinutes = Math.max(10, Math.round(durationMs / 60000))
    return {
      slot_datetime: toLocalInput(start),
      duration_minutes: durationMinutes,
      consultation_type: "UZIVO",
      online_link: "",
      max_students: 1,
      is_recurring: false,
      freq: "WEEKLY",
      by_weekday: [start.getDay()],
      ends_mode: "count",
      count: 8,
      until: "",
    }
  }, [defaultStart, defaultEnd])

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  })

  useEffect(() => {
    if (open) form.reset(defaults)
  }, [open, defaults, form])

  const consultationType = form.watch("consultation_type") as ConsultationType
  const isRecurring = form.watch("is_recurring")
  const freq = form.watch("freq")
  const endsMode = form.watch("ends_mode")

  async function handleSubmit(values: FormValues) {
    const slotIso = new Date(values.slot_datetime).toISOString()
    const payload: SlotCreateRequest = {
      slot_datetime: slotIso,
      duration_minutes: values.duration_minutes,
      consultation_type: values.consultation_type,
      max_students: values.max_students,
      online_link:
        values.consultation_type === "ONLINE" ? values.online_link || null : null,
      is_available: true,
    }

    if (values.is_recurring && values.freq) {
      payload.recurring_rule = {
        freq: values.freq,
        ...(values.freq === "WEEKLY" && values.by_weekday
          ? { by_weekday: values.by_weekday }
          : {}),
        ...(values.ends_mode === "count"
          ? { count: values.count }
          : values.ends_mode === "until" && values.until
            ? { until: values.until }
            : {}),
      }
      payload.valid_from = toIsoDate(new Date(values.slot_datetime))
      if (values.ends_mode === "until" && values.until) {
        payload.valid_until = values.until
      }
    }

    await onSubmit(payload)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Novi slot za konsultacije</DialogTitle>
          <DialogDescription>
            Definišite pojedinačan termin ili rekurentnu seriju (npr. svakog utorka).
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="slot_datetime"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Datum i vreme početka</FormLabel>
                    <FormControl>
                      <Input
                        type="datetime-local"
                        disabled={isSubmitting}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="duration_minutes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Trajanje (min)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={10}
                        max={240}
                        step={5}
                        disabled={isSubmitting}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="consultation_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tip konsultacija</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      disabled={isSubmitting}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="UZIVO">Uživo</SelectItem>
                        <SelectItem value="ONLINE">
                          <span className="inline-flex items-center gap-1.5">
                            <Video className="size-3.5" aria-hidden />
                            Online
                          </span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="max_students"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Maks. studenata</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={1}
                        max={30}
                        disabled={isSubmitting}
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>1 = 1-na-1, više = grupno.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {consultationType === "ONLINE" && (
              <FormField
                control={form.control}
                name="online_link"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Online link</FormLabel>
                    <FormControl>
                      <Input
                        type="url"
                        placeholder="https://meet.google.com/..."
                        disabled={isSubmitting}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <div className="rounded-lg border border-border p-3">
              <FormField
                control={form.control}
                name="is_recurring"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between space-y-0">
                    <div className="space-y-0.5">
                      <FormLabel className="flex items-center gap-1.5">
                        <Repeat className="size-3.5" aria-hidden />
                        Rekurentna serija
                      </FormLabel>
                      <FormDescription className="text-xs">
                        Ponavljaj ovaj slot po pravilu (npr. svake nedelje).
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                        disabled={isSubmitting}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              {isRecurring && (
                <div className="mt-3 space-y-3 border-t border-border pt-3">
                  <FormField
                    control={form.control}
                    name="freq"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Učestalost</FormLabel>
                        <Select
                          value={field.value}
                          onValueChange={field.onChange}
                          disabled={isSubmitting}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="WEEKLY">Nedeljno</SelectItem>
                            <SelectItem value="MONTHLY">Mesečno</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {freq === "WEEKLY" && (
                    <FormField
                      control={form.control}
                      name="by_weekday"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Dani u nedelji</FormLabel>
                          <div className="flex flex-wrap gap-2">
                            {WEEKDAYS.map((day) => {
                              const current = field.value ?? []
                              const checked = current.includes(day.value)
                              return (
                                <label
                                  key={day.value}
                                  className="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs"
                                >
                                  <Checkbox
                                    checked={checked}
                                    disabled={isSubmitting}
                                    onCheckedChange={(v) => {
                                      const next = new Set(current)
                                      if (v) next.add(day.value)
                                      else next.delete(day.value)
                                      field.onChange(
                                        Array.from(next).sort((a, b) => a - b)
                                      )
                                    }}
                                  />
                                  {day.label}
                                </label>
                              )
                            })}
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <FormField
                    control={form.control}
                    name="ends_mode"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Završetak serije</FormLabel>
                        <Select
                          value={field.value}
                          onValueChange={field.onChange}
                          disabled={isSubmitting}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="count">
                              Nakon broja ponavljanja
                            </SelectItem>
                            <SelectItem value="until">
                              Do određenog datuma
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {endsMode === "count" ? (
                    <FormField
                      control={form.control}
                      name="count"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Broj ponavljanja</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={1}
                              max={52}
                              disabled={isSubmitting}
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  ) : (
                    <FormField
                      control={form.control}
                      name="until"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Poslednji datum</FormLabel>
                          <FormControl>
                            <Input
                              type="date"
                              disabled={isSubmitting}
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Odustani
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
                Sačuvaj slot
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
