/**
 * relative-time.ts — Smart "pre X" formatter za StudentPlus.
 *
 * KORAK 7 — bell dropdown i toast koriste ovu funkciju umesto čistog
 * `formatDistanceToNow`. Pravila (od najnovijeg ka najstarijem):
 *
 *   < 60 sekundi  →  "upravo sad"
 *   < 60 minuta   →  "pre 5 min"
 *   < 6 sati      →  "pre 3 sata"
 *   ista kalend.  →  "danas u 14:23"
 *   juče          →  "juče u 14:23"
 *   < 7 dana      →  "pre 3 dana"
 *   < ista godina →  "23. apr"
 *   ostalo        →  "23.04.2025."
 *
 * Tačno-na-minut osvežavanje radimo eksterno (parent komponente koriste
 * setInterval ili `useEffect` tick, kao u TicketChat-u).
 *
 * `formatRelative` iz `lib/utils/date.ts` ostaje za druge slučajeve
 * (audit log, calendar legends) gde je samo "pre 3 sata" dovoljan.
 */

import {
  differenceInCalendarDays,
  differenceInHours,
  differenceInMinutes,
  format,
  isSameYear,
  isToday,
  isYesterday,
  parseISO,
} from "date-fns"
import { sr } from "date-fns/locale"

type DateInput = Date | string

function toDate(value: DateInput): Date {
  return typeof value === "string" ? parseISO(value) : value
}

export function formatSmartRelative(value: DateInput): string {
  const date = toDate(value)
  const now = new Date()
  const diffMin = differenceInMinutes(now, date)
  const diffHr = differenceInHours(now, date)

  if (diffMin < 1) return "upravo sad"
  if (diffMin < 60) return `pre ${diffMin} min`
  if (diffHr < 6) {
    const word = diffHr === 1 ? "sat" : diffHr < 5 ? "sata" : "sati"
    return `pre ${diffHr} ${word}`
  }
  if (isToday(date)) return `danas u ${format(date, "HH:mm")}`
  if (isYesterday(date)) return `juče u ${format(date, "HH:mm")}`

  const diffDays = differenceInCalendarDays(now, date)
  if (diffDays > 0 && diffDays < 7) {
    const word = diffDays === 1 ? "dan" : diffDays < 5 ? "dana" : "dana"
    return `pre ${diffDays} ${word}`
  }

  if (isSameYear(date, now)) {
    return format(date, "d. MMM", { locale: sr })
  }

  return format(date, "dd.MM.yyyy.", { locale: sr })
}
