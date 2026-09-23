export type SavedSupplier = {
  id: string;
  name: string;
  verified?: boolean;
  savedAt: string;
};

const STORAGE_KEY = "tradebay.supplier-shortlist";
export const SHORTLIST_EVENT = "tradebay-shortlist-change";

function canUseStorage() {
  return typeof window !== "undefined";
}

function readAll(): SavedSupplier[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedSupplier[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === "string" && item.id);
  } catch {
    return [];
  }
}

function writeAll(items: SavedSupplier[]) {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new Event(SHORTLIST_EVENT));
  } catch {
    /* ignore quota / private mode */
  }
}

export function listSavedSuppliers(): SavedSupplier[] {
  return readAll().sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1));
}

export function isSupplierSaved(supplierId: string): boolean {
  return readAll().some((item) => item.id === supplierId);
}

export function saveSupplier(input: {
  id: string;
  name: string;
  verified?: boolean;
}): SavedSupplier[] {
  const existing = readAll().filter((item) => item.id !== input.id);
  const next: SavedSupplier[] = [
    {
      id: input.id,
      name: input.name.trim() || "Supplier",
      verified: Boolean(input.verified),
      savedAt: new Date().toISOString(),
    },
    ...existing,
  ];
  writeAll(next);
  return next;
}

export function removeSupplier(supplierId: string): SavedSupplier[] {
  const next = readAll().filter((item) => item.id !== supplierId);
  writeAll(next);
  return next;
}

export function toggleSupplier(input: {
  id: string;
  name: string;
  verified?: boolean;
}): { saved: boolean; items: SavedSupplier[] } {
  if (isSupplierSaved(input.id)) {
    return { saved: false, items: removeSupplier(input.id) };
  }
  return { saved: true, items: saveSupplier(input) };
}
