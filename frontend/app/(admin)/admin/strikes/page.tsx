/**
 * (admin)/admin/strikes/page.tsx — Strike registar.
 *
 * ROADMAP 4.7. Thin wrapper; all the logic lives in StrikesTable.
 */

import { StrikesTable } from "@/components/admin/strikes-table"
import { PageHeader } from "@/components/shared/page-header"

export default function AdminStrikesPage() {
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Strike registar"
        description="Studenti sa aktivnim strike poenima i blokadama."
      />
      <StrikesTable />
    </div>
  )
}
