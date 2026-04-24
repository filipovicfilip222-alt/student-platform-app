/**
 * (admin)/admin/document-requests/page.tsx — Admin queue for student
 * document requests.
 *
 * ROADMAP 4.8. Status filter (PENDING default) drives
 * `useAdminDocumentRequests(status)`. Per-row actions open
 * `ApproveDialog` / `RejectDialog` or immediately mark the request as
 * completed once the student has picked the document up in person.
 */

"use client"

import { useState } from "react"
import { FileClock } from "lucide-react"

import { AdminRequestRow } from "@/components/document-requests/admin-request-row"
import { ApproveDialog } from "@/components/document-requests/approve-dialog"
import { RejectDialog } from "@/components/document-requests/reject-dialog"
import { EmptyState } from "@/components/shared/empty-state"
import { PageHeader } from "@/components/shared/page-header"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { DOCUMENT_STATUS_LABELS } from "@/lib/constants/document-types"
import {
  useAdminDocumentRequests,
  useCompleteDocumentRequest,
} from "@/lib/hooks/use-document-requests"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { DocumentRequestResponse, DocumentStatus } from "@/types"

const STATUS_OPTIONS: Array<DocumentStatus | "ALL"> = [
  "ALL",
  "PENDING",
  "APPROVED",
  "REJECTED",
  "COMPLETED",
]

export default function AdminDocumentRequestsPage() {
  const [status, setStatus] = useState<DocumentStatus | "ALL">("PENDING")
  const query = useAdminDocumentRequests(status === "ALL" ? undefined : status)
  const complete = useCompleteDocumentRequest()

  const [approveTarget, setApproveTarget] =
    useState<DocumentRequestResponse | null>(null)
  const [rejectTarget, setRejectTarget] =
    useState<DocumentRequestResponse | null>(null)

  async function handleComplete(req: DocumentRequestResponse) {
    try {
      await complete.mutateAsync(req.id)
      toastSuccess("Označeno kao preuzeto")
    } catch (err) {
      toastApiError(err, "Ažuriranje nije uspelo.")
    }
  }

  const requests = query.data ?? []

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Zahtevi za dokumente"
        description="Obrada zahteva koje su podneli studenti."
      >
        <div className="w-48">
          <Select
            value={status}
            onValueChange={(v) => setStatus(v as DocumentStatus | "ALL")}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s === "ALL" ? "Svi statusi" : DOCUMENT_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </PageHeader>

      {query.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Skeleton key={idx} className="h-28 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <EmptyState
          icon={FileClock}
          title="Zahtevi nisu dostupni"
          description="Backend endpoint /admin/document-requests još nije aktivan (ROADMAP 4.8)."
        />
      ) : requests.length === 0 ? (
        <EmptyState
          icon={FileClock}
          title="Nema zahteva"
          description="Za izabrani status ne postoje zahtevi u redu."
        />
      ) : (
        <ul className="space-y-2">
          {requests.map((r) => (
            <AdminRequestRow
              key={r.id}
              request={r}
              onApprove={() => setApproveTarget(r)}
              onReject={() => setRejectTarget(r)}
              onComplete={() => void handleComplete(r)}
              isBusy={complete.isPending}
            />
          ))}
        </ul>
      )}

      <ApproveDialog
        request={approveTarget}
        onOpenChange={(open) => !open && setApproveTarget(null)}
      />
      <RejectDialog
        request={rejectTarget}
        onOpenChange={(open) => !open && setRejectTarget(null)}
      />
    </div>
  )
}
