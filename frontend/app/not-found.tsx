import { Button } from "@/components/ui/Button";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-start justify-center px-6">
      <p className="text-sm font-semibold uppercase tracking-wider text-secondary">
        404
      </p>
      <h1 className="font-display mt-2 text-3xl font-semibold text-primary">
        Page not found
      </h1>
      <p className="mt-3 text-sm text-muted-foreground">
        The route you requested is not part of this TradeBay shell yet.
      </p>
      <Link href="/" className="mt-6">
        <Button>Back to home</Button>
      </Link>
    </div>
  );
}
