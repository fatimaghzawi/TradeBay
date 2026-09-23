import { apiClient } from "@/lib/api/client";

export type AdaptiveQuestion = {
  id: string;
  prompt: string;
  input_type: "single" | "multi" | "text" | "number";
  options: string[];
  why?: string | null;
};

export type PlannerPreferences = {
  business_goal?: string | null;
  unsure_goal?: boolean;
  location?: string | null;
  budget_range?: string | null;
  budget_min?: string | null;
  budget_max?: string | null;
  inventory_budget?: string | null;
  operating_cash?: string | null;
  business_model?: string[];
  experience?: string | null;
  time_commitment?: string | null;
  risk_preference?: string | null;
  desired_monthly_income?: string | null;
  desired_margin?: string | null;
  product_preferences?: string[];
  customer_type?: string | null;
  category_hints?: string[];
  adaptive?: Record<string, unknown>;
};

export type PlannerSession = {
  id: string;
  status: string;
  current_step: string;
  answers: Record<string, unknown>;
  preferences: PlannerPreferences;
  adaptive_questions: AdaptiveQuestion[];
  plan_id: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PlanItem = {
  id: string;
  item_name: string;
  description?: string | null;
  product_id: string | null;
  category_id: string | null;
  category_name?: string | null;
  supplier_business_id: string | null;
  supplier_name?: string | null;
  quantity: string | null;
  unit?: string | null;
  priority: string;
  estimated_unit_price: string | null;
  estimated_total_price: string | null;
  target_selling_price: string | null;
  estimated_margin: string | null;
  suggested_moq?: number | null;
  reason?: string | null;
  source_type?: string | null;
  image_url?: string | null;
};

export type BusinessPlan = {
  id: string;
  title: string | null;
  status: string;
  location: string | null;
  version: number;
  budget: string | null;
  estimated_monthly_revenue?: string | null;
  gross_margin_pct?: string | null;
  business_type?: string | null;
  description?: string | null;
  currency?: string;
  preferences: PlannerPreferences;
  concept: Record<string, unknown>;
  budget_allocation: Record<string, string>;
  financial_projection: Record<string, string | null>;
  market_snapshot: Record<string, unknown>;
  risks: {
    title: string;
    description: string;
    why_it_matters: string;
    mitigation: string;
  }[];
  milestones: {
    phase: string;
    title: string;
    description: string;
    week?: number | null;
    order: number;
    tasks?: string[];
    status?: string;
  }[];
  assumptions: { text: string; label: string }[];
  budget_adjustments: string[];
  progress: Record<string, unknown>;
  parent_plan_id?: string | null;
  sourcing_request_id?: string | null;
  items: PlanItem[];
  suppliers: {
    supplier_business_id: string;
    supplier_name?: string | null;
    product_count: number;
    verified: boolean;
    logo_url?: string | null;
  }[];
  next_actions: { key: string; label: string }[];
  created_at: string | null;
  updated_at: string | null;
};

export type RfqPreview = {
  publishable: boolean;
  message: string;
  rfq_draft: {
    title: string;
    delivery_location?: string | null;
    target_budget?: string | null;
    desired_timeline?: string | null;
    lines: {
      product_name: string;
      product_id: string | null;
      quantity: string | null;
      unit: string;
      target_unit_price: string | null;
      supplier_business_id: string | null;
    }[];
    notes: string;
  };
};

export type SourcingDraftResult = {
  sourcing_request_id: string;
  status: string;
  items: {
    id: string;
    requested_name: string;
    quantity: string | null;
    unit: string;
    product_id?: string | null;
  }[];
  message: string;
};

export type AssistantResult = {
  reply: string;
  mutations: Record<string, unknown> | null;
  messages: { id: string; role: string; content: string; created_at: string | null }[];
};

export const businessPlannerApi = {
  createSession() {
    return apiClient.post<PlannerSession>("/business-planner/sessions", {});
  },

  getSession(sessionId: string) {
    return apiClient.get<PlannerSession>(`/business-planner/sessions/${sessionId}`);
  },

  submitAnswers(sessionId: string, step: string, answers: Record<string, unknown>) {
    return apiClient.post<PlannerSession>(`/business-planner/sessions/${sessionId}/answers`, {
      step,
      answers,
    });
  },

  nextQuestions(sessionId: string) {
    return apiClient.post<{ session: PlannerSession; questions: AdaptiveQuestion[] }>(
      `/business-planner/sessions/${sessionId}/next-questions`,
      {},
    );
  },

  generate(sessionId: string) {
    return apiClient.post<BusinessPlan>(`/business-planner/sessions/${sessionId}/generate`, {});
  },

  listPlans(page = 1, pageSize = 20) {
    return apiClient.getPage<BusinessPlan>("/business-plans", {
      params: { page, page_size: pageSize },
    });
  },

  getPlan(planId: string) {
    return apiClient.get<BusinessPlan>(`/business-plans/${planId}`);
  },

  patchPlan(
    planId: string,
    body: {
      title?: string;
      milestone_updates?: { order: number; status: string }[];
      preferences?: PlannerPreferences;
    },
  ) {
    return apiClient.patch<BusinessPlan>(`/business-plans/${planId}`, body);
  },

  regenerate(planId: string, body: { preferences?: PlannerPreferences; reason?: string } = {}) {
    return apiClient.post<BusinessPlan>(`/business-plans/${planId}/regenerate`, body);
  },

  assistant(planId: string, message: string) {
    return apiClient.post<AssistantResult>(`/business-plans/${planId}/assistant`, { message });
  },

  sourcingDraft(planId: string) {
    return apiClient.post<SourcingDraftResult>(`/business-plans/${planId}/sourcing-draft`, {});
  },

  rfqPreview(planId: string) {
    return apiClient.post<RfqPreview>(`/business-plans/${planId}/rfq-preview`, {});
  },

  convertToRfq(planId: string) {
    return apiClient.post<{
      rfq: { id: string; rfq_number: string; status: string };
      suggested_supplier_ids: string[];
      message: string;
      next_url_hint?: string | null;
    }>(`/business-plans/${planId}/convert-to-rfq`, {});
  },
};
