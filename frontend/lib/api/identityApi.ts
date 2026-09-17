import { apiClient } from "@/lib/api/client";
import type { AuthBusiness } from "@/lib/api/authApi";

export type Business = AuthBusiness;

export type BusinessListResponse = {
  businesses: Business[];
};

export type Member = {
  id: string;
  user_id: string;
  email: string | null;
  role_id: string;
  role_name: string | null;
  status: string;
};

export type Role = {
  id: string;
  name: string;
  is_system_role: boolean;
  permissions: string[];
};

export type Invitation = {
  id: string;
  invited_email: string;
  role_id: string;
  status: string;
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
};

export const identityApi = {
  listBusinesses: async (): Promise<BusinessListResponse> => {
    const items = await apiClient.get<Business[]>("/businesses");
    return { businesses: Array.isArray(items) ? items : [] };
  },
  getCurrentBusiness: () => apiClient.get<Business | null>("/businesses/current"),
  createBusiness: (payload: CreateBusinessPayload) =>
    apiClient.post<Business>("/businesses", payload),
  switchBusiness: (businessId: string) =>
    apiClient.post<{ business: Business }>("/businesses/current/switch", {
      business_id: businessId,
    }),
  listMembers: () => apiClient.get<Member[]>("/members"),
  updateMemberRole: (membershipId: string, roleId: string) =>
    apiClient.patch<{ id: string; role_id: string }>(`/members/${membershipId}`, {
      role_id: roleId,
    }),
  removeMember: (membershipId: string) =>
    apiClient.delete<{ removed: boolean }>(`/members/${membershipId}`),
  listRoles: () => apiClient.get<Role[]>("/roles"),
  createRole: (name: string, permissions: string[]) =>
    apiClient.post<Role>("/roles", { name, permissions }),
  updateRole: (roleId: string, permissions: string[]) =>
    apiClient.patch<Role>(`/roles/${roleId}`, { permissions }),
  deleteRole: (roleId: string) => apiClient.delete<{ deleted: boolean }>(`/roles/${roleId}`),
  listPermissions: () => apiClient.get<Permission[]>("/permissions"),
  listInvitations: () => apiClient.get<Invitation[]>("/invitations"),
  invite: (email: string, roleId: string) =>
    apiClient.post<Invitation>("/invitations", { email, role_id: roleId }),
  acceptInvitation: (token: string) =>
    apiClient.post<{ business_id: string; role_id: string }>("/invitations/accept", {
      token,
    }),
  revokeInvitation: (invitationId: string) =>
    apiClient.post<{ revoked: boolean }>(`/invitations/${invitationId}/revoke`),
};
