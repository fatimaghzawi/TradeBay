import { apiClient } from "@/lib/api/client";

export const platformMoneyApi = {
  health: () => apiClient.get<{ status: string }>("/platform-money/health"),
};
