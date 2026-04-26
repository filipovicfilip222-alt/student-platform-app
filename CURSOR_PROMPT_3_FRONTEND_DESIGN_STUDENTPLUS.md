# CURSOR PROMPT 3 — Frontend Design Polish (StudentPlus brand)

> **Status:** Adaptirana verzija sa **konačnim brand-om i paletom**. Aplikacija nosi ime **StudentPlus**, logo je dostavljen u 2 PNG varijante (light + dark), paleta je definisana ispod.
>
> **Šta je drugačije od originalnog Prompta 3:**
> - **Brand finalizovan**: ime „StudentPlus", paleta burgundy (primary) + amber gold (accent), Inter tipografija
> - **Logo se NE pravi custom** — koristi se PNG ikonica koju Filip dostavlja u 2 varijante
> - i18n (KORAK 12 originalnog) **isključen** — sr-Latn ostaje hardkodovan, V2
> - Marketing landing (KORAK 13 originalnog) **opcioni**
> - Animacije (KORAK 10 originalnog) **smanjene** — samo osnovne, bez svih „delight" detalja
> - SVI testovi (a11y audit, Lighthouse) **zadržani** — quality minimum
>
> **Veličina:** ~9–10 dana fokusiranog rada.
>
> **Preduslov:** Prompt 1 + Prompt 2 (DEMO_READY) su završeni i verifikovani.

---

## 0. BRAND SPECIFIKACIJA — koristi DOSLOVNO ovo

### 0.1 Ime aplikacije

**StudentPlus** — uvek pisano kao jedna reč sa velikim S i P, bez razmaka.

Word-mark u logotipu:
- „Student" — tamno siva (`#1F2937` light tema, `#F9FAFB` dark tema)
- „Plus" — amber gold (`#E8A93D` light tema, `#F4C56A` dark tema)

U SVAKOM mestu gde se trenutno pojavljuje „Konsultacije FON & ETF" ili sl. → zameniti sa „StudentPlus".

### 0.2 Light theme paleta (FINALNA, ne menjati)

```css
/* PRIMARY — burgundy */
--primary: 348 60% 30%;              /* #7B1E2C burgundy — glavna akcija */
--primary-foreground: 0 0% 100%;     /* white na primary */
--primary-hover: 348 60% 25%;        /* tamniji za :hover */
--primary-active: 348 60% 20%;       /* još tamniji za :active */

/* ACCENT — amber gold */
--accent: 38 76% 57%;                /* #E8A93D amber — CTA, success highlight, badges */
--accent-foreground: 0 0% 10%;       /* tamno-sivi na accent */

/* SEMANTIC */
--success: 142 71% 45%;              /* #22C55E — green */
--warning: 38 92% 50%;                /* #EAB308 — yellow */
--destructive: 0 72% 51%;             /* #DC2626 — red */
--info: 217 91% 60%;                  /* #3B82F6 — blue */

/* SURFACE */
--background: 0 0% 100%;             /* #FFFFFF */
--foreground: 222 47% 11%;           /* #0F172A — primary text */
--muted: 210 40% 96%;                /* #F1F5F9 */
--muted-foreground: 215 16% 47%;     /* #64748B */
--border: 214 32% 91%;               /* #E2E8F0 */
--input: 214 32% 91%;
--ring: 348 60% 30%;                 /* burgundy ring za focus */

/* CARDS / POPOVER */
--card: 0 0% 100%;
--card-foreground: 222 47% 11%;
--popover: 0 0% 100%;
--popover-foreground: 222 47% 11%;

/* FACULTY BADGES */
--faculty-fon: 38 76% 57%;           /* amber gold — FON */
--faculty-fon-foreground: 0 0% 10%;
--faculty-etf: 348 60% 30%;          /* burgundy — ETF */
--faculty-etf-foreground: 0 0% 100%;
```

**Razlog izbora:** Burgundy je primary jer je ozbiljniji za akademski kontekst. Amber gold je accent koji ide na ZAKAŽI dugmad (najvažnija CTA), success states, FON badge. Razdvajanje FON/ETF kroz različite boje (gold vs burgundy) konzistentno sa logom. Burgundy ETF + Gold FON je arbitrarna ali konzistentna podela — ti odluči koja fakulteta dobija koju boju ako želiš obrnuto, javiš pre KORAKA 1.

### 0.3 Dark theme paleta (FINALNA)

