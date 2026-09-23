import { LoadingState } from "@/components/ui/LoadingState";

export default function AdminLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4 py-10">
      <LoadingState variant="page" title="Loading" message="Opening platform controls…" />
    </div>
  );
}
