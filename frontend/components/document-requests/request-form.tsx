/**
 * request-form.tsx — Student submits a new document request.
 *
 * ROADMAP 4.8. Student picks a DocumentType + optional free-text note.
 * Submits via POST /document-requests.
 */

"use client"

import { useState } from "react"
import { Loader2, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import {
  DOCUMENT_TYPES,
  documentTypeLabel,
} from "@/lib/constants/document-types"
import { useCreateDocumentRequest } from "@/lib/hooks/use-document-requests"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { DocumentType } from "@/types"

export function RequestForm() {
  const [type, setType] = useState<DocumentType>("POTVRDA_STATUSA")
  const [note, setNote] = useState("")
  const mutation = useCreateDocumentRequest()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await mutation.mutateAsync({
        document_type: type,
        note: note.trim() || null,
      })
      toastSuccess(
        "Zahtev podnet",
        `Bićete obavešteni kada administracija obradi zahtev.`
      )
      setNote("")
    } catch (err) {
      toastApiError(err, "Zahtev nije uspeo.")
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-3 rounded-lg border border-border bg-background p-4"
    >
      <h3 className="text-sm font-semibold">Novi zahtev</h3>

      <div className="grid gap-1.5">
        <Label htmlFor="doc-type">Tip dokumenta</Label>
        <Select
          value={type}
          onValueChange={(v) => setType(v as DocumentType)}
        >
          <SelectTrigger id="doc-type" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DOCUMENT_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {documentTypeLabel(t)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="doc-note">Napomena (opciono)</Label>
        <Textarea
          id="doc-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          placeholder="Dodatne informacije za administraciju…"
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Šaljem…
            </>
          ) : (
            <>
              <Plus aria-hidden />
              Podnesi zahtev
            </>
          )}
        </Button>
      </div>
    </form>
  )
}
