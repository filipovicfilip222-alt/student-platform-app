import { NextRequest, NextResponse } from "next/server"

// Routes that don't require authentication
const PUBLIC_PATHS = ["/login", "/register", "/forgot-password"]

// Routes that require a specific role (checked in route group layouts,
// middleware only checks that a session cookie exists)
const ROLE_PREFIXES: Record<string, string> = {
  "/admin": "ADMIN",
  "/professor/dashboard": "PROFESOR",
  "/professor/settings": "PROFESOR",
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // The refresh_token cookie is the only server-visible auth signal.
  // Access token lives in Zustand memory — it's restored by providers.tsx on mount.
  const hasSession = request.cookies.has("refresh_token")

  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  )
  const isRoot = pathname === "/"

  // ── Unauthenticated user trying to access protected route ──────────────────
  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone()
    url.pathname = "/login"
    // Preserve the intended destination for post-login redirect
    url.searchParams.set("from", pathname)
    return NextResponse.redirect(url)
  }

  // ── Authenticated user visiting a public/auth page → redirect to dashboard ─
  if (hasSession && (isPublic || isRoot)) {
    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Run on all routes except:
  // - Next.js internals (_next/*)
  // - Static assets
  // - API routes (handled by backend, proxied through nginx)
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|manifest.json|icons/).*)",
  ],
}
