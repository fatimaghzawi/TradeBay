import { apiClient } from "@/lib/api/client";

/** Scaffolded client — no offer accept/counter logic. */
export const negotiationApi = {
  list: () =>
    apiClient.get<unknown>("/negotiations", {
      params: { page: 1, page_size: 20 },
    }),
  get: (id: string) => apiClient.get<unknown>(`/negotiations/${id}`),
  listOffers: (negotiationId: string) =>
    apiClient.get<unknown>(`/negotiations/${negotiationId}/offers`, {
      params: { page: 1, page_size: 50 },
    }),
};
