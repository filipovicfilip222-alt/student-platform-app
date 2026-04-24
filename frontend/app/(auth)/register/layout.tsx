/**
 * register/layout.tsx — Local layout that attaches SEO metadata.
 */

import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Registracija",
  description:
    "Kreirajte nalog sa vašom studentskom email adresom " +
    "(@student.fon.bg.ac.rs ili @student.etf.bg.ac.rs).",
  robots: { index: true, follow: true },
}

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
