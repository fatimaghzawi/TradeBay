"use client";

import { PermissionGate } from "@/components/auth/PermissionGate";
import { InvoiceDocument } from "@/components/commerce/InvoiceDocument";
import { use } from "react";

export default function InvoicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <PermissionGate permission="invoices.read">
      <InvoiceDocument invoiceId={id} />
    </PermissionGate>
  );
}
