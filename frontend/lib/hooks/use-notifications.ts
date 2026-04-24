/**
 * use-notifications.ts — Notification list + unread counter + read mutations.
 *
 * Transport handoff (Phase 5 Izmena 4 + websocket-schema.md §4):
 *  - While the notifications WS is NOT connected, the unread counter and
 *    the dropdown list fall back to REST polling every 30 s.
 *  - When `<NotificationStream />` flips `useNotificationWsStatus` to
 *    `isConnected = true`, `refetchInterval` becomes `false` and the WS
 *    takes over (`notification.created` events invalidate the list,
 *    `notification.unread_count` events update the counter directly).
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.2). The polling
 * fallback keeps the UI functional; toggle activates automatically when
 * the backend goes live without code changes here.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notificationsApi } from "@/lib/api/notifications"
import { useNotificationWsStatus } from "@/lib/stores/notification-ws-status"
import type { NotificationResponse, Uuid } from "@/types"

export const NOTIFICATION_LIST_KEY = ["notifications", "list"] as const
export const NOTIFICATION_UNREAD_KEY = [
  "notifications",
  "unread-count",
] as const

const POLL_INTERVAL_MS = 30_000

export function useNotifications(
  params: { limit?: number; unread_only?: boolean } = {}
) {
  const wsConnected = useNotificationWsStatus((s) => s.isConnected)

  return useQuery<NotificationResponse[]>({
    queryKey: [...NOTIFICATION_LIST_KEY, params] as const,
    queryFn: () => notificationsApi.list(params),
    staleTime: 15 * 1000,
    refetchInterval: wsConnected ? false : POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  })
}

export function useUnreadCount() {
  const wsConnected = useNotificationWsStatus((s) => s.isConnected)

  return useQuery<number>({
    queryKey: NOTIFICATION_UNREAD_KEY,
    queryFn: () => notificationsApi.unreadCount().then((r) => r.count),
    staleTime: 15 * 1000,
    refetchInterval: wsConnected ? false : POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
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
