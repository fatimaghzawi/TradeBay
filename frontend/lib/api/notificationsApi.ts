import { apiClient } from "@/lib/api/client";

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  message: string | null;
  reference_type: string | null;
  reference_id: string | null;
  cta_path: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string | null;
};

export const notificationsApi = {
  list: (params?: { page?: number; page_size?: number; unread_only?: boolean }) =>
    apiClient.getPage<AppNotification>("/notifications", { params }),

  unreadCount: () => apiClient.get<{ count: number }>("/notifications/unread-count"),

  markRead: (id: string) =>
    apiClient.post<AppNotification>(`/notifications/${id}/read`),

  markAllRead: () => apiClient.post<{ marked: number }>("/notifications/read-all"),
};
