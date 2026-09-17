import { LoadingState } from "@/components/ui/LoadingState";

export default function RootLoading() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <LoadingState rows={5} />
    </div>
  );
}
