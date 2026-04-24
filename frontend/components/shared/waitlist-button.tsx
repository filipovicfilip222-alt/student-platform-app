/**
 * waitlist-button.tsx — Join/leave a fully-booked slot's waitlist.
 *
 * ROADMAP 3.5 / Faza 3.5. Renders a single button that toggles
 * waitlist membership for `slotId`. The parent passes in the initial
 * "is on list" flag; on success we invalidate waitlist queries so any
 * list view refreshes.
 *
 * Parses "Pozicija: N" from MessageResponse.message to surface the
 * student's current queue position in the success toast.
 */

"use client"

import { useState } from "react"
import { BellOff, BellRing, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useJoinWaitlist, useLeaveWaitlist } from "@/lib/hooks/use-waitlist"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { MessageResponse, Uuid } from "@/types"

export interface WaitlistButtonProps {
  slotId: Uuid
  initiallyJoined?: boolean
  className?: string
}

function parsePosition(res: MessageResponse): number | null {
  const match = /Pozicija:\s*(\d+)/i.exec(res.message ?? "")
  return match ? Number(match[1]) : null
}

export function WaitlistButton({
  slotId,
  initiallyJoined = false,
  className,
}: WaitlistButtonProps) {
  const [isJoined, setIsJoined] = useState(initiallyJoined)
  const joinMutation = useJoinWaitlist()
  const leaveMutation = useLeaveWaitlist()
  const isPending = joinMutation.isPending || leaveMutation.isPending

  function handleJoin() {
    joinMutation.mutate(slotId, {
      onSuccess: (res) => {
        setIsJoined(true)
        const position = parsePosition(res)
        toastSuccess(
          position !== null
            ? `Na listi čekanja ste — pozicija ${position}.`
            : "Prijavljeni ste na listu čekanja."
        )
      },
      onError: (err) => toastApiError(err, "Greška pri prijavi na listu čekanja."),
    })
  }

  function handleLeave() {
    leaveMutation.mutate(slotId, {
      onSuccess: () => {
        setIsJoined(false)
        toastSuccess("Uklonjeni ste sa liste čekanja.")
      },
      onError: (err) => toastApiError(err, "Greška pri odjavi sa liste čekanja."),
    })
  }

  return (
    <Button
      type="button"
      variant={isJoined ? "outline" : "default"}
      size="sm"
      className={className}
      disabled={isPending}
      onClick={isJoined ? handleLeave : handleJoin}
    >
      {isPending ? (
        <Loader2 className="animate-spin" aria-hidden />
      ) : isJoined ? (
        <BellOff aria-hidden />
      ) : (
        <BellRing aria-hidden />
      )}
      {isJoined ? "Napusti listu čekanja" : "Prijavi se na listu čekanja"}
    </Button>
  )
}
