/**
 * request-delegate-dialog.tsx — Delegate an appointment request to an assistant.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). PROFESOR-only: only a professor can
 * delegate; the assistant then sees the request in their own inbox and
 * may approve / reject it (RBAC guarded on the backend).
 *
 * The assistant list comes from `professorsApi.listAssistants()` — a
 * TODO backend endpoint (ROADMAP 3.7). While it 404s, the dialog shows
 * an empty state.
 */

"use client"

import { useEffect, useState } from "react"
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/empty-state"
import { useMyAssistants } from "@/lib/hooks/use-my-profile"
import { formatDateTime } from "@/lib/utils/date"
import { Users } from "lucide-react"
import type { AppointmentResponse, Uuid } from "@/types"

export interface RequestDelegateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  appointment: AppointmentResponse | null
  onConfirm: (assistantId: Uuid) => void
  isPending: boolean
}

export function RequestDelegateDialog({
  open,
  onOpenChange,
  appointment,
  onConfirm,
  isPending,
}: RequestDelegateDialogProps) {
  const assistantsQuery = useMyAssistants()
  const [selected, setSelected] = useState<Uuid | undefined>(undefined)

  useEffect(() => {
    if (open) setSelected(undefined)
  }, [open])

  if (!appointment) return null

  const assistants = assistantsQuery.data ?? []
  const noAssistants = !assistantsQuery.isLoading && assistants.length === 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delegiraj zahtev</DialogTitle>
          <DialogDescription>
            Termin zakazan za{" "}
            <strong className="font-semibold text-foreground">
              {formatDateTime(appointment.slot_datetime)}
            </strong>
            . Izabrani asistent će moći da odobri ili odbije zahtev.
          </DialogDescription>
        </DialogHeader>

        {noAssistants ? (
          <EmptyState
            icon={Users}
            title="Nemate asistenta za delegiranje"
            description={
              assistantsQuery.isError
                ? "Lista asistenata trenutno nije dostupna (backend u izradi)."
                : "Dodajte asistente kroz administraciju predmeta i pokušajte ponovo."
            }
          />
        ) : (
          <div className="space-y-1.5">
            <label
              htmlFor="assistant-select"
              className="text-sm font-medium leading-none"
            >
              Asistent
            </label>
            <Select
              value={selected ?? undefined}
              onValueChange={(v) => setSelected(v)}
              disabled={isPending || assistantsQuery.isLoading}
            >
              <SelectTrigger id="assistant-select" className="w-full">
                <SelectValue
                  placeholder={
                    assistantsQuery.isLoading
                      ? "Učitavam asistente..."
                      : "Izaberite asistenta"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {assistants.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.full_name}
                    {a.subjects.length > 0 && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({a.subjects.join(", ")})
                      </span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Odustani
          </Button>
          <Button
            type="button"
            onClick={() => selected && onConfirm(selected)}
            disabled={!selected || isPending}
          >
            {isPending && <Loader2 className="animate-spin" aria-hidden />}
            Delegiraj
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
