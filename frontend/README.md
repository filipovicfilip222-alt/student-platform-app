# StudentPlus — Frontend

Next.js 14 (App Router) frontend za **StudentPlus**, platformu za
zakazivanje konsultacija između studenata i profesora FON-a i ETF-a.
Ovaj README pokriva samo razvojni flow frontenda. Opšti pregled arhitekture je u
[`../CLAUDE.md`](../CLAUDE.md) i [`../docs/`](../docs/).

## Tech stack

| Sloj | Biblioteka |
|------|------------|
| Runtime | Next.js 14 App Router, React 18 |
| Jezik | TypeScript (strict) |
| Styling | Tailwind CSS + shadcn/ui (Radix primitive) |
| State (klijent) | Zustand |
| State (server) | TanStack Query v5 |
| Forme | react-hook-form + zod |
| HTTP | axios (sa JWT refresh queue iz `lib/api.ts`) |
| Kalendar | FullCalendar (timegrid / daygrid / interaction) |
| PWA | `@ducanh2912/next-pwa` (workbox runtime caching) |
| E2E | Playwright (chromium + Pixel 5) |

## Prerequisites

- Node.js **20.x LTS** (Playwright + sharp očekuju stabilnu verziju).
- Backend servis koji radi na `http://localhost:8000` za kompletnu
  funkcionalnost. Videti [`../backend/README`](../backend).
- (Opcionalno za E2E) seed-ovani DB, videti [`e2e/README.md`](./e2e/README.md).

## Quickstart

```bash
npm install
cp .env.example .env      # ako još ne postoji — videti "Environment"
npm run dev
# aplikacija → http://localhost:3000
```

## Environment

Frontend čita sledeće env varijable u vreme build-a / runtime-a:

| Varijabla | Default | Opis |
|-----------|---------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Base URL backend API-ja. Koristi ga axios i E2E fixture-i. |
| `NEXT_PUBLIC_APP_ENV` | `development` | Čita se u debug UI-ju gde je relevantno. |

U produkciji dodatno:

| Varijabla | Primer | Razlog |
|-----------|--------|--------|
| `NEXT_PUBLIC_API_URL` | `https://api.konsultacije.example/api/v1` | Backend iza nginx-a. |
| `NEXT_PUBLIC_APP_ENV` | `production` | Skriva dev-only info. |
| `NEXTJS_NODE_OPTIONS` | `--max-old-space-size=2048` | Ako build-uje se u ograničenom RAM kontejneru. |

`.env*` fajlovi su u `.gitignore`. **Nikad ne commit-uj pravi `.env`.**

## Scripts

```bash
npm run dev             # next dev (port 3000)
npm run build           # next build (+ next-pwa generiše sw.js, workbox-*.js)
npm run start           # produkcijski server
npm run lint            # ESLint (next/core-web-vitals config)
npm run typecheck       # tsc --noEmit
npm run generate:icons  # regeneriši PWA ikone (scripts/generate-icons.mjs)
npm run test:e2e        # Playwright E2E (chromium + mobile-chrome)
npm run test:e2e:ui     # Playwright UI mode
npm run test:e2e:headed # Headed browser za debug
```

## Project structure

Detaljan pregled je u [`../docs/FRONTEND_STRUKTURA.md`](../docs/FRONTEND_STRUKTURA.md).
Skraćena verzija:

```
frontend/
├── app/                       # App Router rute
│   ├── (auth)/               # public: login, register, forgot/reset
│   ├── (student)/            # STUDENT role
│   ├── (professor)/          # PROFESOR + ASISTENT
│   ├── (admin)/              # ADMIN
│   ├── layout.tsx            # root layout + metadata + PWA meta
│   ├── providers.tsx         # TanStack Query, Toaster, NotificationStream
│   └── page.tsx              # root → redirect na /login (middleware obrađuje auth)
├── components/
│   ├── ui/                   # shadcn/ui (ne menjati)
│   ├── shared/               # AppShell, Sidebar, TopBar, UserMenu, OfflineIndicator, …
│   ├── calendar/             # BookingCalendar, AvailabilityCalendar
│   ├── appointments/         # detail header, forme, chat dialog-ovi
│   ├── chat/                 # poruke, input, counter, closed notice
│   ├── student/              # search card, profile header, FAQ accordion
│   ├── professor/            # inbox, forme, FAQ, canned responses
│   ├── admin/                # users table, bulk import, audit log, …
│   ├── document-requests/    # forme, approve/reject dialozi
│   └── notifications/        # center, stream, push toggle (stub)
├── lib/
│   ├── api.ts                # axios klijent sa refresh queue
│   ├── api/                  # per-feature API wrappers
│   ├── hooks/                # TanStack Query hooks
│   ├── stores/               # Zustand (auth, impersonation, ws-status)
│   ├── utils/                # cn, date, file-validation, email-domain, …
│   ├── constants/            # roles, topic-categories, routes, nav-items, …
│   └── ws/                   # chat-socket, notification-socket
├── types/                    # TypeScript tipovi (usklađeni sa backend Pydantic)
├── public/
│   ├── manifest.json         # PWA manifest
│   ├── icons/                # ikone (generisane sa scripts/generate-icons.mjs)
│   ├── sw.js                 # generisan tokom build-a (gitignored)
│   └── workbox-*.js          # generisan tokom build-a (gitignored)
├── e2e/                      # Playwright testovi
├── middleware.ts             # JWT refresh cookie gate
├── next.config.mjs           # next-pwa konfiguracija
└── playwright.config.ts
```

