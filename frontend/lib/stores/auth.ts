/**
 * auth.ts — Zustand auth store.
 *
 * Security rules (from CLAUDE.md):
 *  ✅ Access token stored in memory (this store) — never in localStorage/sessionStorage.
 *  ✅ Refresh token lives in httpOnly cookie set by the backend.
 *  ✅ On logout: backend revokes the Redis entry; cookie is cleared server-side.
 */

import { create } from "zustand"

import type { UserResponse } from "@/types/auth"

interface AuthState {
  /** Currently authenticated user. null when unauthenticated or loading. */
  user: UserResponse | null
  /** JWT access token in memory. null until session is restored. */
  accessToken: string | null
  /** True while the initial session-restore request is in flight. */
  isLoading: boolean

  // ── Actions ──────────────────────────────────────────────────────────────
  /** Set both user and access token after a successful login / session restore. */
  setAuth: (user: UserResponse, accessToken: string) => void
  /** Update only the access token (used by the Axios refresh interceptor). */
  setAccessToken: (accessToken: string) => void
  /** Clear all auth state after logout or failed refresh. */
  clearAuth: () => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isLoading: true,

  setAuth: (user, accessToken) =>
    set({ user, accessToken, isLoading: false }),

  setAccessToken: (accessToken) =>
    set({ accessToken }),

  clearAuth: () =>
    set({ user: null, accessToken: null, isLoading: false }),

  setLoading: (isLoading) =>
    set({ isLoading }),
}))

// ── Selectors (use these in components for stability) ─────────────────────────

export const selectUser = (s: AuthState) => s.user
export const selectIsAuthenticated = (s: AuthState) => s.accessToken !== null
export const selectIsLoading = (s: AuthState) => s.isLoading
export const selectRole = (s: AuthState) => s.user?.role ?? null
