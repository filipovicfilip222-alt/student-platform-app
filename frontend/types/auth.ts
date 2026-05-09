// Types that mirror the backend Pydantic schemas exactly.
// Keep in sync with /backend/app/schemas/auth.py

export type UserRole = "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN"
export type Faculty = "FON" | "ETF"

export interface UserResponse {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  faculty: Faculty
  is_active: boolean
  is_verified: boolean
  profile_image_url: string | null
  created_at: string
  /**
   * Strike sistem (PRD §5.3) — relevantno samo za STUDENT-e.
   * Backend popunjava preko `_build_user_response` u `auth.py`.
   * Za ostale uloge uvek `0` / `null`.
   */
  total_strike_points: number
  blocked_until: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
  user: UserResponse
}

export interface RegisterRequest {
  email: string
  password: string
  first_name: string
  last_name: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

export interface MessageResponse {
  message: string
}
