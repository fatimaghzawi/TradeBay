import { NotFoundState } from "@/components/ui/NotFoundState";
import { ROUTES } from "@/lib/constants";

export default function AdminNotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4 py-10">
      <NotFoundState
        size="page"
        title="Not found"
        message="That admin page doesn’t exist."
        homeHref={ROUTES.admin.home}
        homeLabel="Back to admin"
      />
    </div>
  );
}
