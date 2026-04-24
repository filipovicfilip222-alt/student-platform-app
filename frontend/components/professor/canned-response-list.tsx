/**
 * canned-response-list.tsx — Canned responses CRUD (settings → Canned tab).
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Lists templates, exposes create /
 * edit / delete. Backend endpoints are 404 until ROADMAP 3.7 ships —
 * the list falls back to EmptyState in that case.
 */

"use client"

import { useState } from "react"
import { Loader2, MessageSquareQuote, Pencil, Plus, Trash2 } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useCannedResponses,
  useDeleteCannedResponse,
} from "@/lib/hooks/use-canned-responses"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { CannedResponseResponse } from "@/types"

import { CannedResponseFormDialog } from "./canned-response-form-dialog"

export function CannedResponseList() {
  const listQuery = useCannedResponses()
  const deleteMutation = useDeleteCannedResponse()

  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<CannedResponseResponse | null>(null)
  const [toDelete, setToDelete] = useState<CannedResponseResponse | null>(null)

  function handleDelete() {
    if (!toDelete) return
    deleteMutation.mutate(toDelete.id, {
      onSuccess: () => {
        toastSuccess("Šablon obrisan.")
        setToDelete(null)
      },
      onError: (err) => toastApiError(err, "Greška pri brisanju šablona."),
    })
  }

  const items = listQuery.data ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h2 className="text-base font-semibold">Šabloni odgovora</h2>
          <p className="text-sm text-muted-foreground">
            Koriste se u dialogu za odbijanje termina i u chat porukama.
          </p>
        </div>
        <Button type="button" onClick={() => setCreateOpen(true)}>
          <Plus aria-hidden />
          Novi šablon
        </Button>
      </div>

      {listQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-24 w-full rounded-lg" />
        </div>
      ) : listQuery.isError ? (
        <EmptyState
          icon={MessageSquareQuote}
          title="Šabloni nisu dostupni"
          description="Endpoint je još u izradi (backend ROADMAP 3.7)."
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={MessageSquareQuote}
          title="Još nemate šablone"
          description="Napravite prvi šablon da ubrzate odgovore studentima."
        />
      ) : (
        <div className="space-y-2">
          {items.map((canned) => (
            <div
              key={canned.id}
              className="flex items-start gap-3 rounded-lg border bg-card p-3"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-medium text-sm text-foreground">
                  {canned.title}
                </p>
                <p className="whitespace-pre-line text-sm text-muted-foreground">
                  {canned.content}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Izmeni šablon"
                  onClick={() => setEditing(canned)}
                >
                  <Pencil aria-hidden />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Obriši šablon"
                  onClick={() => setToDelete(canned)}
                >
                  <Trash2 aria-hidden className="text-destructive" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <CannedResponseFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        canned={null}
      />
      <CannedResponseFormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        canned={editing}
      />

      <AlertDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Obrisati šablon?</AlertDialogTitle>
            <AlertDialogDescription>
              Ova akcija je nepovratna.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Odustani
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Brišem...
                </>
              ) : (
                "Obriši"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
