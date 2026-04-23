/**
 * api.ts — Axios instance with JWT interceptor.
 *
 * Token flow:
 *  - Access token is stored in Zustand (memory only — never localStorage).
 *  - Refresh token is an httpOnly cookie, sent automatically by the browser.
 *  - On 401, one refresh attempt is made; if it fails the user is logged out.
 *  - Concurrent 401s while a refresh is in progress are queued and replayed.
 */

import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"

import { useAuthStore } from "@/lib/stores/auth"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost/api/v1"

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send httpOnly refresh_token cookie on every request
  headers: { "Content-Type": "application/json" },
})

// ── Request interceptor — attach access token ──────────────────────────────

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor — handle 401 with auto-refresh ───────────────────

type QueueEntry = {
  resolve: (token: string) => void
  reject: (err: unknown) => void
}

let isRefreshing = false
let pendingQueue: QueueEntry[] = []

function flushQueue(token: string | null, error: unknown = null) {
  pendingQueue.forEach(({ resolve, reject }) =>
    token ? resolve(token) : reject(error)
  )
  pendingQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    const is401 = error.response?.status === 401
    const isRefreshRoute = original?.url?.includes("/auth/refresh")
    const alreadyRetried = original?._retry

    if (!is401 || isRefreshRoute || alreadyRetried || !original) {
      return Promise.reject(error)
    }

    // ── Another refresh already in flight — queue this request ──────────────
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject })
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      })
    }

    // ── Start a new refresh cycle ──────────────────────────────────────────
    original._retry = true
    isRefreshing = true

    try {
      // POST /auth/refresh — browser sends the httpOnly cookie automatically
      const { data } = await axios.post(
        `${BASE_URL}/auth/refresh`,
        {},
        { withCredentials: true }
      )

      const newToken: string = data.access_token
      useAuthStore.getState().setAuth(data.user, newToken)
      flushQueue(newToken)

      original.headers.Authorization = `Bearer ${newToken}`
      return api(original)
    } catch (refreshError) {
      flushQueue(null, refreshError)
      useAuthStore.getState().clearAuth()

      if (typeof window !== "undefined") {
        window.location.href = "/login"
      }

      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

export default api
