/**
 * offline-indicator.tsx — Floating banner shown when the browser is offline.
 *
 * ROADMAP 5.2 / Phase 6.3f. Mounted once inside <AppShell /> so it's visible
 * on every authenticated page. The service worker keeps a read-only cache of
 * /api/v1/students/appointments and /api/v1/notifications; we just tell the
 * user that whatever they see now is an archived snapshot.
 */

"use client"

import { WifiOff } from "lucide-react"
import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

export function OfflineIndicator() {
  const [online, setOnline] = useState<boolean>(true)

  useEffect(() => {
    if (typeof navigator === "undefined") return
    setOnline(navigator.onLine)
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener("online", up)
    window.addEventListener("offline", down)
    return () => {
      window.removeEventListener("online", up)
      window.removeEventListener("offline", down)
    }
  }, [])

  if (online) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4"
      )}
    >
      <div
        className={cn(
          "pointer-events-auto flex items-center gap-2 rounded-full border border-amber-500/40",
          "bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-900 shadow-lg backdrop-blur",
          "dark:text-amber-200"
        )}
      >
        <WifiOff className="h-4 w-4" aria-hidden />
        <span>Offline mod — pregled samo arhive</span>
      </div>
    </div>
  )
}