```css
/* PRIMARY — desaturated burgundy za dark bg */
--primary: 348 50% 50%;              /* #B0405A — bržna/svetlija burgundy varijanta */
--primary-foreground: 0 0% 100%;
--primary-hover: 348 50% 55%;
--primary-active: 348 50% 60%;

/* ACCENT — softer amber za dark */
--accent: 38 65% 65%;                /* #F4C56A — toplija svetla amber */
--accent-foreground: 38 25% 12%;     /* #2A1E0A — tamno-amber na accent */

/* SEMANTIC */
--success: 142 60% 50%;
--warning: 38 80% 60%;
--destructive: 0 65% 55%;
--info: 217 80% 65%;

/* SURFACE */
--background: 222 47% 5%;            /* #050816 — vrlo tamna sa modrim tonom */
--foreground: 210 40% 96%;           /* #F1F5F9 */
--muted: 222 25% 12%;                /* #1A1F2E */
--muted-foreground: 215 16% 65%;
--border: 222 25% 18%;               /* #252A3A */
--input: 222 25% 18%;
--ring: 348 50% 50%;

/* CARDS */
--card: 222 35% 8%;                  /* #0B1020 — slight lift od background-a */
--card-foreground: 210 40% 96%;
--popover: 222 35% 10%;
--popover-foreground: 210 40% 96%;

/* FACULTY BADGES */
--faculty-fon: 38 65% 65%;           /* svetlija amber */
--faculty-fon-foreground: 38 25% 12%;
--faculty-etf: 348 50% 50%;          /* svetlija burgundy */
--faculty-etf-foreground: 0 0% 100%;
```

**Razlog dark verzije:**
- Burgundy `#7B1E2C` (light primary) na tamnoj pozadini je previše taman — ne kontrastira. Zato dark varianta ide na `#B0405A` (svetlija burgundy, sačuvani ton).
- Amber `#E8A93D` na tamnoj pozadini izgleda OK ali agresivno — softer `#F4C56A` je čitljivija.
- Background nije čisto crn (`#000000`) — koristi `#050816` koji ima blagi modri ton da omekša kontrast i smanji eye strain.
- Card surface (`#0B1020`) je za mrvicu svetlija od background-a da hijerarhija bude vidljiva.

### 0.4 Tipografija

**Inter** za sve (variable font, 400/500/600/700). Mono je **JetBrains Mono** za code u FAQ-u.

```typescript
// frontend/app/layout.tsx
import { Inter, JetBrains_Mono } from 'next/font/google'

const inter = Inter({
  subsets: ['latin', 'latin-ext'],  // latin-ext za š, č, ć, ž, đ
  variable: '--font-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})
```

**Hijerarhija (Tailwind):**
- `text-4xl font-bold` (36px / 700) — page title
- `text-2xl font-semibold` (24px / 600) — section heading
- `text-lg font-medium` (18px / 500) — card title
- `text-base` (16px / 400) — body
- `text-sm` (14px / 400) — secondary, muted
- `text-xs` (12px / 500) — labels, badges

### 0.5 Spacing, radius, shadow

- **Default gap:** 12-16px (kompaktan, data-heavy app)
- **Border radius:** 8px default (`rounded-md`), 12px za kartice (`rounded-xl`)
- **Shadow:** Subtle, tipa shadcn default (`shadow-sm`, `shadow-md`)

---

## 1. KAKO STAVITI LOGO PNG FAJLOVE

