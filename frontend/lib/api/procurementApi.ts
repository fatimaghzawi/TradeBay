import { apiClient } from "@/lib/api/client";

export type Address = {
  street?: string | null;
  city?: string | null;
  district?: string | null;
  governorate?: string | null;
  postal_code?: string | null;
  country?: string | null;
};

export type RFQItem = {
  id: string;
  product_id: string | null;
  category_id: string | null;
  supplier_business_id?: string | null;
  supplier_name?: string | null;
  product_name: string;
  sku: string | null;
  quantity: string;
  unit: string;
  target_unit_price: string | null;
  catalog_unit_price?: string | null;
  primary_image_url?: string | null;
  requirements: string | null;
  notes: string | null;
  sort_order?: number;
};

export type RFQInvite = {
  supplier_business_id: string | null;
  supplier_name?: string | null;
  supplier_logo_url?: string | null;
  status: string;
  invited_at: string | null;
  viewed_at: string | null;
  responded_at: string | null;
  decline_reason: string | null;
};

export type QuotationSummary = {
  id: string;
  quotation_number: string;
  rfq_id: string | null;
  supplier_id: string | null;
  supplier_name?: string | null;
  supplier_logo_url?: string | null;
  status: string;
  currency: string;
  subtotal: string;
  discount_total: string;
  charge_total: string;
  tax_total: string;
  total: string;
  current_version: number;
  valid_until: string | null;
  submitted_at: string | null;
};

export type QuotationLine = {
  id: string;
  rfq_item_id: string | null;
  version?: number;
  product_id: string | null;
  product_name_snapshot: string | null;
  sku_snapshot: string | null;
  quantity: string;
  unit: string;
  unit_price: string;
  moq: number | null;
  lead_time_days: number | null;
  discount: string;
  tax: string;
  shipping_allocation: string;
  line_total: string;
  notes: string | null;
};

export type Quotation = QuotationSummary & {
  payment_terms: string | null;
  delivery_terms: string | null;
  notes: string | null;
  lines: QuotationLine[];
};

