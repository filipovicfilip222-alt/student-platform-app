/**
 * push-subscription-toggle.tsx — Web Push opt-in toggle (KORAK 1 Prompta 2).
 *
 * Lives in the user dropdown menu (`components/shared/user-menu.tsx`).
 * Wraps `usePushSubscription` and renders one of three visual states:
 *
 *   • supported & enabled  — Switch is ON, click → unsubscribe.
 *   • supported & disabled — Switch is OFF, click → subscribe (triggers
 *                            browser permission prompt inside the same
 *                            user gesture).
 *   • unsupported / denied — Switch is disabled with an explanatory tooltip;
 *                            user must change browser-level permission to
 *                            recover (we deliberately don't auto-redirect
 *                            to chrome://settings — that's not a thing in
 *                            most browsers and it's invasive UX).
 *
 * When `isPending` is true (mid-flight permission request or HTTP roundtrip)
 * we render a Loader spinner where the switch normally sits, preventing
 * double-click double-subscribes.
 */

"use client"

import { BellRing, Loader2 } from "lucide-react"

import { Switch } from "@/components/ui/switch"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { usePushSubscription, type PushStatus } from "@/lib/hooks/use-push-subscription"

const STATUS_TOOLTIP: Record<PushStatus, string | null> = {
  loading: null,
  enabled: "Push notifikacije su uključene na ovom uređaju.",
  disabled: "Uključi push notifikacije na ovom uređaju.",
  unsupported:
    "Tvoj pregledač ne podržava push notifikacije, ili je veza nesigurna.",
  denied:
    "Dozvola za notifikacije je odbijena. Promeni je u podešavanjima sajta i osveži stranicu.",
}

export function PushSubscriptionToggle() {
  const { status, isPending, error, enable, disable } = usePushSubscription()

  const isInteractive = status === "enabled" || status === "disabled"
  const isOn = status === "enabled"
  const tooltipText = error ?? STATUS_TOOLTIP[status]

  const handleToggle = async (next: boolean) => {
    if (isPending) return
    if (next) {
      await enable()
    } else {
      await disable()
    }
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm"
            aria-label="Push notifikacije"
            data-testid="push-subscription-toggle"
            data-push-status={status}
          >
            <span className="flex items-center gap-2 text-muted-foreground">
              <BellRing className="h-4 w-4" aria-hidden />
              Push notifikacije
            </span>
            {isPending ? (
              <Loader2
                className="h-4 w-4 animate-spin text-muted-foreground"
                aria-label="U toku..."
              />
            ) : (
              <Switch
                checked={isOn}
                disabled={!isInteractive || isPending}
                onCheckedChange={handleToggle}
                aria-label={
                  isOn
                    ? "Isključi push notifikacije"
                    : "Uključi push notifikacije"
                }
              />
            )}
          </div>
        </TooltipTrigger>
        {tooltipText ? (
          <TooltipContent side="left">{tooltipText}</TooltipContent>
        ) : null}
      </Tooltip>
    </TooltipProvider>
  )
}
