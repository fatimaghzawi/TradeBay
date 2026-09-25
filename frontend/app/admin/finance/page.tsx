"use client";

import { AdminFinance } from "@/components/commerce/AdminFinance";
import { Suspense } from "react";

export default function AdminFinancePage() {
  return (
    <Suspense fallback={null}>
      <AdminFinance />
    </Suspense>
  );
}
