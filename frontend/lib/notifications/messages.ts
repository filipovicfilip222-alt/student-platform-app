/**
 * messages.ts — Title + body templates po `NotificationType`.
 *
 * KORAK 7 — centralni izvor za "kratak naslov" koji koristi:
 *   - toast (NotificationStream → sonner)
 *   - bell dropdown (kao fallback ako backend ne pošalje title)
 *   - push notification SW (KORAK 1 Prompta 2 — kratke poruke do 80 chars)
 *
 * NB: backend `NotificationResponse` već nosi `title` i `body`. Ova mapa
 * se koristi samo kao fallback ili za toast title gde želimo kraću
 * verziju nego što backend šalje (npr. "Termin potvrđen" umesto pune
 * rečenice "Vaš termin sa prof. X je potvrđen za 25.04. 14:00").
 */

import type { NotificationType } from "@/types/notification"

export interface NotificationCopy {
  toastTitle: string
  fallbackTitle: string
}

const COPY: Record<NotificationType, NotificationCopy> = {
  APPOINTMENT_CONFIRMED: {
    toastTitle: "Termin potvrđen",
    fallbackTitle: "Termin je potvrđen",
  },
  APPOINTMENT_REJECTED: {
    toastTitle: "Termin odbijen",
    fallbackTitle: "Termin je odbijen",
  },
  APPOINTMENT_CANCELLED: {
    toastTitle: "Termin otkazan",
    fallbackTitle: "Termin je otkazan",
  },
  APPOINTMENT_DELEGATED: {
    toastTitle: "Termin delegiran",
    fallbackTitle: "Termin je preuzeo asistent",
  },
  APPOINTMENT_REMINDER_24H: {
    toastTitle: "Podsetnik: termin sutra",
    fallbackTitle: "Termin sutra",
  },
  APPOINTMENT_REMINDER_1H: {
    toastTitle: "Termin za 1h",
    fallbackTitle: "Vaš termin počinje za 1 sat",
  },
  NEW_APPOINTMENT_REQUEST: {
    toastTitle: "Novi zahtev",
    fallbackTitle: "Novi zahtev za termin",
  },
  NEW_CHAT_MESSAGE: {
    toastTitle: "Nova poruka",
    fallbackTitle: "Nova poruka u razgovoru",
  },
  WAITLIST_OFFER: {
    toastTitle: "Slot dostupan",
    fallbackTitle: "Slot je oslobođen",
  },
  STRIKE_ADDED: {
    toastTitle: "Dobili ste strike",
    fallbackTitle: "Dodat je strike na vaš nalog",
  },
  BLOCK_ACTIVATED: {
    toastTitle: "Nalog blokiran",
    fallbackTitle: "Vaš nalog je privremeno blokiran",
  },
  BLOCK_LIFTED: {
    toastTitle: "Blokada uklonjena",
    fallbackTitle: "Vaš nalog je ponovo aktivan",
  },
  DOCUMENT_REQUEST_APPROVED: {
    toastTitle: "Zahtev odobren",
    fallbackTitle: "Vaš zahtev je odobren",
  },
  DOCUMENT_REQUEST_REJECTED: {
    toastTitle: "Zahtev odbijen",
    fallbackTitle: "Vaš zahtev je odbijen",
  },
  DOCUMENT_REQUEST_COMPLETED: {
    toastTitle: "Dokument spreman",
    fallbackTitle: "Vaš dokument je spreman za preuzimanje",
  },
  BROADCAST: {
    toastTitle: "Obaveštenje",
    fallbackTitle: "Novo obaveštenje",
  },
}

export function getNotificationCopy(type: NotificationType): NotificationCopy {
  return (
    COPY[type] ?? {
      toastTitle: "Obaveštenje",
      fallbackTitle: "Novo obaveštenje",
    }
  )
}

export function getToastTitle(type: NotificationType): string {
  return getNotificationCopy(type).toastTitle
}

export function getFallbackTitle(type: NotificationType): string {
  return getNotificationCopy(type).fallbackTitle
}
