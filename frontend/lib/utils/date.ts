/**
 * date.ts — Date formatting helpers.
 *
 * Thin wrappers over `date-fns` with the Serbian Latin locale preloaded.
 * Accepts both `Date` instances and ISO strings returned by the API.
 */

import { format, formatDistanceToNow, parseISO } from "date-fns"
import { sr } from "date-fns/locale"

type DateInput = Date | string

function toDate(value: DateInput): Date {
  return typeof value === "string" ? parseISO(value) : value
}

/** Example: 24.04.2026. 14:30 */
export function formatDateTime(value: DateInput): string {
  return format(toDate(value), "dd.MM.yyyy. HH:mm", { locale: sr })
}

/** Example: 24.04.2026. */
export function formatDate(value: DateInput): string {
  return format(toDate(value), "dd.MM.yyyy.", { locale: sr })
}

/** Example: pre 3 sata, za 2 dana */
export function formatRelative(value: DateInput): string {
  return formatDistanceToNow(toDate(value), { addSuffix: true, locale: sr })
}

/** Example: 14:30 */
export function formatTime(value: DateInput): string {
  return format(toDate(value), "HH:mm", { locale: sr })
}
