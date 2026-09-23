import { apiClient } from "@/lib/api/client";

export type Conversation = {
  id: string;
  subject: string | null;
  type: string;
  context_type: string | null;
  context_id: string | null;
  initiator_business_id: string | null;
  counterparty_business_id: string | null;
  counterparty_name?: string | null;
  counterparty_logo_url?: string | null;
  status: string;
  last_message_at: string | null;
  last_message_preview: string | null;
  message_count: number;
  unread_count?: number;
  last_read_at?: string | null;
  created_at: string | null;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string | null;
  sender_user_id: string | null;
  sender_business_id: string | null;
  message_type: string;
  body: string | null;
  is_deleted?: boolean;
  reply_to_message_id?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
  system_event?: string | null;
  created_at: string | null;
  edited_at: string | null;
  deleted_at?: string | null;
};

export const communicationApi = {
  listConversations: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<Conversation>("/conversations", { params }),

  unreadCount: () => apiClient.get<{ count: number }>("/conversations/unread-count"),

  getConversation: (id: string) =>
    apiClient.get<Conversation>(`/conversations/${id}`),

  markRead: (id: string) => apiClient.post<Conversation>(`/conversations/${id}/read`),

  openConversation: (body: {
    counterparty_business_id: string;
    type?: string;
    context_type?: string;
    context_id?: string;
    subject?: string;
  }) => apiClient.post<Conversation>("/conversations", body),

  listMessages: (
    conversationId: string,
    params?: { page?: number; page_size?: number; after?: string },
  ) =>
    apiClient.getPage<ConversationMessage>(`/conversations/${conversationId}/messages`, {
      params,
    }),

  sendMessage: (
    conversationId: string,
    body:
      | string
      | {
          body?: string;
          message_type?: string;
          reply_to_message_id?: string;
          reference_type?: string;
          reference_id?: string;
        },
  ) => {
    const payload = typeof body === "string" ? { body } : body;
    return apiClient.post<ConversationMessage>(
      `/conversations/${conversationId}/messages`,
      payload,
    );
  },

  editMessage: (conversationId: string, messageId: string, body: string) =>
    apiClient.patch<ConversationMessage>(
      `/conversations/${conversationId}/messages/${messageId}`,
      { body },
    ),

  deleteMessage: (conversationId: string, messageId: string) =>
    apiClient.delete<ConversationMessage>(
      `/conversations/${conversationId}/messages/${messageId}`,
    ),
};
