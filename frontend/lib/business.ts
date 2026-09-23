export const BUSINESS_TYPE_OPTIONS = [
  { value: "buyer", label: "Buyer" },
  { value: "supplier", label: "Supplier" },
] as const;

export const LEBANON_REGIONS = [
  { value: "Beirut", label: "Beirut" },
  { value: "Mount Lebanon", label: "Mount Lebanon" },
  { value: "North", label: "North" },
  { value: "South", label: "South" },
  { value: "Nabatieh", label: "Nabatieh" },
  { value: "Bekaa", label: "Bekaa" },
  { value: "Baalbek-Hermel", label: "Baalbek-Hermel" },
  { value: "Akkar", label: "Akkar" },
] as const;

export type BusinessDraft = {
  legal_name: string;
  name: string;
  type: "buyer" | "supplier";
  tax_number: string;
  contact_person: string;
  contact_phone: string;
  contact_email: string;
  email_domain: string;
  street: string;
  street2: string;
  city: string;
  governorate: string;
  postal_code: string;
  businessId?: string;
};

export const EMPTY_BUSINESS_DRAFT: BusinessDraft = {
  legal_name: "",
  name: "",
  type: "buyer",
  tax_number: "",
  contact_person: "",
  contact_phone: "",
  contact_email: "",
  email_domain: "",
  street: "",
  street2: "",
  city: "",
  governorate: "Beirut",
  postal_code: "",
};

const PUBLIC_MAIL_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "yahoo.com",
  "yahoo.co.uk",
  "hotmail.com",
  "outlook.com",
  "live.com",
  "msn.com",
  "icloud.com",
  "me.com",
  "aol.com",
  "proton.me",
  "protonmail.com",
  "mail.com",
  "yandex.com",
  "gmx.com",
  "zoho.com",
]);

export function deriveEmailDomain(email: string): string {
  const at = email.trim().toLowerCase().lastIndexOf("@");
  if (at < 0) return "";
  const domain = email.trim().toLowerCase().slice(at + 1);
  if (!domain || PUBLIC_MAIL_DOMAINS.has(domain)) return "";
  return domain;
}

const DRAFT_KEY = "tradebay.business.draft";

export function saveBusinessDraft(draft: BusinessDraft) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

export function loadBusinessDraft(): BusinessDraft | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return null;
  try {
    return { ...EMPTY_BUSINESS_DRAFT, ...(JSON.parse(raw) as BusinessDraft) };
  } catch {
    return null;
  }
}

export function clearBusinessDraft() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(DRAFT_KEY);
}

const PREFERRED_TYPE_KEY = "tradebay.preferredBusinessType";

export function savePreferredBusinessType(type: "buyer" | "supplier") {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PREFERRED_TYPE_KEY, type);
}

export function loadPreferredBusinessType(): "buyer" | "supplier" | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(PREFERRED_TYPE_KEY);
  if (value === "buyer" || value === "supplier") return value;
  return null;
}

export function formatAddress(address?: {
  street?: string | null;
  city?: string | null;
  district?: string | null;
  governorate?: string | null;
  postal_code?: string | null;
  country?: string | null;
} | null) {
  if (!address) return "—";
  const parts = [
    address.street,
    address.district,
    address.city,
    address.governorate,
    address.postal_code,
    address.country,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "—";
}
