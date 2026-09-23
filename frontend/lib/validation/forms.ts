import { isValidLebanonPhone } from "@/lib/phone";
import {
  companyDomainSchema,
  emailSchema,
  httpUrlSchema,
  optionalEmailSchema,
  optionalNonNegativeString,
  optionalText,
  optionalWebsiteSchema,
  optionalYearSchema,
  passwordSchema,
  positiveNumberString,
  rateString,
  requiredText,
} from "@/lib/validation/common";
import { z } from "zod";

export const profileSchema = z.object({
  first_name: requiredText("First name", 100),
  last_name: requiredText("Last name", 100),
});

export const adminCreateUserSchema = z.object({
  first_name: requiredText("First name", 100),
  last_name: requiredText("Last name", 100),
  email: emailSchema,
  password: passwordSchema,
});

export const adminCreateBusinessSchema = z.object({
  business_name: requiredText("Company name", 200),
  email_domain: z
    .string()
    .trim()
    .max(253, "Domain must be 253 characters or fewer")
    .optional()
    .or(z.literal("")),
  legal_name: z.string().trim().max(200).optional().or(z.literal("")),
  tax_number: z.string().trim().max(64).optional().or(z.literal("")),
  owner_first_name: requiredText("First name", 100),
  owner_last_name: requiredText("Last name", 100),
  owner_email: emailSchema,
  owner_password: passwordSchema,
});

export const inviteMemberSchema = z.object({
  personal_email: emailSchema,
  company_local: z
    .string()
    .trim()
    .min(1, "Company login is required")
    .max(64, "Company login must be 64 characters or fewer")
    .regex(/^[a-z0-9._+-]+$/i, "Use letters, numbers, and . _ + - only"),
  role_id: z.string().min(1, "Select a role"),
});

export const productCreateSchema = z.object({
  name: requiredText("Product name", 200),
  sku: requiredText("SKU", 64),
  category_id: z.string().min(1, "Select a category"),
  unit: z.string().min(1, "Select a unit"),
  description: z.string().trim().max(4000).optional().or(z.literal("")),
  origin: z.string().trim().max(120).optional().or(z.literal("")),
  moq: z
    .string()
    .trim()
    .min(1, "Minimum order quantity is required")
    .refine((value) => {
      const n = Number(value);
      return Number.isInteger(n) && n >= 1;
    }, "Minimum order quantity must be at least 1"),
  lead_time: z
    .string()
    .trim()
    .min(1, "Lead time is required")
    .refine((value) => {
      const n = Number(value);
      return Number.isInteger(n) && n >= 0;
    }, "Lead time must be 0 or more days"),
});

export const roleNameSchema = z.object({
  name: requiredText("Role name", 80),
});

const optionalMoneyString = optionalNonNegativeString("Price");

export const productRfqSchema = z.object({
  quantity: positiveNumberString("Quantity"),
  targetPrice: optionalMoneyString,
  requiredBy: optionalText(40),
  requirements: optionalText(4000),
  notes: optionalText(2000),
});

export const sourcingBasicsSchema = z.object({
  title: requiredText("Title", 200),
  notes: optionalText(2000),
});

export const rfqLineSchema = z.object({
  product_name: requiredText("Product name", 200),
  quantity: positiveNumberString("Quantity"),
  target_unit_price: optionalMoneyString,
});

export const offerLineSchema = z.object({
  quantity: positiveNumberString("Quantity"),
  unit_price: z
    .string()
    .trim()
    .min(1, "Unit price is required")
    .refine((value) => {
      const n = Number(value);
      return Number.isFinite(n) && n > 0;
    }, "Unit price must be greater than 0"),
});

export function companyProfileSchema(identityLocked: boolean) {
  return z.object({
    name: identityLocked ? z.string() : requiredText("Company name", 200),
    emailDomain: identityLocked ? z.string() : companyDomainSchema,
    yearEstablished: optionalYearSchema,
    website: optionalWebsiteSchema,
    email: optionalEmailSchema,
    phone: z
      .string()
      .refine(
        (value) => !value || isValidLebanonPhone(value),
        "Enter a valid Lebanese phone: +961 followed by 8 digits.",
      ),
    legalName: optionalText(200),
    taxNumber: optionalText(64),
    description: optionalText(500),
  });
}

