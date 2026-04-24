/**
 * use-broadcast.ts — Admin broadcast send + history.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import type { BroadcastRequest } from "@/types"

const KEY = ["admin", "broadcasts"] as const

export function useBroadcastHistory() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => adminApi.listBroadcastHistory(),
    staleTime: 60 * 1000,
  })
}

export function useSendBroadcast() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BroadcastRequest) => adminApi.sendBroadcast(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
