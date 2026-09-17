import { apiClient } from "@/lib/api/client";

/** Scaffolded client — no LLM calls. */
export const aiSourcingApi = {
    listRequests: () =>
    apiClient.get<unknown>("/ai-sourcing/requests", {
      params: { page: 1, page_size: 20 },
    }),
  getRequest: (id: string) =>
    apiClient.get<unknown>(`/ai-sourcing/requests/${id}`),
};