export const createBusinessSchema = z.object({
  name: requiredText("Company name", 200),
  legal_name: requiredText("Legal name", 200),
  contact_email: emailSchema,
  email_domain: companyDomainSchema,
  tax_number: optionalText(64),
  contact_person: requiredText("Contact person", 120),
  contact_phone: z
    .string()
    .refine(
      isValidLebanonPhone,
      "Enter a valid Lebanese phone: +961 followed by 8 digits.",
    ),
  street: requiredText("Address", 200),
  street2: optionalText(200),
  city: requiredText("City", 80),
  governorate: requiredText("Region", 80),
  postal_code: optionalText(20),
});

export const platformSettingsSchema = z.object({
  platform_name: requiredText("Platform name", 120),
  commission_rate: rateString,
  minimum_order_value: optionalNonNegativeString("Minimum order value"),
  payment_provider: optionalText(80),
});

export const taxSettingsSchema = z.object({
  name: requiredText("Tax name", 80),
  rate: rateString,
});

export const letterheadSettingsSchema = z.object({
  business_name: requiredText("Business name", 200),
  business_email: optionalEmailSchema,
  business_phone: optionalText(40),
  tax_registration_number: optionalText(64),
  invoice_prefix: requiredText("Invoice prefix", 20),
});

export const categoryCreateSchema = z.object({
  name: requiredText("Category name", 80),
  slug: z
    .string()
    .trim()
    .max(80, "Slug must be 80 characters or fewer")
    .refine(
      (value) => !value || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value),
      "Use lowercase letters, numbers, and hyphens",
    ),
  description: optionalText(500),
});

export const priceTierSchema = z
  .object({
    min_quantity: z
      .string()
      .trim()
      .min(1, "Min quantity is required")
      .refine((value) => {
        const n = Number(value);
        return Number.isInteger(n) && n >= 1;
      }, "Min quantity must be a whole number of at least 1"),
    max_quantity: z.string(),
    unit_price: z
      .string()
      .trim()
      .min(1, "Unit price is required")
      .refine((value) => {
        const n = Number(value);
        return Number.isFinite(n) && n > 0;
      }, "Unit price must be greater than 0"),
    open_ended: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.open_ended || !data.max_quantity.trim()) return;
    const min = Number(data.min_quantity);
    const max = Number(data.max_quantity);
    if (!Number.isInteger(max) || max < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Max quantity must be a whole number of at least 1",
        path: ["max_quantity"],
      });
      return;
    }
    if (Number.isFinite(min) && max < min) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Max quantity must be at least the min quantity",
        path: ["max_quantity"],
      });
    }
  });

export const stockQtySchema = z.object({
  quantity: z
    .string()
    .trim()
    .min(1, "Quantity is required")
    .refine((value) => {
      const n = Number(value);
      return Number.isFinite(n) && n > 0;
    }, "Quantity must be greater than 0"),
  reason: optionalText(200),
});

export const evidenceUrlSchema = z.object({
  url: httpUrlSchema,
});

export const sourcingLetterSchema = z.object({
  description: z
    .string()
    .trim()
    .min(8, "Write at least a short description of what you need")
    .max(8000, "Description must be 8000 characters or fewer"),
});

export const plannerBudgetSchema = z.object({
  inventoryBudget: optionalNonNegativeString("Inventory budget"),
  operatingCash: optionalNonNegativeString("Operating cash"),
});

export const plannerPrefsSchema = z.object({
  monthlyIncome: optionalNonNegativeString("Desired monthly income"),
});

export const plannerLocationSchema = z.object({
  customLocation: requiredText("Location", 80),
});

export const shipmentIssueSchema = z.object({
  reason: requiredText("Reason", 200),
  note: optionalText(1000),
});

export const receiveQtySchema = z.object({
  quantity: z
    .string()
    .trim()
    .min(1, "Accepted quantity is required")
    .refine((value) => {
      const n = Number(value);
      return Number.isFinite(n) && n >= 0;
    }, "Accepted quantity must be a valid number"),
});
