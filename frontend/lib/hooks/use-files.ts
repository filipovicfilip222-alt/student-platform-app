/**
 * use-files.ts — File upload / listing / deletion for an appointment.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.6).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { appointmentsApi } from "@/lib/api/appointments"
import type { Uuid } from "@/types"

const makeKey = (appointmentId: Uuid) =>
  ["appointment", appointmentId, "files"] as const

export function useFiles(appointmentId: Uuid | null | undefined) {
  return useQuery({
    queryKey: makeKey(appointmentId as Uuid),
    queryFn: () => appointmentsApi.listFiles(appointmentId as Uuid),
    enabled: Boolean(appointmentId),
  })
}

export function useUploadFile(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) =>
      appointmentsApi.uploadFile(appointmentId, file),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: makeKey(appointmentId) }),
  })
}

export function useDeleteFile(appointmentId: Uuid) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (fileId: Uuid) =>
      appointmentsApi.deleteFile(appointmentId, fileId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: makeKey(appointmentId) }),
  })
}
