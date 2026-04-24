/**
 * impersonation.ts — Admin impersonation session metadata.
 *
 * Auth token swap is handled by `useAuthStore`. This store only tracks who the
 * original admin was so `<ImpersonationBanner />` can render and the "Exit"
 * action can restore the admin session (see lib/hooks/use-impersonation.ts).
 *
 * Intentionally not persisted: on refresh the admin's access token is gone
 * anyway (memory-only) — a fresh refresh will reissue the original admin's
 * token from Redis, and the banner should stay hidden until the admin
 * re-initiates impersonation.
 */

import { create } from "zustand"

import type { UserResponse } from "@/types/auth"

interface ImpersonationState {
  /** True while the admin is viewing the app as another user. */
  isImpersonating: boolean
  /** The original admin's id — matches the `imp` claim in the new JWT. */
  adminId: string | null
  /** The admin's full UserResponse so we can restore it when exiting. */
  originalUser: UserResponse | null

  setImpersonating: (payload: {
    adminId: string
    originalUser: UserResponse
  }) => void
  clearImpersonation: () => void
}

export const useImpersonationStore = create<ImpersonationState>((set) => ({
  isImpersonating: false,
  adminId: null,
  originalUser: null,

  setImpersonating: ({ adminId, originalUser }) =>
    set({ isImpersonating: true, adminId, originalUser }),

  clearImpersonation: () =>
    set({ isImpersonating: false, adminId: null, originalUser: null }),
}))
