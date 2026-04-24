/**
 * impersonation.ts — Admin impersonation session metadata.
 *
 * Auth token swap is handled by `useAuthStore`. This store only tracks who the
 * original admin was so `<ImpersonationBanner />` can render and the "Exit"
 * action can restore the admin session (see lib/hooks/use-impersonation.ts).
 *
 * Contract source: docs/websocket-schema.md §6.
 * - `adminId`, `adminEmail`, `adminName` are populated directly from the
 *   `imp` / `imp_email` / `imp_name` claims decoded from the JWT — we never
 *   call /auth/me for the admin name because the impersonated session's
 *   `/auth/me` now returns the TARGET user, not the admin.
 * - `originalUser` is the full UserResponse captured before the token swap
 *   so we can surface rich info in the banner and, if ever needed, fall
 *   back to it after the token expires (TTL 30 min, no refresh — see §6.1).
 *
 * Intentionally not persisted: on refresh the admin's access token is gone
 * (memory-only). A fresh /auth/refresh reissues the original admin's token,
 * and the banner should stay hidden until the admin re-initiates
 * impersonation.
 */

import { create } from "zustand"

import type { UserResponse } from "@/types/auth"

interface ImpersonationState {
  /** True while the admin is viewing the app as another user. */
  isImpersonating: boolean
  /** Admin user id — mirrors the `imp` claim in the active JWT. */
  adminId: string | null
  /** Admin email — from `imp_email` claim. */
  adminEmail: string | null
  /** Admin full name — from `imp_name` claim. */
  adminName: string | null
  /**
   * Snapshot of the admin's UserResponse taken at impersonation start.
   * Used by the banner to show the admin's identity without decoding the
   * token, and kept in sync with whatever token is currently active.
   */
  originalUser: UserResponse | null
  /** ISO-8601 moment the impersonation token expires (schema §6.1). */
  expiresAt: string | null

  setImpersonating: (payload: {
    adminId: string
    adminEmail: string
    adminName: string
    originalUser: UserResponse
    expiresAt: string | null
  }) => void
  clearImpersonation: () => void
}

const INITIAL_STATE = {
  isImpersonating: false,
  adminId: null,
  adminEmail: null,
  adminName: null,
  originalUser: null,
  expiresAt: null,
} satisfies Omit<
  ImpersonationState,
  "setImpersonating" | "clearImpersonation"
>

export const useImpersonationStore = create<ImpersonationState>((set) => ({
  ...INITIAL_STATE,

  setImpersonating: ({ adminId, adminEmail, adminName, originalUser, expiresAt }) =>
    set({
      isImpersonating: true,
      adminId,
      adminEmail,
      adminName,
      originalUser,
      expiresAt,
    }),

  clearImpersonation: () => set({ ...INITIAL_STATE }),
}))
