/**
 * use-push-subscription.ts — Web Push opt-in/opt-out hook (KORAK 1 Prompta 2).
 *
 * Wraps the 3-step browser flow:
 *   1. `Notification.requestPermission()` (user gesture required)
 *   2. `registration.pushManager.subscribe({ applicationServerKey, userVisibleOnly: true })`
 *   3. `POST /api/v1/notifications/subscribe`
 *
 * State machine (`status`):
 *   - "loading"     — initial mount, or transitional during enable/disable.
 *   - "unsupported" — browser lacks ServiceWorker / PushManager / Notification
 *                     APIs, or runs without a secure context (HTTP host other
 *                     than localhost). Toggle is disabled with explanatory copy.
 *   - "denied"      — `Notification.permission === "denied"`. Browser-level
 *                     permission blocked; user must reset it from site settings.
 *   - "disabled"    — supported, permission default/granted, but no active
 *                     subscription on this device. Toggle reads OFF.
 *   - "enabled"     — `pushManager.getSubscription()` returned non-null AND
 *                     we registered it server-side. Toggle reads ON.
 *
 * Production-only caveat:
 *   - `next-pwa` disables the service worker in development (next.config.mjs
 *     line `disable: process.env.NODE_ENV === "development"`). In dev mode
 *     `navigator.serviceWorker.ready` either rejects or never resolves, so
 *     the hook surfaces "unsupported" with the dev-mode explanation. The
 *     demo runs against the production build (`docker compose build frontend`).
 *
 * Why this is a hook and not a context:
 *   - Only one component (the user-menu toggle) consumes this state in V1.
 *   - If broadcast notifications later need a "go re-subscribe" CTA from
 *     elsewhere we can lift this into a Zustand store; for now the local
 *     useState keeps wiring simple and prevents context re-render storms.
 */

"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { notificationsApi } from "@/lib/api/notifications"

export type PushStatus =
  | "loading"
  | "unsupported"
  | "denied"
  | "disabled"
  | "enabled"

export interface UsePushSubscriptionReturn {
  status: PushStatus
  /** Set during enable/disable mutations so the toggle can show a spinner. */
  isPending: boolean
  /** Last error message surfaced from the browser or backend, cleared by the next attempt. */
  error: string | null
  enable: () => Promise<void>
  disable: () => Promise<void>
}

/**
 * Decode VAPID public key (base64url) → Uint8Array as expected by
 * `pushManager.subscribe({ applicationServerKey })`.
 *
 * Standard helper from MDN; we keep it inline (16 LOC) instead of pulling
 * a tiny npm dep that adds 1 prod dependency for nothing.
 */
// We return an ArrayBuffer (not a Uint8Array view) to dodge the TS 5.7+
// `Uint8Array<ArrayBufferLike>` vs `BufferSource` mismatch — PushManager's
// `applicationServerKey` accepts BufferSource and a fresh ArrayBuffer is
// the cleanest member of that union.
function urlBase64ToArrayBuffer(base64UrlEncoded: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64UrlEncoded.length % 4)) % 4)
  const base64 = (base64UrlEncoded + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/")
  const rawData = atob(base64)
  const buf = new ArrayBuffer(rawData.length)
  const view = new Uint8Array(buf)
  for (let i = 0; i < rawData.length; i++) {
    view[i] = rawData.charCodeAt(i)
  }
  return buf
}

function detectSupport(): boolean {
  if (typeof window === "undefined") return false
  if (!("serviceWorker" in navigator)) return false
  if (!("PushManager" in window)) return false
  if (!("Notification" in window)) return false
  // Web Push requires a secure context. Browsers whitelist localhost so the
  // dev/demo flow works without HTTPS termination.
  if (!window.isSecureContext) return false
  return true
}

export function usePushSubscription(): UsePushSubscriptionReturn {
  const [status, setStatus] = useState<PushStatus>("loading")
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Cache the VAPID key so we don't hit the backend twice in one session.
  const vapidKeyRef = useRef<string | null>(null)

  const evaluate = useCallback(async () => {
    if (!detectSupport()) {
      setStatus("unsupported")
      return
    }
    if (Notification.permission === "denied") {
      setStatus("denied")
      return
    }
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      setStatus(sub ? "enabled" : "disabled")
    } catch {
      // SW failed to register (e.g. running dev build with PWA disabled, or
      // worker file 404). Treat as unsupported so the UI shows a clean state.
      setStatus("unsupported")
    }
  }, [])

  useEffect(() => {
    void evaluate()
  }, [evaluate])

  const enable = useCallback(async () => {
    setError(null)
    setIsPending(true)
    try {
      if (!detectSupport()) {
        throw new Error("Push notifikacije nisu podržane u ovom pregledaču.")
      }

      // (1) Permission — must run inside a user gesture (toggle click).
      const permission = await Notification.requestPermission()
      if (permission !== "granted") {
        setStatus(permission === "denied" ? "denied" : "disabled")
        throw new Error(
          permission === "denied"
            ? "Dozvola za notifikacije je odbijena."
            : "Dozvola za notifikacije nije odobrena."
        )
      }

      // (2) Subscribe at browser level.
      const reg = await navigator.serviceWorker.ready
      let sub = await reg.pushManager.getSubscription()
      if (!sub) {
        if (!vapidKeyRef.current) {
          const { public_key } = await notificationsApi.getVapidPublicKey()
          vapidKeyRef.current = public_key
        }
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToArrayBuffer(vapidKeyRef.current),
        })
      }

      // (3) Persist on backend (UPSERT — safe to repeat).
      const subJson = sub.toJSON() as {
        endpoint?: string
        keys?: { p256dh?: string; auth?: string }
      }
      if (!subJson.endpoint || !subJson.keys?.p256dh || !subJson.keys?.auth) {
        throw new Error(
          "Pretplata nije validna (nedostaju ključevi). Pokušaj ponovo."
        )
      }
      await notificationsApi.subscribeToPush({
        endpoint: subJson.endpoint,
        keys: { p256dh: subJson.keys.p256dh, auth: subJson.keys.auth },
        user_agent: navigator.userAgent,
      })
      setStatus("enabled")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Greška pri pretplati."
      setError(msg)
    } finally {
      setIsPending(false)
    }
  }, [])

  const disable = useCallback(async () => {
    setError(null)
    setIsPending(true)
    try {
      if (!detectSupport()) {
        setStatus("unsupported")
        return
      }
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) {
        const endpoint = sub.endpoint
        // Browser side first — even if backend call fails the device stops
        // receiving push, which is the primary user intent.
        await sub.unsubscribe()
        try {
          await notificationsApi.unsubscribeFromPush({ endpoint })
        } catch {
          // Backend cleanup is best-effort; backend will also delete the row
          // when push delivery returns 410 Gone after the browser has gone
          // silent (push_service.send_push 410 cleanup).
        }
      }
      setStatus("disabled")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Greška pri odjavi."
      setError(msg)
    } finally {
      setIsPending(false)
    }
  }, [])

  return { status, isPending, error, enable, disable }
}
