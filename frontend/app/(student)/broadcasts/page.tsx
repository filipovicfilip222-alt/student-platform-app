/**
 * (student)/broadcasts/page.tsx — Studentska stranica obaveštenja od
 * studentske službe (admin broadcast).
 *
 * Sadržaj je shared sa `(professor)/professor/broadcasts/page.tsx` —
 * vidi `<BroadcastsList />` u `components/notifications/broadcasts-list.tsx`.
 * Razdvojene rute postoje da svaka rola dobije svoj sidebar.
 */

"use client"

import { BroadcastsList } from "@/components/notifications/broadcasts-list"

export default function StudentBroadcastsPage() {
  return (
    <BroadcastsList description="Poruke koje vam je poslala studentska služba (svim studentima, vašem fakultetu ili ciljano vama)." />
  )
}
