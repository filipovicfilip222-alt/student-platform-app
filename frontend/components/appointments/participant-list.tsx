/**
 * participant-list.tsx — List of students attached to a group appointment.
 *
 * ROADMAP 3.6 / Faza 3.6. Wires confirm/decline mutations for the row
 * belonging to the currently logged-in student.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Users } from "lucide-react"

import { ParticipantRow } from "./participant-row"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { appointmentsApi } from "@/lib/api/appointments"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { ParticipantResponse, Uuid } from "@/types"

export interface ParticipantListProps {
  appointmentId: Uuid
}

export function ParticipantList({ appointmentId }: ParticipantListProps) {
  const qc = useQueryClient()
  const currentUserId = useAuthStore((s) => s.user?.id ?? null)

  const participantsQuery = useQuery({
    queryKey: ["appointment", appointmentId, "participants"] as const,
    queryFn: () => appointmentsApi.listParticipants(appointmentId),
  })

  function invalidateAll() {
    qc.invalidateQueries({
      queryKey: ["appointment", appointmentId, "participants"],
    })
    qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
  }

  const confirmMutation = useMutation({
    mutationFn: (participantId: Uuid) =>
      appointmentsApi.confirmParticipation(appointmentId, participantId),
    onSuccess: () => {
      toastSuccess("Potvrdili ste učešće.")
      invalidateAll()
    },
    onError: (err) => toastApiError(err, "Greška pri potvrdi učešća."),
  })

  const declineMutation = useMutation({
    mutationFn: (participantId: Uuid) =>
      appointmentsApi.declineParticipation(appointmentId, participantId),
    onSuccess: () => {
      toastSuccess("Odbili ste učešće.")
      invalidateAll()
    },
    onError: (err) => toastApiError(err, "Greška pri odbijanju učešća."),
  })

  const participants: ParticipantResponse[] = participantsQuery.data ?? []
  const isMutating = confirmMutation.isPending || declineMutation.isPending

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between border-b p-4">
        <CardTitle className="inline-flex items-center gap-2 text-base font-semibold">
          <Users className="size-4 text-muted-foreground" aria-hidden />
          Učesnici
        </CardTitle>
        <span className="text-xs text-muted-foreground tabular-nums">
          {participants.length}
        </span>
      </CardHeader>
      <CardContent className="p-4">
        {participantsQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-14 rounded-md" />
            <Skeleton className="h-14 rounded-md" />
          </div>
        ) : participantsQuery.isError ? (
          <p className="text-xs text-muted-foreground">
            Učesnici nedostupni (očekuje se backend ROADMAP 3.6).
          </p>
        ) : participants.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Nema drugih učesnika na ovom terminu.
          </p>
        ) : (
          <ul className="space-y-2">
            {participants.map((p) => (
              <ParticipantRow
                key={p.id}
                participant={p}
                isCurrentUser={p.student_id === currentUserId}
                onConfirm={(id) => confirmMutation.mutate(id)}
                onDecline={(id) => declineMutation.mutate(id)}
                isMutating={isMutating}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
