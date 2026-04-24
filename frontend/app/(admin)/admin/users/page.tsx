/**
 * (admin)/admin/users/page.tsx — ADMIN korisnici.
 *
 * ROADMAP 4.7. Wires the UsersTable (CRUD + impersonate) to the
 * BulkImportDialog. UsersTable owns filter state; the page's only job
 * is to own the "open bulk import" toggle.
 */

"use client"

import { useState } from "react"

import { BulkImportDialog } from "@/components/admin/bulk-import-dialog"
import { UsersTable } from "@/components/admin/users-table"
import { PageHeader } from "@/components/shared/page-header"

export default function AdminUsersPage() {
  const [bulkOpen, setBulkOpen] = useState(false)

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Korisnici"
        description="Pregled naloga, CRUD akcije, bulk import i impersonacija."
      />

      <UsersTable onBulkImportClick={() => setBulkOpen(true)} />

      <BulkImportDialog open={bulkOpen} onOpenChange={setBulkOpen} />
    </div>
  )
}
