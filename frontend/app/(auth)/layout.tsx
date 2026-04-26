/**
 * (auth)/layout.tsx — Public route-group layout (split-screen).
 *
 * Layout odgovornosti (KORAK 2):
 *   - lg+ : 50/50 split — leva forma, desna brand panel sa burgundy → amber
 *           gradient-om i feature listom (`<MarketingPanel />`).
 *   - md- : full-width forma centrirana na muted bg-u; marketing panel
 *           potpuno nestaje (`hidden lg:flex` u panelu) da se ne troši
 *           viewport.
 *
 * Page-ovi (login/register/forgot/reset) renderuju SAMO formu — naslov,
 * opis i navigaciju. Karticu, marketing panel i page-shell vlasi OVAJ
 * layout, a ne pojedinačni page-ovi (eliminiše duplo-uvlačenje
 * `min-h-screen` koje je postojalo pre KORAKA 2).
 *
 * AppShell se NE renderuje — auth se servira pre nego što useAuthStore
 * ima user-a; AppShell pokušaj `user.role` rezultovao bi runtime greškom.
 */

import { MarketingPanel } from "@/components/auth/marketing-panel"

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <main
        id="main-content"
        tabIndex={-1}
        className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10 outline-none sm:px-6 lg:bg-background lg:px-12"
      >
        <div className="w-full max-w-md">{children}</div>
      </main>
      <MarketingPanel />
    </div>
  )
}
