"use client";

import { ROUTES } from "@/lib/constants";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

function RedirectToCatalogRfq() {
  const router = useRouter();
  const search = useSearchParams();

  useEffect(() => {
    const qs = search.toString();
    router.replace(qs ? `${ROUTES.procurementNew}?${qs}` : ROUTES.procurementNew);
  }, [router, search]);

  return <LoadingEntity entity="RFQ" />;
}

export default function SourcingRfqPage() {
  return (
    <Suspense fallback={<LoadingEntity entity="RFQ" />}>
      <RedirectToCatalogRfq />
    </Suspense>
  );
}
