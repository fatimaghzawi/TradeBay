import { NotFoundState } from "@/components/ui/NotFoundState";
import { ROUTES } from "@/lib/constants";

export default function DashboardNotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4 py-10">
      <NotFoundState
        size="page"
        title="Not found"
        message="That workspace page doesn’t exist. Pick another destination from the bay."
        homeHref={ROUTES.dashboard}
        homeLabel="Back to dashboard"
      />
    </div>
  );
}
