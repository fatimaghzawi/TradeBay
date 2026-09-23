"use client";

import { LebanesePhoneField } from "@/components/ui/LebanesePhoneField";
import { FieldError, NumberInput } from "@/components/ui/FormField";
import { ApiError } from "@/lib/api/client";
import {
  identityApi,
  type Business,
  type UpdateBusinessPayload,
} from "@/lib/api/identityApi";
import { formatAddress, LEBANON_REGIONS } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { mediaUrlFresh } from "@/lib/media";
import { companyProfileSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { BusyText } from "@/components/ui/LoadingState";

type ProfileTab = "details" | "contact" | "verification" | "settings";

const COMPANY_SIZES = [
  "1-10 employees",
  "11-50 employees",
  "51-200 employees",
  "201-500 employees",
  "500+ employees",
];

const SUGGESTED_CATEGORIES = [
  "Food & Beverage",
  "Retail Supply",
  "Local Products",
  "Wholesale",
  "Hospitality",
  "Agriculture",
];

const SUGGESTED_TAGS = [
  "Local Producer",
  "Wholesale",
  "Organic",
  "Export Ready",
  "Family Business",
];

function cleanWebsite(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed || /^https?:\/\/$/i.test(trimmed)) return undefined;
  return trimmed;
}

type CompanyProfileViewProps = {
  business: Business;
  memberCount: number;
  locked: boolean;
  initialTab?: ProfileTab;
  onSaved: (business: Business) => void;
  onOpenDocuments?: () => void;
};

function TagEditor({
  label,
  values,
  onChange,
  suggestions,
  disabled,
  addLabel,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  suggestions: string[];
  disabled?: boolean;
  addLabel: string;
}) {
  const [draft, setDraft] = useState("");
  const available = suggestions.filter((item) => !values.includes(item));

  function add(value: string) {
    const next = value.trim();
    if (!next || values.includes(next) || values.length >= 12) return;
    onChange([...values, next]);
    setDraft("");
  }

  return (
    <div className="tb-cp-field">
      <span className="tb-cp-label">{label}</span>
      <div className="tb-cp-tags">
        {values.map((tag) => (
          <span key={tag} className="tb-cp-tag">
            {tag}
            {disabled ? null : (
              <button
                type="button"
                aria-label={`Remove ${tag}`}
                onClick={() => onChange(values.filter((item) => item !== tag))}
              >
                ×
              </button>
            )}
          </span>
        ))}
      </div>
      {disabled ? null : (
        <div className="tb-cp-tag-add">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add(draft);
              }
            }}
            placeholder={addLabel}
            list={`${label}-suggestions`}
          />
          <datalist id={`${label}-suggestions`}>
            {available.map((item) => (
              <option key={item} value={item} />
            ))}
          </datalist>
          <button type="button" onClick={() => add(draft)} disabled={!draft.trim()}>
            + {addLabel}
          </button>
        </div>
      )}
    </div>
  );
}

