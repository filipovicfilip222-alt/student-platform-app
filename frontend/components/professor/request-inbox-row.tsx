/**
 * request-inbox-row.tsx — Single table row in the professor inbox.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Displays student summary, slot time,
 * topic + truncated description. Action column exposes Approve / Reject /
 * Delegate through a dropdown menu — parent component decides which
 * dialog to open.
 */

"use client"

import { Check, MoreHorizontal, Share2, X } from "lucide-react"

import { AppointmentStatusBadge } from "@/components/appointments/appointment-status-badge"
import { RoleGate } from "@/components/shared/role-gate"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TableCell, TableRow } from "@/components/ui/table"
import { topicCategoryLabel } from "@/lib/constants/topic-categories"
import { formatDateTime } from "@/lib/utils/date"
import type { AppointmentResponse } from "@/types"

export interface RequestInboxRowProps {
  appointment: AppointmentResponse
  onApprove: () => void
  onReject: () => void
  onDelegate: () => void
}

export function RequestInboxRow({
  appointment,
  onApprove,
  onReject,
  onDelegate,
}: RequestInboxRowProps) {
  return (
    <TableRow>
      <TableCell className="font-medium">
        {formatDateTime(appointment.slot_datetime)}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {/* TODO: show student full name once backend joins in lead_student */}
        {appointment.lead_student_id.slice(0, 8)}…
      </TableCell>
      <TableCell>
        <span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs">
          {topicCategoryLabel(appointment.topic_category)}
        </span>
      </TableCell>
      <TableCell className="max-w-[320px] whitespace-normal text-xs text-muted-foreground">
        <span className="line-clamp-2">{appointment.description}</span>
      </TableCell>
      <TableCell>
        <AppointmentStatusBadge status={appointment.status} />
      </TableCell>
      <TableCell className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Akcije nad zahtevom"
            >
              <MoreHorizontal aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Akcije</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => onApprove()}>
              <Check aria-hidden />
              Odobri
            </DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              onSelect={() => onReject()}
            >
              <X aria-hidden />
              Odbij
            </DropdownMenuItem>
            <RoleGate allowedRoles={["PROFESOR"]}>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => onDelegate()}>
                <Share2 aria-hidden />
                Delegiraj asistentu
              </DropdownMenuItem>
            </RoleGate>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  )
}
