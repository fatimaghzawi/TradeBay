import { apiClient } from "@/lib/api/client";

export type Invoice = {
  id: string;
  invoice_number: string;
  order_id: string | null;
  order_number?: string | null;
  checkout_id?: string | null;
  buyer_business_id?: string | null;
  buyer_name?: string | null;
  supplier_business_id?: string | null;
  supplier_name?: string | null;
  status: string;
  currency: string;
  subtotal?: string | null;
  discount_total?: string | null;
  charge_total?: string | null;
  tax_total?: string | null;
  tax_name?: string | null;
  tax_rate?: string | null;
  total: string;
  amount_paid: string;
  amount_credited?: string;
  amount_due?: string;
  outstanding: string;
  customer_credit?: string;
  issued_at: string | null;
  due_at: string | null;
  created_at?: string | null;
  lines?: {
    product_id?: string | null;
    description: string;
    quantity: string | null;
    unit?: string | null;
    unit_price: string | null;
    line_total: string | null;
  }[];
  payment?: {
    payment_reference: string | null;
    receipt_number: string | null;
    status: string;
    method: string | null;
    paid_at: string | null;
  } | null;
};

export type Payable = {
  id: string;
  payable_number: string;
  order_id: string | null;
  status: string;
  currency: string;
  gross_amount: string | null;
  commission_amount: string | null;
  net_payable_amount: string | null;
};

export type ArBalance = {
  business_id: string;
  currency: string;
  debits: string;
  credits: string;
  outstanding: string;
};

export type FinancialTransaction = {
  id: string;
  transaction_number: string;
  transaction_type: string;
  direction: string;
  amount: string | null;
  description: string | null;
  posted_at: string | null;
};

export type CreditNote = {
  id: string;
  credit_note_number: string;
  invoice_id: string | null;
  amount: string | null;
  reason: string | null;
  status: string;
};

export type Payment = {
  id: string;
  payment_reference: string;
  receipt_number?: string | null;
  receipt_issued_at?: string | null;
  amount: string | null;
  currency?: string;
  status: string;
  payment_method: string | null;
  provider?: string | null;
  checkout_id?: string | null;
  failure_message?: string | null;
  created_at?: string | null;
  paid_at?: string | null;
  allocations?: { invoice_id: string; allocated_amount: string | null }[];
};

export const financeApi = {
  listInvoices: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<Invoice>("/invoices", { params }),

  getPayment: (id: string) => apiClient.get<Payment>(`/payments/${id}`),

  getInvoice: (id: string) => apiClient.get<Invoice>(`/invoices/${id}`),

  recordPayment: (
    invoiceId: string,
    body: { amount: string; payment_method?: string; reference?: string; complete?: boolean },
  ) =>
    apiClient.post<{ payment_id: string; invoice: Invoice; status: string }>(
      `/invoices/${invoiceId}/payments`,
      body,
    ),

  listPayments: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<Payment>("/payments", { params }),

  completePayment: (paymentId: string) =>
    apiClient.post<Payment>(`/payments/${paymentId}/complete`),

  listCreditNotes: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<CreditNote>("/credit-notes", { params }),

  createCreditNote: (
    invoiceId: string,
    body: { amount: string; reason: string; apply?: boolean },
  ) => apiClient.post<CreditNote>(`/invoices/${invoiceId}/credit-notes`, body),

  createRefund: (
    paymentId: string,
    body: { amount: string; reason?: string; credit_note_id?: string; process?: boolean },
  ) => apiClient.post(`/payments/${paymentId}/refunds`, body),

  arBalance: () => apiClient.get<ArBalance>("/finance/ar-balance"),

  customerBalance: (buyerId: string) =>
    apiClient.get<ArBalance>(`/finance/customers/${buyerId}/balance`),

  listTransactions: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<FinancialTransaction>("/finance/transactions", { params }),

  customerTransactions: (buyerId: string, params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<FinancialTransaction>(`/finance/customers/${buyerId}/transactions`, {
      params,
    }),

  listPayables: (params?: { page?: number; page_size?: number }) =>
    apiClient.getPage<Payable>("/payables", { params }),

  settlePayable: (id: string) => apiClient.post<Payable>(`/payables/${id}/settle`),
};
