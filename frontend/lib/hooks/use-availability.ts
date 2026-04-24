/**
 * use-availability.ts — Professor availability slot + blackout management.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import type {
  BlackoutCreateRequest,
  SlotCreateRequest,
  SlotUpdateRequest,
  Uuid,
} from "@/types"

const SLOTS_KEY = ["professor", "slots"] as const
const BLACKOUTS_KEY = ["professor", "blackouts"] as const

export function useMySlots() {
  return useQuery({
    queryKey: SLOTS_KEY,
    queryFn: () => professorsApi.listMySlots(),
    staleTime: 30 * 1000,
  })
}

export function useCreateSlot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: SlotCreateRequest) => professorsApi.createSlot(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: SLOTS_KEY }),
  })
}

export function useUpdateSlot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: SlotUpdateRequest }) =>
      professorsApi.updateSlot(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: SLOTS_KEY }),
  })
}

export function useDeleteSlot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => professorsApi.deleteSlot(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SLOTS_KEY }),
  })
}

export function useBlackouts() {
  return useQuery({
    queryKey: BLACKOUTS_KEY,
    queryFn: () => professorsApi.listBlackouts(),
    staleTime: 60 * 1000,
  })
}

export function useCreateBlackout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BlackoutCreateRequest) =>
      professorsApi.createBlackout(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: BLACKOUTS_KEY })
      qc.invalidateQueries({ queryKey: SLOTS_KEY })
    },
  })
}

export function useDeleteBlackout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => professorsApi.deleteBlackout(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: BLACKOUTS_KEY })
      qc.invalidateQueries({ queryKey: SLOTS_KEY })
    },
  })
}
