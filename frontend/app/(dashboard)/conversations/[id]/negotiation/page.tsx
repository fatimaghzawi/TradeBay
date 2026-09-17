import { DomainPlaceholder } from "@/components/shared/DomainPlaceholder";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";

export default async function NegotiationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <DomainPlaceholder
        domain="Negotiation"
        title="Negotiation workspace"
        description={`Conversation ${id} — offer history and counter-offers are deferred.`}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardTitle>Summary</CardTitle>
          <CardDescription>Status, parties, linked RFQ/quotation.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Current offer</CardTitle>
          <CardDescription>Active proposed terms will show here.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Offer history</CardTitle>
          <CardDescription>parent_offer chain: offer → counter → counter.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Counter-offer</CardTitle>
          <CardDescription>Form for quantity, price, delivery, payment terms.</CardDescription>
        </Card>
      </div>
    </div>
  );
}
