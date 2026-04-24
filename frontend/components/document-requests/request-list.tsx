/**
 * request-list.tsx — Student's own document-request history.
 *
 * ROADMAP 4.8. Renders the list returned by `useMyDocumentRequests`.
 * Read-only from the student side (cancel is not in scope per PRD).
 */

"use client"

import { FileClock, FileText } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/shared/empty-state"
import {
  DOCUMENT_STATUS_LABELS,
  documentTypeLabel,
} from "@/lib/constants/document-types"
import { useMyDocumentRequests } from "@/lib/hooks/use-document-requests"
import { formatDateTime } from "@/lib/utils/date"
import type { DocumentStatus } from "@/types"

const STATUS_VARIANT: Record<
  DocumentStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  PENDING: "secondary",
  APPROVED: "default",
  REJECTED: "destructive",
  COMPLETED: "outline",
}

export function RequestList() {
  const query = useMyDocumentRequests()

  if (query.isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={idx} className="h-20 w-full" />
        ))}
      </div>
    )
  }

  if (query.isError) {
    return (
      <EmptyState
        icon={FileClock}
        title="Lista zahteva nije dostupna"
        description="Backend endpoint /document-requests/me još nije aktivan (ROADMAP 4.8)."
      />
    )
  }

  const requests = query.data ?? []
  if (requests.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="Još nema zahteva"
        description="Kada podnesete zahtev, pojaviće se ovde sa trenutnim statusom."
      />
    )
  }

  return (
    <ul className="space-y-2">
      {requests.map((r) => (
        <li
          key={r.id}
          className="rounded-lg border border-border bg-background p-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileText
                className="size-4 text-muted-foreground"
                aria-hidden
              />
              <span className="text-sm font-semibold">
                {documentTypeLabel(r.document_type)}
              </span>
            </div>
            <Badge variant={STATUS_VARIANT[r.status]}>
              {DOCUMENT_STATUS_LABELS[r.status]}
            </Badge>
          </div>

          <div className="mt-1 text-xs text-muted-foreground">
            Podneto: {formatDateTime(r.created_at)}
            {r.pickup_date && (
              <> · Preuzimanje: <strong>{r.pickup_date}</strong></>
            )}
          </div>

          {r.note && (
            <p className="mt-2 text-xs">
              <span className="font-medium">Napomena: </span>
              {r.note}
            </p>
          )}

          {r.admin_note && (
            <p className="mt-2 rounded-md bg-muted/50 px-2 py-1 text-xs">
              <span className="font-medium">Admin: </span>
              {r.admin_note}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
