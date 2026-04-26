/**
 * use-notifications.ts — Notification list + unread counter + read mutations.
 *
 * Transport handoff (Phase 5 Izmena 4 + websocket-schema.md §4):
 *  - While the notifications WS is NOT connected, the unread counter and
 *    the dropdown list fall back to REST polling.
 *  - When `<NotificationStream />` flips `useNotificationWsStatus` to
 *    `isConnected = true`, `refetchInterval` becomes `false` and the WS
 *    takes over (`notification.created` events invalidate the list,
 *    `notification.unread_count` events update the counter directly).
 *
 * Defensive fallback for the ROADMAP 4.2 gap:
 *  - If the REST endpoint returns 404 (backend not deployed yet), TanStack
 *    Query's default behaviour is to retry on every fetch and keep polling
 *    on the normal 30 s cadence — that previously produced 60+ failed
 *    requests in 90 s, freezing unrelated dropdowns under failed-promise
 *    bookkeeping. We now:
 *      1. Skip retries on 404 entirely (it will not magically appear).
 *      2. Keep retrying transient errors (network flap, 5xx) up to twice.
 *      3. Slow polling to 5 min once we have observed a 404 — frequent
 *         enough to pick up a backend deploy mid-session, rare enough not
 *         to flood the network tab.
 *      4. Disable focus-refetch (the parent QueryClient sets this globally,
 *         but we re-assert it here so the contract is visible at the call
 *         site).
 *
 *  Once ROADMAP 4.2 lands the same hook keeps working with no changes:
 *  the first successful fetch clears `query.state.error`, the interval
 *  drops back to 30 s, and the WS handshake will succeed on the next page
 *  load (after which polling switches off entirely).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios from "axios"

import { notificationsApi } from "@/lib/api/notifications"
import { useNotificationWsStatus } from "@/lib/stores/notification-ws-status"
import type { NotificationResponse, Uuid } from "@/types"

export const NOTIFICATION_LIST_KEY = ["notifications", "list"] as const
export const NOTIFICATION_UNREAD_KEY = [
  "notifications",
  "unread-count",
] as const

const POLL_INTERVAL_MS = 30 * 1_000
const POLL_INTERVAL_AFTER_404_MS = 5 * 60 * 1_000
const TRANSIENT_RETRY_LIMIT = 2

function isNotFound(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404
}

/**
 * Retry callback shared by both notification queries:
 *   - 404 → never retry (endpoint genuinely missing).
 *   - other axios / network errors → retry up to TRANSIENT_RETRY_LIMIT.
 */
function notFoundAwareRetry(failureCount: number, error: unknown): boolean {
  if (isNotFound(error)) return false
  return failureCount < TRANSIENT_RETRY_LIMIT
}

/**
 * Pick a refetch interval that adapts to the last observed error:
 *   - WS already delivering → no polling at all.
 *   - Last fetch was 404 → poll every 5 min (endpoint missing, save the
 *     network tab).
 *   - Otherwise → standard 30 s cadence.
 */
function pickPollInterval(
  wsConnected: boolean,
  lastError: unknown
): number | false {
  if (wsConnected) return false
  if (isNotFound(lastError)) return POLL_INTERVAL_AFTER_404_MS
  return POLL_INTERVAL_MS
}

export function useNotifications(
  params: { limit?: number; unread_only?: boolean } = {}
) {
  const wsConnected = useNotificationWsStatus((s) => s.isConnected)

  return useQuery<NotificationResponse[]>({
    queryKey: [...NOTIFICATION_LIST_KEY, params] as const,
    queryFn: () => notificationsApi.list(params),
    staleTime: 15 * 1000,
    retry: notFoundAwareRetry,
    refetchInterval: (query) =>
      pickPollInterval(wsConnected, query.state.error),
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  })
}

export function useUnreadCount() {
  const wsConnected = useNotificationWsStatus((s) => s.isConnected)

  return useQuery<number>({
    queryKey: NOTIFICATION_UNREAD_KEY,
    queryFn: () => notificationsApi.unreadCount().then((r) => r.count),
    staleTime: 15 * 1000,
    retry: notFoundAwareRetry,
    refetchInterval: (query) =>
      pickPollInterval(wsConnected, query.state.error),
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => notificationsApi.markRead(id),
    onMutate: async (id) => {
      // Optimistic: flip the flag + decrement the counter locally so the
      // UI updates instantly even before the backend confirms.
      await qc.cancelQueries({ queryKey: NOTIFICATION_LIST_KEY })

      qc.setQueriesData<NotificationResponse[]>(
        { queryKey: NOTIFICATION_LIST_KEY },
        (prev) =>
          prev
            ? prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
            : prev
      )
      qc.setQueryData<number>(NOTIFICATION_UNREAD_KEY, (prev) =>
        typeof prev === "number" ? Math.max(0, prev - 1) : prev
      )
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: NOTIFICATION_LIST_KEY })
      qc.invalidateQueries({ queryKey: NOTIFICATION_UNREAD_KEY })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: NOTIFICATION_LIST_KEY })
      qc.setQueriesData<NotificationResponse[]>(
        { queryKey: NOTIFICATION_LIST_KEY },
        (prev) => (prev ? prev.map((n) => ({ ...n, is_read: true })) : prev)
      )
      qc.setQueryData<number>(NOTIFICATION_UNREAD_KEY, 0)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: NOTIFICATION_LIST_KEY })
      qc.invalidateQueries({ queryKey: NOTIFICATION_UNREAD_KEY })
    },
  })
}
