import { apiClient } from "@/lib/api/client";

export type NegotiationOffer = {
  id: string;
  status: string;
  currency: string;
  payment_terms: string | null;
  total_price: string | null;
  created_by_business_id?: string | null;
  created_at: string | null;
  items: {
    rfq_item_id: string | null;
    product_name_snapshot: string | null;
    quantity: string;
    unit_price: string;
    line_total: string | null;
  }[];
};

export type Negotiation = {
  id: string;
  rfq_id: string | null;
  quotation_id: string | null;
  status: string;
  buyer_business_id?: string | null;
  supplier_business_id?: string | null;
  buyer_name?: string | null;
  supplier_name?: string | null;
  buyer_logo_url?: string | null;
  supplier_logo_url?: string | null;
  payment_terms?: string | null;
  baseline_lines?: {
    rfq_item_id: string | null;
    product_name_snapshot: string | null;
    quantity: string;
    unit_price: string;
    line_total: string | null;
  }[];
  offers: NegotiationOffer[];
};

export const negotiationApi = {
  open: (rfq_id: string, quotation_id: string) =>
    apiClient.post<Negotiation>("/negotiations", { rfq_id, quotation_id }),

  listForRfq: (rfq_id: string) =>
    apiClient.get<Negotiation[]>("/negotiations", { params: { rfq_id } }),

  get: (id: string) => apiClient.get<Negotiation>(`/negotiations/${id}`),

  proposeOffer: (
    id: string,
    body: {
      payment_terms?: string;
      parent_offer_id?: string;
      lines: {
        rfq_item_id: string;
        quantity: string;
        unit_price: string;
        product_name?: string;
      }[];
    },
  ) => apiClient.post<Negotiation>(`/negotiations/${id}/offers`, body),

  acceptOffer: (negotiationId: string, offerId: string) =>
    apiClient.post<Negotiation>(`/negotiations/${negotiationId}/offers/${offerId}/accept`),

  rejectOffer: (negotiationId: string, offerId: string) =>
    apiClient.post<Negotiation>(`/negotiations/${negotiationId}/offers/${offerId}/reject`),
};
