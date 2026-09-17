import { apiClient } from "@/lib/api/client";

export const aiApi = {
  health: () => apiClient.get<{ status: string }>("/ai/health"),
};
