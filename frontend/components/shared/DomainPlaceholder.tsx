import { Badge } from "@/components/ui/Badge";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

export function DomainPlaceholder({
  domain,
  title,
  description,
}: {
  domain: string;
  title: string;
  description: string;
}) {
  return (
    <div className="space-y-6">
      <div>
        <Badge tone="warning">{domain}</Badge>
        <h1 className="font-display mt-3 text-2xl font-semibold text-primary">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          {description}
        </p>
      </div>
      <Card>
        <CardTitle>Module shell</CardTitle>
        <CardDescription>
          Domain screens will live here. Backend permissions remain authoritative.
        </CardDescription>
      </Card>
      <EmptyState
        title="No data wired yet"
        description="Connect this route to API modules when backend endpoints are ready."
      />
    </div>
  );
}
