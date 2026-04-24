/**
 * admin-request-row.tsx — One document-request row in the admin queue.
 *
 * ROADMAP 4.8. Shows document type, status, requester note, and action
 * buttons (Approve / Reject / Mark as picked up). The parent
 * `admin/document-requests/page.tsx` supplies mutation instances so this
 * row stays a pure presentational component.
 */

"use client"

import { Check, Clock, FileText, Package, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DOCUMENT_STATUS_LABELS,
  documentTypeLabel,
} from "@/lib/constants/document-types"
import { formatDateTime } from "@/lib/utils/date"
import type { DocumentRequestResponse, DocumentStatus } from "@/types"

interface Props {
  request: DocumentRequestResponse
  onApprove: () => void
  onReject: () => void
  onComplete: () => void
  isBusy?: boolean
}

const STATUS_VARIANT: Record<
  DocumentStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  PENDING: "secondary",
  APPROVED: "default",
  REJECTED: "destructive",
  COMPLETED: "outline",
}

export function AdminRequestRow({
  request,
  onApprove,
  onReject,
  onComplete,
  isBusy,
}: Props) {
  return (
    <li className="rounded-lg border border-border bg-background p-3 transition hover:bg-muted/30">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex size-8 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <FileText className="size-4" aria-hidden />
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">
              {documentTypeLabel(request.document_type)}
            </span>
            <Badge variant={STATUS_VARIANT[request.status]}>
              {DOCUMENT_STATUS_LABELS[request.status]}
            </Badge>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="size-3" aria-hidden />
            Podneto {formatDateTime(request.created_at)}
          </div>
          {request.note && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Napomena: </span>
              {request.note}
            </p>
          )}
          {request.admin_note && (
            <p className="rounded-md bg-muted/50 px-2 py-1 text-xs">
              <span className="font-medium">Admin: </span>
              {request.admin_note}
            </p>
          )}
          {request.pickup_date && (
            <p className="text-xs text-muted-foreground">
              Datum preuzimanja:{" "}
              <span className="font-medium text-foreground">
                {request.pickup_date}
              </span>
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-col gap-1">
          {request.status === "PENDING" && (
            <>
              <Button size="sm" onClick={onApprove} disabled={isBusy}>
                <Check aria-hidden />
                Odobri
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onReject}
                disabled={isBusy}
              >
                <X aria-hidden />
                Odbij
              </Button>
            </>
          )}
          {request.status === "APPROVED" && (
            <Button size="sm" variant="secondary" onClick={onComplete} disabled={isBusy}>
              <Package aria-hidden />
              Preuzeto
            </Button>
          )}
        </div>
      </div>
    </li>
  )
}
