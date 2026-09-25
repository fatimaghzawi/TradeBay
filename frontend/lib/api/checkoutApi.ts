import { apiClient } from "@/lib/api/client";
import { emitCartChanged } from "@/lib/api/cartApi";

export type PaymentMethodId = "cash" | "card";

export type CheckoutLine = {
  product_id: string | null;
  product_name: string;
  sku?: string | null;
  unit: string;
  moq?: number;
  quantity: number | string;
  unit_price: string;
  line_total: string;
  image_url?: string | null;
};

export type CheckoutPreviewGroup = {
  supplier_business_id: string;
  supplier_name: string;
  currency: string;
  subtotal: string;
  tax_total: string;
  tax_name: string | null;
  tax_rate: string | null;
  total: string;
  lines: CheckoutLine[];
};

export type PaymentMethodOption = {
  id: PaymentMethodId;
  label: string;
  available: boolean;
  description: string;
};

export type CheckoutPreview = {
  currency: string;
  supplier_count: number;
  subtotal: string;
  tax_total: string;
  total: string;
  split_notice: string | null;
  price_changes: {
    product_id: string;
    product_name: string;
    previous_unit_price: string | null;
    unit_price: string;
  }[];
  groups: CheckoutPreviewGroup[];
  methods: PaymentMethodOption[];
  card_publishable_key: string | null;
};

export type CheckoutOrder = {
  order_id: string;
  order_number: string;
  order_status: string;
  payment_status: string | null;
  supplier_business_id: string;
  supplier_name: string;
  subtotal: string;
  tax_total: string;
  total: string;
  line_count: number;
  invoice: { id: string; invoice_number: string; status: string; total: string } | null;
  lines?: CheckoutLine[];
};

export type CheckoutPayment = {
  id: string;
  payment_reference: string;
  status: string;
  method: PaymentMethodId;
  provider: string;
  amount: string;
  currency: string;
  failure_message: string | null;
  receipt_number: string | null;
  paid_at: string | null;
  requires_attention: boolean;
  allocations: { invoice_id: string; invoice_number: string | null; supplier_name: string | null; amount: string }[];
};

export type Checkout = {
  id: string;
  checkout_number: string;
  status: "awaiting_payment" | "paid" | "cancelled" | string;
  payment_method: PaymentMethodId;
  currency: string;
  subtotal: string;
  tax_total: string;
  total: string;
  active_total: string;
  supplier_count: number;
  split_notice: string | null;
  notes: string | null;
  buyer_business_id: string;
  orders: CheckoutOrder[];
  payment: CheckoutPayment | null;
  card_publishable_key: string | null;
  status_history: { status: string; note: string | null; changed_at: string | null }[];
  created_at: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  client_secret?: string | null;
  idempotent_replay?: boolean;
};

export type SupplierBalance = {
  supplier_business_id?: string;
  supplier_name?: string | null;
  currency?: string;
  gross_sales: string;
  platform_fees: string;
  net_earnings: string;
  pending_balance: string;
  available_balance: string;
  paid_out: string;
  total_credits: string;
  total_debits: string;
  balance: string;
  logo_url?: string | null;
  verification_status?: string | null;
  orders_count?: number;
  pending_payout_id?: string | null;
  position?: "paid" | "partially_paid" | "ready" | "on_hold" | string;
};

export type SupplierLedgerEntry = {
  id: string;
  entry_type: "sale" | "platform_fee" | "funds_released" | "payout" | "adjustment" | string;
  direction: "credit" | "debit";
  bucket: "pending" | "available";
  amount: string;
  currency: string;
  order_id: string | null;
  order_number?: string | null;
  invoice_number?: string | null;
  commission_rate?: string | null;
  description?: string | null;
  created_at: string | null;
  running_balance?: string | null;
};

