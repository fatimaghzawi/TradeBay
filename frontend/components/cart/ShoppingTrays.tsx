"use client";

import { useToast } from "@/components/ui/Toast";
import { BusyText } from "@/components/ui/LoadingState";
import { ApiError } from "@/lib/api/client";
import {
  CART_CHANGED_EVENT,
  cartApi,
  type Cart,
  type CartItem,
} from "@/lib/api/cartApi";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import {
  favoriteCount,
  listSavedProducts,
  PRODUCT_FAV_EVENT,
  removeProductFavorite,
  type SavedProduct,
} from "@/lib/productFavorites";
import {
  OPEN_CART_TRAY_EVENT,
  OPEN_FAVORITES_TRAY_EVENT,
  openCartTray,
} from "@/lib/shoppingTrays";
import { cn } from "@/lib/utils";
import { formatMoneyAmount } from "@/lib/numericInput";
import { NumberInput } from "@/components/ui/FormField";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type TrayKind = "cart" | "favorites" | null;

function TrayShell({
  open,
  onClose,
  title,
  kicker,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  kicker: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!mounted) return null;

  return createPortal(
    <>
      <button
        type="button"
        aria-label="Close tray"
        className={cn("tb-shop-tray__scrim", open && "is-open")}
        onClick={onClose}
      />
      <aside
        className={cn("tb-shop-tray", open && "is-open")}
        aria-hidden={!open}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="tb-shop-tray__head">
          <div>
            <p className="tb-shop-tray__kicker">{kicker}</p>
            <h2 className="tb-shop-tray__title">{title}</h2>
          </div>
          <button type="button" className="tb-shop-tray__close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="tb-shop-tray__body">{children}</div>
        {footer ? <footer className="tb-shop-tray__foot">{footer}</footer> : null}
      </aside>
    </>,
    document.body,
  );
}

function QtyChip({
  item,
  busy,
  onCommit,
}: {
  item: CartItem;
  busy: boolean;
  onCommit: (quantity: number) => void;
}) {
  const [draft, setDraft] = useState(String(item.quantity));

  useEffect(() => {
    setDraft(String(item.quantity));
  }, [item.id, item.quantity]);

  function commit(raw: string) {
    const parsed = Number.parseInt(raw.replace(/[^\d]/g, ""), 10);
    if (!Number.isFinite(parsed)) {
      setDraft(String(item.quantity));
      return;
    }
    const next = Math.max(item.moq || 1, Math.min(1_000_000, parsed));
    setDraft(String(next));
    if (next !== item.quantity) onCommit(next);
  }

  return (
    <div className="tb-shop-tray__qty">
      <button
        type="button"
        disabled={busy || item.quantity <= item.moq}
        aria-label="Decrease"
        onClick={() => onCommit(item.quantity - 1)}
      >
        −
      </button>
      <NumberInput
        kind="integer"
        className="tb-shop-tray__qty-input"
        min={item.moq || 1}
        max={1_000_000}
        value={draft}
        disabled={busy}
        aria-label={`Quantity for ${item.product_name}`}
        onChange={(e) => setDraft(e.target.value)}
        onFocus={(e) => e.currentTarget.select()}
        onBlur={() => commit(draft)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") {
            setDraft(String(item.quantity));
            e.currentTarget.blur();
          }
        }}
      />
      <button
        type="button"
        disabled={busy}
        aria-label="Increase"
        onClick={() => onCommit(item.quantity + 1)}
      >
        +
      </button>
    </div>
  );
}

function PriceField({
  item,
}: {
  item: CartItem;
}) {
  return (
    <div className="tb-shop-tray__prices">
      <p className="tb-shop-tray__listed">
        Unit {item.currency} {formatMoneyAmount(item.unit_price)}
      </p>
    </div>
  );
}

function lineAmount(item: CartItem): number {
  const price = Number(item.unit_price || 0);
  return Number.isFinite(price) ? price * item.quantity : 0;
}

function cartTotal(cart: Cart): { currency: string; amount: number } {
  const currency = cart.currency || cart.items[0]?.currency || "USD";
  const fromApi = Number(cart.subtotal);
  if (Number.isFinite(fromApi) && cart.subtotal != null && cart.subtotal !== "") {
    return { currency, amount: fromApi };
  }
  return {
    currency,
    amount: cart.items.reduce((sum, item) => sum + lineAmount(item), 0),
  };
}

