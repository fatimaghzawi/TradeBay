"use client";

import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  CART_CHANGED_EVENT,
  hydrateCartCache,
  isProductInCachedCart,
  cartApi,
  type CartChangedDetail,
} from "@/lib/api/cartApi";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import { openCartTray } from "@/lib/shoppingTrays";
import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui/LoadingState";

function CartIcon({ className }: { className?: string }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      className={className}
    >
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
  );
}

type AddToCartButtonProps = {
  productId: string;
  quantity?: number;
  className?: string;
  tone?: "accent" | "soft" | "ghost";
  stopPropagation?: boolean;
};

export function AddToCartButton({
  productId,
  quantity = 1,
  className,
  tone = "accent",
  stopPropagation = false,
}: AddToCartButtonProps) {
  const { business, hasPermission, isAuthenticated } = useAuth();
  const { success, error: toastError } = useToast();
  const [pending, setPending] = useState(false);
  const [added, setAdded] = useState(() => isProductInCachedCart(productId));

  const isBuyer = business?.type === "buyer";
  const canAdd = isAuthenticated && isBuyer && hasPermission("products.read");

  useEffect(() => {
    setAdded(isProductInCachedCart(productId));
    const sync = (event: Event) => {
      const detail = (event as CustomEvent<CartChangedDetail>).detail;
      if (detail?.product_ids) {
        setAdded(detail.product_ids.includes(productId));
        return;
      }
      setAdded(isProductInCachedCart(productId));
    };
    window.addEventListener(CART_CHANGED_EVENT, sync);
    void hydrateCartCache().then(() => setAdded(isProductInCachedCart(productId)));
    return () => window.removeEventListener(CART_CHANGED_EVENT, sync);
  }, [productId]);

  if (!canAdd) return null;

  const shell =
    "relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition disabled:opacity-60";

  if (added) {
    return (
      <button
        type="button"
        className={cn(
          shell,
          "border border-[color-mix(in_srgb,var(--tb-success)_40%,var(--tb-line))] bg-[var(--tb-success-soft)] text-[var(--tb-success)] hover:bg-[var(--tb-hover-strong)]",
          className,
        )}
        title="In cart — open cart"
        aria-label="Added to cart — open cart"
        onClick={(event) => {
          if (stopPropagation) event.stopPropagation();
          openCartTray();
        }}
      >
        <CartIcon />
        <span
          className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--tb-success)] text-[10px] font-bold leading-none text-white"
          aria-hidden
        >
          ✓
        </span>
      </button>
    );
  }

  const toneClass =
    tone === "soft"
      ? "border border-[var(--tb-line)] bg-[var(--tb-surface-muted)] text-[var(--tb-ink)] hover:bg-[var(--tb-hover-strong)]"
      : tone === "ghost"
        ? "border border-transparent text-[var(--tb-ink)] hover:bg-[var(--tb-hover)]"
        : "bg-[var(--tb-primary)] text-[var(--tb-primary-foreground)] hover:brightness-95";

  return (
    <button
      type="button"
      disabled={pending}
      aria-busy={pending || undefined}
      title={pending ? "Adding…" : "Add to cart"}
      aria-label={pending ? "Adding to cart" : "Add to cart"}
      className={cn(shell, toneClass, className)}
      onClick={(event) => {
        if (stopPropagation) {
          event.preventDefault();
          event.stopPropagation();
        }
        setPending(true);
        void cartApi
          .addItem(productId, quantity)
          .then((cart) => {
            setAdded(true);
            success(
              "Added to cart",
              `${cart.item_count} item${cart.item_count === 1 ? "" : "s"} in cart`,
            );
          })
          .catch((err) => {
            toastError(
              "Could not add",
              err instanceof ApiError ? err.message : "Couldn't add this product.",
            );
          })
          .finally(() => setPending(false));
      }}
    >
      {pending ? <Spinner size="sm" /> : <CartIcon />}
    </button>
  );
}
