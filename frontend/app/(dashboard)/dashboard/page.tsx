import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { DASHBOARD_DOMAINS } from "@/lib/constants";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-primary">
          Dashboard
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Quick entry points across TradeBay domains.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {DASHBOARD_DOMAINS.map((domain) => (
          <Link key={domain.key} href={domain.href} className="block">
            <Card className="h-full transition hover:border-secondary">
              <CardTitle>{domain.title}</CardTitle>
              <CardDescription>{domain.description}</CardDescription>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
