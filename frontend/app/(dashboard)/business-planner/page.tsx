import { DomainPlaceholder } from "@/components/shared/DomainPlaceholder";
import { Card, CardDescription, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function BusinessPlannerPage() {
  return (
    <div className="space-y-6">
      <DomainPlaceholder
        domain="Business Planner"
        title="Plan My Business"
        description="Skeleton only. AI generation, price estimates, and supplier conversion will be implemented later."
      />
      <Card>
        <CardTitle>Planning to open a business?</CardTitle>
        <CardDescription>
          Let TradeBay help you plan what you need — categories, quantities, and
          estimated costs — then find suppliers through AI Sourcing.
        </CardDescription>
        <div className="mt-4">
          <Button disabled variant="accent">
            Plan My Business (coming soon)
          </Button>
        </div>
      </Card>
    </div>
  );
}
