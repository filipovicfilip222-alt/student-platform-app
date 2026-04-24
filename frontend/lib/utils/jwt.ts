/**
 * jwt.ts — Unsafe JWT payload decoder.
 *
 * Decodes the base64url payload of a JWT **without verifying the signature**.
 * Use only for UX hints (e.g. reading the `imp` impersonation claim set by the
 * admin flow). Authorization is always enforced by the backend.
 */

export interface JwtPayload {
  sub?: string
  exp?: number
  iat?: number
  /** Admin user id when the token was issued through an impersonation flow. */
  imp?: string
  /** Token issuer — set by backend. */
  iss?: string
  [key: string]: unknown
}

function base64UrlDecode(segment: string): string {
  const padded = segment.replace(/-/g, "+").replace(/_/g, "/")
  const padding = padded.length % 4 === 0 ? 0 : 4 - (padded.length % 4)

  if (typeof globalThis.atob === "function") {
    return globalThis.atob(padded + "=".repeat(padding))
  }

  // Fallback for older runtimes — never hit in browser or modern Node.
  return Buffer.from(padded + "=".repeat(padding), "base64").toString("binary")
}

export function decodeJwtPayload<T extends JwtPayload = JwtPayload>(
  token: string
): T | null {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return null

    const decoded = base64UrlDecode(parts[1])
    const json = decodeURIComponent(
      decoded
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    )

    return JSON.parse(json) as T
  } catch {
    return null
  }
}

/** True if the token carries an `imp` claim (admin impersonating another user). */
export function isImpersonationToken(token: string): boolean {
  const payload = decodeJwtPayload(token)
  return typeof payload?.imp === "string" && payload.imp.length > 0
}
