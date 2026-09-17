import { apiClient } from "@/lib/api/client";

/** Scaffolded client — no messaging logic. */
export const communicationApi = {
  listConversations: () =>
    apiClient.get<unknown>("/conversations", {
      params: { page: 1, page_size: 20 },
    }),
  getConversation: (id: string) =>
    apiClient.get<unknown>(`/conversations/${id}`),
  listMessages: (conversationId: string) =>
    apiClient.get<unknown>(`/conversations/${conversationId}/messages`, {
      params: { page: 1, page_size: 50 },
    }),
};
