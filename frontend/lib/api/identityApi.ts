import { apiClient } from "@/lib/api/client";
import type { AuthBusiness } from "@/lib/api/authApi";
import type {
  PurchaseOrderSummary,
  RFQSummary,
} from "@/lib/api/procurementApi";

export type Business = AuthBusiness;

export type BusinessListResponse = {
  businesses: Business[];
};

export type PublicCompany = {
  id: string;
  name: string;
  type: string;
  status: string;
  legal_name?: string | null;
  logo_url?: string | null;
  cover_url?: string | null;
  description?: string | null;
  website?: string | null;
  year_established?: number | null;
  company_size?: string | null;
  industry_categories?: string[] | null;
  business_tags?: string[] | null;
  address?: {
    city?: string | null;
    governorate?: string | null;
    country?: string | null;
  } | null;
  verification_status?: string | null;
};

export type Member = {
  id: string;
  user_id: string;
  email: string | null;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  role_id: string;
  role_name: string | null;
  status: string;
  joined_at?: string | null;
  user_status?: string | null;
  suspension_reason?: string | null;
};

export type PlatformUserBusiness = {
  membership_id: string;
  business_id: string;
  business_name: string | null;
  business_type: string | null;
  role_name: string | null;
  membership_status: string | null;
};

export type PlatformUser = {
  id: string;
  email: string | null;
  first_name?: string | null;
  last_name?: string | null;
  status: string;
  avatar_url?: string | null;
  email_verified_at?: string | null;
  suspension_reason?: string | null;
  created_at?: string | null;
  businesses: PlatformUserBusiness[];
};

export type SessionDevice = {
  id: string;
  active_business_account_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  last_used_at: string | null;
  created_at: string | null;
  expires_at: string | null;
  is_current: boolean;
};

export type AuditEvent = {
  id: string;
  action: string | null;
  resource_type: string | null;
  resource_id: string | null;
  business_account_id: string | null;
  user_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string | null;
};

export type Role = {
  id: string;
  name: string;
  description?: string | null;
  is_system_role: boolean;
  permissions: string[];
};

export type Invitation = {
  id: string;
  invited_email: string;
  delivery_email?: string | null;
  role_id: string;
  role_name?: string | null;
  status: string;
  expires_at?: string | null;
  created_at?: string | null;
  business_name?: string | null;
  inviter_name?: string | null;
  permissions?: string[];
  already_pending?: boolean;
  message?: string;
};

export type InvitationPreview = {
  id: string;
  invited_email: string;
  delivery_email?: string | null;
  business_name: string | null;
  role_id: string;
  role_name: string | null;
  status: string;
  expires_at: string | null;
  inviter_name: string | null;
};

export type Permission = {
  resource: string;
  action: string;
  code: string;
  description: string;
};

export type CreateBusinessPayload = {
  name: string;
  type?: string;
  legal_name?: string;
  tax_number?: string;
  contact_email?: string;
  contact_phone?: string;
  email_domain?: string;
  address?: {
    street?: string;
    city?: string;
    district?: string;
    governorate?: string;
    postal_code?: string;
    country?: string;
  };
};

export type UpdateBusinessPayload = {
  name?: string;
  legal_name?: string;
  tax_number?: string;
  contact_email?: string;
  contact_phone?: string;
  email_domain?: string;
  description?: string;
  website?: string;
  year_established?: number;
  company_size?: string;
  industry_categories?: string[];
  business_tags?: string[];
  address?: {
    street?: string;
    city?: string;
    district?: string;
    governorate?: string;
    postal_code?: string;
    country?: string;
  };
};

