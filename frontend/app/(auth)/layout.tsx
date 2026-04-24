/**
 * (auth)/layout.tsx — Public route-group layout for /login, /register,
 * /forgot-password, /reset-password.
 *
 * ROADMAP 2.3 — auth layout.
 *
 * The login and register pages each render their own full-height
 * centred card with the "Konsultacije FON & ETF" branding in the
 * CardTitle, so this layout intentionally stays a pass-through — adding
 * another header here would clash with the page-owned `min-h-screen`
 * wrapper. When we redesign auth pages in a later milestone, branding
 * and layout can be lifted here.
 *
 * Important: this layout must NOT render `<AppShell>` — auth pages are
 * served before any user exists in the Zustand store. Including the
 * shell would recursively try to read `user.role`.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
