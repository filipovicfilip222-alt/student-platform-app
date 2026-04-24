/**
 * use-strikes.ts — Admin view of students with strike points + unblock.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import type { UnblockRequest, Uuid } from "@/types"

const KEY = ["admin", "strikes"] as const

export function useStrikes() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => adminApi.listStrikes(),
    staleTime: 30 * 1000,
  })
}

export function useUnblockStudent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      studentId,
      data,
    }: {
      studentId: Uuid
      data: UnblockRequest
    }) => adminApi.unblockStudent(studentId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
