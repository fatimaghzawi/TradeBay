"use client";

import {
  InventoryLinkBtn,
  InventoryPageHeader,
} from "@/components/catalog/InventoryUi";
import { VerifiedBadge } from "@/components/admin/VerifiedBadge";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ApiError } from "@/lib/api/client";
import { identityApi, type PublicCompany } from "@/lib/api/identityApi";
import { formatAddress } from "@/lib/business";
import { ROUTES } from "@/lib/constants";
import { mediaUrl } from "@/lib/media";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

function websiteHref(value?: string | null) {
  const trimmed = (value || "").trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export default function CompanyPublicPage() {
  const params = useParams<{ id: string }>();
  const companyId = params.id;
  const [company, setCompany] = useState<PublicCompany | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void identityApi
      .getPublicCompany(companyId)
      .then((row) => setCompany(row))
      .catch((err) => {
        setCompany(null);
        setError(err instanceof ApiError ? err.message : "Couldn't load this company.");
      })
      .finally(() => setLoading(false));
  }, [companyId]);

  const location = useMemo(
    () => formatAddress(company?.address ?? null),
    [company?.address],
  );
  const website = websiteHref(company?.website);
  const isSupplier = company?.type === "supplier";
  const verified = company?.verification_status === "verified";
  const logo = mediaUrl(company?.logo_url);

  if (loading) return <LoadingEntity entity="company" />;
  if (!company) {
    return (
      <div className="tb-inv-page">
        <FeedbackBanner tone="error" title="Company not found">
          {error || "This company is not available."}
        </FeedbackBanner>
      </div>
    );
  }

  return (
    <div className="tb-inv-page">
      <InventoryPageHeader
        eyebrow={isSupplier ? "Supplier" : "Buyer"}
        title={company.name}
        description={
          company.description?.trim() ||
          "Public trading profile — company details shared with RFQ counterparties."
        }
        meta={
          <span className="tb-inv-chip">
            {isSupplier ? "Supplier" : "Buyer"}
          </span>
        }
        actions={
          isSupplier ? (
            <InventoryLinkBtn href={ROUTES.supplierProfile(company.id)} tone="accent">
              See catalog →
            </InventoryLinkBtn>
          ) : null
        }
      />

      <section className="tb-sup-profile-hero" aria-label="Company">
        <div className="tb-sup-profile-avatar" aria-hidden>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt="" />
          ) : (
            <span>{company.name.slice(0, 2).toUpperCase()}</span>
          )}
        </div>
        <div className="min-w-0">
          <p className="tb-sup-profile-kicker">
            {isSupplier ? "TradeBay supplier" : "TradeBay buyer"}
          </p>
          <h2 className="tb-sup-profile-name tb-verified-inline">
            {company.name}
            {isSupplier ? (
              <VerifiedBadge
                verified={verified}
                showWhenUnverified={false}
                size="md"
              />
            ) : null}
          </h2>
          {company.legal_name && company.legal_name !== company.name ? (
            <p className="tb-sup-profile-copy">{company.legal_name}</p>
          ) : null}
        </div>
      </section>

      <dl className="tb-company-facts">
        <div>
          <dt>Location</dt>
          <dd>{location}</dd>
        </div>
        <div>
          <dt>Established</dt>
          <dd>{company.year_established || "—"}</dd>
        </div>
        <div>
          <dt>Company size</dt>
          <dd>{company.company_size || "—"}</dd>
        </div>
        <div>
          <dt>Website</dt>
          <dd>
            {website ? (
              <a href={website} target="_blank" rel="noreferrer">
                {company.website}
              </a>
            ) : (
              "—"
            )}
          </dd>
        </div>
        {(company.industry_categories || []).length ? (
          <div className="tb-company-facts__wide">
            <dt>Industries</dt>
            <dd>{(company.industry_categories || []).join(" · ")}</dd>
          </div>
        ) : null}
        {(company.business_tags || []).length ? (
          <div className="tb-company-facts__wide">
            <dt>Focus</dt>
            <dd>{(company.business_tags || []).join(" · ")}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
