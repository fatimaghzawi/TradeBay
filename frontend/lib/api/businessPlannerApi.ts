import { apiClient } from "@/lib/api/client";

/** Scaffolded client — no AI plan generation. */
export const businessPlannerApi = {
  listPlans: () =>
    apiClient.get<unknown>("/business-plans", {
      params: { page: 1, page_size: 20 },
    }),
  getPlan: (id: string) =>
    apiClient.get<unknown>(`/business-plans/${id}`),
};
