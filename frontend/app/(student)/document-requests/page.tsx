/**
 * (student)/document-requests/page.tsx — Student document requests.
 *
 * ROADMAP 4.8. Two-column layout on md+ screens: the request form on
 * the left (can submit another type), the student's own history on the
 * right (status + admin notes).
 */

import { PageHeader } from "@/components/shared/page-header"
import { RequestForm } from "@/components/document-requests/request-form"
import { RequestList } from "@/components/document-requests/request-list"

export default function StudentDocumentRequestsPage() {
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Zahtevi za dokumente"
        description="Podnesite zahtev za studentsku potvrdu ili drugi dokument — administracija obrađuje u roku od 3 radna dana."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <RequestForm />
        <RequestList />
      </div>
    </div>
  )
}
