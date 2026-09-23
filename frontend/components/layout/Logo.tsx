"use client";

import { APP_NAME, ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";

const LOGO = "/images/TradeBay-logo-light.png";

/** Official TradeBay logo. Dark mode adds a light chip via CSS so forest greens stay readable. */
export function Logo({
  className,
  compact = false,
  href = ROUTES.dashboard,
}: {
  className?: string;
  compact?: boolean;
  href?: string;
  /** @deprecated Kept for call-site compat; unused. */
  invert?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn("tb-logo inline-flex items-center", className)}
      aria-label={APP_NAME}
    >
      <Image
        src={LOGO}
        alt={APP_NAME}
        width={compact ? 120 : 148}
        height={compact ? 32 : 40}
        className={cn(
          "w-auto object-contain object-left",
          compact ? "h-7" : "h-9",
        )}
        priority
      />
    </Link>
  );
}
