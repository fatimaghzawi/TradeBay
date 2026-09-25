"use client";

import { LebanesePhoneField } from "@/components/ui/LebanesePhoneField";
import { BusinessAsideCard } from "@/components/business/BusinessAsideCard";
import { BusinessStepper } from "@/components/business/BusinessStepper";
import { ApiError } from "@/lib/api/client";
import {
  BUSINESS_TYPE_OPTIONS,
  EMPTY_BUSINESS_DRAFT,
  LEBANON_REGIONS,
  loadBusinessDraft,
  saveBusinessDraft,
  clearBusinessDraft,
  loadPreferredBusinessType,
  deriveEmailDomain,
  type BusinessDraft,
} from "@/lib/business";
import { identityApi } from "@/lib/api/identityApi";
import { ROUTES } from "@/lib/constants";
import { createBusinessSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { BusyText } from "@/components/ui/LoadingState";
import { BackLink } from "@/components/ui/BackLink";

export default function CreateBusinessPage() {
  const router = useRouter();
  const { refreshSession, user, businesses } = useAuth();
  const formRef = useRef<HTMLFormElement>(null);
  const [draft, setDraft] = useState<BusinessDraft>(EMPTY_BUSINESS_DRAFT);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [typeLocked, setTypeLocked] = useState(false);
  const live = useLiveFields(createBusinessSchema, {
    name: draft.name,
    legal_name: draft.legal_name,
    contact_email: draft.contact_email,
    email_domain: draft.email_domain,
    tax_number: draft.tax_number,
    contact_person: draft.contact_person,
    contact_phone: draft.contact_phone,
    street: draft.street,
    street2: draft.street2,
    city: draft.city,
    governorate: draft.governorate,
    postal_code: draft.postal_code,
  });

  useEffect(() => {
    const hasTrading = businesses.some((b) => b.type !== "platform");
    if (hasTrading) {
      router.replace(ROUTES.businesses);
      return;
    }
    const existing = loadBusinessDraft();
    const preferred = loadPreferredBusinessType();
    if (existing) {
      setDraft(existing);
      setTypeLocked(Boolean(preferred));
    } else {
      setDraft((d) => ({
        ...d,
        type: preferred ?? d.type,
        contact_email: user?.email ?? d.contact_email,
        email_domain:
          d.email_domain ||
          deriveEmailDomain(user?.email ?? d.contact_email) ||
          "",
        contact_person: user
          ? `${user.first_name} ${user.last_name}`.trim()
          : d.contact_person,
      }));
      setTypeLocked(Boolean(preferred));
    }
  }, [user, businesses, router]);

  function update<K extends keyof BusinessDraft>(key: K, value: BusinessDraft[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="relative space-y-5">
      <LeafWash />
      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <BackLink href={ROUTES.businesses}>Back</BackLink>
          <h1 className="mt-2 font-[family-name:var(--font-outfit)] text-3xl tracking-tight text-heading sm:text-[2.15rem]">
            Create your company
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Establish your organization on TradeBay with a company name, work email, and
            company domain. You become the Business Admin.
            {draft.type === "supplier"
              ? " Suppliers then upload documents so TradeBay can verify selling rights."
              : " Buyers can start sourcing after email verification."}
          </p>
        </div>
        <BusinessStepper active={1} variant={draft.type === "buyer" ? "buyer" : "supplier"} />
      </div>

      {draft.type === "supplier" ? (
        <p className="rounded-xl bg-muted px-3.5 py-2.5 text-sm text-warning">
          Next step: upload documents so TradeBay can approve selling.
        </p>
      ) : (
        <p className="rounded-xl bg-success-soft px-3.5 py-2.5 text-sm text-link">
          Buyer businesses skip document verification and can source after creation.
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.9fr)]">
        <form
          ref={formRef}
          id="create-business-form"
          className="tb-card space-y-5 p-5 sm:p-6"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            if (!live.finish()) {
              setError("Fix the highlighted fields before continuing.");
              return;
            }
            if (!agreed) {
              setError("Confirm you are authorized to register this business.");
              return;
            }
            setPending(true);
            const street = [draft.street, draft.street2].filter(Boolean).join(", ");
            void identityApi
              .createBusiness({
                name: draft.name.trim(),
                type: draft.type,
                legal_name: draft.legal_name.trim() || draft.name.trim(),
                tax_number: draft.tax_number.trim() || undefined,
                contact_email: draft.contact_email.trim() || undefined,
                contact_phone: draft.contact_phone.trim() || undefined,
                email_domain:
                  draft.email_domain.trim() ||
                  deriveEmailDomain(draft.contact_email) ||
                  undefined,
                address: {
                  street: street || undefined,
                  city: draft.city.trim() || undefined,
                  governorate: draft.governorate || undefined,
                  postal_code: draft.postal_code.trim() || undefined,
                  country: "Lebanon",
                },
              })
              .then(async (business) => {
                saveBusinessDraft({ ...draft, businessId: business.id, type: draft.type });
                
                await identityApi.switchBusiness(business.id);
                if (draft.type === "supplier") {
                  router.push(ROUTES.businessesVerify);
                } else {
                  clearBusinessDraft();
                  router.push(ROUTES.businesses);
                }
                void refreshSession();
              })
              .catch((err) =>
                setError(
                  err instanceof ApiError
                    ? err.message
                    : "Couldn't create business.",
                ),
              )
              .finally(() => setPending(false));
          }}
        >
          <Section title="Company identity">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Company name"
                required
                value={draft.name}
                onChange={(v) => update("name", v)}
                onBlur={() => live.touch("name")}
                error={live.errors.name}
              />
              <Field
                label="Legal name"
                required
                value={draft.legal_name}
                onChange={(v) => update("legal_name", v)}
                onBlur={() => live.touch("legal_name")}
                error={live.errors.legal_name}
              />
              <Field
                label="Company email"
                required
                type="email"
                value={draft.contact_email}
                onChange={(v) => {
                  update("contact_email", v);
                  if (!draft.email_domain.trim()) {
                    update("email_domain", deriveEmailDomain(v));
                  }
                }}
                onBlur={() => live.touch("contact_email")}
                error={live.errors.contact_email}
              />
              <Field
                label="Company domain"
                required
                value={draft.email_domain}
                onChange={(v) => update("email_domain", v.replace(/^@/, "").toLowerCase())}
                onBlur={() => live.touch("email_domain")}
                error={live.errors.email_domain}
                hint="e.g. safawi.com — teammates must use this domain"
              />
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold text-foreground">
                  Business type <span className="text-accent-text">*</span>
                </span>
                {typeLocked ? (
                  <div className="flex h-11 items-center rounded-xl border border-border bg-muted px-3 text-sm">
                    <span className="font-medium capitalize text-foreground">
                      {draft.type}
                      <span className="ml-2 font-normal text-muted-foreground">
                        (locked from registration — cannot be changed)
                      </span>
                    </span>
                  </div>
                ) : (
                  <select
                    required
                    value={draft.type}
                    onChange={(e) =>
                      update("type", e.target.value as BusinessDraft["type"])
                    }
                    className=""
                  >
                    {BUSINESS_TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                )}
              </label>
              <Field
                label="Tax number"
                value={draft.tax_number}
                onChange={(v) => update("tax_number", v)}
                onBlur={() => live.touch("tax_number")}
                error={live.errors.tax_number}
              />
            </div>
          </Section>

          <Section title="Contact information">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Contact person"
                required
                value={draft.contact_person}
                onChange={(v) => update("contact_person", v)}
                onBlur={() => live.touch("contact_person")}
                error={live.errors.contact_person}
              />
              <LebanesePhoneField
                required
                value={draft.contact_phone}
                onChange={(v) => update("contact_phone", v)}
                onBlur={() => live.touch("contact_phone")}
                error={live.errors.contact_phone}
              />
              <div className="sm:col-span-2">
                <Field
                  label="Email address"
                  required
                  type="email"
                  value={draft.contact_email}
                  onChange={(v) => update("contact_email", v)}
                  onBlur={() => live.touch("contact_email")}
                  error={live.errors.contact_email}
                />
              </div>
            </div>
          </Section>

          <Section title="Business address">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Field
                  label="Address line 1"
                  required
                  value={draft.street}
                  onChange={(v) => update("street", v)}
                  onBlur={() => live.touch("street")}
                  error={live.errors.street}
                />
              </div>
              <div className="sm:col-span-2">
                <Field
                  label="Address line 2"
                  value={draft.street2}
                  onChange={(v) => update("street2", v)}
                  onBlur={() => live.touch("street2")}
                  error={live.errors.street2}
                  placeholder="Optional"
                />
              </div>
              <Field
                label="City"
                required
                value={draft.city}
                onChange={(v) => update("city", v)}
                onBlur={() => live.touch("city")}
                error={live.errors.city}
              />
              <label className="block">
                <span className="mb-1.5 block text-sm font-semibold text-foreground">
                  Region <span className="text-accent-text">*</span>
                </span>
                <select
                  required
                  value={draft.governorate}
                  onChange={(e) => update("governorate", e.target.value)}
                  onBlur={() => live.touch("governorate")}
                  className=""
                >
                  {LEBANON_REGIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                {live.errors.governorate ? (
                  <span className="tb-hint" data-tone="error">
                    {live.errors.governorate}
                  </span>
                ) : null}
              </label>
              <Field
                label="Postal code"
                value={draft.postal_code}
                onChange={(v) => update("postal_code", v)}
                onBlur={() => live.touch("postal_code")}
                error={live.errors.postal_code}
              />
            </div>
          </Section>

          <label className="flex items-start gap-3 rounded-xl bg-muted px-3.5 py-3 text-sm text-ink-soft">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-1"
            />
            <span>
              I confirm I am authorized to register this business and agree to
              TradeBay&apos;s terms.
            </span>
          </label>

          {error ? (
            <p role="alert" className="tb-alert tb-alert--error">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={pending}
            className="tb-btn tb-btn--accent tb-btn--lg lg:hidden"
           aria-busy={pending || undefined}>
            <BusyText busy={pending}>{pending ? "Creating…" : "Continue"}</BusyText>
          </button>
        </form>

        <BusinessAsideCard
          title={
            draft.type === "supplier"
              ? "Selling requires supplier verification"
              : "Buyers can start sourcing right away"
          }
          points={
            draft.type === "supplier"
              ? [
                  "Create your company profile first",
                  "Upload registration docs to unlock selling",
                  "Platform review usually takes 1–2 business days",
                ]
              : [
                  "Email-verified accounts can create a buyer business",
                  "Start RFQs and marketplace sourcing immediately",
                  "No document verification required to buy",
                ]
          }
          action={
            <button
              type="button"
              disabled={pending}
              onClick={() => formRef.current?.requestSubmit()}
              className="hidden h-12 w-full items-center justify-center rounded-xl bg-accent text-sm font-bold text-accent-foreground disabled:opacity-60 lg:inline-flex"
            >
              <BusyText busy={pending}>{pending ? "Creating…" : "Continue"}</BusyText>
            </button>
          }
        />
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 font-[family-name:var(--font-syne)] text-base font-bold text-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  onBlur,
  required,
  type = "text",
  placeholder,
  hint,
  error,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  required?: boolean;
  type?: string;
  placeholder?: string;
  hint?: string;
  error?: string;
}) {
  return (
    <label className="block">
      <span className="tb-field-label mb-1.5 block text-sm font-semibold">
        {label}
        {required ? <span className="text-accent-text"> *</span> : null}
      </span>
      <input
        type={type}
        required={required}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
      />
      {error ? (
        <span className="tb-hint" data-tone="error">
          {error}
        </span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </label>
  );
}

function LeafWash() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute -right-8 -top-6 h-48 w-48 rounded-full bg-secondary-soft/50 blur-3xl"
    />
  );
}