export const identityApi = {
  listBusinesses: async (): Promise<BusinessListResponse> => {
    const items = await apiClient.get<Business[]>("/businesses");
    return { businesses: Array.isArray(items) ? items : [] };
  },
  getCurrentBusiness: () => apiClient.get<Business | null>("/businesses/current"),
  getBusiness: (businessId: string) =>
    apiClient.get<Business>(`/businesses/${businessId}`),
  getPublicCompany: (businessId: string) =>
    apiClient.get<PublicCompany>(`/companies/${businessId}`),
  createBusiness: (payload: CreateBusinessPayload) =>
    apiClient.post<Business>("/businesses", payload),
  updateBusiness: (businessId: string, payload: UpdateBusinessPayload) =>
    apiClient.patch<Business>(`/businesses/${businessId}`, payload),
  uploadBusinessMedia: (businessId: string, kind: "logo" | "cover", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.upload<Business>(`/businesses/${businessId}/media/${kind}`, form);
  },
  uploadVerificationDocument: (
    businessId: string,
    documentType: string,
    file: File,
  ) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.upload<{
      document_type: string;
      file_name: string | null;
      url: string;
    }>(
      `/businesses/${businessId}/verification/documents/${encodeURIComponent(documentType)}`,
      form,
    );
  },
  submitSupplierVerification: (
    businessId: string,
    documents: { document_type: string; file_name?: string; url?: string }[],
  ) =>
    apiClient.post<Business>(`/businesses/${businessId}/verification/submit`, {
      documents,
    }),
  withdrawSupplierDocument: (businessId: string, documentType: string) =>
    apiClient.delete<Business>(
      `/businesses/${businessId}/verification/documents/${encodeURIComponent(documentType)}`,
    ),
  listPlatformSuppliers: (params?: {
    verification_status?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }) =>
    apiClient.getPage<Business>("/platform/suppliers", { params }),
  listPlatformBusinesses: (params?: {
    account_type?: string;
    status?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<Business>("/platform/businesses", { params }),
  getPlatformBusiness: (businessId: string) =>
    apiClient.get<Business>(`/platform/businesses/${businessId}`),
  listPlatformBusinessMembers: (
    businessId: string,
    params?: { status?: string; q?: string; page?: number; page_size?: number },
  ) =>
    apiClient.getPage<Member>(`/platform/businesses/${businessId}/members`, {
      params,
    }),
  listPlatformBusinessRoles: (
    businessId: string,
    params?: { q?: string; page?: number; page_size?: number },
  ) =>
    apiClient.getPage<Role>(`/platform/businesses/${businessId}/roles`, {
      params,
    }),
  getPlatformBusinessRole: (businessId: string, roleId: string) =>
    apiClient.get<Role>(`/platform/businesses/${businessId}/roles/${roleId}`),
  createPlatformBusinessRole: (
    businessId: string,
    name: string,
    permissions: string[],
  ) =>
    apiClient.post<Role>(`/platform/businesses/${businessId}/roles`, {
      name,
      permissions,
    }),
  updatePlatformBusinessRole: (
    businessId: string,
    roleId: string,
    permissions: string[],
  ) =>
    apiClient.patch<Role>(
      `/platform/businesses/${businessId}/roles/${roleId}`,
      { permissions },
    ),
  deletePlatformBusinessRole: (businessId: string, roleId: string) =>
    apiClient.delete<{ deleted: boolean }>(
      `/platform/businesses/${businessId}/roles/${roleId}`,
    ),
  updatePlatformBusinessMemberRole: (
    businessId: string,
    membershipId: string,
    roleId: string,
  ) =>
    apiClient.patch<{ id: string; role_id: string }>(
      `/platform/businesses/${businessId}/members/${membershipId}/role`,
      { role_id: roleId },
    ),
  listPlatformBusinessAuditLogs: (
    businessId: string,
    params?: {
      action?: string;
      resource_type?: string;
      page?: number;
      page_size?: number;
    },
  ) =>
    apiClient.getPage<AuditEvent>(
      `/platform/businesses/${businessId}/audit-logs`,
      { params },
    ),
  getPlatformBusinessAuditLog: (businessId: string, auditLogId: string) =>
    apiClient.get<AuditEvent>(
      `/platform/businesses/${businessId}/audit-logs/${auditLogId}`,
    ),
  listPlatformBusinessOrders: (
    businessId: string,
    params?: { status?: string; page?: number; page_size?: number },
  ) =>
    apiClient.getPage<PurchaseOrderSummary>(
      `/platform/businesses/${businessId}/purchase-orders`,
      { params },
    ),
  listPlatformBusinessRfqs: (
    businessId: string,
    params?: { status?: string; page?: number; page_size?: number },
  ) =>
    apiClient.getPage<RFQSummary>(
      `/platform/businesses/${businessId}/rfqs`,
      { params },
    ),
  listPlatformUsers: (params?: {
    status?: string;
    q?: string;
    email_verified?: boolean;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<PlatformUser>("/platform/users", { params }),
  createPlatformUser: (payload: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) =>
    apiClient.post<{
      id: string;
      email: string;
      first_name: string;
      last_name: string;
      status: string;
      email_verified_at: string | null;
    }>("/platform/users", payload),
  createPlatformBusiness: (payload: {
    account_type: "buyer" | "supplier";
    business_name: string;
    owner_email: string;
    owner_password: string;
    owner_first_name: string;
    owner_last_name: string;
    email_domain?: string;
    legal_name?: string;
    tax_number?: string;
    contact_email?: string;
    contact_phone?: string;
    verify_supplier?: boolean;
  }) =>
    apiClient.post<{
      user: {
        id: string;
        email: string;
        first_name: string;
        last_name: string;
        status: string;
        email_verified_at: string | null;
      };
      business: Business;
    }>("/platform/businesses", payload),
  suspendPlatformUser: (userId: string, reason: string) =>
    apiClient.post<{ suspended: boolean }>("/platform/users/suspend", {
      user_id: userId,
      reason,
    }),
  reactivatePlatformUser: (userId: string) =>
    apiClient.post<{ reactivated: boolean }>(`/platform/users/${userId}/reactivate`),
  reviewSupplierVerification: (
    businessId: string,
    decision: "approve" | "reject" | "revoke",
    reason?: string,
  ) =>
    apiClient.post<Business>(`/platform/suppliers/${businessId}/review`, {
      decision,
      reason,
    }),
  switchBusiness: (businessId: string) =>
    apiClient.post<{ business: Business }>("/businesses/switch", {
      business_id: businessId,
    }),
  listMembers: (params?: {
    status?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<Member>("/members", { params }),
  getMember: (membershipId: string) =>
    apiClient.get<Member>(`/members/${membershipId}`),
  updateMemberRole: (membershipId: string, roleId: string) =>
    apiClient.patch<{ id: string; role_id: string }>(`/members/${membershipId}`, {
      role_id: roleId,
    }),
  removeMember: (membershipId: string) =>
    apiClient.delete<{ removed: boolean }>(`/members/${membershipId}`),
  listRoles: (params?: { q?: string; page?: number; page_size?: number }) =>
    apiClient.getPage<Role>("/roles", { params }),
  getRole: (roleId: string) => apiClient.get<Role>(`/roles/${roleId}`),
  createRole: (name: string, permissions: string[]) =>
    apiClient.post<Role>("/roles", { name, permissions }),
  updateRole: (roleId: string, permissions: string[]) =>
    apiClient.patch<Role>(`/roles/${roleId}`, { permissions }),
  deleteRole: (roleId: string) => apiClient.delete<{ deleted: boolean }>(`/roles/${roleId}`),
  listPermissions: () => apiClient.get<Permission[]>("/permissions"),
  listInvitations: (params?: {
    status?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<Invitation>("/invitations", { params }),
  invite: (email: string, roleId: string, permissions: string[], companyEmail?: string) =>
    apiClient.post<Invitation>("/invitations", {
      email,
      company_email: companyEmail || undefined,
      role_id: roleId,
      permissions,
    }),
  previewInvitation: (token: string) =>
    apiClient.get<InvitationPreview>("/invitations/preview", { params: { token } }),
  acceptInvitation: (token: string) =>
    apiClient.post<{
      business_id: string;
      role_id: string;
      role_name?: string | null;
      membership_id?: string | null;
      already_accepted?: boolean;
      business?: Business;
    }>("/invitations/accept", {
      token,
    }),
  declineInvitation: (token: string) =>
    apiClient.post<{ declined: boolean }>("/invitations/decline", { token }),
  resendInvitation: (invitationId: string) =>
    apiClient.post<Invitation>(`/invitations/${invitationId}/resend`),
  revokeInvitation: (invitationId: string) =>
    apiClient.post<{ revoked: boolean }>(`/invitations/${invitationId}/revoke`),
  updateProfile: (payload: { first_name?: string; last_name?: string }) =>
    apiClient.patch<{ user: import("@/lib/api/authApi").AuthUser }>("/me", payload),
  listSessions: () => apiClient.get<SessionDevice[]>("/sessions"),
  revokeSession: (sessionId: string) =>
    apiClient.delete<{ revoked: boolean }>(`/sessions/${sessionId}`),
  revokeOtherSessions: () =>
    apiClient.delete<{ revoked: number }>("/sessions"),
  suspendMember: (membershipId: string, reason: string) =>
    apiClient.post<{ suspended: boolean }>(`/members/${membershipId}/suspend`, {
      reason,
    }),
  reactivateMember: (membershipId: string) =>
    apiClient.post<{ reactivated: boolean }>(`/members/${membershipId}/reactivate`),
  suspendUser: (userId: string, reason: string) =>
    apiClient.post<{ suspended: boolean }>("/users/suspend", {
      user_id: userId,
      reason,
    }),
  reactivateUser: (userId: string) =>
    apiClient.post<{ reactivated: boolean }>(`/users/${userId}/reactivate`),
  listAuditLogs: (params?: {
    action?: string;
    resource_type?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<AuditEvent>("/audit-logs", { params }),
  getAuditLog: (auditLogId: string) =>
    apiClient.get<AuditEvent>(`/audit-logs/${auditLogId}`),
  platformMe: () =>
    apiClient.get<{
      platform_business: {
        id: string;
        name: string;
        type: string;
        status: string;
      } | null;
      membership_id: string | null;
      role_id: string | null;
      role_name: string | null;
      active_is_platform: boolean;
      permissions: string[];
    }>("/platform/me"),
  listPlatformAuditLogs: (params?: {
    action?: string;
    resource_type?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<AuditEvent>("/platform/audit-logs", { params }),
  getPlatformAuditLog: (auditLogId: string) =>
    apiClient.get<AuditEvent>(`/platform/audit-logs/${auditLogId}`),
};
