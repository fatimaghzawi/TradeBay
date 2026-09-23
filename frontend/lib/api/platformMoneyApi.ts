import { apiClient } from "@/lib/api/client";

export type PlatformTransaction = {
  id: string;
  transaction_number: string | null;
  type: string;
  amount: string | null;
  currency: string;
  funds_state: string | null;
  reference_type: string | null;
  reference_id: string | null;
  order_id: string | null;
  payment_id: string | null;
  supplier_business_id: string | null;
  status: string | null;
  description: string | null;
  posted_at: string | null;
};

export type PlatformFee = {
  id: string;
  order_id: string | null;
  supplier_business_id: string | null;
  base_amount: string | null;
  rate: string | null;
  commission_amount: string | null;
  currency: string;
  status: string | null;
  recognized_at: string | null;
};

export type SupplierPayout = {
  id: string;
  payout_number: string | null;
  supplier_business_id: string | null;
  supplier_payable_id: string | null;
  gross_amount: string | null;
  platform_fee_amount: string | null;
  net_amount: string | null;
  currency: string;
  status: string;
  provider: string | null;
  provider_transaction_id: string | null;
  failure_reason: string | null;
  completed_at: string | null;
};

export type OrderMoneySummary = {
  order_id: string;
  fee: PlatformFee | null;
  payable: Record<string, unknown> | null;
  payout: SupplierPayout | null;
  transactions: PlatformTransaction[];
};

export type PlatformMoneyOverview = {
  currency: string;
  held_amount: string;
  released_amount: string;
  fees_ledger_amount: string;
  fees_recognized_amount: string;
  payouts_completed_amount: string;
  refunds_amount: string;
  buyer_payments_amount: string;
  pending_payouts_count: number;
  pending_payouts_net: string;
  open_payables_count: number;
  recognized_fees_count: number;
  recent_transactions: PlatformTransaction[];
  pending_payouts: SupplierPayout[];
};

export const platformMoneyApi = {
  overview: () => apiClient.get<PlatformMoneyOverview>("/platform-money/overview"),

  listTransactions: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<PlatformTransaction>("/platform-money/transactions", { params }),

  getTransaction: (id: string) =>
    apiClient.get<PlatformTransaction>(`/platform-money/transactions/${id}`),

  listFees: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<PlatformFee>("/platform-money/fees", { params }),

  listPayouts: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<SupplierPayout>("/platform-money/payouts", { params }),

  getPayout: (id: string) =>
    apiClient.get<SupplierPayout>(`/platform-money/payouts/${id}`),

  processPayout: (id: string) =>
    apiClient.post<SupplierPayout>(`/platform-money/payouts/${id}/process`),

  failPayout: (id: string, reason?: string) =>
    apiClient.post<SupplierPayout>(`/platform-money/payouts/${id}/fail`, {
      reason: reason ?? null,
    }),

  releaseOrderFunds: (orderId: string) =>
    apiClient.post(`/platform-money/orders/${encodeURIComponent(orderId)}/release`),

  orderSummary: (orderId: string) =>
    apiClient.get<OrderMoneySummary>(`/platform-money/orders/${orderId}/summary`),
};
