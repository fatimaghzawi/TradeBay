import { apiClient } from "@/lib/api/client";

export type QuantityRequirement = {
  product: string;
  quantity: number | null;
  unit: string | null;
};

export type ProcurementRequirements = {
  business_type: string | null;
  business_description: string;
  location: string | null;
  product_requirements: string[];
  categories: string[];
  quantities: QuantityRequirement[];
  purchase_frequency: string | null;
  delivery_requirements: string | null;
  supplier_preferences: string[];
  budget_range: string | null;
  missing_information: string[];
};

export type AnalyzeResult = {
  sourcing_request_id: string;
  requirements: ProcurementRequirements;
  status: string;
  clarification?: string | null;
};

export type RecommendationProduct = {
  id: string;
  product_id: string | null;
  product_name: string | null;
  product_sku: string | null;
  category_name: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  supplier_verified: boolean;
  moq: number | null;
  unit: string | null;
  unit_price: string | null;
  currency: string | null;
  primary_image_url?: string | null;
  availability_status: string;
  relevance_label: string | null;
  match_score: number | null;
  matched_requirements: string[];
  unmatched_requirements: string[];
  reasons: string[];
  signals?: Record<string, number>;
};

export type SupplierMatch = {
  supplier_id: string;
  supplier_name: string;
  verified: boolean;
  product_count: number;
  matched_requirements: string[];
  reasons: string[];
  relevance_label: string | null;
};

export type RecommendationsResult = {
  sourcing_request_id: string;
  status: string;
  products: RecommendationProduct[];
  suppliers: SupplierMatch[];
  message?: string | null;
  suggestions: string[];
  loose_match?: boolean;
};

export type SourcingRequestSummary = {
  id: string;
  status: string;
  original_prompt: string;
  requirements: ProcurementRequirements | Record<string, unknown> | null;
  ai_summary: string | null;
  destination: string | null;
  item_count: number;
  recommendation_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type SourcingDraftResult = SourcingRequestSummary & {
  items: {
    id: string;
    requested_name: string;
    quantity: string | null;
    unit: string;
    destination: string | null;
    product_id?: string | null;
  }[];
  published: boolean;
  message: string;
};

export const aiSourcingApi = {
  analyze(business_description: string) {
    return apiClient.post<AnalyzeResult>("/ai-sourcing/analyze", {
      business_description,
    });
  },

  confirm(sourcing_request_id: string, requirements: ProcurementRequirements) {
    return apiClient.post<AnalyzeResult>("/ai-sourcing/requirements/confirm", {
      sourcing_request_id,
      requirements,
    });
  },

  recommend(sourcing_request_id: string, limit = 20) {
    return apiClient.post<RecommendationsResult>("/ai-sourcing/recommendations", {
      sourcing_request_id,
      limit,
    });
  },

  createRequest(sourcing_request_id: string) {
    return apiClient.post<SourcingDraftResult>("/ai-sourcing/create-request", {
      sourcing_request_id,
    });
  },

  getRequest(sourcing_request_id: string) {
    return apiClient.get<
      SourcingRequestSummary & {
        items: SourcingDraftResult["items"];
        recommendations: {
          products: RecommendationProduct[];
          suppliers: SupplierMatch[];
        };
      }
    >(`/ai-sourcing/requests/${sourcing_request_id}`);
  },

  listRequests(params?: { page?: number; page_size?: number }) {
    return apiClient.getPage<SourcingRequestSummary>("/ai-sourcing/requests", {
      params,
    });
  },

  convertToRfq(sourcing_request_id: string) {
    return apiClient.post<{
      rfq: { id: string; rfq_number: string };
      suggested_supplier_ids: string[];
      message: string;
    }>(`/ai-sourcing/requests/${sourcing_request_id}/convert-to-rfq`);
  },

  getProfile() {
    return apiClient.get<Record<string, unknown> | null>("/ai-sourcing/profile");
  },
};
