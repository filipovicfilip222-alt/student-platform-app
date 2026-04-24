/**
 * use-notifications.ts — Notification list + unread counter + read mutations.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.1). Until then these
 * hooks will error; the NotificationCenter should handle that gracefully.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notificationsApi } from "@/lib/api/notifications"
import type { Uuid } from "@/types"

const LIST_KEY = ["notifications"] as const
const UNREAD_KEY = ["notifications", "unread-count"] as const

export function useNotifications(
  params: { limit?: number; unread_only?: boolean } = {}
) {
  return useQuery({
    queryKey: [...LIST_KEY, params] as const,
    queryFn: () => notificationsApi.list(params),
    staleTime: 30 * 1000,
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: UNREAD_KEY,
    queryFn: () => notificationsApi.unreadCount().then((r) => r.count),
    refetchInterval: 60 * 1000,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: LIST_KEY })
      qc.invalidateQueries({ queryKey: UNREAD_KEY })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: LIST_KEY })
      qc.invalidateQueries({ queryKey: UNREAD_KEY })
    },
  })
}
