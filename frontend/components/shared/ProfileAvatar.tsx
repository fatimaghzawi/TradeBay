"use client";

import { mediaUrl } from "@/lib/media";
import { cn } from "@/lib/utils";

export function ProfileAvatar({
  src,
  label,
  className,
  size = "md",
}: {
  src?: string | null;
  label: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const url = mediaUrl(src);
  const initials =
    label
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "TB";

  const sizeClass =
    size === "sm" ? "h-8 w-8 text-[0.62rem]" : size === "lg" ? "h-12 w-12 text-sm" : "h-9 w-9 text-[0.7rem]";

  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt=""
        className={cn(
          "shrink-0 rounded-full object-cover ring-1 ring-border-strong",
          sizeClass,
          className,
        )}
      />
    );
  }

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground",
        sizeClass,
        className,
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}
