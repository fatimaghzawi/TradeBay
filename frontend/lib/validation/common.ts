import { z } from "zod";

export const EMAIL_MESSAGE = "Enter a valid email address";
export const REQUIRED_MESSAGE = "This field is required";
export const PASSWORD_LENGTH_MESSAGE = "Use at least 8 characters";
export const PASSWORD_LETTER_MESSAGE = "Include at least one letter";
export const PASSWORD_NUMBER_MESSAGE = "Include at least one number";

export const IMAGE_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
] as const;

export const DOCUMENT_MIME_TYPES = [...IMAGE_MIME_TYPES, "application/pdf"] as const;

export const IMAGE_MAX_BYTES = 8 * 1024 * 1024;
export const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024;

export const emailSchema = z
  .string()
  .trim()
  .min(1, REQUIRED_MESSAGE)
  .email(EMAIL_MESSAGE);

export const optionalEmailSchema = z
  .string()
  .trim()
  .refine((value) => !value || emailSchema.safeParse(value).success, EMAIL_MESSAGE);

export const requiredText = (label: string, max = 200) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .max(max, `${label} is too long`);

export const optionalText = (max = 2000) =>
  z
    .string()
    .trim()
    .max(max, "This text is too long")
    .optional()
    .or(z.literal(""));

export const COMPANY_DOMAIN_RE =
  /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

export const companyDomainSchema = z
  .string()
  .trim()
  .min(1, "Company domain is required")
  .max(253, "Domain is too long")
  .refine(
    (value) => COMPANY_DOMAIN_RE.test(value.replace(/^@/, "").toLowerCase()),
    "Company domain needs a suffix like .com — e.g. levantsale.com",
  );

export const optionalWebsiteSchema = z
  .string()
  .trim()
  .refine((value) => {
    if (!value || /^https?:\/\/$/i.test(value)) return true;
    try {
      const url = new URL(value);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch {
      return false;
    }
  }, "Enter a valid website URL");

export const optionalYearSchema = z
  .string()
  .trim()
  .refine((value) => {
    if (!value) return true;
    const year = Number(value);
    return Number.isInteger(year) && year >= 1800 && year <= 2100;
  }, "Enter a valid year established");

export const rateString = z
  .string()
  .trim()
  .min(1, "Rate is required")
  .refine((value) => {
    const n = Number(value);
    return Number.isFinite(n) && n >= 0 && n <= 1;
  }, "Enter a rate between 0 and 1");

export const optionalNonNegativeString = (label: string) =>
  z
    .string()
    .trim()
    .refine((value) => {
      if (!value) return true;
      const n = Number(value);
      return Number.isFinite(n) && n >= 0;
    }, `${label} must be a valid number`);

export const httpUrlSchema = z
  .string()
  .trim()
  .min(1, "URL is required")
  .refine((value) => {
    try {
      const url = new URL(value);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch {
      return false;
    }
  }, "Enter a valid http or https URL");

export const passwordSchema = z
  .string()
  .min(8, PASSWORD_LENGTH_MESSAGE)
  .max(128, "Password must be 128 characters or fewer")
  .regex(/[A-Za-z]/, PASSWORD_LETTER_MESSAGE)
  .regex(/[0-9]/, PASSWORD_NUMBER_MESSAGE)
  
  .refine(
    (value) => new TextEncoder().encode(value).length <= 72,
    "Password is too long. Please choose a shorter password.",
  );

export const positiveNumberString = (label: string, { integer = false } = {}) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .refine((value) => {
      const n = Number(value);
      if (!Number.isFinite(n) || n < 0) return false;
      if (integer && !Number.isInteger(n)) return false;
      return true;
    }, integer ? `${label} must be a whole number` : `${label} must be a valid number`);

export function issuesToFieldMap(
  issues: readonly { path: (string | number)[]; message: string }[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const issue of issues) {
    const key = issue.path[0];
    if (typeof key === "string" && errors[key] == null) {
      errors[key] = issue.message;
    }
  }
  return errors;
}

export function validateUpload(
  file: File | null | undefined,
  options: {
    required?: boolean;
    kinds: "image" | "document";
    label?: string;
  },
): string | null {
  const label = options.label ?? "File";
  if (!file) {
    return options.required ? `${label} is required` : null;
  }
  const allowed =
    options.kinds === "image" ? IMAGE_MIME_TYPES : DOCUMENT_MIME_TYPES;
  const max = options.kinds === "image" ? IMAGE_MAX_BYTES : DOCUMENT_MAX_BYTES;
  const typeOk =
    (allowed as readonly string[]).includes(file.type) ||
    (options.kinds === "image" && file.type.startsWith("image/"));
  if (!typeOk) {
    return options.kinds === "image"
      ? `${label} must be a JPEG, PNG, WEBP, or GIF`
      : `${label} must be a PDF, JPEG, PNG, or WEBP`;
  }
  if (file.size > max) {
    const mb = Math.round(max / (1024 * 1024));
    return `${label} must be ${mb} MB or smaller`;
  }
  return null;
}
