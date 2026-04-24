/**
 * use-impersonation.ts — Start / end an admin impersonation session.
 *
 * On start: swap the access token + user in the auth store, and remember the
 * original admin identity in the impersonation store so the banner can offer
 * an "Exit" action.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.7).
 */

"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import { useAuthStore } from "@/lib/stores/auth"
import { useImpersonationStore } from "@/lib/stores/impersonation"
import type { Uuid } from "@/types"

export function useStartImpersonation() {
  const qc = useQueryClient()
  const { user: currentUser, setAuth } = useAuthStore.getState()
  const startImpersonation = useImpersonationStore(
    (s) => s.setImpersonating
  )

  return useMutation({
    mutationFn: (userId: Uuid) => adminApi.impersonateStart(userId),
    onSuccess: (data) => {
      if (currentUser) {
        startImpersonation({
          adminId: currentUser.id,
          originalUser: currentUser,
        })
      }
      setAuth(data.user, data.access_token)
      qc.clear()
    },
  })
}

export function useEndImpersonation() {
  const qc = useQueryClient()
  const setAuth = useAuthStore((s) => s.setAuth)
  const clearImpersonation = useImpersonationStore((s) => s.clearImpersonation)

  return useMutation({
    mutationFn: () => adminApi.impersonateEnd(),
    onSuccess: (data) => {
      setAuth(data.user, data.access_token)
      clearImpersonation()
      qc.clear()
    },
  })
}
