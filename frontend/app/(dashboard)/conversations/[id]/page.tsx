import { DomainPlaceholder } from "@/components/shared/DomainPlaceholder";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default async function ConversationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <DomainPlaceholder
        domain="Communication"
        title={`Conversation ${id}`}
        description="Message thread placeholder. No send/receive logic yet."
      />
      <Card>
        <CardTitle>Messages</CardTitle>
        <CardDescription>Message list will render here.</CardDescription>
        <div className="mt-4 h-40 rounded-lg border border-dashed border-border bg-surface-muted" />
      </Card>
      <Link href={`/conversations/${id}/negotiation`}>
        <Button variant="accent">Start Negotiation (placeholder)</Button>
      </Link>
    </div>
  );
}
