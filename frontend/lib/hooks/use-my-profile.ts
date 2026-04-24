/**
 * use-my-profile.ts — Professor's own profile (settings → Profil tab).
 *
 * ROADMAP 3.7 / Faza 4 (frontend).
 *
 * Separate from use-professors.ts (which is student-facing discovery) so
 * the query keys don't collide and the hook can default-disable itself
 * while the backend endpoint is still a stub.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 3.7). The hook will
 * start returning data automatically once GET /professors/profile ships.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { professorsApi } from "@/lib/api/professors"
import { useAuthStore } from "@/lib/stores/auth"
import type { ProfessorProfileUpdate } from "@/types"

const ME_KEY = ["professor", "me"] as const
const ASSISTANTS_KEY = ["professor", "assistants"] as const

export function useMyProfessorProfile() {
  const role = useAuthStore((s) => s.user?.role ?? null)
  const enabled = role === "PROFESOR" || role === "ASISTENT"

  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => professorsApi.getMyProfile(),
    enabled,
    staleTime: 2 * 60 * 1000,
    retry: false,
  })
}

export function useUpdateMyProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ProfessorProfileUpdate) =>
      professorsApi.updateProfile(data),
    onSuccess: (data) => {
      qc.setQueryData(ME_KEY, data)
      qc.invalidateQueries({ queryKey: ME_KEY })
    },
  })
}

export function useMyAssistants() {
  const role = useAuthStore((s) => s.user?.role ?? null)
  const enabled = role === "PROFESOR"

  return useQuery({
    queryKey: ASSISTANTS_KEY,
    queryFn: () => professorsApi.listAssistants(),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}
