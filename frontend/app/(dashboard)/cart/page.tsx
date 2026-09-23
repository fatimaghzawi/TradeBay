"use client";

import { ROUTES } from "@/lib/constants";
import { openCartTray } from "@/lib/shoppingTrays";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Legacy /cart route — opens the cart tray over the marketplace. */
export default function CartPage() {
  const router = useRouter();

  useEffect(() => {
    openCartTray();
    router.replace(ROUTES.inventoryProducts);
  }, [router]);

  return (
    <p className="py-16 text-center text-sm text-[var(--tb-muted-fg)]">Opening cart…</p>
  );
}
