/**
 * worker/index.js — Custom Service Worker fragment (KORAK 1 Prompta 2).
 *
 * Auto-imported by @ducanh2912/next-pwa via the default `customWorkerSrc`
 * (= "worker/" relative to the Next.js project root). The plugin compiles
 * this file with esbuild and prepends an `importScripts(...)` line in the
 * generated `public/sw.js`.
 *
 * Responsibilities:
 *   1. `push` event   — parse the trimmed JSON payload sent by
 *      `backend/app/services/push_service.py::send_push()` and surface it
 *      as an OS-level notification.
 *   2. `notificationclick` event — open / focus the deep link from
 *      `payload.url`, falling back to `/dashboard` if anything is malformed.
 *
 * Why we do the JSON parse ourselves instead of relying on `event.data.json()`:
 *   - `event.data` may be `null` if the push servis gave us an empty payload
 *     (some test infrastructure does this for keepalive pings — Mozilla
 *     occasionally fires empty pushes when re-validating an endpoint).
 *   - `event.data.json()` throws a SyntaxError for non-JSON bodies; we want
 *     to fall back to a generic notification instead of swallowing the
 *     event silently.
 *
 * What we deliberately DON'T do here:
 *   - Don't fetch additional data from the API. The push payload is
 *     authoritative; if we needed the full body we'd hit our own endpoint
 *     after the user clicks (currently not needed — body is in the payload).
 *   - Don't render a custom action set. Some browsers (Safari) ignore
 *     `actions`, so keeping the notification simple yields consistent UX.
 */

self.addEventListener("push", (event) => {
  /** @type {{ title?: string, body?: string, url?: string, type?: string, tag?: string }} */
  let payload = {}
  if (event.data) {
    try {
      payload = event.data.json()
    } catch (_err) {
      // Non-JSON payload — fall back to plain text in body.
      try {
        payload = { body: event.data.text() }
      } catch (_err2) {
        payload = {}
      }
    }
  }

  const title = payload.title || "StudentPlus"
  const options = {
    body: payload.body || "Stigla je nova notifikacija.",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    tag: payload.tag || "studentplus",
    // Older notifications with the same `tag` are silently replaced in the
    // OS tray — without `renotify`, the user wouldn't see any banner the
    // second time. We always renotify so reminder upgrades (24h → 1h) are
    // visible.
    renotify: Boolean(payload.tag),
    data: { url: payload.url || "/dashboard", type: payload.type || null },
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()

  const targetUrl = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : "/dashboard"

  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      })
      // Try to focus an existing tab on the same origin first — avoids
      // opening a duplicate window if the user already has the app open.
      for (const client of allClients) {
        try {
          const clientUrl = new URL(client.url)
          const targetParsed = new URL(targetUrl, self.location.origin)
          if (clientUrl.origin === targetParsed.origin) {
            await client.focus()
            // Navigate the focused tab to the deep link if it's not already there.
            if (clientUrl.pathname !== targetParsed.pathname) {
              return client.navigate(targetParsed.href).catch(() => undefined)
            }
            return undefined
          }
        } catch (_err) {
          // Ignore malformed client URLs; fall through to openWindow.
        }
      }
      return self.clients.openWindow(targetUrl)
    })()
  )
})
