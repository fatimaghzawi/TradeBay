import { apiClient } from "@/lib/api/client";

export type CartItem = {
  id: string;
  product_id: string;
  supplier_business_id: string;
  supplier_name?: string | null;
  product_name: string;
  sku?: string | null;
  unit: string;
  moq: number;
  quantity: number;
  unit_price?: string | null;
  suggested_unit_price?: string | null;
  currency: string;
  primary_image_url?: string | null;
  line_total?: string | null;
  updated_at?: string | null;
};

export type Cart = {
  buyer_business_id: string;
  item_count: number;
  quantity_total: number;
  currency?: string | null;
  subtotal?: string | null;
  items: CartItem[];
};

export type CartCheckoutResult = {
  rfq_id: string;
  rfq_number?: string;
  status?: string;
  suppliers_invited: number;
  invite_warning?: string | null;
  cart: Cart;
};

export type CartOrderSummary = {
  id: string;
  order_number?: string;
  supplier_business_id: string;
  total?: string | null;
  currency?: string;
  status?: string;
};

export type CartOrderResult = {
  orders: CartOrderSummary[];
  order_count: number;
  cart: Cart;
};

export type CartChangedDetail = {
  item_count: number;
  product_ids: string[];
};

export const CART_CHANGED_EVENT = "tradebay-cart-change";

let cachedProductIds = new Set<string>();
let cachedItemCount = 0;
let hydratePromise: Promise<void> | null = null;
let cartHydrated = false;

export function getCachedCartProductIds(): Set<string> {
  return new Set(cachedProductIds);
}

export function isProductInCachedCart(productId: string): boolean {
  return cachedProductIds.has(productId);
}

function rememberCart(cart: Cart | null | undefined) {
  cachedProductIds = new Set((cart?.items ?? []).map((item) => item.product_id));
  cachedItemCount = cart?.item_count ?? 0;
  cartHydrated = true;
}

export function emitCartChanged(cart?: Cart | null) {
  if (cart) rememberCart(cart);
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<CartChangedDetail>(CART_CHANGED_EVENT, {
      detail: {
        item_count: cachedItemCount,
        product_ids: [...cachedProductIds],
      },
    }),
  );
}

/** One shared GET /cart so product grids don't stampede the API. */
export function hydrateCartCache(): Promise<void> {
  if (typeof window === "undefined" || cartHydrated) return Promise.resolve();
  if (!hydratePromise) {
    hydratePromise = cartApi
      .get()
      .then(() => undefined)
      .catch(() => undefined);
  }
  return hydratePromise;
}

function withCartSideEffects(result: Cart): Cart {
  emitCartChanged(result);
  return result;
}

export const cartApi = {
  get: (opts?: { emit?: boolean }) =>
    apiClient.get<Cart>("/cart").then((cart) => {
      rememberCart(cart);
      // Reads must not emit — ShoppingTrays refetches on this event, which
      // would GET /cart again and loop until the proxy dies.
      if (opts?.emit) emitCartChanged(cart);
      return cart;
    }),
  summary: () =>
    apiClient.get<{ item_count: number; quantity_total: number }>("/cart/summary"),
  addItem: (productId: string, quantity = 1, suggestedUnitPrice?: string | null) =>
    apiClient
      .post<Cart>("/cart/items", {
        product_id: productId,
        quantity,
        ...(suggestedUnitPrice != null && suggestedUnitPrice !== ""
          ? { suggested_unit_price: suggestedUnitPrice }
          : {}),
      })
      .then(withCartSideEffects),
  updateItem: (
    itemId: string,
    patch: { quantity?: number; suggested_unit_price?: string | null },
  ) => apiClient.patch<Cart>(`/cart/items/${itemId}`, patch).then(withCartSideEffects),
  removeItem: (itemId: string) =>
    apiClient.delete<Cart>(`/cart/items/${itemId}`).then(withCartSideEffects),
  clear: () => apiClient.delete<Cart>("/cart").then(withCartSideEffects),
  checkout: (body?: { title?: string; notes?: string; publish?: boolean }) =>
    apiClient
      .post<CartCheckoutResult>("/cart/checkout", { publish: false, ...body })
      .then((result) => {
        rememberCart(result.cart);
        emitCartChanged(result.cart);
        return result;
      }),
  placeOrders: (body?: { notes?: string }) =>
    apiClient
      .post<CartOrderResult>("/cart/order", body ?? {})
      .then((result) => {
        rememberCart(result.cart);
        emitCartChanged(result.cart);
        return result;
      }),
};
