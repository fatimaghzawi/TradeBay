import { apiClient } from "@/lib/api/client";

export type AuthUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  status: string;
  avatar_url?: string | null;
  email_verified_at: string | null;
};

export type AuthBusiness = {
  id: string;
  name: string;
  type: string;
  status: string;
  verification_status?: string | null;
  verification_documents?: {
    document_type?: string | null;
    file_name?: string | null;
    url?: string | null;
    uploaded_at?: string | null;
  }[] | null;
  rejection_reason?: string | null;
  legal_name?: string | null;
  tax_number?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  email_domain?: string | null;
  logo_url?: string | null;
  cover_url?: string | null;
  description?: string | null;
  website?: string | null;
  year_established?: number | null;
  company_size?: string | null;
  industry_categories?: string[] | null;
  business_tags?: string[] | null;
  address?: {
    street?: string | null;
    city?: string | null;
    district?: string | null;
    governorate?: string | null;
    postal_code?: string | null;
    country?: string | null;
  } | null;
  role_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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
  business_type?: "buyer" | "supplier";
  invitation_token?: string;
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
    }>("/auth/register", payload),
  logout: () => apiClient.post<{ logged_out: boolean }>("/auth/logout"),
  refresh: () =>
    apiClient.post<{ user: AuthUser; access_token_expires_in_minutes: number }>(
      "/auth/refresh",
      undefined,
      { skipRefresh: true },
    ),
  forgotPassword: (email: string) =>
    apiClient.post<{ requested: boolean }>("/auth/forgot-password", { email }),
  verifyEmail: (token: string, email?: string) =>
    apiClient.post<{ user: AuthUser }>("/auth/email/verify", {
      token,
      ...(email ? { email } : {}),
    }),
  resendVerification: () =>
    apiClient.post<{ requested: boolean }>("/auth/email/resend"),
  resendVerificationEmail: (email: string) =>
    apiClient.post<{ requested: boolean }>("/auth/email/resend", { email }),
  resetPassword: (token: string, password: string) =>
    apiClient.post<{ reset: boolean }>("/auth/password/reset", { token, password }),
  changePassword: (current_password: string, new_password: string) =>
    apiClient.post<{ changed: boolean }>("/auth/password/change", {
      current_password,
      new_password,
    }),
};
