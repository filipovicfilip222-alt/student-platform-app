/**
 * icons.ts — NotificationType → Lucide ikona + boja (StudentPlus paleta).
 *
 * KORAK 7 — centralni mapping koji je do sada živeo inline u
 * `notification-item.tsx`. Sa centralizacijom dobijamo:
 *   - jedan istinski izvor za boje (success → green, warning → amber,
 *     info → burgundy, destructive → red),
 *   - reuse u toast-u, push payload-u i mobile drawer-u.
 *
 * Tone klase mapiraju na semantičke tokene iz globals.css; svi su
 * dark-mode safe (auto invert kroz `--success`, `--warning` etc.).
 */

import {
  AlertTriangle,
  Bell,
  Calendar,
  CalendarCheck2,
  CalendarX2,
  Clock,
  FileCheck2,
  FileX2,
  Megaphone,
  MessageSquare,
  ShieldAlert,
  ShieldCheck,
  UserPlus,
  type LucideIcon,
} from "lucide-react"

import type { NotificationType } from "@/types/notification"

export type NotificationTone =
  | "success"
  | "warning"
  | "info"
  | "destructive"
  | "muted"

export interface NotificationVisual {
  icon: LucideIcon
  tone: NotificationTone
}

const VISUALS: Record<NotificationType, NotificationVisual> = {
  APPOINTMENT_CONFIRMED: { icon: CalendarCheck2, tone: "success" },
  APPOINTMENT_REJECTED: { icon: CalendarX2, tone: "destructive" },
  APPOINTMENT_CANCELLED: { icon: CalendarX2, tone: "destructive" },
  APPOINTMENT_DELEGATED: { icon: Calendar, tone: "info" },
  APPOINTMENT_REMINDER_24H: { icon: Clock, tone: "warning" },
  APPOINTMENT_REMINDER_1H: { icon: Clock, tone: "warning" },
  NEW_APPOINTMENT_REQUEST: { icon: UserPlus, tone: "info" },
  NEW_CHAT_MESSAGE: { icon: MessageSquare, tone: "info" },
  WAITLIST_OFFER: { icon: Calendar, tone: "info" },
  STRIKE_ADDED: { icon: AlertTriangle, tone: "destructive" },
  BLOCK_ACTIVATED: { icon: ShieldAlert, tone: "destructive" },
  BLOCK_LIFTED: { icon: ShieldCheck, tone: "success" },
  DOCUMENT_REQUEST_APPROVED: { icon: FileCheck2, tone: "success" },
  DOCUMENT_REQUEST_REJECTED: { icon: FileX2, tone: "destructive" },
  DOCUMENT_REQUEST_COMPLETED: { icon: FileCheck2, tone: "success" },
  BROADCAST: { icon: Megaphone, tone: "info" },
}

/**
 * Tailwind klase po tone-u. Pozadina je 10% varijacija, foreground je puna
 * boja, što daje mekan badge-look bez zatamnjenja teksta na cards.
 */
const TONE_CLASSES: Record<NotificationTone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  info: "bg-primary/10 text-primary",
  destructive: "bg-destructive/10 text-destructive",
  muted: "bg-muted text-muted-foreground",
}

const FALLBACK: NotificationVisual = { icon: Bell, tone: "muted" }

export function getNotificationVisual(type: NotificationType): NotificationVisual {
  return VISUALS[type] ?? FALLBACK
}

export function getNotificationToneClasses(tone: NotificationTone): string {
  return TONE_CLASSES[tone]
}
