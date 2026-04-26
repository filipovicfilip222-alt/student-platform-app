import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import { Providers } from "./providers"
import "./globals.css"
import { cn } from "@/lib/utils"

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-mono",
  weight: ["400", "500", "600"],
})

export const metadata: Metadata = {
  title: {
    default: "StudentPlus",
    template: "%s | StudentPlus",
  },
  description:
    "StudentPlus — pametno upravljanje konsultacijama na FON-u i ETF-u.",
  manifest: "/manifest.json",
  applicationName: "StudentPlus",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "StudentPlus",
  },
  icons: {
    icon: [
      { url: "/icons/favicon-16.png", sizes: "16x16", type: "image/png" },
      { url: "/icons/favicon-32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [
      { url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  formatDetection: {
    telephone: false,
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#7B1E2C" },
    { media: "(prefers-color-scheme: dark)", color: "#050816" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="sr"
      suppressHydrationWarning
      className={cn(inter.variable, jetbrainsMono.variable, "no-transitions")}
    >
      <head>
        {/* Strip the no-transitions guard once the document is interactive,
            so theme toggle (KORAK 1) and any future CSS transitions can run.
            next-themes injects the `.dark` class before hydration; without
            this guard, the very first paint would animate the swap. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "document.documentElement.classList.remove('no-transitions');",
          }}
        />
      </head>
      <body className={cn("font-sans antialiased")}>
        <a href="#main-content" className="skip-link">
          Preskoči na glavni sadržaj
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
