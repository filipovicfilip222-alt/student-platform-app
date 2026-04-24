/**
 * faq-form-dialog.tsx — Create or edit a single FAQ entry.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Shared dialog for Create + Edit —
 * parent passes an optional `faq` prop; when null the form acts as
 * "Create new". `sort_order` is not editable here: reordering is done
 * via up/down buttons in the list view.
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
import { useCreateFaq, useUpdateFaq } from "@/lib/hooks/use-faq"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { FaqResponse } from "@/types"

const schema = z.object({
  question: z
    .string()
    .trim()
    .min(5, "Pitanje mora imati najmanje 5 karaktera.")
    .max(300, "Pitanje ne sme biti duže od 300 karaktera."),
  answer: z
    .string()
    .trim()
    .min(5, "Odgovor mora imati najmanje 5 karaktera.")
    .max(2000, "Odgovor ne sme biti duži od 2000 karaktera."),
})

type FormValues = z.infer<typeof schema>

export interface FaqFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  faq: FaqResponse | null
  nextSortOrder: number
}

export function FaqFormDialog({
  open,
  onOpenChange,
  faq,
  nextSortOrder,
}: FaqFormDialogProps) {
  const createMutation = useCreateFaq()
  const updateMutation = useUpdateFaq()
  const isEdit = faq !== null
  const isPending = createMutation.isPending || updateMutation.isPending

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { question: "", answer: "" },
  })

  useEffect(() => {
    if (!open) return
    form.reset({
      question: faq?.question ?? "",
      answer: faq?.answer ?? "",
    })
  }, [open, faq, form])

  function handleSubmit(values: FormValues) {
    if (isEdit && faq) {
      updateMutation.mutate(
        { id: faq.id, data: values },
        {
          onSuccess: () => {
            toastSuccess("FAQ izmenjen.")
            onOpenChange(false)
          },
          onError: (err) => toastApiError(err, "Greška pri izmeni FAQ-a."),
        }
      )
      return
    }
    createMutation.mutate(
      { ...values, sort_order: nextSortOrder },
      {
        onSuccess: () => {
          toastSuccess("FAQ dodat.")
          onOpenChange(false)
        },
        onError: (err) => toastApiError(err, "Greška pri kreiranju FAQ-a."),
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Izmeni FAQ" : "Novi FAQ"}</DialogTitle>
          <DialogDescription>
            Često postavljana pitanja studenata i vaši odgovori.
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
              name="question"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Pitanje</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Kako da se pripremim za ispit?"
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
              name="answer"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Odgovor</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={6}
                      placeholder="Preporučujem da krenete od prezentacija sa predavanja..."
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
                {isEdit ? "Sačuvaj" : "Dodaj FAQ"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
