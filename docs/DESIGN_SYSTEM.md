# StudentPlus — Design System

**Verzija:** 1.0 (KORAK 1, 26-04-2026)
**Stack:** Tailwind CSS v4 (zero-config) · Shadcn/ui · next-themes · Inter + JetBrains Mono
**Source of truth fajl:** `frontend/app/globals.css`

> Ovaj dokument je merodavan za vizuelni jezik **StudentPlus** aplikacije. Svaka
> izmena palete, tipografije, spacing-a ili brand pravila prolazi kroz ovaj
> fajl prvo, pa onda u kod.

---

## 1. Brand identitet

### Naziv
**StudentPlus** — uvek jedna reč. „Student" tamno-sivi (`text-foreground`),
„Plus" amber gold (`text-accent`). Bez razmaka, bez spojnice. U logotipu se
ikona-mark renderuje kao PNG iz `frontend/public/branding/`, tekst odvojeno
HTML-om kroz Inter font.

### Logo
- **Mark:** 2 PNG fajla u `frontend/public/branding/`:
  - `logo-mark-light.png` — za light theme + transparentne kontejnere
  - `logo-mark-dark.png` — za dark theme
- **Komponenta:** `frontend/components/shared/logo.tsx` (`<Logo variant="full|mark-only" size="sm|md|lg|xl" />`)
- **Theme switching:** kroz `useTheme()` iz `next-themes` + `mounted` guard protiv FOUC-a
- **Generisane ikone** iz mark-a kroz `npm run generate:icons` (sharp pipeline):
  - `public/icons/icon-{192,512}.png` (transparent — manifest "any" purpose)
  - `public/icons/icon-maskable.png` (512×512, burgundy fill, 80% safe zone)
  - `public/icons/apple-touch-icon.png` (180×180, burgundy fill — iOS ne podržava alpha)
  - `public/icons/favicon-{16,32,48}.png` (transparent)
  - `public/favicon.ico` (multi-layer ili PNG-in-ICO fallback)

---

## 2. Paleta — light theme

Sve vrednosti su **HSL trojke bez wrappera** u `:root` bloku. Tailwind v4
`@theme inline` blok ih wrapuje u `hsl(var(...))` da omogući
`hsl(var(--primary) / 0.5)` alpha trick.

| Token | HSL | Hex (sRGB) | Upotreba |
|---|---|---|---|
| `--primary` | `348 60% 30%` | `#7B1E2C` | Burgundy — glavna brand boja, primary CTA, brand mark fill |
| `--primary-foreground` | `0 0% 100%` | `#FFFFFF` | Tekst preko primary surface-a |
| `--primary-hover` | `348 60% 25%` | `#671623` | Hover state primary dugmadi |
| `--primary-active` | `348 60% 20%` | `#530F1B` | Pressed state |
| `--accent` | `38 76% 57%` | `#E8A93D` | Amber gold — „Plus" u logu, FON badge, hero CTA highlight |
| `--accent-foreground` | `0 0% 10%` | `#1A1A1A` | Tekst preko amber-a |
| `--success` | `142 71% 45%` | `#21BC53` | Approved status, success toast |
| `--warning` | `38 92% 50%` | `#F59E0B` | Strike 1-2/3, deadline warning |
| `--destructive` | `0 72% 51%` | `#DC2626` | Cancel, reject, delete |
| `--info` | `217 91% 60%` | `#3B82F6` | Informativni toast, hint |
| `--background` | `0 0% 100%` | `#FFFFFF` | Page bg |
| `--foreground` | `222 47% 11%` | `#0F172A` | Primary tekst |
| `--muted` | `210 40% 96%` | `#F1F5F9` | Sekundarne kartice, table row hover |
| `--muted-foreground` | `215 16% 47%` | `#64748B` | Sekundarni tekst, placeholder |
| `--border` | `214 32% 91%` | `#E2E8F0` | Subtle separator |
| `--ring` | `348 60% 30%` | `#7B1E2C` | Focus ring (a11y) |
| `--faculty-fon` | `38 76% 57%` | `#E8A93D` | FON badge |
| `--faculty-etf` | `348 60% 30%` | `#7B1E2C` | ETF badge |

**WCAG kontrasti (acceptance):**
- Burgundy `#7B1E2C` na beloj `#FFFFFF` → **9.4:1** (AAA)
- Amber `#E8A93D` na tamno-sivom `#1A1A1A` → **8.1:1** (AAA)
- Muted text `#64748B` na `#FFFFFF` → **4.69:1** (AA za normal text)

---

## 3. Paleta — dark theme

Burgundy je desaturisan i osvetljen (lakši za oči noću), amber softer.
Pozadina je deep navy `#050816` — kontrastnija od neutralne sive,
podržava brand identitet.

| Token | HSL | Hex (sRGB) |
|---|---|---|
| `--primary` | `348 50% 50%` | `#B0405A` |
| `--accent` | `38 65% 65%` | `#F4C56A` |
| `--background` | `222 47% 5%` | `#050816` |
| `--foreground` | `210 40% 96%` | `#F1F5F9` |
| `--card` | `222 35% 8%` | `#0E1424` |
| `--muted` | `222 25% 12%` | `#181D2C` |
| `--border` | `222 25% 18%` | `#252C42` |

---

## 4. Tipografija

**Inter** za sve text utility-je. **JetBrains Mono** rezerviše `--font-mono`
za inline code u FAQ-u (KORAK 6).

