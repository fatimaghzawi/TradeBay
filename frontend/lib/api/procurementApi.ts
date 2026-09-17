import { apiClient } from "@/lib/api/client";

export const procurementApi = {
  health: () => apiClient.get<{ status: string }>("/procurement/health"),
};
