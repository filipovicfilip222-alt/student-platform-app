/**
 * approve-dialog.tsx — Admin approves a document request.
 *
 * ROADMAP 4.8. Requires a pickup_date (ISO date) + optional admin note.
 * Success toast lives in the parent page so this component stays focused
 * on form validation.
 */

"use client"

import { useEffect, useState } from "react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { documentTypeLabel } from "@/lib/constants/document-types"
import { useApproveDocumentRequest } from "@/lib/hooks/use-document-requests"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { DocumentRequestResponse } from "@/types"

interface Props {
  request: DocumentRequestResponse | null
  onOpenChange: (open: boolean) => void
}

export function ApproveDialog({ request, onOpenChange }: Props) {
  const [pickupDate, setPickupDate] = useState("")
  const [note, setNote] = useState("")
  const mutation = useApproveDocumentRequest()

  useEffect(() => {
    if (request) {
      setPickupDate("")
      setNote("")
    }
  }, [request])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!request || !pickupDate) return
    try {
      await mutation.mutateAsync({
        id: request.id,
        data: {
          pickup_date: pickupDate,
          admin_note: note.trim() || null,
        },
      })
      toastSuccess(
        "Zahtev odobren",
        `Student će biti obavešten. Datum preuzimanja: ${pickupDate}.`
      )
      onOpenChange(false)
    } catch (err) {
      toastApiError(err, "Odobravanje nije uspelo.")
    }
  }

  return (
    <Dialog open={Boolean(request)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Odobri zahtev za dokument</DialogTitle>
          <DialogDescription>
            {request && (
              <>
                Tip:{" "}
                <strong>{documentTypeLabel(request.document_type)}</strong>.
                Potvrdite datum kada će student moći da preuzme dokument.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="approve-date">Datum preuzimanja</Label>
            <Input
              id="approve-date"
              type="date"
              value={pickupDate}
              onChange={(e) => setPickupDate(e.target.value)}
              required
              min={new Date().toISOString().slice(0, 10)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="approve-note">Napomena (opciono)</Label>
            <Textarea
              id="approve-note"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Npr. Preuzeti u kancelariji 205 uz studentsku legitimaciju."
              maxLength={500}
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
            <Button type="submit" disabled={mutation.isPending || !pickupDate}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Odobravam…
                </>
              ) : (
                "Odobri"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