export type RFQSummary = {
  id: string;
  rfq_number: string;
  title: string;
  rfq_type?: "product" | "sourcing" | string;
  status: string;
  visibility: string;
  currency: string;
  product_id?: string | null;
  supplier_business_id?: string | null;
  buyer_business_id?: string | null;
  buyer_name?: string | null;
  buyer_logo_url?: string | null;
  response_deadline: string | null;
  invite_count: number;
  quotation_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type RFQDetail = RFQSummary & {
  description: string | null;
  destination: Address | null;
  required_by: string | null;
  notes: string | null;
  awarded_quotation_id: string | null;
  supplier_name?: string | null;
  supplier_logo_url?: string | null;
  source?: string | null;
  source_supplier_ids?: string[];
  items: RFQItem[];
  invites: RFQInvite[];
  quotations: Quotation[];
  supplier_requests?: SupplierRequest[];
  order_id?: string | null;
  order_number?: string | null;
  order_status?: string | null;
};

export type EligibleSupplier = {
  supplier_business_id: string;
  name: string | null;
  verified: boolean;
  product_match: boolean;
  can_invite?: boolean;
  verification_status?: string | null;
  products?: {
    product_id: string | null;
    product_name: string | null;
    sku?: string | null;
    quantity?: string | null;
    unit?: string | null;
  }[];
};

export type SupplierRequest = {
  supplier_business_id: string | null;
  supplier_name?: string | null;
  invite_status?: string | null;
  quotation_id?: string | null;
  quotation_status?: string | null;
  stage: string;
  products: {
    id?: string;
    product_name?: string | null;
    quantity?: string | null;
    unit?: string | null;
    primary_image_url?: string | null;
  }[];
};

export type ComparisonResult = {
  rfq: RFQSummary;
  rfq_items: RFQItem[];
  quotations: { quotation: QuotationSummary; lines: QuotationLine[] }[];
};

export type OrderItem = {
  id: string;
  product_id: string | null;
  product_name_snapshot: string | null;
  sku_snapshot: string | null;
  quantity: string;
  unit: string;
  unit_price: string;
  line_total: string;
  shipped_quantity: string | null;
  received_quantity: string | null;
  damaged_quantity: string | null;
  missing_quantity: string | null;
  rejected_quantity: string | null;
};

export type ShipmentSummary = {
  id: string;
  shipment_number: string;
  order_id: string | null;
  status: string;
  carrier_name: string | null;
  tracking_number: string | null;
  estimated_delivery_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
};

export type PurchaseOrderSummary = {
  id: string;
  order_number: string;
  status: string;
  currency: string;
  total: string;
  buyer_business_id: string | null;
  buyer_name?: string | null;
  buyer_logo_url?: string | null;
  buyer_legal_name?: string | null;
  buyer_tax_number?: string | null;
  buyer_contact_email?: string | null;
  buyer_contact_phone?: string | null;
  buyer_address?: Address | null;
  supplier_business_id: string | null;
  supplier_name?: string | null;
  supplier_logo_url?: string | null;
  supplier_legal_name?: string | null;
  supplier_tax_number?: string | null;
  supplier_contact_email?: string | null;
  supplier_contact_phone?: string | null;
  supplier_address?: Address | null;
  rfq_id: string | null;
  quotation_id: string | null;
  quotation_number?: string | null;
  created_at: string | null;
  confirmed_at: string | null;
};

export type PurchaseOrder = PurchaseOrderSummary & {
  subtotal: string;
  discount_total: string;
  charge_total: string;
  tax_total: string;
  tax_rate_snapshot?: string | null;
  tax_name_snapshot?: string | null;
  tax_rate_percent?: string | null;
  payment_terms: string | null;
  payment_method?: string | null;
  delivery_terms: string | null;
  payment_status: string | null;
  shipping_address: Address | null;
  rejection_reason: string | null;
  status_history: { status: string; note: string | null; changed_at: string | null }[];
  items: OrderItem[];
  shipments: ShipmentSummary[];
};

export type Shipment = ShipmentSummary & {
  origin: string | null;
  shipping_notes: string | null;
  shipping_address: Address | null;
  tracking_events: {
    status: string;
    description: string | null;
    location: string | null;
    source: string;
    occurred_at: string | null;
  }[];
  delivery_evidence: {
    evidence_type: string;
    url: string;
    note: string | null;
    captured_at: string | null;
  }[];
  receiving: {
    order_item_id: string | null;
    received_quantity: string;
    damaged_quantity: string;
    missing_quantity: string;
    rejected_quantity: string;
    notes: string | null;
  }[];
  received_at: string | null;
  items: {
    id: string;
    order_item_id: string | null;
    product_name_snapshot: string | null;
    sku_snapshot: string | null;
    quantity: string;
    unit: string;
  }[];
};

export type ProcurementDashboard = {
  role: "buyer" | "supplier";
  next_actions: ({ key: string; label: string } | null)[];
  rfqs: RFQSummary[];
  orders: PurchaseOrderSummary[];
  quotes_waiting?: number;
  pending_acknowledgements?: number;
};

export type CreateRFQItemInput = {
  product_id?: string | null;
  category_id?: string | null;
  product_name: string;
  sku?: string | null;
  quantity: string;
  unit?: string;
  catalog_unit_price?: string | null;
  target_unit_price?: string | null;
  primary_image_url?: string | null;
  requirements?: string | null;
  notes?: string | null;
  supplier_business_id?: string | null;
};

export type SentRfqSummary = {
  id: string;
  rfq_number?: string | null;
  supplier_business_id?: string | null;
  supplier_name?: string | null;
  item_count?: number;
};

export type SendRfqResult = {
  rfq: RFQDetail;
  sent: SentRfqSummary[];
};

export type CreateRFQInput = {
  title: string;
  description?: string | null;
  destination?: Address | null;
  required_by?: string | null;
  response_deadline?: string | null;
  currency?: string;
  notes?: string | null;
  visibility?: string;
  items: CreateRFQItemInput[];
  sourcing_request_id?: string | null;
  business_plan_id?: string | null;
};

export type QuotationLineInput = {
  rfq_item_id: string;
  quantity: string;
  unit_price: string;
  moq?: number | null;
  lead_time_days?: number | null;
  discount?: string;
  tax?: string;
  shipping_allocation?: string;
  notes?: string | null;
};

export type UpsertQuotationInput = {
  valid_until?: string | null;
  payment_terms?: string | null;
  delivery_terms?: string | null;
  currency?: string;
  notes?: string | null;
  document_discount?: string;
  document_shipping?: string;
  document_tax?: string;
  lines: QuotationLineInput[];
};

export const procurementApi = {
  dashboard: () => apiClient.get<ProcurementDashboard>("/procurement/dashboard"),

  listRfqs: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    rfq_type?: string;
    as_supplier?: boolean;
  }) => apiClient.getPage<RFQSummary>("/rfqs", { params }),

  getRfq: (id: string) => apiClient.get<RFQDetail>(`/rfqs/${id}`),

  createRfq: (body: CreateRFQInput) => apiClient.post<RFQDetail>("/rfqs", body),

  createProductRfq: (body: {
    product_id: string;
    quantity: string;
    unit?: string;
    target_unit_price?: string | null;
    required_by?: string | null;
    response_deadline?: string | null;
    destination?: Address | null;
    requirements?: string | null;
    notes?: string | null;
    currency?: string;
    publish?: boolean;
  }) => apiClient.post<RFQDetail>("/rfqs/product", body),

  createSourcingRfq: (body: {
    title: string;
    description?: string | null;
    requirements?: string | null;
    quantity: string;
    unit?: string;
    target_unit_price?: string | null;
    category_id?: string | null;
    product_name?: string | null;
    required_by?: string | null;
    response_deadline?: string | null;
    destination?: Address | null;
    notes?: string | null;
    currency?: string;
    visibility?: string;
    publish?: boolean;
    items?: CreateRFQItemInput[];
    sourcing_request_id?: string | null;
    business_plan_id?: string | null;
  }) => apiClient.post<RFQDetail>("/rfqs/sourcing", body),

  updateRfq: (id: string, body: Partial<CreateRFQInput>) =>
    apiClient.patch<RFQDetail>(`/rfqs/${id}`, body),

  publishRfq: (id: string) => apiClient.post<RFQDetail>(`/rfqs/${id}/publish`),

  sendRfq: (id: string) => apiClient.post<SendRfqResult>(`/rfqs/${id}/send`),

  eligibleSuppliers: (rfqId: string) =>
    apiClient.get<EligibleSupplier[]>(`/rfqs/${rfqId}/eligible-suppliers`),

  inviteSuppliers: (rfqId: string, supplier_business_ids: string[]) =>
    apiClient.post<RFQDetail>(`/rfqs/${rfqId}/invite-suppliers`, { supplier_business_ids }),

  acceptInvite: (rfqId: string) =>
    apiClient.post<RFQDetail>(`/rfqs/${rfqId}/invitations/accept`),

  declineInvite: (rfqId: string, reason?: string) =>
    apiClient.post<RFQDetail>(`/rfqs/${rfqId}/invitations/decline`, { reason }),

  upsertQuotation: (rfqId: string, body: UpsertQuotationInput, submit = false) =>
    apiClient.post<Quotation>(`/rfqs/${rfqId}/quotations`, body, {
      params: { submit },
    }),

  comparison: (rfqId: string) =>
    apiClient.get<ComparisonResult>(`/rfqs/${rfqId}/comparison`),

  award: (rfqId: string, quotation_id: string) =>
    apiClient.post<PurchaseOrder>(`/rfqs/${rfqId}/award`, {
      quotation_id,
      confirm: true,
    }),

  handshake: (rfqId: string, quotation_id: string) =>
    apiClient.post<PurchaseOrder>(`/rfqs/${rfqId}/handshake`, {
      quotation_id,
      confirm: true,
    }),

  issueOrder: (
    orderId: string,
    body: {
      payment_method: string;
      payment_terms?: string | null;
      delivery_terms?: string | null;
    },
  ) => apiClient.post<PurchaseOrder>(`/purchase-orders/${orderId}/issue`, body),

  getQuotation: (id: string) => apiClient.get<Quotation>(`/quotations/${id}`),

  withdrawQuotation: (id: string) =>
    apiClient.post<Quotation>(`/quotations/${id}/withdraw`),

  rejectQuotation: (id: string, reason?: string) =>
    apiClient.post<Quotation>(`/quotations/${id}/reject`, { reason: reason || null }),

  listOrders: (params?: { page?: number; page_size?: number; status?: string }) =>
    apiClient.getPage<PurchaseOrderSummary>("/purchase-orders", { params }),

  getOrder: (id: string) => apiClient.get<PurchaseOrder>(`/purchase-orders/${id}`),

  acknowledgeOrder: (id: string) =>
    apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/acknowledge`),

  createShipment: (
    orderId: string,
    body: {
      carrier_name?: string;
      origin?: string;
      estimated_delivery_at?: string;
      shipping_notes?: string;
      lines: { order_item_id: string; quantity: string }[];
    },
  ) => apiClient.post<Shipment>(`/purchase-orders/${orderId}/shipments`, body),

  getShipment: (id: string) => apiClient.get<Shipment>(`/shipments/${id}`),

  addTrackingEvent: (
    id: string,
    body: { status: string; description?: string; location?: string },
  ) => apiClient.post<Shipment>(`/shipments/${id}/tracking-events`, body),

  addDeliveryEvidence: (
    id: string,
    body: { evidence_type: string; url: string; note?: string },
  ) => apiClient.post<Shipment>(`/shipments/${id}/delivery-evidence`, body),

  receiveShipment: (
    id: string,
    body: {
      notes?: string;
      complete_order?: boolean;
      lines: {
        order_item_id: string;
        received_quantity: string;
        damaged_quantity?: string;
        missing_quantity?: string;
        rejected_quantity?: string;
        notes?: string;
      }[];
    },
  ) => apiClient.post<Shipment>(`/shipments/${id}/receive`, body),

  orderPdfUrl: (orderId: string) => `/api/v1/purchase-orders/${orderId}/pdf`,

  quotationPdfUrl: (quotationId: string) => `/api/v1/quotations/${quotationId}/pdf`,
};