export type SupplierFinanceOrder = {
  order_id: string;
  order_number: string | null;
  buyer_name: string | null;
  order_value: string;
  commission: string;
  supplier_earnings: string;
  money_state: "held" | "ready" | "paid" | "partial" | string;
  paid: string;
  remaining: string;
  paid_at: string | null;
  order_status: string | null;
  lifecycle: {
    buyer_paid: boolean;
    held: boolean;
    fulfilled: boolean;
    released: boolean;
    ready: boolean;
    supplier_paid: boolean;
  };
};

export type SupplierFinanceEvent = {
  id: string;
  kind: string;
  filters: string[];
  title: string;
  detail: string;
  order_id: string | null;
  order_number: string | null;
  amount: string;
  sign: "plus" | "plain" | "minus";
  created_at: string | null;
};

export type SupplierFinancePayout = {
  id: string;
  payout_number: string | null;
  status: string | null;
  net_amount: string;
  currency: string;
  order_id: string | null;
  order_number: string | null;
  created_at: string | null;
  completed_at: string | null;
};

export type SupplierFinancialOverview = {
  supplier_name: string;
  currency: string;
  gross_sales: string;
  commission: string;
  supplier_earnings: string;
  paid: string;
  held: string;
  ready: string;
  outstanding: string;
  paid_order_count: number;
  held_order_count: number;
  ready_payout_count: number;
  held_share: string;
  last_payment: { amount: string; paid_at: string | null; order_number: string | null } | null;
  orders: SupplierFinanceOrder[];
  activity: SupplierFinanceEvent[];
  payouts: SupplierFinancePayout[];
  trend: {
    range: string;
    bucket: string;
    buckets: {
      label: string;
      gross_sales: string;
      commission: string;
      supplier_earnings: string;
      payouts: string;
    }[];
  };
};

export const checkoutApi = {
  preview: () => apiClient.get<CheckoutPreview>("/checkout/preview"),

  
  place: (
    idempotencyKey: string,
    body: { payment_method: PaymentMethodId; expected_total?: string; notes?: string },
  ) =>
    apiClient
      .post<Checkout>("/checkouts", body, { headers: { "Idempotency-Key": idempotencyKey } })
      .then((checkout) => {
        emitCartChanged({ buyer_business_id: checkout.buyer_business_id, item_count: 0, quantity_total: 0, items: [] });
        return checkout;
      }),

  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    apiClient.getPage<Checkout>("/checkouts", { params }),

  get: (id: string) => apiClient.get<Checkout>(`/checkouts/${id}`),

  startCardPayment: (id: string) =>
    apiClient.post<{ client_secret: string; publishable_key: string | null; checkout: Checkout }>(
      `/checkouts/${id}/card-payment`,
    ),

  refreshPayment: (id: string) => apiClient.post<Checkout>(`/checkouts/${id}/refresh-payment`),

  cancel: (id: string, reason?: string) =>
    apiClient.post<Checkout>(`/checkouts/${id}/cancel`, { reason: reason || undefined }),

  cancelOrder: (orderId: string, reason?: string) =>
    apiClient.post<{ order_id: string; status: string }>(`/purchase-orders/${orderId}/cancel`, {
      reason: reason || undefined,
    }),

  confirmCash: (paymentId: string, note?: string) =>
    apiClient.post(`/payments/${paymentId}/confirm-cash`, { note: note || undefined }),

  supplierBalance: () => apiClient.get<SupplierBalance>("/supplier-balance"),

  supplierEntries: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<SupplierLedgerEntry>("/supplier-balance/entries", { params }),

  adminBalances: () => apiClient.get<SupplierBalance[]>("/admin/supplier-balances"),

  adminSupplierEntries: (supplierId: string, params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<SupplierLedgerEntry>(`/admin/supplier-balances/${supplierId}/entries`, { params }),

  adminSupplierOverview: (supplierId: string, range: "7d" | "30d" | "90d" | "year" = "30d") =>
    apiClient.get<SupplierFinancialOverview>(`/admin/supplier-balances/${supplierId}/overview`, {
      params: { range },
    }),
};

export function newIdempotencyKey(): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `checkout-${rand}`;
}