export function ShoppingTraysHost() {
  const router = useRouter();
  const { business, hasPermission, isAuthenticated } = useAuth();
  const { success, error: toastError } = useToast();
  const [tray, setTray] = useState<TrayKind>(null);
  const [cart, setCart] = useState<Cart | null>(null);
  const [favorites, setFavorites] = useState<SavedProduct[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [working, setWorking] = useState<"rfq" | "order" | null>(null);

  const isBuyer = business?.type === "buyer";
  const canCart =
    isAuthenticated && isBuyer && hasPermission("products.read");
  const canRfq = hasPermission("rfqs.create");
  const canOrder = hasPermission("quotations.accept");

  const reloadCart = useCallback(() => {
    if (!canCart) {
      setCart(null);
      return;
    }
    void cartApi
      .get()
      .then(setCart)
      .catch(() => setCart(null));
  }, [canCart]);

  const reloadFavorites = useCallback(() => {
    setFavorites(listSavedProducts());
  }, []);

  useEffect(() => {
    const openCart = () => {
      if (canCart) setTray("cart");
    };
    const openFav = () => setTray("favorites");
    window.addEventListener(OPEN_CART_TRAY_EVENT, openCart);
    window.addEventListener(OPEN_FAVORITES_TRAY_EVENT, openFav);
    return () => {
      window.removeEventListener(OPEN_CART_TRAY_EVENT, openCart);
      window.removeEventListener(OPEN_FAVORITES_TRAY_EVENT, openFav);
    };
  }, [canCart]);

  useEffect(() => {
    if (tray === "cart") reloadCart();
    if (tray === "favorites") reloadFavorites();
  }, [tray, reloadCart, reloadFavorites]);

  useEffect(() => {
    const onCart = () => {
      if (tray === "cart") reloadCart();
    };
    const onFav = () => reloadFavorites();
    window.addEventListener(CART_CHANGED_EVENT, onCart);
    window.addEventListener(PRODUCT_FAV_EVENT, onFav);
    return () => {
      window.removeEventListener(CART_CHANGED_EVENT, onCart);
      window.removeEventListener(PRODUCT_FAV_EVENT, onFav);
    };
  }, [reloadCart, reloadFavorites, tray]);

  async function patchItem(
    item: CartItem,
    patch: { quantity?: number },
  ) {
    setBusyId(item.id);
    try {
      setCart(await cartApi.updateItem(item.id, patch));
    } catch (err) {
      toastError(
        "Update failed",
        err instanceof ApiError ? err.message : "Could not update line.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      {canCart ? (
      <TrayShell
        open={tray === "cart"}
        onClose={() => setTray(null)}
        kicker="Marketplace bag"
        title="Cart"
        footer={
          cart && cart.items.length > 0 ? (
            <div className="tb-shop-tray__checkout">
              <div className="tb-shop-tray__total">
                <span>Total</span>
                <strong>
                  {cartTotal(cart).currency} {formatMoneyAmount(cartTotal(cart).amount)}
                </strong>
              </div>
              <div className="tb-shop-tray__actions">
              <button
                type="button"
                className="tb-shop-tray__btn is-soft"
                disabled={!!working || !canRfq}
                onClick={() => {
                  setWorking("rfq");
                  void cartApi
                    .checkout({ publish: false })
                    .then((result) => {
                      setCart(result.cart);
                      success("Draft RFQ ready", "Review quantities, then send to suppliers.");
                      setTray(null);
                      router.push(ROUTES.procurementRfq(result.rfq_id));
                    })
                    .catch((err) =>
                      toastError(
                        "RFQ failed",
                        err instanceof ApiError ? err.message : "Could not create RFQ.",
                      ),
                    )
                    .finally(() => setWorking(null));
                }}
              >
                {working === "rfq" ? "Creating…" : "Request quotes"}
              </button>
              <button
                type="button"
                className="tb-shop-tray__btn is-accent"
                disabled={!!working}
                onClick={() => {
                  setTray(null);
                  router.push(ROUTES.orders);
                }}
              >
                Order now (soon)
              </button>
            </div>
            </div>
          ) : null
        }
      >
        {!cart || cart.items.length === 0 ? (
          <div className="tb-shop-tray__empty">
            <p>Your bag is empty</p>
            <span>Browse products to get started.</span>
            <Link
              href={ROUTES.inventoryProducts}
              className="tb-shop-tray__link"
              onClick={() => setTray(null)}
            >
              Browse products
            </Link>
          </div>
        ) : (
          <ul className="tb-shop-tray__list">
            {cart.items.map((item) => (
              <li key={item.id} className="tb-shop-tray__card">
                <div className="tb-shop-tray__thumb">
                  {item.primary_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={mediaUrl(item.primary_image_url)} alt="" />
                  ) : (
                    <span>{(item.product_name || "?").slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
                <div className="tb-shop-tray__meta">
                  <Link
                    href={ROUTES.inventoryProduct(item.product_id)}
                    onClick={() => setTray(null)}
                  >
                    {item.product_name}
                  </Link>
                  <p>{item.supplier_name ?? "Supplier"}</p>
                  <p className="tb-shop-tray__line">
                    {item.currency} {formatMoneyAmount(lineAmount(item))}
                  </p>
                  <div className="tb-shop-tray__controls">
                    <QtyChip
                      item={item}
                      busy={busyId === item.id}
                      onCommit={(quantity) => void patchItem(item, { quantity })}
                    />
                    <PriceField item={item} />
                  </div>
                </div>
                <button
                  type="button"
                  className="tb-shop-tray__remove"
                  disabled={busyId === item.id}
                  onClick={() => {
                    setBusyId(item.id);
                    void cartApi
                      .removeItem(item.id)
                      .then(setCart)
                      .catch((err) =>
                        toastError(
                          "Remove failed",
                          err instanceof ApiError ? err.message : "Could not remove.",
                        ),
                      )
                      .finally(() => setBusyId(null));
                  }}
                >
                  <BusyText busy={busyId === item.id}>Remove</BusyText>
                </button>
              </li>
            ))}
          </ul>
        )}
      </TrayShell>
      ) : null}

      <TrayShell
        open={tray === "favorites"}
        onClose={() => setTray(null)}
        kicker="Saved for later"
        title="Favorites"
      >
        {favorites.length === 0 ? (
          <div className="tb-shop-tray__empty">
            <p>No favorites yet</p>
            <span>Save products you like while browsing.</span>
            <Link
              href={ROUTES.inventoryProducts}
              className="tb-shop-tray__link"
              onClick={() => setTray(null)}
            >
              Browse products
            </Link>
          </div>
        ) : (
          <ul className="tb-shop-tray__list">
            {favorites.map((item) => (
              <li key={item.id} className="tb-shop-tray__card">
                <div className="tb-shop-tray__thumb">
                  {item.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={mediaUrl(item.image)} alt="" />
                  ) : (
                    <span>{item.name.slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
                <div className="tb-shop-tray__meta">
                  <Link
                    href={item.href || ROUTES.inventoryProduct(item.id)}
                    onClick={() => setTray(null)}
                  >
                    {item.name}
                  </Link>
                  <p>Saved {new Date(item.savedAt).toLocaleDateString()}</p>
                  <div className="tb-shop-tray__fav-actions">
                    {canCart && !item.id.startsWith("landing:") ? (
                      <button
                        type="button"
                        className="tb-shop-tray__mini"
                        onClick={() => {
                          void cartApi
                            .addItem(item.id, 1)
                            .then(() => {
                              success("Added to cart");
                              openCartTray();
                            })
                            .catch((err) =>
                              toastError(
                                "Could not add",
                                err instanceof ApiError ? err.message : "Unable to add.",
                              ),
                            );
                        }}
                      >
                        Add to cart
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="tb-shop-tray__mini is-mute"
                      onClick={() => setFavorites(removeProductFavorite(item.id))}
                    >
                      Unsave
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {favorites.length > 0 ? (
          <p className="tb-shop-tray__hint">{favoriteCount()} saved</p>
        ) : null}
      </TrayShell>
    </>
  );
}
