/**
 * push-subscription-toggle.tsx — Web Push subscription UI.
 *
 * ROADMAP 5.2 / Phase 6.3g — STUB.
 *
 * The production flow is:
 *   1. Notification.requestPermission()
 *   2. registration.pushManager.subscribe({
 *        userVisibleOnly: true,
 *        applicationServerKey: VAPID_PUBLIC_KEY,
 *      })
 *   3. POST subscription JSON to /api/v1/notifications/subscribe
 *
 * Backend VAPID endpoint is NOT YET implemented (ROADMAP 4.2 open). Until it
 * ships we render the toggle as a disabled switch with a tooltip so the UI
 * slot exists and the wiring work is localised to this file when the backend
 * lands.
 */

"use client"

import { BellRing } from "lucide-react"

import { Switch } from "@/components/ui/switch"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export function PushSubscriptionToggle() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm"
            aria-label="Push notifikacije"
          >
            <span className="flex items-center gap-2 text-muted-foreground">
              <BellRing className="h-4 w-4" aria-hidden />
              Push notifikacije
            </span>
            <Switch disabled aria-label="Uključi push notifikacije" />
          </div>
        </TooltipTrigger>
        <TooltipContent side="left">
          Uskoro dostupno — čeka se backend VAPID endpoint (ROADMAP 4.2).
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
