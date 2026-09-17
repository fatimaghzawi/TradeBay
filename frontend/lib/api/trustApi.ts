import { apiClient } from "@/lib/api/client";

export const trustApi = {
  health: () => apiClient.get<{ status: string }>("/trust/health"),
};
