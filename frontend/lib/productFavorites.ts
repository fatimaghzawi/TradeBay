/** Local product favorites for guests and signed-in users. */

export type SavedProduct = {
  id: string;
  name: string;
  image?: string | null;
  /** Optional deep link when id is not a catalog product (e.g. landing demos). */
  href?: string | null;
  savedAt: string;
};

const STORAGE_KEY = "tradebay.product-favorites";
export const PRODUCT_FAV_EVENT = "tradebay-product-fav-change";

function canUseStorage() {
  return typeof window !== "undefined";
}

function readAll(): SavedProduct[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedProduct[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === "string" && item.id);
  } catch {
    return [];
  }
}

function writeAll(items: SavedProduct[]) {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new Event(PRODUCT_FAV_EVENT));
  } catch {
    /* ignore */
  }
}

export function listSavedProducts(): SavedProduct[] {
  return readAll().sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1));
}

export function isProductSaved(productId: string): boolean {
  return readAll().some((item) => item.id === productId);
}

export function toggleProductFavorite(input: {
  id: string;
  name: string;
  image?: string | null;
  href?: string | null;
}): { saved: boolean; items: SavedProduct[] } {
  const existing = readAll();
  if (existing.some((item) => item.id === input.id)) {
    const next = existing.filter((item) => item.id !== input.id);
    writeAll(next);
    return { saved: false, items: next };
  }
  const next: SavedProduct[] = [
    {
      id: input.id,
      name: input.name.trim() || "Product",
      image: input.image ?? null,
      href: input.href ?? null,
      savedAt: new Date().toISOString(),
    },
    ...existing,
  ];
  writeAll(next);
  return { saved: true, items: next };
}

export function removeProductFavorite(productId: string): SavedProduct[] {
  const next = readAll().filter((item) => item.id !== productId);
  writeAll(next);
  return next;
}

export function favoriteCount(): number {
  return readAll().length;
}
