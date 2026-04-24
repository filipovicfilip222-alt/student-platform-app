/**
 * use-crm.ts — Professor CRM notes per student.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import type { CrmNoteCreate, Uuid } from "@/types"

const makeKey = (studentId: Uuid) =>
  ["professor", "crm-notes", studentId] as const

export function useCrmNotes(studentId: Uuid | null | undefined) {
  return useQuery({
    queryKey: makeKey(studentId as Uuid),
    queryFn: () => professorsApi.listCrmNotes(studentId as Uuid),
    enabled: Boolean(studentId),
  })
}

export function useCreateCrmNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CrmNoteCreate) => professorsApi.createCrmNote(data),
    onSuccess: (_, variables) =>
      qc.invalidateQueries({ queryKey: makeKey(variables.student_id) }),
  })
}

export function useDeleteCrmNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: Uuid; studentId: Uuid }) =>
      professorsApi.deleteCrmNote(id),
    onSuccess: (_, variables) =>
      qc.invalidateQueries({ queryKey: makeKey(variables.studentId) }),
  })
}
