/**
 * faq-list.tsx — FAQ management UI (settings → FAQ tab).
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Lists the professor's FAQ entries
 * sorted by `sort_order`, exposes create/edit/delete dialogs and
 * up/down re-ordering (by swapping `sort_order` with the neighbour).
 *
 * Until the backend endpoints ship (ROADMAP 3.7), useFaq() will 404 and
 * the list renders as EmptyState.
 */

"use client"

import { useMemo, useState } from "react"
import { Plus, HelpCircle, Loader2 } from "lucide-react"

import { EmptyState } from "@/components/shared/empty-state"
import { Button } from "@/components/ui/button"
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  useDeleteFaq,
  useFaq,
  useUpdateFaq,
} from "@/lib/hooks/use-faq"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { FaqResponse } from "@/types"

import { FaqFormDialog } from "./faq-form-dialog"
import { FaqItemRow } from "./faq-item-row"

export function FaqList() {
  const faqQuery = useFaq()
  const updateMutation = useUpdateFaq()
  const deleteMutation = useDeleteFaq()

  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<FaqResponse | null>(null)
  const [toDelete, setToDelete] = useState<FaqResponse | null>(null)

  const sorted = useMemo(() => {
    return [...(faqQuery.data ?? [])].sort(
      (a, b) => a.sort_order - b.sort_order
    )
  }, [faqQuery.data])

  const nextSortOrder =
    sorted.length > 0 ? sorted[sorted.length - 1].sort_order + 1 : 1

  function swapSortOrders(a: FaqResponse, b: FaqResponse) {
    updateMutation.mutate(
      { id: a.id, data: { sort_order: b.sort_order } },
      {
        onError: (err) => toastApiError(err, "Greška pri reorderu."),
      }
    )
    updateMutation.mutate(
      { id: b.id, data: { sort_order: a.sort_order } },
      {
        onError: (err) => toastApiError(err, "Greška pri reorderu."),
      }
    )
  }

  function handleMoveUp(index: number) {
    if (index <= 0) return
    swapSortOrders(sorted[index], sorted[index - 1])
  }

  function handleMoveDown(index: number) {
    if (index >= sorted.length - 1) return
    swapSortOrders(sorted[index], sorted[index + 1])
  }

  function handleDelete() {
    if (!toDelete) return
    deleteMutation.mutate(toDelete.id, {
      onSuccess: () => {
        toastSuccess("FAQ obrisan.")
        setToDelete(null)
      },
      onError: (err) => toastApiError(err, "Greška pri brisanju FAQ-a."),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h2 className="text-base font-semibold">Često postavljana pitanja</h2>
          <p className="text-sm text-muted-foreground">
            Pitanja i odgovori su javno vidljivi na vašem profilu.
          </p>
        </div>
        <Button type="button" onClick={() => setCreateOpen(true)}>
          <Plus aria-hidden />
          Novi FAQ
        </Button>
      </div>

      {faqQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
        </div>
      ) : faqQuery.isError ? (
        <EmptyState
          icon={HelpCircle}
          title="FAQ lista nije dostupna"
          description="Endpoint je još u izradi (backend ROADMAP 3.7)."
        />
      ) : sorted.length === 0 ? (
        <EmptyState
          icon={HelpCircle}
          title="Još nemate FAQ stavki"
          description="Dodajte prvo pitanje da studenti dobiju brže odgovore."
        />
      ) : (
        <div className="space-y-2">
          {sorted.map((faq, i) => (
            <FaqItemRow
              key={faq.id}
              faq={faq}
              isFirst={i === 0}
              isLast={i === sorted.length - 1}
              disabled={updateMutation.isPending || deleteMutation.isPending}
              onMoveUp={() => handleMoveUp(i)}
              onMoveDown={() => handleMoveDown(i)}
              onEdit={() => setEditing(faq)}
              onDelete={() => setToDelete(faq)}
            />
          ))}
        </div>
      )}

      <FaqFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        faq={null}
        nextSortOrder={nextSortOrder}
      />
      <FaqFormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        faq={editing}
        nextSortOrder={nextSortOrder}
      />

      <AlertDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Obrisati FAQ?</AlertDialogTitle>
            <AlertDialogDescription>
              Ova akcija je nepovratna. Pitanje i odgovor će biti uklonjeni
              sa vašeg profila.
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
