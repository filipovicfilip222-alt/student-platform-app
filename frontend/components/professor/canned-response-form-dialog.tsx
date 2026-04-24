/**
 * canned-response-form-dialog.tsx — Create or edit a canned response.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Shared by the list row (edit) and
 * the "Novi šablon" button (create).
 */

"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
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
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  useCreateCannedResponse,
  useUpdateCannedResponse,
} from "@/lib/hooks/use-canned-responses"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { CannedResponseResponse } from "@/types"

const schema = z.object({
  title: z
    .string()
    .trim()
    .min(3, "Naziv mora imati najmanje 3 karaktera.")
    .max(100, "Naziv ne sme biti duži od 100 karaktera."),
  content: z
    .string()
    .trim()
    .min(10, "Tekst mora imati najmanje 10 karaktera.")
    .max(2000, "Tekst ne sme biti duži od 2000 karaktera."),
})

type FormValues = z.infer<typeof schema>

export interface CannedResponseFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  canned: CannedResponseResponse | null
}

export function CannedResponseFormDialog({
  open,
  onOpenChange,
  canned,
}: CannedResponseFormDialogProps) {
  const createMutation = useCreateCannedResponse()
  const updateMutation = useUpdateCannedResponse()
  const isEdit = canned !== null
  const isPending = createMutation.isPending || updateMutation.isPending

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", content: "" },
  })

  useEffect(() => {
    if (!open) return
    form.reset({
      title: canned?.title ?? "",
      content: canned?.content ?? "",
    })
  }, [open, canned, form])

  function handleSubmit(values: FormValues) {
    if (isEdit && canned) {
      updateMutation.mutate(
        { id: canned.id, data: values },
        {
          onSuccess: () => {
            toastSuccess("Šablon sačuvan.")
            onOpenChange(false)
          },
          onError: (err) => toastApiError(err, "Greška pri izmeni šablona."),
        }
      )
      return
    }
    createMutation.mutate(values, {
      onSuccess: () => {
        toastSuccess("Šablon kreiran.")
        onOpenChange(false)
      },
      onError: (err) => toastApiError(err, "Greška pri kreiranju šablona."),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Izmeni šablon" : "Novi šablon"}
          </DialogTitle>
          <DialogDescription>
            Šabloni ubrzavaju odbijanje termina i odgovore na chat poruke.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
            noValidate
          >
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Naziv</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Prebukiran — predlog drugog termina"
                      disabled={isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="content"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sadržaj</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={6}
                      placeholder="Poštovani, trenutno sam prebukiran za ovaj termin..."
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
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="animate-spin" aria-hidden />}
                {isEdit ? "Sačuvaj" : "Dodaj šablon"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
