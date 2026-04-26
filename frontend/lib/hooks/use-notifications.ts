/**
 * use-notifications.ts — Notification list + unread counter + read mutations.
 *
 * Transport handoff (websocket-schema.md §4 + Faza 4.2):
 *  - Primary kanal je WebSocket: ``<NotificationStream />`` flips
 *    ``useNotificationWsStatus`` to ``isConnected = true`` on handshake,
 *    after which ``refetchInterval`` becomes ``false`` and the WS owns
 *    state (``notification.created`` events update the cache,
 *    ``notification.unread_count`` events update the counter directly).
 *  - REST polling (30 s) je SAMO fallback dok WS nije konektovan
 *    (handshake u toku, prolazni 4500, jitter delay) ili kad
 *    ``notification-socket`` nakon 5 pokušaja proglasi kanal trajno
 *    nedostupnim. U fallback režimu WS status flag je ``isConnected=false``,
 *    polling 30 s drži UI sveže do recovery-ja ili reload-a stranice.
 *
 * Note: defanzivni 5-min polling iz prethodne sesije (uveo se dok je 4.2
 * endpoint vraćao 404) je uklonjen — endpoint sad postoji, retry/poll
 * logiku vraćamo na default-e iz QueryClient-a + ovaj jednostavan
 * conditional ``refetchInterval``.
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

const POLL_INTERVAL_MS = 30 * 1_000

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
    refetchOnWindowFocus: false,
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
