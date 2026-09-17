import { DomainPlaceholder } from "@/components/shared/DomainPlaceholder";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";

export default function AISourcingPage() {
  return (
    <div className="space-y-6">
      <DomainPlaceholder
        domain="AI Sourcing"
        title="AI Sourcing Assistant"
        description="Skeleton only. No LLM, embeddings, or recommendation algorithms yet."
      />
      <Card>
        <CardTitle>Natural language request</CardTitle>
        <CardDescription>
          Example (future): &quot;I need 500 boxes of olive oil delivered to Beirut
          within 10 days.&quot;
        </CardDescription>
        <div className="mt-4 rounded-lg border border-dashed border-border bg-surface-muted px-4 py-8 text-sm text-muted-foreground">
          Prompt input and recommendation results will appear here.
        </div>
      </Card>
    </div>
  );
}
