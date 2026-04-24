/**
 * reject-dialog.tsx — Admin rejects a document request.
 *
 * ROADMAP 4.8. Rejection requires a written admin_note (min 10 chars)
 * which the student sees as the rejection reason.
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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { documentTypeLabel } from "@/lib/constants/document-types"
import { useRejectDocumentRequest } from "@/lib/hooks/use-document-requests"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { DocumentRequestResponse } from "@/types"

interface Props {
  request: DocumentRequestResponse | null
  onOpenChange: (open: boolean) => void
}

export function RejectDialog({ request, onOpenChange }: Props) {
  const [note, setNote] = useState("")
  const mutation = useRejectDocumentRequest()

  useEffect(() => {
    if (request) setNote("")
  }, [request])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!request || note.trim().length < 10) return
    try {
      await mutation.mutateAsync({
        id: request.id,
        data: { admin_note: note.trim() },
      })
      toastSuccess("Zahtev odbijen", "Student će videti razlog u svojoj listi zahteva.")
      onOpenChange(false)
    } catch (err) {
      toastApiError(err, "Odbijanje nije uspelo.")
    }
  }

  return (
    <Dialog open={Boolean(request)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Odbij zahtev za dokument</DialogTitle>
          <DialogDescription>
            {request && (
              <>
                Tip:{" "}
                <strong>{documentTypeLabel(request.document_type)}</strong>.
                Unesite razlog odbijanja (minimum 10 karaktera).
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="reject-reason">Razlog</Label>
            <Textarea
              id="reject-reason"
              rows={5}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              required
              minLength={10}
              placeholder="Npr. Dokument nije dostupan za studente sa prezentovanim statusom."
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
              variant="destructive"
              disabled={mutation.isPending || note.trim().length < 10}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Odbijam…
                </>
              ) : (
                "Odbij"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
