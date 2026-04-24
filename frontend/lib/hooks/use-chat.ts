/**
 * use-chat.ts — Appointment ticket chat (polling fallback + send mutation).
 *
 * ROADMAP 3.6 explicitly allows 2s polling on GET /appointments/{id}/messages
 * until ROADMAP 4.1 ships the WebSocket migration. When that lands, swap the
 * `refetchInterval` out for a socket.io subscription that invalidates this key.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.6).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { appointmentsApi } from "@/lib/api/appointments"
import type { ChatMessageCreate, Uuid } from "@/types"

const makeKey = (appointmentId: Uuid) =>
  ["appointment", appointmentId, "messages"] as const

export function useChatMessages(appointmentId: Uuid | null | undefined) {
  return useQuery({
    queryKey: makeKey(appointmentId as Uuid),
    queryFn: () => appointmentsApi.listMessages(appointmentId as Uuid),
    enabled: Boolean(appointmentId),
    refetchInterval: 2000,
  })
}

export function useSendMessage(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ChatMessageCreate) =>
      appointmentsApi.sendMessage(appointmentId, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: makeKey(appointmentId) }),
  })
}
