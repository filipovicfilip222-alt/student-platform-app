/**
 * (admin)/admin/audit-log/page.tsx — Admin audit log.
 *
 * ROADMAP 4.7. Thin page wrapper around AuditLogTable.
 */

import { AuditLogTable } from "@/components/admin/audit-log-table"
import { PageHeader } from "@/components/shared/page-header"

export default function AdminAuditLogPage() {
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Audit log"
        description="Hronologija svih administrativnih akcija — izvor istine za inspekciju."
      />
      <AuditLogTable />
    </div>
  )
}
