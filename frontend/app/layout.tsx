import type { Metadata, Viewport } from "next"
import { Inter } from "next/font/google"
import { Providers } from "./providers"
import "./globals.css"
import { cn } from "@/lib/utils"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: {
    default: "Konsultacije FON & ETF",
    template: "%s | Konsultacije FON & ETF",
  },
  description:
    "Platforma za zakazivanje konsultacija između studenata i profesora FON-a i ETF-a.",
  manifest: "/manifest.json",
  applicationName: "Konsultacije FON & ETF",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Konsultacije",
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
  themeColor: "#0f172a",
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
    <html lang="sr" suppressHydrationWarning className={cn("font-sans")}>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
