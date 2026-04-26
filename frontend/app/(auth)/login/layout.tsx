/**
 * login/layout.tsx — Local layout that attaches SEO metadata.
 *
 * The login page itself is a Client Component (due to react-hook-form
 * and zustand), so it cannot export `metadata` directly. We wrap it in
 * this server layout just for the metadata contribution.
 */

import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Prijava",
  description:
    "Prijavite se u StudentPlus — platformu za zakazivanje konsultacija " +
    "sa profesorima Fakulteta organizacionih nauka i Elektrotehničkog " +
    "fakulteta Univerziteta u Beogradu.",
  robots: { index: true, follow: true },
}

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
