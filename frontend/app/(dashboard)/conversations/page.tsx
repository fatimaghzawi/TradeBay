"use client";

import { ChatEmptyStage } from "@/components/communication/ChatInbox";
import { InventoryPageHeader } from "@/components/catalog/InventoryUi";
import { useAuth } from "@/providers/AuthProvider";

export default function ConversationsIndexPage() {
  const { hasPermission } = useAuth();

  if (!hasPermission("conversations.read")) {
    return (
      <InventoryPageHeader
        title="Conversations"
        description="You don't have access to messages. Contact your business administrator if you need access."
      />
    );
  }

  return <ChatEmptyStage />;
}