```ts
// frontend/app/layout.tsx
const inter = Inter({
  subsets: ["latin", "latin-ext"],   // latin-ext za š/č/ć/ž/đ
  display: "swap",
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
})
```

Hijerarhija (Tailwind utility):

| Klasa | Upotreba |
|---|---|
| `text-4xl font-bold` | Page title (`<h1>`) |
| `text-2xl font-semibold` | Section heading (`<h2>`) |
| `text-lg font-medium` | Card title (`<h3>`) |
| `text-base` | Body text (default) |
| `text-sm` | Sekundarni tekst, table cells |
| `text-xs font-medium uppercase tracking-wide` | Labels, badges |
| `font-mono text-sm` | Inline code (FAQ) |

---

## 5. Spacing, radius, shadow

- **Default gap:** 12-16px (`gap-3` / `gap-4`) — kompaktna data-heavy app
- **Border radius:**
  - `rounded-md` (8px) — dugmad, input-i, badges
  - `rounded-xl` (12px) — kartice, modali
  - `rounded-lg` (10px) — popoveri, dropdown sadržaj
- **Shadow:**
  - `shadow-sm` — subtle elevation (cards default)
  - `shadow-md` — popovers, floating panels
  - Hover lift na karticama: `hover:shadow-[0_4px_12px_hsl(var(--primary)/0.15)]` (KORAK 3)

Definisano u `globals.css`:
```css
--radius-sm: calc(var(--radius) - 4px);   /*  4px */
--radius-md: calc(var(--radius) - 2px);   /*  6px */
--radius-lg: var(--radius);               /*  8px */
--radius-xl: calc(var(--radius) + 4px);   /* 12px */
```

---

## 6. Tailwind v4 lock-in

- **NEMA `tailwind.config.ts`.** v4 koristi zero-config auto-detection content-a
  i očekuje da sve teme budu deklarisane u CSS kroz `@theme inline` blok.
- Vraćanje `tailwind.config.ts` će biti **tiho ignorisano** od strane Lightning CSS-a — utility klase neće biti generisane.
- Svaki novi `--color-*` mora biti dodat u TRI mesta:
  1. `:root { --new-token: ... }` (HSL trojka, light)
  2. `.dark { --new-token: ... }` (HSL trojka, dark)
  3. `@theme inline { --color-new-token: hsl(var(--new-token)) }` (Tailwind utility mapping)

Detalji o v3→v4 migraciji su u `docs/FRONTEND_STRUKTURA.md` §8.1.

---

## 7. Theme switching

- **Provider:** `ThemeProvider` iz `next-themes` u `frontend/app/providers.tsx`
- **Default:** `system` (poštuje OS preference)
- **Storage key:** `studentplus-theme` (localStorage)
- **HTML class:** `class="dark"` na `<html>` kad je dark aktivan
- **Body transition:** `200ms ease` na `background-color` + `color` (smooth swap, ne flicker)
- **FOUC guard:** `<html class="no-transitions">` se uklanja inline script-om u `<head>` čim je document interactive — sprečava da se prvi paint animira
- **Logo PNG swap:** `useTheme().resolvedTheme` + `mounted` state machine — pre hidracije renderuje neutralni placeholder

UI: `<ThemeToggle />` u `components/shared/theme-toggle.tsx` — DropdownMenuSub
sa Light / Dark / System opcijama, integrisan u `<UserMenu />`.

---

## 8. Reduced motion

`globals.css` ima globalni `@media (prefers-reduced-motion: reduce)` koji
postavlja `animation-duration: 0.01ms` + `transition-duration: 0.01ms` na
**sve** elemente. UI ostaje funkcionalan (klikabilan), ali vizuelni
feedback je instant umesto animiran.

KORAK 9 (framer-motion) sloji dodatnu logiku iznad ove osnove — varijante
se prosleđuju `reducedMotion="user"` propu.

---

## 9. Manifest + favicon

- `public/manifest.json` — `name: "StudentPlus"`, `short_name: "StudentPlus"`, `theme_color: #7B1E2C`, `background_color: #FFFFFF`, 4 ikone
- `public/favicon.ico` — multi-layer (16+32+48) ili PNG-in-ICO fallback (Sharp 0.34 ICO encoder ne postoji u WASM build-u)
- `app/layout.tsx` `<link rel="icon">` referencira `favicon-16.png` i `favicon-32.png`
- iOS: `apple-touch-icon.png` 180×180 sa burgundy fill-om (iOS Safari ignoriše alfu)

PWA viewport `theme_color`:
- Light: `#7B1E2C` (burgundy — vidi se u browser tab strip-u na Androidu)
- Dark: `#050816` (deep navy)

---

## 10. Brand audit pravila

Globalni naziv aplikacije je **strogo** „StudentPlus". Sledeće pojmove NE
smatramo brand-om i ne menjamo ih:

- `"Studentska služba"` — institucionalna referenca u realnom svetu
- `roleLabel("STUDENT")` = `"Student"` — rola, ne brand
- `student.fon.bg.ac.rs`, `etf.bg.ac.rs` itd. — domeni email validacije
- `"FON"` / `"ETF"` u kontekstu fakulteta — referenca na realne entitete

Pre svake izmene koja menja brand naziv: `rg "Konsultacije FON|FON & ETF Platforma|Studentska Platforma FON" frontend/ backend/` mora vratiti 0 hitova kao acceptance.

---

*Dokument se ažurira kad god se promeni paleta, tipografija ili brand pravilo. Verzioniše se u istom commit-u kao izmena `globals.css`.*
