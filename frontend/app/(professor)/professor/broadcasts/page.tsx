/**
 * (professor)/professor/broadcasts/page.tsx — Profesorska / asistentska
 * stranica obaveštenja od studentske službe.
 *
 * Sadržaj je shared sa `(student)/broadcasts/page.tsx` — vidi
 * `<BroadcastsList />` u `components/notifications/broadcasts-list.tsx`.
 * Razlog za razdvojene rute (umesto jedne shared) je da svaka rola
 * dobije svoj sidebar (PROFESOR layout vs STUDENT layout).
 */

"use client"

import { BroadcastsList } from "@/components/notifications/broadcasts-list"

export default function ProfessorBroadcastsPage() {
  return (
    <BroadcastsList description="Poruke koje je studentska služba poslala vama, vašem fakultetu ili svim profesorima." />
  )
}
