/**
 * Root page — simple gate that defers the decision to the middleware.
 *
 * Middleware (`frontend/middleware.ts`) already redirects:
 *   - authenticated users on `/` → `/dashboard`
 *   - unauthenticated users on protected routes → `/login`
 *
 * So if this component ever renders (shouldn't, because middleware runs
 * first), we simply push to /login to avoid an ambiguous blank page.
 */

import { redirect } from "next/navigation"

export default function RootPage(): never {
  redirect("/login")
}
