/**
 * use-canned-responses.ts — Professor canned reply snippets.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import type {
  CannedResponseCreate,
  CannedResponseUpdate,
  Uuid,
} from "@/types"

const KEY = ["professor", "canned-responses"] as const

export function useCannedResponses() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => professorsApi.listCannedResponses(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateCannedResponse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CannedResponseCreate) =>
      professorsApi.createCannedResponse(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateCannedResponse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: CannedResponseUpdate }) =>
      professorsApi.updateCannedResponse(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useDeleteCannedResponse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => professorsApi.deleteCannedResponse(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
