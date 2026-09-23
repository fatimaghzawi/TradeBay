"use client";

import type { AuthBusiness } from "@/lib/api/authApi";
import { mediaUrl } from "@/lib/media";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function companyInitials(name: string | null | undefined): string {
  const parts = (name || "CO").trim().split(/\s+/).filter(Boolean).slice(0, 2);
  const letters = parts.map((part) => part[0] || "").join("");
  return letters.toUpperCase() || "CO";
}

export function companyLocation(business: Pick<AuthBusiness, "address">): string {
  const city = business.address?.city?.trim();
  const gov = business.address?.governorate?.trim();
  if (city && gov && city !== gov) return `${city}, ${gov}`;
  return city || gov || "Lebanon";
}

export function companyBio(business: AuthBusiness): string {
  const written = business.description?.trim();
  if (written) return written;
  const legal = business.legal_name || business.name;
  const kind =
    business.type === "supplier"
      ? "supplier"
      : business.type === "buyer"
        ? "buyer"
        : "company";
  return `${legal} is a Lebanese ${kind} based in ${companyLocation(business)}.`;
}

export function CompanyLogo({
  url,
  name,
  className,
}: {
  url?: string | null;
  name?: string | null;
  className?: string;
}) {
  const src = mediaUrl(url);
  return (
    <div className={cn("tb-co-logo", className)} data-empty={!src || undefined}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" />
      ) : (
        <span aria-hidden>{companyInitials(name)}</span>
      )}
    </div>
  );
}

export function AdminCompanyHero({
  business,
  memberCount,
  actions,
  badges,
}: {
  business: AuthBusiness;
  memberCount?: number;
  actions?: ReactNode;
  badges?: ReactNode;
}) {
  const established =
    business.year_established ??
    (business.created_at ? new Date(business.created_at).getFullYear() : null);
  const website = business.website?.trim();

  return (
    <article className="tb-co-hero">
      <div className="tb-co-hero__sheet">
        <CompanyLogo
          url={business.logo_url}
          name={business.name}
          className="tb-co-hero__logo"
        />
        <div className="tb-co-hero__body">
          <div className="tb-co-hero__top">
            <div className="min-w-0">
              <div className="tb-co-hero__name">
                <h2>{business.name}</h2>
                {badges}
              </div>
              {business.legal_name && business.legal_name !== business.name ? (
                <p className="tb-co-hero__legal">{business.legal_name}</p>
              ) : null}
              <p className="tb-co-hero__bio">{companyBio(business)}</p>
              <ul className="tb-co-hero__meta">
                <li>{companyLocation(business)}</li>
                {established ? <li>Est. {established}</li> : null}
                {typeof memberCount === "number" ? (
                  <li>
                    {memberCount} team member{memberCount === 1 ? "" : "s"}
                  </li>
                ) : null}
                {business.email_domain ? <li>@{business.email_domain}</li> : null}
                {website ? (
                  <li>
                    <a href={website} target="_blank" rel="noopener noreferrer">
                      Website
                    </a>
                  </li>
                ) : null}
              </ul>
            </div>
            {actions ? <div className="tb-co-hero__actions">{actions}</div> : null}
          </div>
        </div>
      </div>
    </article>
  );
}
