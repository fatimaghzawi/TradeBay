"use client";

import { AdminPayoutDesk } from "@/components/admin/AdminMoneyDesk";
import { Suspense } from "react";

export default function AdminSettlementsPage() {
  return (
    <Suspense fallback={null}>
      <AdminPayoutDesk />
    </Suspense>
  );
}
