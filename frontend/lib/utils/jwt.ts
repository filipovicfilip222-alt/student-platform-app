/**
 * jwt.ts — Unsafe JWT payload decoder.
 *
 * Decodes the base64url payload of a JWT **without verifying the signature**.
 * Used only for UX hints — notably reading the impersonation claims so
 * `<ImpersonationBanner />` can render immediately after an admin starts an
 * impersonation session. Authorization is always enforced by the backend.
 *
 * Contract source: docs/websocket-schema.md §6.2 — access tokens carry
 * `sub`, `role`, `email`, `exp`, `type` claims. Impersonation tokens add
 * `imp`, `imp_email`, `imp_name`.
 */

export interface AccessTokenPayload {
  /** Target user id (the "acts as" user when impersonating, the real user otherwise). */
  sub?: string
  role?: "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN" | string
  email?: string
  exp?: number
  iat?: number
  iss?: string
  /** Constant `"access"` for access tokens, `"refresh"` for refresh tokens. */
  type?: "access" | "refresh" | string

  // ── Impersonation claims (only present when admin is impersonating) ───────
  /** Admin user id that initiated the impersonation session. */
  imp?: string
  /** Admin email (UX only — never trust for authorization). */
  imp_email?: string
  /** Admin full name (UX only). */
  imp_name?: string

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

export function decodeJwtPayload<T extends AccessTokenPayload = AccessTokenPayload>(
  token: string
): T | null {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return null

    const decoded = base64UrlDecode(parts[1])
    // Handle non-ASCII characters in claims (e.g. Serbian Latin in imp_name).
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

/**
 * Summary of the three impersonation-related claims. Returns `null` when the
 * token is not an impersonation token or cannot be decoded. Caller should
 * still treat these strings as UX-only hints.
 */
export interface ImpersonationClaims {
  adminId: string
  adminEmail: string
  adminName: string
}

export function readImpersonationClaims(token: string): ImpersonationClaims | null {
  const payload = decodeJwtPayload(token)
  if (!payload) return null
  if (typeof payload.imp !== "string" || payload.imp.length === 0) return null

  return {
    adminId: payload.imp,
    adminEmail: typeof payload.imp_email === "string" ? payload.imp_email : "",
    adminName: typeof payload.imp_name === "string" ? payload.imp_name : "",
  }
}
