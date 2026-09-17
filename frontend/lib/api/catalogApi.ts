import { apiClient } from "@/lib/api/client";

export const catalogApi = {
  health: () => apiClient.get<{ status: string }>("/catalog/health"),
};
