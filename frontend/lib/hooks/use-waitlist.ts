/**
 * use-waitlist.ts — Join / leave the waitlist for a fully-booked slot.
 *
 * Backend returns MessageResponse with "Pozicija: N" in the text; if a
 * dedicated response shape is added later we'll parse position here.
 */

"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { studentsApi } from "@/lib/api/students"
import type { Uuid } from "@/types"

export function useJoinWaitlist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (slotId: Uuid) => studentsApi.joinWaitlist(slotId),
    onSuccess: (_, slotId) => {
      qc.invalidateQueries({ queryKey: ["waitlist", slotId] })
      qc.invalidateQueries({
        queryKey: ["professors", "slots"],
        predicate: (q) => q.queryKey.includes(slotId),
      })
    },
  })
}

export function useLeaveWaitlist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (slotId: Uuid) => studentsApi.leaveWaitlist(slotId),
    onSuccess: (_, slotId) => {
      qc.invalidateQueries({ queryKey: ["waitlist", slotId] })
    },
  })
}
