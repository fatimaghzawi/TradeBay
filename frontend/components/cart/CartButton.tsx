"use client";

import {
  CART_CHANGED_EVENT,
  cartApi,
  type CartChangedDetail,
} from "@/lib/api/cartApi";
import { openCartTray } from "@/lib/shoppingTrays";
import { useAuth } from "@/providers/AuthProvider";
import { useEffect, useState } from "react";

/** Buyer cart shortcut — opens the shopping tray. */
export function CartButton() {
  const { business, hasPermission, isAuthenticated } = useAuth();
  const [count, setCount] = useState(0);

  const visible =
    isAuthenticated &&
    business?.type === "buyer" &&
    hasPermission("products.read");

  useEffect(() => {
    if (!visible) {
      setCount(0);
      return;
    }
    let cancelled = false;
    const applyCount = (next: number) => {
      if (!cancelled) setCount(next);
    };
    const load = () => {
      void cartApi
        .get()
        .then((cart) => applyCount(cart.item_count))
        .catch(() => applyCount(0));
    };
    const onChange = (event: Event) => {
      const detail = (event as CustomEvent<CartChangedDetail>).detail;
      if (typeof detail?.item_count === "number") {
        applyCount(detail.item_count);
        return;
      }
      load();
    };
    load();
    window.addEventListener(CART_CHANGED_EVENT, onChange);
    return () => {
      cancelled = true;
      window.removeEventListener(CART_CHANGED_EVENT, onChange);
    };
  }, [visible]);

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={() => openCartTray()}
      className="relative flex h-10 w-10 items-center justify-center rounded-full border border-[var(--tb-border)] bg-[var(--tb-surface)] text-[var(--tb-ink)] transition hover:border-[var(--tb-primary)]/45 hover:text-[var(--tb-ink)]"
      aria-label={count > 0 ? `Cart, ${count} items` : "Cart"}
      title="Cart"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M6 6h15l-1.5 9h-12z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M6 6L5 3H2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="9" cy="20" r="1.4" fill="currentColor" />
        <circle cx="18" cy="20" r="1.4" fill="currentColor" />
      </svg>
      {count > 0 ? (
        <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--tb-accent)] px-1 text-[10px] font-bold leading-none text-[var(--tb-accent-foreground)]">
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </button>
  );
}
