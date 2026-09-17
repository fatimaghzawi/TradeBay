import { apiClient } from "@/lib/api/client";

export const financeApi = {
  health: () => apiClient.get<{ status: string }>("/finance/health"),
};
