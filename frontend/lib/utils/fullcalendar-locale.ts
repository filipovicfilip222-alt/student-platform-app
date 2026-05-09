/**
 * fullcalendar-locale.ts — Serbian (Latin) locale for FullCalendar 6.x.
 *
 * Why a custom locale instead of `locale="sr"`:
 *
 *   1. The bundled `@fullcalendar/core/locales/sr.js` is *mostly* Latin but
 *      contains a few Cyrillic look-alike characters smuggled into Latin
 *      words (e.g. "M\u0435s\u0435c", "N\u0435d\u0435lja", "C\u0435o" — the `\u0435` is
 *      Cyrillic U+0435, not Latin U+0065). Visually fine in some fonts,
 *      but technically Cyrillic and unprofessional in a Latin product.
 *
 *   2. When `locale` is passed as a *string code* alone (e.g. `"sr"`)
 *      FullCalendar falls back to `Intl.DateTimeFormat` for month/day
 *      names. The CLDR default for `sr` is **Cyrillic** in most engines,
 *      so the calendar header would render "April 2026" → "\u0410\u043F\u0440\u0438\u043B 2026".
 *
 * Passing a locale object with `code: "sr-Latn"` solves both problems:
 *   - Our hand-curated Latin button/list strings are used verbatim.
 *   - Month/weekday names are routed through `Intl.DateTimeFormat("sr-Latn", ...)`
 *     which is well-supported in all evergreen browsers and yields proper
 *     Latin output ("April", "Maj", "Ponedeljak", ...).
 */

import type { LocaleInput } from "@fullcalendar/core"

/**
 * NOTE on shape: FullCalendar's bundled locales use a Moment-style
 * `week: { dow, doy }` shape, but the public `LocaleInput` TypeScript
 * surface only declares the flat `firstDay` field. We follow the typed
 * surface — this still gives Monday-first week, which is the only thing
 * we care about (`doy`/first-week-of-year only affects rare week-number
 * displays which we don't prominently use).
 */
export const srLatnLocale: LocaleInput = {
  code: "sr-Latn",
  firstDay: 1, // Monday
  buttonText: {
    prev: "Prethodna",
    next: "Sledeća",
    today: "Danas",
    year: "Godina",
    month: "Mesec",
    week: "Nedelja",
    day: "Dan",
    list: "Lista",
  },
  weekText: "Ned",
  allDayText: "Ceo dan",
  moreLinkText(n: number) {
    return `+ još ${n}`
  },
  noEventsText: "Nema događaja za prikaz",
}
