import type { NavIconKey } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function NavIcon({
  name,
  className,
}: {
  name: NavIconKey;
  className?: string;
}) {
  const cls = cn("h-[1.15rem] w-[1.15rem] shrink-0", className);
  switch (name) {
    case "home":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" />
        </svg>
      );
    case "building":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 20V7l8-3 8 3v13" />
          <path d="M9 20v-5h6v5" />
          <path d="M9 10h.01M12 10h.01M15 10h.01M9 14h.01M12 14h.01M15 14h.01" />
        </svg>
      );
    case "cart":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M3 5h2l2.2 11h10.6L21 8H7" />
          <circle cx="10" cy="19" r="1.2" />
          <circle cx="17" cy="19" r="1.2" />
        </svg>
      );
    case "messages":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M5 6h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H10l-4 3v-3H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z" />
        </svg>
      );
    case "orders":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M8 7h12v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7Z" />
          <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          <path d="M10 12h6M10 16h4" />
        </svg>
      );
    case "finance":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v8M9.5 10.5c.6-1 1.6-1.5 2.5-1.5 1.4 0 2.5.8 2.5 2s-1.1 2-2.5 2-2.5.8-2.5 2c0 1.1 1.1 2 2.5 2 .9 0 1.9-.5 2.5-1.5" />
        </svg>
      );
    case "chart":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 19h16" />
          <path d="M7 16V10M12 16V7M17 16v-4" />
        </svg>
      );
    case "catalog":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M5 5h6v6H5V5Zm8 0h6v6h-6V5ZM5 13h6v6H5v-6Zm8 3h6" />
        </svg>
      );
    case "truck":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M3 8h11v9H3V8Zm11 2h4l3 3v4h-7v-7Z" />
          <circle cx="7" cy="18.5" r="1.5" />
          <circle cx="17" cy="18.5" r="1.5" />
        </svg>
      );
    case "shield":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M12 3 5 6v5c0 4.5 3 7.8 7 9 4-1.2 7-4.5 7-9V6l-7-3Z" />
          <path d="m9.5 12 1.8 1.8 3.7-3.8" />
        </svg>
      );
    case "spark":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M12 3v3M12 18v3M4.9 6.5l2.1 2.1M17 15.4l2.1 2.1M3 12h3M18 12h3M4.9 17.5 7 15.4M17 8.6l2.1-2.1" />
          <circle cx="12" cy="12" r="3.2" />
        </svg>
      );
    case "planner":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M8 4h8M7 7h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" />
          <path d="M9 12h6M9 16h4" />
        </svg>
      );
    case "users":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <circle cx="9" cy="8" r="3" />
          <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
          <circle cx="17" cy="9" r="2.4" />
          <path d="M15 19a4.5 4.5 0 0 1 5.5-4.2" />
        </svg>
      );
    case "roles":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M12 3 4 7v4c0 4.2 3.2 7.8 8 9 4.8-1.2 8-4.8 8-9V7l-8-4Z" />
          <path d="M12 11v5M12 8.5h.01" />
        </svg>
      );
    case "mail":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 7h16v10H4V7Z" />
          <path d="m4 7 8 6 8-6" />
        </svg>
      );
    case "help":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M9.8 9.5a2.4 2.4 0 0 1 4.4 1.2c0 1.6-2.2 2-2.2 3.3" />
          <path d="M12 17h.01" />
        </svg>
      );
    case "settings":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 3.5v2.2M12 18.3v2.2M4.9 6.5l1.6 1.6M17.5 15.9l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.9 17.5l1.6-1.6M17.5 8.1l1.6-1.6" />
        </svg>
      );
    case "disputes":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M12 4 3 19h18L12 4Z" />
          <path d="M12 10v4M12 16.5h.01" />
        </svg>
      );
    case "settlements":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 7h16v3H4V7Zm0 5h16v7H4v-7Z" />
          <path d="M8 17h3" />
        </svg>
      );
    case "suppliers":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M4 18V9l4-4h8l4 4v9" />
          <path d="M9 18v-4h6v4" />
          <path d="M8 9h8" />
        </svg>
      );
    case "audit":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M8 4h8v16H8V4Z" />
          <path d="M10 8h4M10 12h4M10 16h2" />
        </svg>
      );
    case "bell":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M6 9.5a6 6 0 1 1 12 0c0 4.2 1.4 5.5 1.4 5.5H4.6S6 13.7 6 9.5Z" />
          <path d="M10 18.5a2 2 0 0 0 4 0" />
        </svg>
      );
    case "quote":
      return (
        <svg viewBox="0 0 24 24" className={cls} aria-hidden {...stroke}>
          <path d="M5 7h14v12H5V7Z" />
          <path d="M8 7V5h8v2M8 12h8M8 16h5" />
        </svg>
      );
    default:
      return null;
  }
}
