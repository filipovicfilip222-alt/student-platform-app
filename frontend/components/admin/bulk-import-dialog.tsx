/**
 * bulk-import-dialog.tsx — Two-step CSV bulk import for ADMIN → Korisnici.
 *
 * ROADMAP 4.7 + FRONTEND_STRUKTURA §3.6. Flow:
 *   Step 1 — select CSV → POST /admin/users/bulk-import/preview
 *            → show valid / invalid / duplicate counts + first 10 invalid rows
 *   Step 2 — confirm → POST /admin/users/bulk-import/confirm
 *            → toast with created / skipped / failed summary
 *
 * Uses a single `file` state reused between preview and confirm so the
 * admin cannot accidentally confirm a different file than was previewed
 * (backend re-parses but UX-wise we still reset between runs).
 */

"use client"

import { useState } from "react"
import { AlertTriangle, CheckCircle2, FileUp, Loader2 } from "lucide-react"

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
import {
  useBulkImportConfirm,
  useBulkImportPreview,
} from "@/lib/hooks/use-admin-users"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { BulkImportPreview } from "@/types"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function BulkImportDialog({ open, onOpenChange }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<BulkImportPreview | null>(null)

  const previewMutation = useBulkImportPreview()
  const confirmMutation = useBulkImportConfirm()

  function reset() {
    setFile(null)
    setPreview(null)
    previewMutation.reset()
    confirmMutation.reset()
  }

  async function handlePreview() {
    if (!file) return
    try {
      const data = await previewMutation.mutateAsync(file)
      setPreview(data)
    } catch (err) {
      toastApiError(err, "Nije moguće parsirati CSV.")
    }
  }

  async function handleConfirm() {
    if (!file) return
    try {
      const result = await confirmMutation.mutateAsync(file)
      toastSuccess(
        "Bulk import završen",
        `Kreirano ${result.created}, preskočeno ${result.skipped}, grešaka ${result.failed}.`
      )
      reset()
      onOpenChange(false)
    } catch (err) {
      toastApiError(err, "Bulk import nije uspeo.")
    }
  }

  function handleClose(nextOpen: boolean) {
    if (!nextOpen) reset()
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Bulk import korisnika</DialogTitle>
          <DialogDescription>
            Učitajte CSV sa kolonama{" "}
            <code className="rounded bg-muted px-1">email, first_name, last_name, role, faculty, password</code>
            . Prvo se prikazuje pregled, a tek potom se podaci unose.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="bulk-file">CSV fajl</Label>
            <input
              id="bulk-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setPreview(null)
              }}
              className="block w-full cursor-pointer rounded-md border border-input bg-background px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-2 file:py-1 file:text-xs file:font-medium hover:bg-muted/40"
            />
          </div>

          {preview && (
            <div className="grid gap-3 rounded-lg border border-border bg-muted/30 p-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <Stat
                  label="Valid"
                  value={preview.valid_rows.length}
                  accent="text-emerald-600"
                />
                <Stat
                  label="Nevalidni"
                  value={preview.invalid_rows.length}
                  accent="text-red-600"
                />
                <Stat
                  label="Duplikati"
                  value={preview.duplicates.length}
                  accent="text-amber-600"
                />
              </div>

              {preview.invalid_rows.length > 0 && (
                <div className="rounded-md bg-background p-2">
                  <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-red-700">
                    <AlertTriangle className="size-3.5" aria-hidden />
                    Prvih {Math.min(preview.invalid_rows.length, 10)} grešaka
                  </p>
                  <ul className="space-y-1 text-xs">
                    {preview.invalid_rows.slice(0, 10).map((r) => (
                      <li
                        key={`${r.row_number}-${r.email}`}
                        className="font-mono text-muted-foreground"
                      >
                        red {r.row_number} · {r.email} ·{" "}
                        <span className="text-red-600">
                          {r.errors.join(", ")}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={previewMutation.isPending || confirmMutation.isPending}
          >
            Otkaži
          </Button>
          {!preview ? (
            <Button
              onClick={() => void handlePreview()}
              disabled={!file || previewMutation.isPending}
            >
              {previewMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Parsing…
                </>
              ) : (
                <>
                  <FileUp aria-hidden />
                  Pregled
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={() => void handleConfirm()}
              disabled={
                confirmMutation.isPending || preview.valid_rows.length === 0
              }
            >
              {confirmMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Uvozim…
                </>
              ) : (
                <>
                  <CheckCircle2 aria-hidden />
                  Potvrdi uvoz ({preview.valid_rows.length})
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string
  value: number
  accent: string
}) {
  return (
    <div className="rounded-md bg-background p-2 ring-1 ring-border">
      <div className={`text-lg font-semibold ${accent}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
    </div>
  )
}
