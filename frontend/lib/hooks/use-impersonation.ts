/**
 * use-impersonation.ts — Start / end an admin impersonation session.
 *
 * Flow (ROADMAP 4.4 + docs/websocket-schema.md §6):
 *
 *   [start]
 *     1. POST /admin/impersonate/{user_id}
 *     2. server returns ImpersonationStartResponse with:
 *          { access_token, user, impersonator, imp_expires_at, expires_in }
 *     3. snapshot the original admin in useImpersonationStore using the
 *        `impersonator` summary from the response (admin name / email come
 *        from there — NOT from a second /auth/me call, because /auth/me
 *        after the token swap would return the target user).
 *     4. swap auth store to the impersonated user + the new access token.
 *     5. clear the React Query cache so stale admin data does not leak.
 *
 *   [end]
 *     1. POST /admin/impersonate/end
 *     2. server returns { access_token, user } — the restored admin session.
 *     3. restore auth store, clear impersonation store, clear cache.
 *
 *   A dedicated refresh for the impersonation token does NOT exist (TTL is
 *   30 min). If the axios interceptor hits 401 during an impersonation
 *   session, `/auth/refresh` will try to reissue the ADMIN's token — the
 *   admin therefore silently drops back out of impersonation and will need
 *   to re-impersonate from the users table.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.4 / 4.7).
 */

"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import { useAuthStore } from "@/lib/stores/auth"
import { useImpersonationStore } from "@/lib/stores/impersonation"
import type { Uuid } from "@/types"

export function useStartImpersonation() {
  const qc = useQueryClient()
  const setAuth = useAuthStore((s) => s.setAuth)
  const setImpersonating = useImpersonationStore((s) => s.setImpersonating)

  return useMutation({
    mutationFn: (userId: Uuid) => adminApi.impersonateStart(userId),
    onSuccess: (data) => {
      const originalAdmin = useAuthStore.getState().user
      const impersonator = data.impersonator

      // Synthesize a minimal admin UserResponse if the current store is
      // unexpectedly empty (edge case after a tab reload). The
      // `impersonator` summary from the server is authoritative.
      const originalUser =
        originalAdmin ?? {
          id: impersonator.id,
          email: impersonator.email,
          first_name: impersonator.first_name,
          last_name: impersonator.last_name,
          role: "ADMIN" as const,
          // The summary does not carry every UserResponse field; the values
          // below are placeholders for UX only and are replaced on
          // impersonateEnd when the full admin UserResponse returns.
          faculty: "FON" as const,
          is_active: true,
          is_verified: true,
          profile_image_url: null,
          created_at: new Date().toISOString(),
        }

      setImpersonating({
        adminId: impersonator.id,
        adminEmail: impersonator.email,
        adminName: `${impersonator.first_name} ${impersonator.last_name}`.trim(),
        originalUser,
        expiresAt: data.imp_expires_at,
      })

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
