"use client";

import { ROUTES } from "@/lib/constants";
import { openCartTray } from "@/lib/shoppingTrays";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function CartPage() {
  const router = useRouter();

  useEffect(() => {
    openCartTray();
    router.replace(ROUTES.inventoryProducts);
  }, [router]);

  return (
    <p className="py-16 text-center text-sm text-muted-foreground">Opening cart…</p>
  );
}
