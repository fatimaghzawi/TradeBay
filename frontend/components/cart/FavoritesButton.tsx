"use client";

import {
  favoriteCount,
  PRODUCT_FAV_EVENT,
} from "@/lib/productFavorites";
import { openFavoritesTray } from "@/lib/shoppingTrays";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useState } from "react";

export function FavoritesButton({
  className,
  badgeClassName,
}: {
  className?: string;
  badgeClassName?: string;
} = {}) {
  const { business, isAuthenticated } = useAuth();
  const [count, setCount] = useState(0);

  const visible = !isAuthenticated || business?.type === "buyer";

  useEffect(() => {
    if (!visible) {
      setCount(0);
      return;
    }
    const sync = () => setCount(favoriteCount());
    sync();
    window.addEventListener(PRODUCT_FAV_EVENT, sync);
    return () => window.removeEventListener(PRODUCT_FAV_EVENT, sync);
  }, [visible]);

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={() => openFavoritesTray()}
      className={cn(
        "relative flex h-10 w-10 items-center justify-center rounded-full border border-border-strong bg-card text-foreground transition hover:border-[var(--tb-primary)]/45 hover:text-foreground",
        className,
      )}
      aria-label={count > 0 ? `Favorites, ${count} saved` : "Favorites"}
      title="Favorites"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M12 20s-7-4.35-7-9.2A3.8 3.8 0 0 1 12 7.5a3.8 3.8 0 0 1 7 3.3C19 15.65 12 20 12 20z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
          fill={count > 0 ? "currentColor" : "none"}
          className={count > 0 ? "text-destructive" : undefined}
        />
      </svg>
      {count > 0 ? (
        <span
          className={cn(
            "absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--tb-danger)] px-1 text-[10px] font-bold leading-none text-white",
            badgeClassName,
          )}
        >
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </button>
  );
}
