/**
 * request-reject-dialog.tsx — Reject an appointment request with a reason.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). The professor must supply a textual
 * reason; a dropdown of canned responses populates the textarea with
 * their content (professor can still edit before submit).
 */

"use client"

import { useEffect, useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Loader2 } from "lucide-react"

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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useCannedResponses } from "@/lib/hooks/use-canned-responses"
import { formatDateTime } from "@/lib/utils/date"
import type { AppointmentResponse } from "@/types"

const schema = z.object({
  reason: z
    .string()
    .trim()
    .min(10, "Razlog mora imati najmanje 10 karaktera.")
    .max(1000, "Razlog ne sme biti duži od 1000 karaktera."),
})

type FormValues = z.infer<typeof schema>

export interface RequestRejectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment: AppointmentResponse | null
  onConfirm: (reason: string) => void
  isPending: boolean
  /** Optional copy overrides — used when this dialog is reused for the
   *  "professor cancels approved appointment" flow on /appointments/[id]. */
  title?: string
  description?: string
  confirmLabel?: string
  reasonLabel?: string
}

const NO_CANNED = "__none__"

export function RequestRejectDialog({
  open,
  onOpenChange,
  appointment,
  onConfirm,
  isPending,
  title = "Odbij zahtev",
  description,
  confirmLabel = "Odbij termin",
  reasonLabel = "Razlog odbijanja",
}: RequestRejectDialogProps) {
  const cannedQuery = useCannedResponses()
  const [selectedCanned, setSelectedCanned] = useState<string>(NO_CANNED)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { reason: "" },
  })

  useEffect(() => {
    if (open) {
      form.reset({ reason: "" })
      setSelectedCanned(NO_CANNED)
    }
  }, [open, form])

  if (!appointment) return null

  function applyCanned(id: string) {
    setSelectedCanned(id)
    if (id === NO_CANNED) return
    const canned = cannedQuery.data?.find((c) => c.id === id)
    if (canned) form.setValue("reason", canned.content, { shouldValidate: true })
  }

  function handleSubmit(values: FormValues) {
    onConfirm(values.reason)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {description ? (
              <>
                {description}{" "}
                <span className="block pt-1 text-xs">
                  Termin:{" "}
                  <strong className="font-semibold text-foreground">
                    {formatDateTime(appointment.slot_datetime)}
                  </strong>
                </span>
              </>
            ) : (
              <>
                Termin zakazan za{" "}
                <strong className="font-semibold text-foreground">
                  {formatDateTime(appointment.slot_datetime)}
                </strong>
                . Student dobija email sa vašim obrazloženjem.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <label
                htmlFor="canned-select"
                className="text-sm font-medium leading-none"
              >
                Šablon (opciono)
              </label>
              <Select
                value={selectedCanned}
                onValueChange={applyCanned}
                disabled={isPending || cannedQuery.isLoading}
              >
                <SelectTrigger id="canned-select" className="w-full">
                  <SelectValue
                    placeholder={
                      cannedQuery.isLoading
                        ? "Učitavam šablone..."
                        : "Bez šablona"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_CANNED}>Bez šablona</SelectItem>
                  {(cannedQuery.data ?? []).map((canned) => (
                    <SelectItem key={canned.id} value={canned.id}>
                      {canned.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Izbor šablona popunjava tekst ispod — možete ga potom
                urediti pre slanja.
              </p>
            </div>

            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{reasonLabel}</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={5}
                      placeholder="Obrazložite zašto termin ne može biti odobren..."
                      disabled={isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                Odustani
              </Button>
              <Button type="submit" variant="destructive" disabled={isPending}>
                {isPending && <Loader2 className="animate-spin" aria-hidden />}
                {confirmLabel}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
