

export const OPEN_CART_TRAY_EVENT = "tradebay-open-cart-tray";
export const OPEN_FAVORITES_TRAY_EVENT = "tradebay-open-favorites-tray";

export function openCartTray() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(OPEN_CART_TRAY_EVENT));
}

export function openFavoritesTray() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(OPEN_FAVORITES_TRAY_EVENT));
}