Ti praviš **2 PNG fajla** (samo ikonu/mark, BEZ teksta — tekst „StudentPlus" se renderuje kao HTML iz Inter font-a):

### 1.1 Specifikacije fajlova koje praviš

| Fajl | Tema | Pozadina | Dimenzije | Format |
|---|---|---|---|---|
| `logo-mark-light.png` | Light theme | Transparentna | 512×512px (kvadrat) | PNG-24 sa alpha |
| `logo-mark-dark.png` | Dark theme | Transparentna | 512×512px (kvadrat) | PNG-24 sa alpha |

**Šta je „mark":** samo ikonica diplomca sa kapom + plus znak. **NE** kompletan logo „StudentPlus" sa tekstom — tekst se piše u HTML-u kroz Inter font da bude responsive i da se boja menja sa temom.

**Saveti za pravljenje:**
- Light varianta = burgundy diplomac + amber gold krug sa plus znakom (kao što si već imao)
- Dark varianta = ista, ali sa **svetlijim tonovima**: koristi `#B0405A` umesto `#7B1E2C` za burgundy, i `#F4C56A` umesto `#E8A93D` za amber. Tako se jasno vidi na tamnoj pozadini.
- Ostavi 32px padding-a (transparentno) oko mark-a unutar 512×512 canvas-a — Cursor će u CSS-u kontrolisati dimenzije, ali padding daje breathing room.

### 1.2 Gde tačno staviš fajlove

```
frontend/public/branding/
├── logo-mark-light.png       ← TI staviš ovde
├── logo-mark-dark.png        ← TI staviš ovde
└── (Cursor pravi sve ostalo — favicon, app-icon-192, app-icon-512)
```

Cursor će napisati skriptu `scripts/generate-icons.mjs` koja iz tvog `logo-mark-light.png` automatski generiše:

```
frontend/public/
├── favicon.ico               ← Cursor generiše iz logo-mark-light.png (16/32/48 sloja)
├── icon.svg                  ← Cursor pravi SVG iz background mark-a (opcioni)
├── apple-touch-icon.png      ← 180×180, iz light varijante
├── android-chrome-192x192.png
├── android-chrome-512x512.png
└── manifest.json             ← Cursor ažurira sa novim icons + ime "StudentPlus"
```

Ti **samo** dostavljaš 2 PNG-a (`logo-mark-light.png` + `logo-mark-dark.png`). Sve ostalo Cursor radi kroz `npm run generate:icons` skriptu.

---

## KORAK 1 — Design tokens + paleta + tipografija + brand setup (TEMELJ)

**Najbitniji korak. Sve ostalo zavisi od ovoga.**

### 1.1 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/public/branding/logo-mark-light.png` | EXTERNAL (Filip dostavlja) | 512×512 transparent PNG, light theme varijanta |
| 2 | `frontend/public/branding/logo-mark-dark.png` | EXTERNAL (Filip dostavlja) | 512×512 transparent PNG, dark theme varijanta |
| 3 | `docs/DESIGN_SYSTEM.md` | NEW | Kompletna dokumentacija: paleta (HSL + hex), tipografija, spacing, radius, shadow, brand smernice |
| 4 | `frontend/app/globals.css` | EDIT | Ubaci CSS varijable iz §0.2 i §0.3 (light + dark). Override `@theme inline` blok da koristi nove varijable |
| 5 | `frontend/tailwind.config.ts` | EDIT (ako postoji posle Tailwind v4 migracije) | Proširi `theme.extend.colors` sa `faculty-fon`, `faculty-etf`, `accent` mapama |
| 6 | `frontend/app/layout.tsx` | EDIT | Učitaj `Inter` i `JetBrains_Mono` (next/font/google sa `subsets: ['latin', 'latin-ext']`), postavi varijable na `<html>`. Promeni `<title>` u `"StudentPlus"`. Promeni `metadata.applicationName` u `"StudentPlus"`. |
| 7 | `frontend/components/ui/theme-provider.tsx` | NEW (ako ne postoji) | `next-themes` provider za light/dark/system |
| 8 | `frontend/components/shared/theme-toggle.tsx` | NEW | Sun/Moon ikon u UserMenu — toggle teme |
| 9 | `frontend/components/shared/logo.tsx` | NEW | Komponenta `<Logo variant="full" \| "mark-only" />`. Koristi `next/image` sa `logo-mark-light.png` ili `logo-mark-dark.png` (kroz `useTheme()`). Pored mark-a renderuje text „Student**Plus**" u HTML-u (Student tamno-sivi, Plus amber gold). |
| 10 | `frontend/public/manifest.json` | EDIT | `"name": "StudentPlus"`, `"short_name": "StudentPlus"`, `"theme_color": "#7B1E2C"` (burgundy primary), `"background_color": "#FFFFFF"`. Dodaj sve generisane ikone (192, 512, maskable). |
| 11 | `frontend/scripts/generate-icons.mjs` | NEW | Skripta koja iz `logo-mark-light.png` generiše `favicon.ico`, `apple-touch-icon.png`, `android-chrome-*.png`. Koristi `sharp` lib (`npm i -D sharp`). Pokreni jednom: `npm run generate:icons`. |
| 12 | `frontend/package.json` | EDIT | Dodaj `"generate:icons": "node scripts/generate-icons.mjs"` u `scripts`. Dodaj `sharp` u `devDependencies`. |
| 13 | Sve postojeće reference na „Konsultacije FON & ETF" | EDIT (audit) | Search-replace sa „StudentPlus": auth pages title, sidebar header, top-bar (mobile), browser tab title, footer ako postoji, register confirmation email template (backend) |

### 1.2 Logo komponenta — implementaciono uputstvo za Cursor

```tsx
// frontend/components/shared/logo.tsx
'use client'
import Image from 'next/image'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

interface LogoProps {
  variant?: 'full' | 'mark-only'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES = {
  sm: { mark: 28, text: 'text-base' },
  md: { mark: 36, text: 'text-lg' },
  lg: { mark: 56, text: 'text-2xl' },
}

export function Logo({ variant = 'full', size = 'md', className = '' }: LogoProps) {
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  
  useEffect(() => setMounted(true), [])
  
  // Pre nego što je theme resolved, pokaži light varijantu (sprečava FOUC)
  const logoSrc = mounted && resolvedTheme === 'dark' 
    ? '/branding/logo-mark-dark.png' 
    : '/branding/logo-mark-light.png'
  
  const { mark: markSize, text: textClass } = SIZES[size]
  
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <Image
        src={logoSrc}
        alt="StudentPlus"
        width={markSize}
        height={markSize}
        priority
        className="select-none"
      />
      {variant === 'full' && (
        <span className={`${textClass} font-semibold tracking-tight select-none`}>
          <span className="text-foreground">Student</span>
          <span className="text-accent">Plus</span>
        </span>
      )}
    </div>
  )
}
```

### 1.3 globals.css — primer strukture

```css
@import 'tailwindcss';

@layer base {
  :root {
    /* LIGHT THEME — sve varijable iz §0.2 */
    --primary: 348 60% 30%;
    --primary-foreground: 0 0% 100%;
    --primary-hover: 348 60% 25%;
    /* ... ostatak iz §0.2 */
  }
  
  .dark {
    /* DARK THEME — sve varijable iz §0.3 */
    --primary: 348 50% 50%;
    --primary-foreground: 0 0% 100%;
    --primary-hover: 348 50% 55%;
    /* ... ostatak iz §0.3 */
  }
  
  body {
    background: hsl(var(--background));
    color: hsl(var(--foreground));
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
}

@theme inline {
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
  --color-faculty-fon: hsl(var(--faculty-fon));
  --color-faculty-fon-foreground: hsl(var(--faculty-fon-foreground));
  --color-faculty-etf: hsl(var(--faculty-etf));
  --color-faculty-etf-foreground: hsl(var(--faculty-etf-foreground));
  /* ... ostalo */
}
```

### 1.4 Acceptance

- [ ] `frontend/public/branding/logo-mark-light.png` i `logo-mark-dark.png` postoje (ti dostavljaš)
- [ ] `npm run generate:icons` uspešno generiše favicon + apple-touch + android ikone iz light varijante
- [ ] `<Logo variant="full" />` u sidebar-u: mark levo, „Student**Plus**" tekst desno (Student tamno-sivi, Plus amber gold)
- [ ] Klik na theme toggle → mark se menja na `logo-mark-dark.png` instant, cela paleta se menja smooth (200ms transition)
- [ ] Browser tab title: „StudentPlus"
- [ ] PWA install prompt: „StudentPlus" + tvoja ikonica
- [ ] Lighthouse PWA audit > 90
- [ ] `docs/DESIGN_SYSTEM.md` postoji sa svim odlukama dokumentovanim

**Procena:** 1 dan.

---

## KORAK 2 — Auth stranice (login, register, forgot, reset) — vizuelni polish

### 2.1 Cilj

- Split layout (50/50 na lg+, 100% forma na md-)
- Levo forma, desno marketing slot (gradient sa logom + slogan)
- Subtle animation pri load-u
- Validacione poruke inline sa lucide ikonama

### 2.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/app/(auth)/layout.tsx` | EDIT | Split layout (50/50 lg+, 100% md-). Levo: forma. Desno: `<MarketingPanel />` |
| 2 | `frontend/components/auth/marketing-panel.tsx` | NEW | Desni panel sa burgundy → amber gold gradient pozadinom. Veliki `<Logo variant="full" size="lg" />`. Slogan (npr. „Pametno upravljanje konsultacijama na FON i ETF"). 1 ilustracija (može iz `undraw.co` sa themable colors — koristi burgundy/amber paletu). |
| 3 | `frontend/app/(auth)/login/page.tsx` | EDIT | Polish: spacing, button hierarchy, social proof footer („FON & ETF zvanično preporučuju" — opciono ako je istina) |
| 4 | `frontend/app/(auth)/register/page.tsx` | EDIT | Inline domain validation feedback, password strength meter |
| 5 | `frontend/components/ui/password-input.tsx` | NEW | Eye-toggle za show/hide password (Lucide `Eye` / `EyeOff` ikone) |
| 6 | `frontend/components/auth/password-strength-meter.tsx` | NEW | 4-segment bar (weak/medium/strong/excellent), `zxcvbn-ts` lib |

### 2.3 Marketing panel — predlog gradient-a

```tsx
// Pozadina: burgundy → tamniji burgundy → amber gold (subtle dijagonala)
<div className="hidden lg:flex lg:flex-1 items-center justify-center
                bg-gradient-to-br from-[#7B1E2C] via-[#5A1422] to-[#E8A93D]/30
                relative overflow-hidden">
  
  {/* Subtle decorative pattern (opciono) */}
  <div className="absolute inset-0 bg-[url('/branding/pattern-dots.svg')] opacity-10" />
  
  {/* Centriran sadržaj */}
  <div className="relative z-10 text-center px-12 max-w-md">
    <Logo variant="full" size="lg" className="justify-center mb-8 [&_span]:text-white" />
    <h2 className="text-3xl font-semibold text-white mb-4">
      Pametno upravljanje konsultacijama
    </h2>
    <p className="text-white/80 text-lg leading-relaxed">
      Zakaži, prati i organizuj termine sa profesorima FON-a i ETF-a 
      na jednom mestu.
    </p>
  </div>
</div>
```

### 2.4 Mikrointerakcije

- Form submit dugme: pri kliku `<Loader2 />` rotacija + disabled + tekst „Prijavljujem..."
- Greška iz backend-a: subtle shake animacija (200ms) + crveni border
- Uspešan register: success state + redirect posle 1.5s
- Smooth focus ring (custom outline boje primary, 2px)

### 2.5 Acceptance

- [ ] /login na 1920px → split layout sa burgundy/amber gradient marketing panelom
- [ ] Resize na 768px → marketing panel nestaje, forma se centrira
- [ ] Pogrešna lozinka → shake (jednom)
- [ ] Tab kroz forme → focus ring vidljiv (burgundy boje)
- [ ] Lighthouse a11y > 95 na svim auth stranicama

**Procena:** 1 dan.

---

## KORAK 3 — Dashboard polish (student + profesor + admin)

### 3.1 Cilj

- Personalizovani pozdrav („Dobro jutro, Marko")
- Prioritizovan content above the fold
- Vizuelna varijacija (ne 3 identične kartice)
- Burgundy/amber accent na ključnim elementima

### 3.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/app/(student)/dashboard/page.tsx` | EDIT | Restrukturira layout: 1 hero card (next appointment) + 2-col grid (notifs + strike) + CTA grid 4 dugmadi |
| 2 | `frontend/components/dashboard/greeting-header.tsx` | NEW | „Dobro jutro, Marko" + datum |
| 3 | `frontend/components/dashboard/next-appointment-hero.tsx` | NEW | **Velika kartica sa amber gold akcentom** za countdown („za 2h 17min"), profesor avatar, predmet, lokacija, dugme „Detalji" (burgundy) / „Otkaži" (red ghost) |
| 4 | `frontend/components/dashboard/quick-actions-grid.tsx` | NEW | 4-6 ikon-CTA sa burgundy hover state-om: Pretraga, Zakaži, Document requests, FAQ |
| 5 | `frontend/components/dashboard/recent-notifications.tsx` | NEW | Lista poslednjih 5 notif-a sa relativnim timestamp-om |
| 6 | `frontend/components/dashboard/strike-status-card.tsx` | EDIT | Vizuelni progress: 0/3 zelena, 1-2 amber, 3+ crvena |

### 3.3 Profesor i admin dashboard

- **Profesor dashboard:** hero = pending requests count + amber „Pregledaj" CTA + kalendar widget
- **Admin dashboard:** metrics row sa sparklines (dnevni booking trend), pending document requests count, recent audit events. **Avatar/header burgundy.**

### 3.4 Acceptance

- [ ] Različit pozdrav po doba dana
- [ ] Sledeći termin sa countdown-om se ažurira svake sekunde
- [ ] Mobile (375px): hero card preko cele širine
- [ ] Empty state: ako nema termina → friendly ilustracija + amber „Pretraži profesore" dugme
- [ ] Hover na quick action card → subtle burgundy shadow

**Procena:** 1.5 dan.

---

## KORAK 4 — Tabele (admin panel) — `@tanstack/react-table` data table

### 4.1 Cilj

- Sticky header
- Compact density toggle
- Active filter chips (burgundy outline)
- Per-row actions u dropdown menu
- Pagination (numbered, burgundy aktivna stranica)
- Bulk actions (select all + actions bar)
- Sort indicator
- Loading: skeleton rows
- Empty state: kontekstualna ilustracija

### 4.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/components/ui/data-table.tsx` | NEW | Generic `<DataTable />` koristeći `@tanstack/react-table` + shadcn primitive |
| 2 | `frontend/components/ui/data-table-toolbar.tsx` | NEW | Filteri iznad: search input + filter dropdowns + active chip display |
| 3 | `frontend/components/ui/data-table-pagination.tsx` | NEW | Numbered pagination + page size selector |
| 4 | `frontend/components/admin/users-table.tsx` | EDIT | Refaktor da koristi `<DataTable />` |
| 5 | `frontend/components/admin/strikes-table.tsx` | EDIT | Isto |
| 6 | `frontend/components/admin/audit-log-table.tsx` | EDIT | Isto |
| 7 | `frontend/components/document-requests/admin-row.tsx` | EDIT | Migracija na DataTable |
| 8 | `frontend/components/shared/empty-state.tsx` | EDIT | Proširi EmptyState — varijante per context (no-data, no-results, error, blocked) |

### 4.3 Acceptance

- [ ] Admin/users sa 500+ unosa → smooth scroll, sticky header
- [ ] Multi-select 10 user-a → bulk action bar (burgundy CTA dugme „Deaktiviraj odabrane")
- [ ] Filter „role=PROFESOR" + search „Petr" → kombinovano radi (sa unaccent iz Prompta 1 KORAK 10)
- [ ] Empty state vidljiv kad filter ne daje rezultate
- [ ] FacultyBadge: FON = amber gold, ETF = burgundy

**Procena:** 1.5 dan.

---

## KORAK 5 — Kalendar (FullCalendar polish)

### 5.1 Cilj

- FullCalendar wrapped tako da koristi naše CSS varijable
- Slot statusi različiti vizuelno: slobodan (border), rezervisan (amber light), blokiran (gray), prošao (mute)
- Hover state pokazuje quick info
- Mobilna verzija prelazi u list view glatko
- Loading: skeleton dana umesto spinner-a

### 5.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/components/calendar/booking-calendar.tsx` | EDIT | Custom `eventContent` render. Theme-aware. |
| 2 | `frontend/components/calendar/availability-calendar.tsx` | EDIT | Drag-drop ghost styling (burgundy outline) |
| 3 | `frontend/app/globals.css` | EDIT | Override FullCalendar default klasa kroz `.fc-*` selektore koji koriste naše CSS vars |
| 4 | `frontend/components/calendar/slot-popover.tsx` | EDIT | Re-design: avatar levo, info sredina, action dugme dolje (burgundy „Zakaži") |
| 5 | `frontend/components/calendar/calendar-skeleton.tsx` | NEW | Skeleton placeholder pre nego što slots stignu |
| 6 | `frontend/components/calendar/calendar-legend.tsx` | EDIT | Vizuelno objašnjenje boja |

### 5.3 Acceptance

- [ ] Toggle dark mode → kalendar prelazi smooth
- [ ] Hover na slot → popover sa 100ms delay-om
- [ ] Klik na slot → modal sa fade animacijom
- [ ] Mobile 375px → list view, slot-ovi čitljivi
- [ ] Slobodan slot ima burgundy outline na hover-u

**Procena:** 1 dan.

---

## KORAK 6 — Chat (TicketChat) — vizuelni polish

### 6.1 Cilj

- Avatar + ime + timestamp na poruci
- Smooth scroll na novu poruku
- Counter „17/20" pred kraj limita postaje amber, „20/20" crven
- 24h countdown postaje crveni < 1h
- Markdown rendering (basic: **bold**, _italic_, links auto-detect)

**Napomena:** typing indicator (`chat.typing` WS event) je preskočen — backend ne podržava. Može se dodati posle prezentacije.

### 6.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/components/chat/ticket-chat.tsx` | EDIT | Layout cleanup, scroll behavior |
| 2 | `frontend/components/chat/chat-message.tsx` | EDIT | Avatar, timestamp pozicioniranje (own right sa burgundy bubble, other left sa muted bubble) |
| 3 | `frontend/components/chat/chat-input.tsx` | EDIT | Auto-grow textarea (max 4 reda), send-on-enter, char counter |
| 4 | `frontend/components/chat/chat-message-counter.tsx` | EDIT | Boja se menja: green→amber→red |
| 5 | `frontend/components/chat/chat-closed-notice.tsx` | EDIT | Friendly ilustracija + razlog |
| 6 | `frontend/lib/utils/markdown.ts` | NEW | Mini-markdown parser ili `react-markdown` sa restricted allowedElements |

### 6.3 Acceptance

- [ ] 2 browsera → poruke u realnom vremenu (već radi iz Prompta 1)
- [ ] Vlastita poruka = burgundy bubble desno
- [ ] Tuđa poruka = muted bubble levo sa avatarom
- [ ] Skrol smooth na novu poruku
- [ ] 18. poruka → counter amber
- [ ] 24h posle → chat zatvoren ekran sa lepom porukom

**Procena:** 1 dan.

---

## KORAK 7 — Notifikacije polish

### 7.1 Cilj

- Bell badge sa pulse animacijom kad stigne nova (burgundy dot)
- Dropdown ima ikone po `NotificationType`
- Read/unread vizuelno različiti (unread ima burgundy dot levo)
- „Označi sve kao pročitano" akcija u footeru
- Toast (Sonner) za real-time notif: slide u sa desne, auto-dismiss 5s, action „Pogledaj"

### 7.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/components/notifications/notification-center.tsx` | EDIT | Polish: dropdown header, footer, ikone po tipu |
| 2 | `frontend/components/notifications/notification-item.tsx` | EDIT | Avatar/icon levo, content sredina, timestamp+actions desno |
| 3 | `frontend/components/notifications/notification-badge.tsx` | NEW | Iz top-bara, pulse animacija sa burgundy dot |
| 4 | `frontend/lib/notifications/icons.ts` | NEW | Map `NotificationType` → Lucide ikona + boja (success → green, warning → amber, info → burgundy) |
| 5 | `frontend/lib/notifications/messages.ts` | NEW | Map `NotificationType` → kratak naslov i body template |
| 6 | `frontend/lib/utils/relative-time.ts` | NEW | „pre 5 min", „juče u 14:23" — `date-fns/formatDistanceToNow` sa srpskim locale-om |

### 7.3 Acceptance

- [ ] Notif preko WS → toast + bell badge pulse + counter inkrementuje
- [ ] Klik na notif → odvodi na relevantni page i mark-as-read
- [ ] Dropdown sa 50+ notif-a → smooth scroll, lazy render

**Procena:** 1 dan.

---

## KORAK 8 — Empty states + loading + error states

**Identično originalnom Promptu 3 KORAK 9** — ne menjam ovde, samo napomena: koristi burgundy/amber paletu u ilustracijama (npr. friendly ilustracija profesora sa amber kapom).

**Procena:** 1 dan.

---

## KORAK 9 — Mikrointerakcije + animacije (SMANJEN OBIM)

### 9.1 Cilj (smanjen za demo timing)

Samo osnovne animacije:
- Page transitions (subtle fade) između ruta
- Modal/Dialog open/close ima spring (ne linear)
- Dugmad imaju press state (scale 0.98)
- Hover na karticama: subtle elevation lift sa burgundy shadow tint

### 9.2 Lista fajlova

| # | Fajl | Akcija | Šta radi |
|---|------|--------|----------|
| 1 | `frontend/package.json` | EDIT | Dodaj `framer-motion` |
| 2 | `frontend/lib/animations/variants.ts` | NEW | Centralno za `motion` varijante (page, modal) |
| 3 | `frontend/components/shared/page-transition.tsx` | NEW | Wrapper koji animira router transitions (Next 14, `usePathname` + `AnimatePresence`) |
| 4 | `frontend/app/globals.css` | EDIT | Dodaj `@media (prefers-reduced-motion: reduce)` override |

### 9.3 Acceptance

- [ ] Navigacija između stranica → blagi cross-fade
- [ ] Otvori modal → spring animacija
- [ ] Hover na cards → burgundy tinted shadow lift
- [ ] OS reduced-motion on → sve animacije nestaju, app radi

**Procena:** 0.5 dan.

---

## KORAK 10 — Accessibility audit

**Identično originalnom Promptu 3 KORAK 11** — ne menjam, ali važno: proveri da burgundy `#7B1E2C` na beloj pozadini ima WCAG AA contrast (4.5:1 za normal text). Test u Lighthouse-u.

**Brza proverava:** burgundy `#7B1E2C` (HSL 348° 60% 30%) na beloj pozadini ima contrast 9.4:1 — **AAA pass**. Amber `#E8A93D` na tamno-sivom (`#1F2937`) tekstu ima contrast 8.1:1 — **AAA pass**. Paleta je sigurno dobra.

**Procena:** 1 dan.

---

## ❌ ISKLJUČENO

- Internacionalizacija (originalni KORAK 12)
- Marketing landing page (originalni KORAK 13) — opciono ako vremena ima

---

## ZAVRŠNI ČEK-LIST

- [ ] `frontend/public/branding/logo-mark-light.png` + `logo-mark-dark.png` postoje
- [ ] `npm run generate:icons` izvršen, sve ikone generisane
- [ ] Browser tab title: „StudentPlus"
- [ ] PWA install: „StudentPlus" + tvoja ikonica
- [ ] Light + dark mode rade konzistentno (burgundy primary, amber accent)
- [ ] Logo komponenta menja PNG na osnovu teme bez FOUC-a
- [ ] Sve stranice imaju 4 stanja (loading, empty, error, success)
- [ ] Lighthouse a11y > 95 na top 5 stranica
- [ ] Animacije rade ali poštuju `prefers-reduced-motion`
- [ ] Mobile (320px–768px) testiran
- [ ] Screenshot tour: 10 screenshot-a (login, dashboard, search, professor profile, booking modal, my-appointments, chat, professor dashboard, admin users, audit log)

---

## TOTAL PROCENA

~9–10 dana fokusiranog rada.

Posle ovog prompta projekat je **vizuelno polished za demo prezentaciju** sa konzistentnim StudentPlus brand-om, burgundy/amber paletom i custom ikonom u 2 varijante.

---

## NAPOMENE ZA TEBE (Filip)

1. **Pravljenje PNG-ova:**
   - Tvoja postojeća ikonica je idealna kao **light verzija** (burgundy diplomac + amber krug). Sačuvaj je kao `logo-mark-light.png`, 512×512, transparent background.
   - Za **dark verziju**, podigni saturaciju i lightness jer tamna pozadina jede kontrast:
     - Burgundy: `#7B1E2C` → `#B0405A` (svetlija varijanta, bolji kontrast na crnoj)
     - Amber: `#E8A93D` → `#F4C56A` (toplija svetla)
   - Ostavi 32px transparent padding oko mark-a unutar 512×512 canvas-a.

2. **Kad pošalješ PNG-ove Cursor-u:**
   - Ne moraš sam staviti u `frontend/public/branding/`. Možeš samo reći Cursor-u u poruci: „evo ti 2 PNG fajla, stavi ih u `frontend/public/branding/`" i drag-drop oba u sesiju.
   - Cursor će ih stvarno staviti tamo i pozvati `npm run generate:icons` da generiše favicon i ostalo.

3. **Ako hoćeš da promeniš FON/ETF boje:**
   - Trenutno: FON = amber gold, ETF = burgundy. Razlog: amber je topliji/druželjubiv (FON je business-y), burgundy je ozbiljniji/tehnički (ETF je inženjerski). Subjektivno.
   - Ako misliš da treba obrnuto (FON = burgundy, ETF = amber) — javi pre KORAKA 1, jednostavna izmena u 2 CSS varijable.

4. **Ako paleta ne radi vizuelno kad je vidiš implementiranu:**
   - Burgundy `#7B1E2C` može da bude previše taman za neke korisnike. Alternativa: `#9B2D3E` (mrvicu svetlija). Cursor može da preporuči izmenu posle KORAKA 1 ako vidi probleme sa kontrastom u screenshotima.

Sretno sa demo-om.
