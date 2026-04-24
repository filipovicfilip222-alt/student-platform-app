/**
 * use-requests-inbox.ts — Professor inbox of pending appointment requests.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import type { Uuid } from "@/types"

const INBOX_KEY = ["professor", "requests-inbox"] as const

export function useRequestsInbox(status: "PENDING" | "ALL" = "PENDING") {
  return useQuery({
    queryKey: [...INBOX_KEY, status] as const,
    queryFn: () => professorsApi.listRequestsInbox(status),
    staleTime: 15 * 1000,
  })
}

function makeInboxInvalidator(qc: ReturnType<typeof useQueryClient>) {
  return () => qc.invalidateQueries({ queryKey: INBOX_KEY })
}

export function useApproveRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (appointmentId: Uuid) =>
      professorsApi.approveRequest(appointmentId),
    onSuccess: makeInboxInvalidator(qc),
  })
}

export function useRejectRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: Uuid; reason: string }) =>
      professorsApi.rejectRequest(id, { reason }),
    onSuccess: makeInboxInvalidator(qc),
  })
}

export function useDelegateRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      assistantId,
    }: {
      id: Uuid
      assistantId: Uuid
    }) => professorsApi.delegateRequest(id, { assistant_id: assistantId }),
    onSuccess: makeInboxInvalidator(qc),
  })
}
