"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useEffect, useRef, useState } from "react"

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
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <SessionRestorer />
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
