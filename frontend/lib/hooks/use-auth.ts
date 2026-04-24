/**
 * use-auth.ts — TanStack Query hooks over authApi.
 *
 * The Zustand `useAuthStore` remains the synchronous read surface for the
 * axios interceptor. These hooks wrap the same endpoints for components that
 * want loading / error state, optimistic updates, etc.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/auth"
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
} from "@/types/auth"

export const AUTH_ME_KEY = ["auth", "me"] as const

export function useMe() {
  const accessToken = useAuthStore((s) => s.accessToken)

  return useQuery<UserResponse>({
    queryKey: AUTH_ME_KEY,
    queryFn: () => authApi.me().then((r) => r.data),
    enabled: accessToken !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth)
  const qc = useQueryClient()

  return useMutation({
    mutationFn: (data: LoginRequest) =>
      authApi.login(data).then((r) => r.data),
    onSuccess: (data: TokenResponse) => {
      setAuth(data.user, data.access_token)
      qc.setQueryData(AUTH_ME_KEY, data.user)
    },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: (data: RegisterRequest) =>
      authApi.register(data).then((r) => r.data),
  })
}

export function useLogout() {
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const qc = useQueryClient()

  return useMutation({
    mutationFn: () => authApi.logout().then((r) => r.data),
    onSettled: () => {
      clearAuth()
      qc.clear()
    },
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) =>
      authApi.forgotPassword({ email }).then((r) => r.data),
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (data: { token: string; new_password: string }) =>
      authApi.resetPassword(data).then((r) => r.data),
  })
}
