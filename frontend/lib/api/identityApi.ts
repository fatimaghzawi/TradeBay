import { apiClient } from "@/lib/api/client";
import type { AuthBusiness } from "@/lib/api/authApi";

export type Business = AuthBusiness;

export type BusinessListResponse = {
  businesses: Business[];
};

export const identityApi = {
  listBusinesses: async (): Promise<BusinessListResponse> => {
    const items = await apiClient.get<Business[]>("/businesses");
    return { businesses: Array.isArray(items) ? items : [] };
  },
  getCurrentBusiness: () => apiClient.get<Business | null>("/businesses/current"),
  switchBusiness: (businessId: string) =>
    apiClient.post<{ business: Business }>("/businesses/current/switch", {
      business_id: businessId,
    }),
};
