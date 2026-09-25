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
  order_number?: string | null;
  fee: PlatformFee | null;
  payable: Record<string, unknown> | null;
  payout: SupplierPayout | null;
  transactions: PlatformTransaction[];
  story?: OrderMoneyStory;
};

export type FinanceStoryStage = {
  key: string;
  label: string;
  done: boolean;
  current: boolean;
  amount: string | null;
};

export type FinanceStory = {
  id: string;
  kind: "buyer_payment" | "payout" | "refund" | string;
  posted_at: string | null;
  amount: string;
  currency: string;
  order_id: string | null;
  order_number: string | null;
  order_status: string | null;
  buyer_name: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  payment_method: string | null;
  payment_reference: string | null;
  payout_id: string | null;
  payout_number: string | null;
  payout_status: string | null;
  state: string;
  buyer_paid: string;
  commission: string;
  supplier_earnings: string;
  supplier_paid: string;
  remaining: string;
  held_amount: string;
  reason: string | null;
  next_step: string | null;
  transaction_number: string | null;
  payable_number: string | null;
  stages: FinanceStoryStage[];
};

export type FinancialActivityFeed = {
  currency: string;
  today: { buyer_payments: string; payouts: string; commission: string };
  stories: FinanceStory[];
};

export type FinanceActivity = {
  id: string;
  message: string;
  posted_at: string | null;
  order_id: string | null;
  order_number: string | null;
  kind: string;
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
  buyer_payments_count: number;
  held_orders_count: number;
  released_orders_count: number;
  completed_payouts_count: number;
  paid_this_month_amount: string;
  ready_suppliers_count: number;
  outstanding_amount: string;
  outstanding_suppliers_count: number;
  commission_rate: string | null;
  pending_payouts_count: number;
  pending_payouts_net: string;
  ready_payouts_count: number;
  ready_payouts_net: string;
  processing_payouts_count: number;
  processing_payouts_net: string;
  open_payables_count: number;
  recognized_fees_count: number;
  refunds_count: number;
  recent_transactions: PlatformTransaction[];
  pending_payouts: SupplierPayout[];
  activity: FinanceActivity[];
};

export type MoneyMovement = {
  range: string;
  bucket: "day" | "week";
  buckets: {
    label: string;
    buyer_payments: string;
    released: string;
    payouts: string;
    commission: string;
  }[];
};

export type BuyerPaymentRow = {
  id: string;
  payment_id: string | null;
  payment_reference: string | null;
  order_id: string | null;
  order_number: string | null;
  buyer_name: string | null;
  amount: string | null;
  currency: string;
  payment_method: string | null;
  status_label: string;
  funds_label: string;
  paid_at: string | null;
  commission_amount: string | null;
  supplier_amount: string | null;
};

export type OrderMoneyStory = {
  currency: string;
  buyer_paid: string;
  payment_method: string | null;
  payment_status: string;
  held_amount: string;
  hold_reason: string | null;
  released_amount: string;
  supplier_gross: string;
  commission_amount: string;
  supplier_payable: string;
  paid_to_supplier: string;
  remaining: string;
  refunded_amount: string;
};

export const platformMoneyApi = {
  overview: () => apiClient.get<PlatformMoneyOverview>("/platform-money/overview"),

  movement: (range: "7d" | "30d" | "90d" | "year") =>
    apiClient.get<MoneyMovement>("/platform-money/movement", { params: { range } }),

  listBuyerPayments: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<BuyerPaymentRow>("/platform-money/buyer-payments", { params }),

  financialActivity: () => apiClient.get<FinancialActivityFeed>("/platform-money/activity"),

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
