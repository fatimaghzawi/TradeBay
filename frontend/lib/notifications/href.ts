import type { AppNotification } from "@/lib/api/notificationsApi";
import { ROUTES } from "@/lib/constants";

export function notificationHref(n: AppNotification): string {
  const path = n.cta_path?.trim();
  if (path?.startsWith("/") && !path.startsWith("//")) {
    // Route unfinished order/finance deep links to Coming Soon surfaces.
    if (
      path.startsWith("/orders") ||
      path.startsWith("/procurement/orders") ||
      path.startsWith("/tracking")
    ) {
      return ROUTES.orders;
    }
    if (path.startsWith("/finance") || path.startsWith("/admin/finance")) {
      return ROUTES.finance;
    }
    return path;
  }
  if (n.reference_type === "invoice") return ROUTES.finance;
  if (n.reference_type === "order") return ROUTES.orders;
  if (n.reference_type === "rfq" && n.reference_id) {
    return ROUTES.procurementRfq(n.reference_id);
  }
  if (n.reference_type === "shipment") return ROUTES.tracking;
  if (n.reference_type === "quotation" && n.reference_id) {
    return ROUTES.quotations;
  }
  if (n.reference_type === "negotiation" && n.reference_id) {
    return `/negotiations/${n.reference_id}`;
  }
  if (n.reference_type === "conversation" && n.reference_id) {
    return `/conversations/${n.reference_id}`;
  }
  if (n.reference_type === "dispute") return ROUTES.notifications;
  if (n.reference_type === "supplier_verification") return ROUTES.admin.suppliers;
  if (n.reference_type === "invitation") return ROUTES.acceptInvitation;
  if (n.reference_type === "membership") return ROUTES.members;
  if (n.reference_type === "business") return ROUTES.settings;
  return ROUTES.notifications;
}
