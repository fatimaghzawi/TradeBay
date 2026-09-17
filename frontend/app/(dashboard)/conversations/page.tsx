import { DomainPlaceholder } from "@/components/shared/DomainPlaceholder";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function ConversationsPage() {
  return (
    <div className="space-y-6">
      <DomainPlaceholder
        domain="Communication"
        title="Conversations"
        description="Conversation list skeleton. Real-time messaging and WebSockets are deferred."
      />
      <Link href="/conversations/preview">
        <Button variant="outline">Open conversation placeholder</Button>
      </Link>
    </div>
  );
}
