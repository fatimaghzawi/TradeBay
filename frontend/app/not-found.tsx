import { NotFoundState } from "@/components/ui/NotFoundState";
import { ROUTES } from "@/lib/constants";

export default function NotFound() {
  return (
    <div className="tb-app flex min-h-[70vh] items-center justify-center px-4">
      <NotFoundState
        size="page"
        title="Page not found"
        message="This route isn’t on the bay — it may have moved, or the link is incomplete."
        homeHref={ROUTES.home}
        homeLabel="Back to home"
      />
    </div>
  );
}
