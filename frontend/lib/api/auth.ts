import api from "@/lib/api"
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  MessageResponse,
} from "@/types/auth"

export const authApi = {
  register: (data: RegisterRequest) =>
    api.post<UserResponse>("/auth/register", data),

  login: (data: LoginRequest) =>
    api.post<TokenResponse>("/auth/login", data),

  refresh: () =>
    api.post<TokenResponse>("/auth/refresh"),

  logout: () =>
    api.post<MessageResponse>("/auth/logout"),

  me: () =>
    api.get<UserResponse>("/auth/me"),

  forgotPassword: (data: ForgotPasswordRequest) =>
    api.post<MessageResponse>("/auth/forgot-password", data),

  resetPassword: (data: ResetPasswordRequest) =>
    api.post<MessageResponse>("/auth/reset-password", data),
}
