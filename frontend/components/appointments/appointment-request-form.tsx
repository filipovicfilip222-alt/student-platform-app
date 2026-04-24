/**
 * appointment-request-form.tsx — Dialog that a student opens after
 * clicking an available slot on the BookingCalendar.
 *
 * ROADMAP 3.5 / Faza 3.5.
 *
 * Flow:
 *   1. Create the appointment (POST /students/appointments).
 *   2. If the student staged files, upload them sequentially to
 *      /appointments/{id}/files. We keep this sequential (not
 *      Promise.all) so a single failure doesn't hide the ordering of
 *      successes in the toast.
 *   3. Close the dialog + show a success toast, ending on /my-appointments
 *      when `onSubmitted` is not supplied by the parent.
 */

"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Loader2, Video } from "lucide-react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { FileUploadZone } from "./file-upload-zone"
import { appointmentsApi } from "@/lib/api/appointments"
import { useCreateAppointment } from "@/lib/hooks/use-appointments"
import { ROUTES } from "@/lib/constants/routes"
import {
  TOPIC_CATEGORIES,
  TOPIC_CATEGORY_LABELS,
} from "@/lib/constants/topic-categories"
import { formatDateTime } from "@/lib/utils/date"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AppointmentResponse, AvailableSlotResponse, TopicCategory } from "@/types"

const schema = z.object({
  topic_category: z.enum(TOPIC_CATEGORIES as unknown as [string, ...string[]]),
  description: z
    .string()
    .trim()
    .min(10, "Opis mora imati najmanje 10 karaktera.")
    .max(1000, "Opis ne sme biti duži od 1000 karaktera."),
})

type FormValues = z.infer<typeof schema>

export interface AppointmentRequestFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  slot: AvailableSlotResponse | null
  onSubmitted?: (appointment: AppointmentResponse) => void
}

export function AppointmentRequestForm({
  open,
  onOpenChange,
  slot,
  onSubmitted,
}: AppointmentRequestFormProps) {
  const router = useRouter()
  const createMutation = useCreateAppointment()
  const [stagedFiles, setStagedFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      topic_category: "OSTALO",
      description: "",
    },
  })

  useEffect(() => {
    if (open) {
      form.reset({ topic_category: "OSTALO", description: "" })
      setStagedFiles([])
    }
  }, [open, form])

  if (!slot) return null

  const isSubmitting = createMutation.isPending || uploading

  async function onSubmit(values: FormValues) {
    if (!slot) return
    try {
      const appointment = await createMutation.mutateAsync({
        slot_id: slot.id,
        topic_category: values.topic_category as TopicCategory,
        description: values.description,
      })

      if (stagedFiles.length > 0) {
        setUploading(true)
        let uploadedCount = 0
        for (const file of stagedFiles) {
          try {
            await appointmentsApi.uploadFile(appointment.id, file)
            uploadedCount += 1
          } catch (err) {
            toastApiError(err, `Greška pri uploadu fajla ${file.name}.`)
          }
        }
        setUploading(false)
        if (uploadedCount > 0) {
          toastSuccess(
            `Termin kreiran. Uploadovano fajlova: ${uploadedCount}/${stagedFiles.length}.`
          )
        } else {
          toastSuccess("Termin je kreiran, ali nijedan fajl nije uploadovan.")
        }
      } else {
        toastSuccess("Termin je uspešno zakazan.", "Čeka na odobrenje profesora.")
      }

      onOpenChange(false)
      if (onSubmitted) {
        onSubmitted(appointment)
      } else {
        router.push(ROUTES.myAppointments)
      }
    } catch (err) {
      setUploading(false)
      toastApiError(err, "Greška pri zakazivanju termina.")
    }
  }

  const isOnline = slot.consultation_type === "ONLINE"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Zahtev za termin</DialogTitle>
          <DialogDescription>
            {formatDateTime(slot.slot_datetime)} · {slot.duration_minutes} min ·{" "}
            {isOnline ? (
              <span className="inline-flex items-center gap-1">
                <Video className="size-3.5" aria-hidden />
                Online
              </span>
            ) : (
              "Uživo"
            )}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="topic_category"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Kategorija teme</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={isSubmitting}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Izaberite kategoriju" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {TOPIC_CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {TOPIC_CATEGORY_LABELS[c]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Opis pitanja</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={5}
                      placeholder="Ukratko opišite šta želite da obradite na konsultacijama..."
                      disabled={isSubmitting}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Minimalno 10, maksimalno 1000 karaktera.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-2">
              <FormLabel asChild>
                <p className="text-sm font-medium">Prilozi (opciono)</p>
              </FormLabel>
              <FileUploadZone
                files={stagedFiles}
                onChange={setStagedFiles}
                disabled={isSubmitting}
              />
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
                {isSubmitting && (
                  <Loader2 className="animate-spin" aria-hidden />
                )}
                {uploading ? "Uploadujem fajlove..." : "Zakaži termin"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
