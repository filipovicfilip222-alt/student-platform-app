/**
 * use-professors.ts — Student-facing professor discovery queries.
 *
 * Wraps studentsApi.searchProfessors / getProfessorProfile / getProfessorSlots.
 * Query-key conventions: ['professors', subResource, ...filters].
 */

"use client"

import { useQuery } from "@tanstack/react-query"

import {
  studentsApi,
  type ProfessorSearchParams,
  type SlotRangeParams,
} from "@/lib/api/students"
import type { Uuid } from "@/types"

export function useProfessorSearch(params: ProfessorSearchParams) {
  return useQuery({
    queryKey: ["professors", "search", params] as const,
    queryFn: () => studentsApi.searchProfessors(params),
    staleTime: 30 * 1000,
  })
}

export function useProfessorProfile(id: Uuid | null | undefined) {
  return useQuery({
    queryKey: ["professors", "profile", id] as const,
    queryFn: () => studentsApi.getProfessorProfile(id as Uuid),
    enabled: Boolean(id),
    staleTime: 60 * 1000,
  })
}

export function useProfessorSlots(
  professorId: Uuid | null | undefined,
  range: SlotRangeParams = {}
) {
  return useQuery({
    queryKey: ["professors", "slots", professorId, range] as const,
    queryFn: () => studentsApi.getProfessorSlots(professorId as Uuid, range),
    enabled: Boolean(professorId),
    refetchInterval: 30 * 1000,
  })
}
