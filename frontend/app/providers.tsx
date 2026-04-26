/**
 * providers.tsx — Root client-side providers.
 *
 * - QueryClientProvider:  shared server-state cache for the whole tree.
 *                         staleTime 30s + refetchOnWindowFocus:false match
 *                         the contract in docs/FRONTEND_STRUKTURA.md §1.7.
 * - SessionRestorer:      on mount, calls POST /auth/refresh once (using the
 *                         httpOnly cookie) so the in-memory Zustand store is
 *                         rehydrated across full page reloads.
 * - NotificationStream:   (placeholder) WebSocket listener — mounted here so
 *                         it outlives individual pages.
 * - Toaster (sonner):     global toast host used by lib/utils/errors.ts.
 */

"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { ThemeProvider } from "next-themes"
import { useEffect, useRef, useState } from "react"

import { NotificationStream } from "@/components/notifications/notification-stream"
import { Toaster } from "@/components/ui/sonner"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/auth"

function SessionRestorer() {
  const { setAuth, clearAuth } = useAuthStore()
  const attempted = useRef(false)

  useEffect(() => {
    if (attempted.current) return
    attempted.current = true

    authApi
      .refresh()
      .then(({ data }) => setAuth(data.user, data.access_token))
      .catch(() => clearAuth())
  }, [setAuth, clearAuth])

  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange={false}
        storageKey="studentplus-theme"
      >
        <SessionRestorer />
        {children}
        <NotificationStream />
        <Toaster richColors closeButton position="top-right" />
        <ReactQueryDevtools initialIsOpen={false} />
      </ThemeProvider>
    </QueryClientProvider>
  )
}
