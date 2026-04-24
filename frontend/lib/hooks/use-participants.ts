/**
 * use-participants.ts — Group appointment participants (confirm / decline).
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.6).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { appointmentsApi } from "@/lib/api/appointments"
import type { Uuid } from "@/types"

const makeKey = (appointmentId: Uuid) =>
  ["appointment", appointmentId, "participants"] as const

export function useParticipants(appointmentId: Uuid | null | undefined) {
  return useQuery({
    queryKey: makeKey(appointmentId as Uuid),
    queryFn: () => appointmentsApi.listParticipants(appointmentId as Uuid),
    enabled: Boolean(appointmentId),
  })
}

export function useConfirmParticipation(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (participantId: Uuid) =>
      appointmentsApi.confirmParticipation(appointmentId, participantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: makeKey(appointmentId) })
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
    },
  })
}

export function useDeclineParticipation(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (participantId: Uuid) =>
      appointmentsApi.declineParticipation(appointmentId, participantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: makeKey(appointmentId) })
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
    },
  })
}
