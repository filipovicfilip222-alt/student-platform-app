/**
 * use-faq.ts — Professor FAQ management.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import type { FaqCreate, FaqUpdate, Uuid } from "@/types"

const KEY = ["professor", "faq"] as const

export function useFaq() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => professorsApi.listFaq(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateFaq() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FaqCreate) => professorsApi.createFaq(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateFaq() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: FaqUpdate }) =>
      professorsApi.updateFaq(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useDeleteFaq() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => professorsApi.deleteFaq(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