## PWA

- Service worker je **isključen u dev-u** (izbegava cache konflikte sa HMR-om).
- `npm run build` generiše `public/sw.js` + `public/workbox-*.js` koji se
  serviraju sa `/`. U nginx-u postavi `Service-Worker-Allowed: /` da bi
  scope bio full-site (videti [produkcijski checklist](#produkcijski-checklist)).
- Runtime cache strategije su definisane u `next.config.mjs`:
  - Immutable assets (`/_next/static/*`, `/icons/*`, Google Fonts) → CacheFirst.
  - `GET /api/v1/students/appointments` i `GET /api/v1/notifications` →
    NetworkFirst sa 3s timeout-om, fallback na cache → omogućava
    offline pregled u `/my-appointments` i `/notifications`.
  - Navigacije → NetworkFirst, 3s timeout.
- Offline indikator (`components/shared/offline-indicator.tsx`) se montira
  u `<AppShell>` i pojavljuje se kao toast kad `navigator.onLine === false`.
- Web Push toggle (`components/notifications/push-subscription-toggle.tsx`)
  je **disabled stub** dok backend ne objavi VAPID endpoint (ROADMAP 4.2).

Regeneracija ikona:

```bash
npm run generate:icons
```

## Testing

### Unit / integration

Trenutno nisu definisani unit testovi za frontend (Jest/Vitest dolazi u
budućem milestone-u).

### E2E

Videti [`e2e/README.md`](./e2e/README.md). TL;DR:

```bash
npx playwright install chromium       # prvi put
npm run test:e2e                      # smoke + auth + search + professor-view
npx playwright test smoke.spec.ts     # samo testovi koji ne zahtevaju backend
```

Specovi koji zavise od endpoint-a koji još nisu implementirani su
dokumentovani u `e2e/README.md` § "Deferred specs".

## Produkcijski checklist

(Napisano za produkcijsku infra rundu — ROADMAP 5.3, Stefanov zadatak.
Ovde su stvari koje frontend **očekuje** od infra-e.)

### Env

Frontend kontejner mora imati postavljene:
- `NEXT_PUBLIC_API_URL` → upiranje na backend (preko nginx-a, HTTPS).
- `NEXT_PUBLIC_APP_ENV=production`.

### CORS

Backend `FRONTEND_URL` u `settings.py` mora da match-uje produkcijski
origin (npr. `https://konsultacije.example.rs`). Inače će axios cookie
flow (HttpOnly refresh_token) biti blokiran.

### Cookie

Refresh token cookie mora biti:
- `Secure` (HTTPS-only)
- `HttpOnly`
- `SameSite=Lax` (omogućava top-level navigation sa backend domena)
- `Domain=.example.rs` ako frontend i backend dele root domen

### nginx

Ključne rute:

```nginx
# Service worker mora imati scope na /
location = /sw.js {
    add_header Service-Worker-Allowed "/";
    add_header Cache-Control "public, max-age=0, must-revalidate";
}

# Manifest
location = /manifest.json {
    add_header Cache-Control "public, max-age=3600";
}

# Static assets (sa build hash-om → safe cache dugo)
location /_next/static/ {
    add_header Cache-Control "public, max-age=31536000, immutable";
}

# Ikonice (bez hash-a → kraći max-age)
location /icons/ {
    add_header Cache-Control "public, max-age=86400";
}

# API proxy
location /api/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # WebSocket (chat + notifications)
    proxy_read_timeout 3600;
}

# SPA fallback
location / {
    proxy_pass http://frontend:3000;
}
```

### Docker build

`next.config.mjs` postavlja `output: "standalone"` — produkcijski Docker
image može biti minimalan:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

## Troubleshooting

- **Build zastaje na "Collecting page data"** → proveri da u `app/providers.tsx`
  nije uvezena `"use client"` komponenta koja poziva browser-only API u
  top-level scope-u.
- **`Hydration failed` u dev-u** → najčešće `next-themes` ili datum formati
  sa `date-fns` koji zavise od timezone-a. Dodaj `suppressHydrationWarning`
  samo na element koji zaista menja vrednost između servera i klijenta.
- **Service worker "haunting"** — stari SW se ne briše** → DevTools →
  Application → Service Workers → Unregister. U produkciji to radi nov
  build (skipWaiting + clientsClaim).
- **ESLint prvo pitanje pri `npm run lint`** → već je konfigurisan sa
  `.eslintrc.json`. Ako nestane: odaberi **Strict** i obriši `.eslintrc.json`
  koji Next generiše (imamo custom).
