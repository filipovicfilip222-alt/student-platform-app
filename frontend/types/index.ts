/**
 * types barrel — re-exports every domain type so consumers can
 * `import type { ... } from '@/types'`.
 *
 * auth.ts declares its own UserRole / Faculty / MessageResponse (kept for
 * backwards compatibility with the existing auth scaffolding). We re-export
 * auth.ts types selectively to avoid colliding with the canonical
 * Role / Faculty / MessageResponse from common.ts. Use the common.ts names
 * in new code.
 */

export * from "./admin"
export * from "./appointment"
export type {
  ForgotPasswordRequest,
  LoginRequest,
  RegisterRequest,
  ResetPasswordRequest,
  TokenResponse,
  UserResponse,
} from "./auth"
export * from "./chat"
export * from "./common"
export * from "./document-request"
export * from "./notification"
export * from "./professor"
export * from "./ws"
