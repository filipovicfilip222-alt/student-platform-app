/**
 * participant-row.tsx — Single row in <ParticipantList />.
 *
 * ROADMAP 3.6 / Faza 3.6. Renders the participant's name + status chip
 * and — for the current user, when status is PENDING — the two CTAs to
 * confirm / decline participation.
 */

"use client"

import { Check, Loader2, Star, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ParticipantResponse, ParticipantStatus } from "@/types"

const STATUS_LABELS: Record<ParticipantStatus, string> = {
  PENDING: "Čeka potvrdu",
  CONFIRMED: "Potvrđeno",
  DECLINED: "Odbio",
}
const STATUS_STYLES: Record<ParticipantStatus, string> = {
  PENDING: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  CONFIRMED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  DECLINED: "bg-muted text-muted-foreground",
}

function getInitials(name?: string): string {
  if (!name) return "?"
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?"
}

export interface ParticipantRowProps {
  participant: ParticipantResponse
  isCurrentUser: boolean
  onConfirm?: (participantId: string) => void
  onDecline?: (participantId: string) => void
  isMutating?: boolean
}

export function ParticipantRow({
  participant,
  isCurrentUser,
  onConfirm,
  onDecline,
  isMutating = false,
}: ParticipantRowProps) {
  const name = participant.student_full_name ?? "Student"
  const canAct =
    isCurrentUser &&
    participant.status === "PENDING" &&
    (onConfirm || onDecline) !== undefined

  return (
    <li className="flex items-center gap-3 rounded-md border border-border/70 p-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {getInitials(name)}
      </div>

      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="flex items-center gap-1 text-sm font-medium text-foreground">
          <span className="truncate">{name}</span>
          {participant.is_lead && (
            <Star
              className="size-3.5 text-amber-500"
              aria-label="Lead student"
            />
          )}
          {isCurrentUser && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              Vi
            </span>
          )}
        </p>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium",
            STATUS_STYLES[participant.status]
          )}
        >
          {STATUS_LABELS[participant.status]}
        </span>
      </div>

      {canAct && (
        <div className="flex items-center gap-1.5">
          {onConfirm && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={isMutating}
              onClick={() => onConfirm(participant.id)}
            >
              {isMutating ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Check aria-hidden />
              )}
              Potvrdi
            </Button>
          )}
          {onDecline && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={isMutating}
              onClick={() => onDecline(participant.id)}
            >
              <X aria-hidden />
              Odbij
            </Button>
          )}
        </div>
      )}
    </li>
  )
}
