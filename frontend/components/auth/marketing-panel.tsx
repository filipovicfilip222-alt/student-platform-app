/**
 * marketing-panel.tsx — Brand panel renderovan u (auth)/layout.tsx.
 *
 * - Prikazuje se samo na lg+ (≥1024px) ekranima — mobile/tablet dobijaju
 *   čistu formu na full-width platnu.
 * - Gradient burgundy → tamna burgundy → amber (subtilno) — kreira brand
 *   "first impression" pre nego što korisnik ikada vidi dashboard.
 * - Tekst i logo su DARK-only kontekst (paleta panela je uvek tamna), pa
 *   namerno koristimo `text-white`, `text-white/70` umesto theme tokena.
 *   Ovaj panel ne menja boju kad korisnik prebaci theme — ostaje brand.
 */

import { CalendarCheck, MessageSquare, ShieldCheck } from "lucide-react"

interface Feature {
  icon: typeof CalendarCheck
  title: string
  description: string
}

const FEATURES: Feature[] = [
  {
    icon: CalendarCheck,
    title: "Pametno zakazivanje",
    description:
      "Pregledaj termine konsultacija u realnom vremenu i rezerviši slot u par klikova.",
  },
  {
    icon: MessageSquare,
    title: "Direktna komunikacija",
    description:
      "Razmeni materijale i pitanja sa profesorom kroz integrisani tiket-chat.",
  },
  {
    icon: ShieldCheck,
    title: "Akademski integritet",
    description:
      "Sve interakcije su evidentirane uz transparentne pravila otkazivanja.",
  },
]

export function MarketingPanel() {
  return (
    <aside
      className="relative hidden h-full overflow-hidden lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16"
      aria-hidden
    >
      {/* Gradient background — burgundy → deep burgundy → amber tint.
          We don't use theme tokens here on purpose: this panel is the
          brand artefact, it MUST keep its identity in both light and dark. */}
      <div
        className="absolute inset-0 -z-10"
        style={{
          background:
            "linear-gradient(135deg, #7B1E2C 0%, #5A1422 45%, #3A0E18 100%)",
        }}
      />
      {/* Amber halo */}
      <div
        className="pointer-events-none absolute -right-32 -top-32 -z-10 size-[480px] rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle, #E8A93D 0%, transparent 70%)" }}
      />
      {/* Diagonal stripe pattern */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.07]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(45deg, #fff 0 1px, transparent 1px 22px)",
        }}
      />

      {/* Top: brand mark + wordmark.
          Panel je uvek tamne boje (brand identity, ne prati theme toggle),
          pa koristimo inline SVG umesto next/image da izbegnemo broken img
          dok PNG fajlovi nisu uploadovani u public/branding/. */}
      <div className="flex items-center gap-3 text-white">
        <svg
          width={48}
          height={48}
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
          className="shrink-0 select-none drop-shadow-md"
        >
          <circle cx="24" cy="24" r="24" fill="#B0405A" />
          <polygon points="24,10 40,18 24,26 8,18" fill="#F4C56A" />
          <path
            d="M16 20v9c0 3.314 3.582 6 8 6s8-2.686 8-6v-9l-8 4-8-4z"
            fill="white"
            fillOpacity="0.92"
          />
          <line x1="40" y1="18" x2="40" y2="30" stroke="#F4C56A" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="40" cy="33" r="3" fill="#F4C56A" />
        </svg>
        <span className="text-2xl font-semibold tracking-tight">
          Student<span style={{ color: "#E8A93D" }}>Plus</span>
        </span>
      </div>

      {/* Middle: tagline + feature list */}
      <div className="space-y-10 text-white">
        <div className="space-y-4">
          <h2 className="max-w-md text-4xl font-bold leading-tight tracking-tight xl:text-5xl">
            Pametno upravljanje konsultacijama na FON-u i ETF-u.
          </h2>
          <p className="max-w-md text-base leading-relaxed text-white/75">
            Jedna platforma za studente, profesore i asistente Univerziteta
            u Beogradu — svi termini, sve poruke, jedan akademski standard.
          </p>
        </div>

        <ul className="space-y-5 text-sm">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <li key={title} className="flex gap-3">
              <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-inset ring-white/15">
                <Icon className="size-5" aria-hidden style={{ color: "#E8A93D" }} />
              </span>
              <div>
                <p className="font-semibold text-white">{title}</p>
                <p className="text-white/70">{description}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Bottom: legal/affiliation strip */}
      <p className="text-xs text-white/55">
        Univerzitet u Beogradu · FON & ETF · Akademska {new Date().getFullYear()}.
      </p>
    </aside>
  )
}