export function CompanyProfileView({
  business,
  memberCount,
  locked,
  initialTab = "details",
  onSaved,
  onOpenDocuments,
}: CompanyProfileViewProps) {
  const { refreshSession } = useAuth();
  const [tab, setTab] = useState<ProfileTab>(initialTab);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingMedia, setUploadingMedia] = useState<"logo" | "cover" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(business.logo_url ?? null);
  const [coverUrl, setCoverUrl] = useState<string | null>(business.cover_url ?? null);
  const [mediaVersion, setMediaVersion] = useState(
    () => business.updated_at ?? Date.now(),
  );
  const logoInputRef = useRef<HTMLInputElement>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);
  const logoPreviewRef = useRef<string | null>(null);
  const coverPreviewRef = useRef<string | null>(null);

  const [name, setName] = useState(business.name ?? "");
  const [legalName, setLegalName] = useState(business.legal_name ?? "");
  const [taxNumber, setTaxNumber] = useState(business.tax_number ?? "");
  const [description, setDescription] = useState(business.description ?? "");
  const [emailDomain, setEmailDomain] = useState(business.email_domain ?? "");
  const [website, setWebsite] = useState(business.website ?? "");
  const [yearEstablished, setYearEstablished] = useState(
    business.year_established?.toString() ??
      (business.created_at
        ? String(new Date(business.created_at).getFullYear())
        : ""),
  );
  const [companySize, setCompanySize] = useState(
    business.company_size ?? "11-50 employees",
  );
  const [categories, setCategories] = useState<string[]>(
    business.industry_categories ?? [],
  );
  const [tags, setTags] = useState<string[]>(business.business_tags ?? []);
  const [email, setEmail] = useState(business.contact_email ?? "");
  const [phone, setPhone] = useState(business.contact_phone ?? "");
  const [street, setStreet] = useState(business.address?.street ?? "");
  const [city, setCity] = useState(business.address?.city ?? "");
  const [governorate, setGovernorate] = useState(
    business.address?.governorate ?? "Beirut",
  );
  const [postalCode, setPostalCode] = useState(business.address?.postal_code ?? "");
  const [country, setCountry] = useState(business.address?.country ?? "Lebanon");

  const isSupplier = business.type === "supplier";
  const verified = isSupplier
    ? business.verification_status === "verified"
    : business.status === "verified" || business.status === "active";
  const reviewPending = isSupplier && business.verification_status === "pending";
  const docsCount = business.verification_documents?.length ?? 0;
  const identityLocked = locked;
  const formLocked = !editing;
  const legalLocked = identityLocked || !editing;
  const profileSchema = useMemo(
    () => companyProfileSchema(identityLocked),
    [identityLocked],
  );
  const live = useLiveFields(profileSchema, {
    name,
    emailDomain,
    yearEstablished,
    website,
    email,
    phone,
    legalName,
    taxNumber,
    description,
  });

  useEffect(() => {
    setName(business.name ?? "");
    setLegalName(business.legal_name ?? "");
    setTaxNumber(business.tax_number ?? "");
    setDescription(business.description ?? "");
    setEmailDomain(business.email_domain ?? "");
    setWebsite(business.website ?? "");
    setYearEstablished(
      business.year_established?.toString() ??
        (business.created_at
          ? String(new Date(business.created_at).getFullYear())
          : ""),
    );
    setCompanySize(business.company_size ?? "11-50 employees");
    setCategories(business.industry_categories ?? []);
    setTags(business.business_tags ?? []);
    setEmail(business.contact_email ?? "");
    setPhone(business.contact_phone ?? "");
    setStreet(business.address?.street ?? "");
    setCity(business.address?.city ?? "");
    setGovernorate(business.address?.governorate ?? "Beirut");
    setPostalCode(business.address?.postal_code ?? "");
    setCountry(business.address?.country ?? "Lebanon");
    // Don't clobber an in-flight local blob preview with a stale server value.
    if (!logoPreviewRef.current) {
      setLogoUrl(business.logo_url ?? null);
    }
    if (!coverPreviewRef.current) {
      setCoverUrl(business.cover_url ?? null);
    }
    if (business.updated_at) {
      setMediaVersion(business.updated_at);
    }
  }, [business]);

  useEffect(() => {
    return () => {
      if (logoPreviewRef.current) URL.revokeObjectURL(logoPreviewRef.current);
      if (coverPreviewRef.current) URL.revokeObjectURL(coverPreviewRef.current);
    };
  }, []);

  const locationLabel = useMemo(() => {
    const cityPart = business.address?.city || business.address?.governorate;
    if (cityPart) return `${cityPart}, Lebanon`;
    if (formatAddress(business.address) !== "—") return formatAddress(business.address);
    return "Lebanon";
  }, [business.address]);

  const establishedYear =
    business.year_established ??
    (business.created_at ? new Date(business.created_at).getFullYear() : null);

  const industryLine = useMemo(() => {
    if (categories.length > 0) {
      return `${categories[0]}${isSupplier ? " Supplier" : " Buyer"}`;
    }
    return isSupplier ? "Supplier company" : "Buyer company";
  }, [categories, isSupplier]);

  const completion = useMemo(() => {
    const checks = [
      Boolean(name.trim()),
      Boolean(email.trim() || phone.trim()),
      Boolean(description.trim()),
      Boolean(logoUrl),
      isSupplier ? docsCount >= 3 || verified : true,
    ];
    const done = checks.filter(Boolean).length;
    return {
      percent: Math.round((done / checks.length) * 100),
      checks: [
        { label: "Basic information", done: Boolean(name.trim()) },
        { label: "Contact information", done: Boolean(email.trim() || phone.trim()) },
        { label: "Business description", done: Boolean(description.trim()) },
        { label: "Add logo", done: Boolean(logoUrl) },
        ...(isSupplier
          ? [
              {
                label: "Upload verification documents",
                done: docsCount >= 3 || verified,
              },
            ]
          : []),
      ],
    };
  }, [description, docsCount, email, isSupplier, logoUrl, name, phone, verified]);

  async function onPickFile(
    kind: "logo" | "cover",
    file: File | undefined,
  ) {
    if (!file || !file.type.startsWith("image/")) return;
    if (file.size > 8 * 1024 * 1024) {
      setError("Image must be 8 MB or smaller.");
      return;
    }

    const preview = URL.createObjectURL(file);
    if (kind === "logo") {
      if (logoPreviewRef.current) URL.revokeObjectURL(logoPreviewRef.current);
      logoPreviewRef.current = preview;
      setLogoUrl(preview);
    } else {
      if (coverPreviewRef.current) URL.revokeObjectURL(coverPreviewRef.current);
      coverPreviewRef.current = preview;
      setCoverUrl(preview);
    }

    setUploadingMedia(kind);
    setError(null);
    setSuccess(null);
    try {
      const row = await identityApi.uploadBusinessMedia(business.id, kind, file);
      const nextLogo = row.logo_url ?? null;
      const nextCover = row.cover_url ?? null;
      const nextVersion = row.updated_at ?? Date.now();

      if (kind === "logo") {
        if (logoPreviewRef.current) {
          URL.revokeObjectURL(logoPreviewRef.current);
          logoPreviewRef.current = null;
        }
        setLogoUrl(nextLogo);
      } else {
        if (coverPreviewRef.current) {
          URL.revokeObjectURL(coverPreviewRef.current);
          coverPreviewRef.current = null;
        }
        setCoverUrl(nextCover);
      }
      setMediaVersion(nextVersion);
      setSuccess(kind === "logo" ? "Logo saved." : "Cover image saved.");
      onSaved?.(row);
      void refreshSession();
    } catch (err) {
      if (kind === "logo") {
        if (logoPreviewRef.current) {
          URL.revokeObjectURL(logoPreviewRef.current);
          logoPreviewRef.current = null;
        }
        setLogoUrl(business.logo_url ?? null);
      } else {
        if (coverPreviewRef.current) {
          URL.revokeObjectURL(coverPreviewRef.current);
          coverPreviewRef.current = null;
        }
        setCoverUrl(business.cover_url ?? null);
      }
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not upload image. Try a JPG or PNG under 8 MB.",
      );
    } finally {
      setUploadingMedia(null);
    }
  }

  const logoSrc = logoUrl?.startsWith("blob:")
    ? logoUrl
    : mediaUrlFresh(logoUrl, mediaVersion);
  const coverSrc = coverUrl?.startsWith("blob:")
    ? coverUrl
    : mediaUrlFresh(coverUrl, mediaVersion) || "/images/company-cover.png";

  async function saveProfile() {
    if (!live.finish()) {
      setError("Fix the highlighted fields before saving.");
      return;
    }
    const year = yearEstablished.trim()
      ? Number.parseInt(yearEstablished.trim(), 10)
      : undefined;
    const domain = emailDomain.replace(/^@/, "").trim().toLowerCase();

    setSaving(true);
    setError(null);
    setSuccess(null);
    const payload: UpdateBusinessPayload = {
      contact_email: email.trim() || undefined,
      contact_phone: phone.trim() || undefined,
      description: description.trim(),
      website: cleanWebsite(website),
      year_established: year,
      company_size: companySize,
      industry_categories: categories,
      business_tags: tags,
    };
    if (!identityLocked) {
      payload.name = name.trim();
      payload.legal_name = legalName.trim() || undefined;
      payload.tax_number = taxNumber.trim() || undefined;
      payload.email_domain = domain || undefined;
      payload.address = {
        street: street.trim() || undefined,
        city: city.trim() || undefined,
        governorate: governorate || undefined,
        postal_code: postalCode.trim() || undefined,
        country: country.trim() || "Lebanon",
      };
    }

    try {
      const row = await identityApi.updateBusiness(business.id, payload);
      onSaved(row);
      setEditing(false);
      setSuccess("Company profile saved.");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Couldn't update company profile.",
      );
    } finally {
      setSaving(false);
    }
  }

  const tabs: { key: ProfileTab; label: string }[] = [
    { key: "details", label: "Business Details" },
    { key: "contact", label: "Contact Information" },
    { key: "verification", label: "Verification" },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div className="tb-cp">
      <p className="tb-ov-crumb">
        Company Identity <span>/</span> Company Profile
      </p>
      <header className="tb-cp-head">
        <div>
          <h1 className="tb-cp-title">Company Profile</h1>
          <p className="tb-cp-lede">
            Manage your company information and keep your profile up to date.
          </p>
        </div>
      </header>

      <div className="tb-cp-layout">
        <div className="tb-cp-main">
          <div className="tb-cp-cover-wrap">
            <div className="tb-cp-cover">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={coverSrc}
                src={coverSrc}
                alt=""
                className="tb-cp-cover-img"
              />
              <p className="tb-cp-cover-script">
                A Stronger Lebanon Through Stronger Businesses
              </p>
              <button
                type="button"
                className="tb-cp-cover-btn"
                disabled={uploadingMedia === "cover"}
                onClick={() => coverInputRef.current?.click()}
              >
                <span aria-hidden>📷</span>{" "}
                {uploadingMedia === "cover" ? "Uploading…" : "Change Cover"}
              </button>
              <input
                ref={coverInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="sr-only"
                onChange={(e) => {
                  void onPickFile("cover", e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </div>

            <section className="tb-cp-summary">
              <div className="tb-cp-logo-col">
                <div className="tb-cp-logo" data-empty={!logoSrc}>
                  {logoSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={logoSrc} src={logoSrc} alt="" className="tb-cp-logo-img" />
                  ) : (
                    <span aria-hidden>
                      {(business.name ?? "CO").slice(0, 2).toUpperCase()}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="tb-cp-logo-btn"
                  disabled={uploadingMedia === "logo"}
                  onClick={() => logoInputRef.current?.click()}
                >
                  {uploadingMedia === "logo" ? "Uploading…" : "Change Logo"}
                </button>
                <input
                  ref={logoInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="sr-only"
                  onChange={(e) => {
                    void onPickFile("logo", e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </div>

              <div className="tb-cp-summary-body">
                <div className="tb-cp-summary-top">
                  <div className="min-w-0">
                    <div className="tb-cp-name-row">
                      <h2>{business.name}</h2>
                      <span
                        className="tb-ov-verified"
                        data-tone={
                          verified ? "ok" : reviewPending ? "wait" : isSupplier ? "bad" : "ok"
                        }
                      >
                        {verified
                          ? "Verified Business"
                          : reviewPending
                            ? "Under Review"
                            : isSupplier
                              ? "Verification Needed"
                              : "Active Buyer"}
                      </span>
                    </div>
                    <p className="tb-cp-industry">{industryLine}</p>
                    <p className="tb-cp-bio">
                      {business.description ||
                        "Add a short description so buyers and partners understand what you offer."}
                    </p>
                    <ul className="tb-cp-meta">
                      <li>
                        <span aria-hidden>📍</span>
                        {locationLabel}
                      </li>
                      <li>
                        <span aria-hidden>📅</span>
                        {establishedYear
                          ? `Established ${establishedYear}`
                          : "Year not set"}
                      </li>
                      <li>
                        <span aria-hidden>👥</span>
                        {memberCount} Team Member{memberCount === 1 ? "" : "s"}
                      </li>
                    </ul>
                  </div>
                  <button
                    type="button"
                    className="tb-cp-edit-btn"
                    onClick={() => {
                      setEditing(true);
                      setTab("details");
                      setSuccess(null);
                    }}
                  >
                    ✎ Edit Profile
                  </button>
                </div>
              </div>
            </section>
          </div>

          <nav className="tb-cp-tabs" aria-label="Company profile sections">
            {tabs.map((item) => (
              <button
                key={item.key}
                type="button"
                className="tb-cp-tab"
                data-active={tab === item.key}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {error ? (
            <p className="tb-cp-alert is-error">{error}</p>
          ) : null}
          {success ? (
            <p className="tb-cp-alert is-ok">{success}</p>
          ) : null}

          {tab === "details" ? (
            <section className="tb-cp-panel">
              <div className="tb-cp-panel-head">
                <span className="tb-cp-panel-icon" aria-hidden>
                  ⛨
                </span>
                <div>
                  <h3>Business Details</h3>
                  <p>Tell us about your business.</p>
                </div>
              </div>

              <div className="tb-cp-grid">
                <div className="tb-cp-col">
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">
                      Company Name <em>*</em>
                    </span>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      onBlur={() => live.touch("name")}
                      disabled={legalLocked}
                      required
                    />
                    <FieldError error={live.errors.name} />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">
                      Company Domain <em>*</em>
                    </span>
                    <input
                      value={emailDomain}
                      onChange={(e) =>
                        setEmailDomain(e.target.value.replace(/^@/, "").toLowerCase())
                      }
                      onBlur={() => live.touch("emailDomain")}
                      disabled={legalLocked}
                      placeholder="levantsale.com"
                    />
                    <FieldError error={live.errors.emailDomain} />
                    <span className="tb-cp-help !mt-1">
                      Must include a suffix, e.g. <strong>yourcompany.com</strong>. This is used for teammate logins like sara@yourcompany.com.
                    </span>
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">
                      Business Type <em>*</em>
                    </span>
                    <select value={business.type} disabled>
                      <option value="supplier">Supplier</option>
                      <option value="buyer">Buyer</option>
                    </select>
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">
                      Short Description <em>*</em>
                    </span>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value.slice(0, 500))}
                      onBlur={() => live.touch("description")}
                      disabled={formLocked}
                      rows={4}
                      maxLength={500}
                    />
                    <FieldError error={live.errors.description} />
                    <span className="tb-cp-counter">
                      {description.length}/500
                    </span>
                  </label>
                  <TagEditor
                    label="Industry Categories"
                    values={categories}
                    onChange={setCategories}
                    suggestions={SUGGESTED_CATEGORIES}
                    disabled={formLocked}
                    addLabel="Add Category"
                  />
                </div>

                <div className="tb-cp-col">
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Company Size</span>
                    <select
                      value={companySize}
                      onChange={(e) => setCompanySize(e.target.value)}
                      disabled={formLocked}
                    >
                      {COMPANY_SIZES.map((size) => (
                        <option key={size} value={size}>
                          {size}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Year Established</span>
                    <NumberInput
                      kind="integer"
                      min={1800}
                      max={2100}
                      value={yearEstablished}
                      onChange={(e) => setYearEstablished(e.target.value)}
                      onBlur={() => live.touch("yearEstablished")}
                      disabled={formLocked}
                    />
                    <FieldError error={live.errors.yearEstablished} />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Website (optional)</span>
                    <input
                      type="url"
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                      onBlur={() => live.touch("website")}
                      disabled={formLocked}
                      placeholder="https://"
                    />
                    <FieldError error={live.errors.website} />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Operating Countries</span>
                    <select value={country} onChange={(e) => setCountry(e.target.value)} disabled={legalLocked}>
                      <option value="Lebanon">Lebanon</option>
                    </select>
                  </label>
                  <TagEditor
                    label="Business Tags"
                    values={tags}
                    onChange={setTags}
                    suggestions={SUGGESTED_TAGS}
                    disabled={formLocked}
                    addLabel="Add Tag"
                  />
                </div>
              </div>

              {identityLocked ? (
                <p className="tb-cp-help">
                  After verification, company name, legal name, tax number, domain, and
                  address stay locked. You can still update phone, description, website,
                  and other profile details.
                </p>
              ) : null}

              {editing ? (
                <div className="tb-cp-actions">
                  <button
                    type="button"
                    className="tb-ov-btn-ghost"
                    onClick={() => {
                      setEditing(false);
                      setError(null);
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="tb-ov-btn-primary"
                    disabled={saving}
                    onClick={() => void saveProfile()}
                  >
                    <BusyText busy={saving}>{saving ? "Saving…" : "Save changes"}</BusyText>
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}

          {tab === "contact" ? (
            <section className="tb-cp-panel">
              <div className="tb-cp-panel-head">
                <span className="tb-cp-panel-icon" aria-hidden>
                  ✉
                </span>
                <div>
                  <h3>Contact Information</h3>
                  <p>How partners reach your company.</p>
                </div>
              </div>
              {identityLocked ? (
                <p className="tb-cp-help">
                  Phone and contact email can be updated. Legal name, tax number, and
                  registered address stay locked after verification.
                </p>
              ) : null}
              <div className="tb-cp-grid">
                <div className="tb-cp-col">
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Legal name</span>
                    <input
                      value={legalName}
                      onChange={(e) => setLegalName(e.target.value)}
                      onBlur={() => live.touch("legalName")}
                      disabled={legalLocked}
                    />
                    <FieldError error={live.errors.legalName} />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Contact email</span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onBlur={() => live.touch("email")}
                      disabled={formLocked}
                    />
                    <FieldError error={live.errors.email} />
                  </label>
                  <LebanesePhoneField
                    label="Contact phone"
                    value={phone}
                    onChange={setPhone}
                    onBlur={() => live.touch("phone")}
                    disabled={formLocked}
                    error={live.errors.phone}
                  />
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Tax number</span>
                    <input
                      value={taxNumber}
                      onChange={(e) => setTaxNumber(e.target.value)}
                      onBlur={() => live.touch("taxNumber")}
                      disabled={legalLocked}
                    />
                    <FieldError error={live.errors.taxNumber} />
                  </label>
                </div>
                <div className="tb-cp-col">
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Street address</span>
                    <input
                      value={street}
                      onChange={(e) => setStreet(e.target.value)}
                      disabled={legalLocked}
                    />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">City</span>
                    <input
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      disabled={legalLocked}
                    />
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Governorate</span>
                    <select
                      value={governorate}
                      onChange={(e) => setGovernorate(e.target.value)}
                      disabled={legalLocked}
                    >
                      {LEBANON_REGIONS.map((region) => (
                        <option key={region.value} value={region.value}>
                          {region.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="tb-cp-field">
                    <span className="tb-cp-label">Postal code</span>
                    <input
                      value={postalCode}
                      onChange={(e) => setPostalCode(e.target.value)}
                      disabled={legalLocked}
                    />
                  </label>
                </div>
              </div>
              {editing ? (
                <div className="tb-cp-actions">
                  <button
                    type="button"
                    className="tb-ov-btn-primary"
                    disabled={saving}
                    onClick={() => void saveProfile()}
                  >
                    <BusyText busy={saving}>{saving ? "Saving…" : "Save changes"}</BusyText>
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}

          {tab === "verification" ? (
            <section className="tb-cp-panel">
              <div className="tb-cp-panel-head">
                <span className="tb-cp-panel-icon" aria-hidden>
                  ✓
                </span>
                <div>
                  <h3>Verification</h3>
                  <p>
                    {isSupplier
                      ? "Documents TradeBay reviews before you can sell."
                      : "Buyer accounts don’t require document verification to source."}
                  </p>
                </div>
              </div>
              {isSupplier ? (
                <>
                  <p className="tb-cp-help">
                    {verified
                      ? "This supplier is approved to sell on TradeBay."
                      : reviewPending
                        ? "Documents are waiting for TradeBay admin review."
                        : "Upload commercial registration, tax certificate, and address proof."}
                  </p>
                  {(business.verification_documents?.length ?? 0) > 0 ? (
                    <ul className="tb-cp-doc-list">
                      {business.verification_documents!.map((doc, index) => (
                        <li key={`${doc.document_type ?? "doc"}-${index}`}>
                          <strong>
                            {doc.document_type === "commercial_registration"
                              ? "Commercial registration"
                              : doc.document_type === "tax_certificate"
                                ? "Tax certificate"
                                : doc.document_type === "address_proof"
                                  ? "Business address proof"
                                  : doc.document_type ?? `Document ${index + 1}`}
                          </strong>
                          <span>{doc.file_name || "Uploaded file"}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="tb-cp-empty">No documents submitted yet.</p>
                  )}
                  {!verified ? (
                    <Link
                      href={ROUTES.businessesVerify}
                      className="tb-ov-btn-accent mt-4 inline-flex"
                    >
                      {(business.verification_documents?.length ?? 0) > 0
                        ? "Resubmit documents"
                        : "Upload verification documents"}
                    </Link>
                  ) : onOpenDocuments ? (
                    <button
                      type="button"
                      className="tb-cp-link-btn mt-4"
                      onClick={onOpenDocuments}
                    >
                      View verification details →
                    </button>
                  ) : null}
                </>
              ) : (
                <p className="tb-cp-help">
                  Create a separate supplier business if you want to sell — business
                  type cannot be changed after registration.
                </p>
              )}
            </section>
          ) : null}

          {tab === "settings" ? (
            <section className="tb-cp-panel">
              <div className="tb-cp-panel-head">
                <span className="tb-cp-panel-icon" aria-hidden>
                  ⚙
                </span>
                <div>
                  <h3>Settings</h3>
                  <p>Account preferences for this company.</p>
                </div>
              </div>
              <dl className="tb-cp-settings">
                <div>
                  <dt>Company domain</dt>
                  <dd>
                    {business.email_domain
                      ? `@${business.email_domain}`
                      : "Not set — add a domain so you can invite teammates"}
                  </dd>
                </div>
                <div>
                  <dt>Business type</dt>
                  <dd>{isSupplier ? "Supplier" : "Buyer"} (locked after creation)</dd>
                </div>
                <div>
                  <dt>Profile editing</dt>
                  <dd>
                    {identityLocked
                      ? "Verified — legal name, tax number, company name, domain, and address stay locked. Phone, description, and other profile details can be updated."
                      : "Editable by company administrators"}
                  </dd>
                </div>
                <div>
                  <dt>Active status</dt>
                  <dd>{business.status}</dd>
                </div>
              </dl>
            </section>
          ) : null}
        </div>

        <aside className="tb-cp-rail">
          <div className="tb-cp-widget">
            <h3>Profile Completion</h3>
            <div className="tb-cp-progress">
              <svg viewBox="0 0 96 96" aria-hidden>
                <circle cx="48" cy="48" r="40" className="tb-cp-progress-track" />
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  className="tb-cp-progress-value"
                  style={{
                    strokeDasharray: `${(completion.percent / 100) * 251.2} 251.2`,
                  }}
                />
              </svg>
              <strong>{completion.percent}%</strong>
            </div>
            <p className="tb-cp-widget-copy">
              {completion.percent >= 100
                ? "Your profile is complete and ready for partners."
                : "Almost there! Complete your profile to increase visibility."}
            </p>
            <ul className="tb-cp-checklist">
              {completion.checks.map((item) => (
                <li key={item.label} data-done={item.done}>
                  <span aria-hidden>{item.done ? "✓" : "○"}</span>
                  {item.label}
                </li>
              ))}
            </ul>
          </div>

          <div className="tb-cp-widget">
            <h3>Verification Status</h3>
            <span
              className={cn("tb-ov-verified", "mt-3")}
              data-tone={verified ? "ok" : reviewPending ? "wait" : isSupplier ? "bad" : "ok"}
            >
              {verified
                ? "Verified Business"
                : reviewPending
                  ? "Under Review"
                  : isSupplier
                    ? "Not Verified"
                    : "Active Buyer"}
            </span>
            <p className="tb-cp-widget-copy mt-3">
              {verified
                ? "Your profile is visible to verified partners on TradeBay."
                : reviewPending
                  ? "TradeBay is reviewing your documents."
                  : isSupplier
                    ? "Upload documents to get verified and sell."
                    : "You’re ready to source from verified suppliers."}
            </p>
            {isSupplier ? (
              <button
                type="button"
                className="tb-cp-link-btn"
                onClick={() => {
                  setTab("verification");
                  onOpenDocuments?.();
                }}
              >
                View Verification Details →
              </button>
            ) : null}
          </div>

          <div className="tb-cp-tip">
            <span className="tb-cp-tip-icon" aria-hidden>
              ▦
            </span>
            <p>
              <strong>A complete profile gets 3× more views.</strong> Businesses
              with complete profiles receive significantly more inquiries from
              serious buyers.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
