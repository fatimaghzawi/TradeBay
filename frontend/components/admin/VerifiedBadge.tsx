import { cn } from "@/lib/utils";

type Props = {
  verified: boolean;
  
  label?: string;
  className?: string;
  size?: "sm" | "md";
  
  showLabel?: boolean;
  
  showWhenUnverified?: boolean;
};

export function VerifiedBadge({
  verified,
  label,
  className,
  size = "sm",
  showLabel = false,
  showWhenUnverified = true,
}: Props) {
  if (!verified && !showWhenUnverified) return null;

  const title = label ?? (verified ? "Verified supplier" : "Unverified");
  return (
    <span
      className={cn(
        "tb-verified-badge",
        verified ? "is-verified" : "is-unverified",
        size === "md" && "tb-verified-badge--md",
        showLabel && "tb-verified-badge--labeled",
        className,
      )}
      title={title}
      aria-label={title}
    >
      {verified ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M9 12.5 11 14.5 15.5 9.5"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M12 8v5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <circle cx="12" cy="16.2" r="1" fill="currentColor" />
        </svg>
      )}
      {showLabel && verified ? (
        <span className="tb-verified-badge__text">Verified</span>
      ) : (
        <span className="tb-verified-badge__sr">{title}</span>
      )}
    </span>
  );
}
