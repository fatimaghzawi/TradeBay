import { LoadingState } from "@/components/ui/LoadingState";

export default function DashboardLoading() {
  return (
    <div className="tb-page flex min-h-[50vh] items-center justify-center px-4 py-10">
      <LoadingState variant="page" title="Loading" message="Preparing your workspace…" />
    </div>
  );
}
