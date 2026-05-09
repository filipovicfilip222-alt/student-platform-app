/**
 * navigation.ts — Mapping `NotificationResponse` → frontend href.
 *
 * Single source of truth za "kuda vodi klik na notifikaciju". Koristi
 * se u dva konteksta:
 *
 *   - In-app klik na `<NotificationItem />` (bell dropdown, dashboard
 *     "Recent notifications" kartica, profesor /broadcasts stranica).
 *   - PWA service worker `notificationclick` handler — backend
 *     `push_service._build_target_url` već implementira simetrično
 *     mapiranje ka punim absolutnim URL-ovima; ovaj fajl drži
 *     identičan ugovor na frontend strani da push klik i in-app klik
 *     vode na ISTU rutu (UX inkonzistentnost je loš trag — npr.
 *     APPOINTMENT_CONFIRMED u oba slučaja vodi na `/appointments/{id}`).
 *
 * Kada dodaješ novi `NotificationType` ili menjaš data shape:
 *   1. ažuriraj backend `push_service._build_target_url`,
 *   2. ažuriraj ovaj helper,
 *   3. dodaj test u `lib/notifications/__tests__/navigation.test.ts` (TODO).
 */

import { ROUTES } from "@/lib/constants/routes"
import type { NotificationResponse } from "@/types/notification"
import type { Role } from "@/types/common"

/**
 * Bezbedno čita string polje iz `data`. Backend uvek šalje UUID-jeve
 * kao stringove — defensive narrowing je ovde čisto type-safety bonus
 * (`Record<string, unknown> | null` ne garantuje shape).
 */
function readString(
  data: NotificationResponse["data"],
  key: string
): string | null {
  if (!data) return null
  const value = (data as Record<string, unknown>)[key]
  return typeof value === "string" && value.length > 0 ? value : null
}

/**
 * Vraća internu rutu na koju klik na notifikaciju treba da odvede,
 * ili `null` ako ne postoji prirodna meta navigacija (STRIKE_*,
 * BLOCK_* se samo markiraju kao pročitano i ostaju u listi).
 *
 * Sve appointment-vezane notifikacije (uključujući NEW_CHAT_MESSAGE
 * jer chat živi u okviru `/appointments/[id]` stranice) vode na
 * shared appointment detail page — backend RBAC odlučuje šta
 * korisnik vidi. Profesor i student dele isti URL ugovor.
 *
 * BROADCAST vodi na rolnu „Obaveštenja" stranicu — student na
 * `/broadcasts`, profesor/asistent na `/professor/broadcasts`. Bez
 * `role` parametra (npr. SW kontekst pre push-a, gde rola nije
 * dostupna) BROADCAST ostaje bez navigacije.
 */
export function getNotificationHref(
  notification: NotificationResponse,
  role?: Role | null
): string | null {
  const { type, data } = notification

  if (
    type.startsWith("APPOINTMENT_") ||
    type === "NEW_APPOINTMENT_REQUEST" ||
    type === "NEW_CHAT_MESSAGE"
  ) {
    const appointmentId = readString(data, "appointment_id")
    if (appointmentId) {
      return ROUTES.appointment(appointmentId)
    }
    return null
  }

  if (type.startsWith("DOCUMENT_REQUEST_")) {
    return ROUTES.documentRequests
  }

  if (type === "WAITLIST_OFFER") {
    return ROUTES.search
  }

  if (type === "BROADCAST") {
    if (role === "STUDENT") return ROUTES.studentBroadcasts
    if (role === "PROFESOR" || role === "ASISTENT") {
      return ROUTES.professorBroadcasts
    }
    // ADMIN nema rolnu „Obaveštenja" stranicu — sopstvene poruke vidi u
    // /admin/broadcast (history). Ne vodimo ga tu sa klika na notifikaciju
    // (admin generalno ne dobija ni svoje broadcastove — fan-out filtrira
    // ADMIN role iz ALL/BY_FACULTY); fallback je `null` umesto pogađanja.
    return null
  }

  return null
}
