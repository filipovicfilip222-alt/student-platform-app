import type { Metadata } from "next"
import { Inter } from 'next/font/google'
import { Providers } from "./providers"
import "./globals.css"
import { cn } from "@/lib/utils"

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: {
    default: "Konsultacije FON & ETF",
    template: "%s | Konsultacije FON & ETF",
  },
  description:
    "Platforma za zakazivanje konsultacija između studenata i profesora FON-a i ETF-a.",
  manifest: "/manifest.json",
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