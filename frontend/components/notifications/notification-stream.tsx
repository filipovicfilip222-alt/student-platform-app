/**
 * notification-stream.tsx — Placeholder for the native WebSocket client that
 * will subscribe to /api/v1/notifications/stream and invalidate the
 * ['notifications'] query on each message.
 *
 * Lives in providers.tsx so it mounts once per session. Returns `null` because
 * it renders no UI — the `<NotificationCenter />` bell in the top bar reads
 * the same query cache it updates.
 *
 * TODO: implement in Phase 5 (ROADMAP 4.1 — requires websocket-schema.md).
 */

"use client"

export function NotificationStream(): null {
  return null
}
