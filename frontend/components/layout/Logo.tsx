import { APP_NAME } from "@/lib/constants";
import { cn } from "@/lib/utils";
import Link from "next/link";

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("inline-flex items-center gap-2", className)}>
      <span
        aria-hidden
        className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground"
      >
        TB
      </span>
      <span className="font-display text-lg font-semibold tracking-tight text-primary">
        {APP_NAME}
      </span>
    </Link>
  );
}
