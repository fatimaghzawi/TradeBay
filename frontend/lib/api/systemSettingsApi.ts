import { apiClient } from "@/lib/api/client";

export type PlatformSettings = {
  id: string;
  platform_name: string;
  default_currency: string;
  commission_rate: string | null;
  commission_type: string | null;
  commission_base: string | null;
  minimum_order_value: string | null;
  payment_provider: string | null;
  payment_provider_active: boolean;
};

export type TaxSettings = {
  id: string;
  name: string;
  rate: string | null;
  type: string | null;
  is_active: boolean;
  effective_from: string | null;
  effective_until: string | null;
};

export type BusinessSettings = {
  id: string;
  business_name: string;
  business_email: string | null;
  business_phone: string | null;
  tax_registration_number: string | null;
  invoice_prefix: string;
  address: Record<string, string | null> | null;
};

export type SystemSettingsBundle = {
  platform: PlatformSettings | null;
  tax: TaxSettings | null;
  tax_history: TaxSettings[];
  business: BusinessSettings | null;
};

export const systemSettingsApi = {
  getAll: () => apiClient.get<SystemSettingsBundle>("/admin/settings"),

  updatePlatform: (body: Partial<{
    platform_name: string;
    default_currency: string;
    commission_rate: string;
    commission_type: string;
    commission_base: string;
    minimum_order_value: string;
    payment_provider: string | null;
    payment_provider_active: boolean;
  }>) => apiClient.patch<PlatformSettings>("/admin/settings/platform", body),

  updateTax: (body: Partial<{
    name: string;
    rate: string;
    type: string;
    is_active: boolean;
    effective_from: string;
    effective_until: string | null;
  }>) => apiClient.patch<TaxSettings>("/admin/settings/tax", body),

  updateBusiness: (body: Partial<{
    business_name: string;
    business_email: string | null;
    business_phone: string | null;
    tax_registration_number: string | null;
    invoice_prefix: string;
  }>) => apiClient.patch<BusinessSettings>("/admin/settings/business", body),
};
