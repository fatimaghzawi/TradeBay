import { apiClient } from "@/lib/api/client";

export type AuthUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  status: string;
  email_verified_at: string | null;
};

export type AuthBusiness = {
  id: string;
  name: string;
  type: string;
  status: string;
};

export type AuthMeResponse = {
  user: AuthUser;
  active_business: AuthBusiness | null;
  membership: {
    id: string;
    business_account_id: string;
    role_id: string;
    status: string;
  } | null;
  role_name: string | null;
  permissions: string[];
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  business_name?: string;
};

export const authApi = {
  me: () => apiClient.get<AuthMeResponse>("/auth/me"),
  login: (payload: LoginPayload) =>
    apiClient.post<{ user: AuthUser; access_token_expires_in_minutes: number }>(
      "/auth/login",
      payload,
    ),
  register: (payload: RegisterPayload) =>
    apiClient.post<{
      user: AuthUser;
      business: AuthBusiness | null;
      verification_token?: string;
    }>("/auth/register", payload),
  logout: () => apiClient.post<{ logged_out: boolean }>("/auth/logout"),
  forgotPassword: (email: string) =>
    apiClient.post<{ requested: boolean }>("/auth/forgot-password", { email }),
  verifyEmail: (token: string) =>
    apiClient.post<{ user: AuthUser }>("/auth/verify-email", { token }),
  resetPassword: (token: string, password: string) =>
    apiClient.post<{ reset: boolean }>("/auth/reset-password", { token, password }),
};
