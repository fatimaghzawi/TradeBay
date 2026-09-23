import { LoadingState } from "@/components/ui/LoadingState";

export default function RootLoading() {
  return (
    <div className="tb-app flex min-h-[70vh] items-center justify-center px-4">
      <LoadingState variant="page" title="Loading TradeBay" message="Opening this surface…" />
    </div>
  );
}
