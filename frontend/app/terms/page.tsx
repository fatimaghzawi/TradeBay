import { LegalDoc, LegalSection } from "@/components/legal/LegalDoc";
import { ROUTES } from "@/lib/constants";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description: "TradeBay Terms & Conditions governing use of the B2B marketplace.",
};

export default function TermsPage() {
  return (
    <LegalDoc title="Terms & Conditions" effectiveDate="17 September 2026">
      <LegalSection title="1. Agreement to these Terms">
        <p>
          By creating a TradeBay account, accessing the platform, or using any TradeBay
          service (including sourcing, catalog, RFQs, quotations, orders, messaging, and
          payments), you agree to these Terms &amp; Conditions (“Terms”) on behalf of
          yourself and, where applicable, the business account you represent.
        </p>
        <p>
          If you do not agree, do not register or continue using TradeBay. If you accept
          on behalf of a company, you confirm that you are authorized to bind that company.
        </p>
      </LegalSection>

      <LegalSection title="2. Eligibility &amp; accounts">
        <p>
          TradeBay is intended for business users engaged in wholesale or commercial
          trade. You must provide accurate registration information, keep credentials
          confidential, and promptly update details that change. You are responsible for
          activity under your account and memberships.
        </p>
        <p>
          Email verification is required before certain commercial actions. We may
          suspend or restrict accounts that are incomplete, abusive, fraudulent, or in
          breach of these Terms.
        </p>
      </LegalSection>

      <LegalSection title="3. Business profiles &amp; supplier verification">
        <p>
          A company may buy after creating a business account. Selling (catalog listings,
          quotations, and related seller actions) requires a supplier profile and
          successful verification by TradeBay platform staff, including review of
          submitted documents.
        </p>
        <p>
          You warrant that documents and information you submit are genuine, current, and
          lawfully obtained. TradeBay may approve, reject, suspend, or revoke verification
          with recorded reasons.
        </p>
      </LegalSection>

      <LegalSection title="4. Marketplace conduct">
        <p>
          You agree to use TradeBay only for lawful B2B purposes. You must not: misrepresent
          products or prices; manipulate RFQs or quotations in bad faith; scrape or abuse
          the platform; interfere with other users; or attempt to bypass permissions,
          verification, or security controls.
        </p>
        <p>
          Roles and permissions are granted per business membership. You may only invite
          users and assign roles within the authority of your own permissions.
        </p>
      </LegalSection>

      <LegalSection title="5. Orders, payments &amp; platform fees">
        <p>
          Commercial terms of a deal (price, quantity, delivery, payment) are formed
          between buyer and supplier according to RFQs, quotations, negotiations, and
          orders on the platform. TradeBay may charge commission or service fees as
          disclosed in the product or settlement flows.
        </p>
        <p>
          Unless stated otherwise, TradeBay is not a party to the underlying sale of goods
          and does not guarantee fulfilment, quality, or payment performance between
          trading parties, except where a specific TradeBay-managed settlement or escrow
          feature is expressly offered.
        </p>
      </LegalSection>

      <LegalSection title="6. Content &amp; intellectual property">
        <p>
          You retain ownership of content you upload (product data, documents, messages)
          and grant TradeBay a licence to host, display, and process it to operate the
          marketplace. TradeBay branding, software, and design remain our property.
        </p>
      </LegalSection>

      <LegalSection title="7. Disputes, reviews &amp; moderation">
        <p>
          Users may open disputes and leave reviews subject to platform rules. TradeBay
          may moderate content, request evidence, and take action including suspension
          where necessary to protect trust and safety.
        </p>
      </LegalSection>

      <LegalSection title="8. Limitation of liability">
        <p>
          To the fullest extent permitted by applicable law, TradeBay is not liable for
          indirect, incidental, or consequential damages arising from marketplace use,
          including lost profits, data loss, or third-party trading outcomes. Our
          aggregate liability related to these Terms is limited to fees you paid to
          TradeBay in the three months preceding the claim, where such a limit is
          enforceable.
        </p>
      </LegalSection>

      <LegalSection title="9. Termination">
        <p>
          You may stop using TradeBay at any time. We may suspend or terminate access for
          breach, risk, legal requirement, or prolonged inactivity. Provisions that by
          nature should survive (including liability limits, IP, and confidentiality)
          continue after termination.
        </p>
      </LegalSection>

      <LegalSection title="10. Changes &amp; contact">
        <p>
          We may update these Terms by posting a revised version with a new effective
          date. Continued use after changes constitutes acceptance. Questions:{" "}
          <a
            href="mailto:legal@tradebay.app"
            className="font-semibold text-[#0d3b2a] underline underline-offset-2"
          >
            legal@tradebay.app
          </a>
          . See also our{" "}
          <Link
            href={ROUTES.privacy}
            className="font-semibold text-[#0d3b2a] underline underline-offset-2"
          >
            Privacy Policy
          </Link>
          .
        </p>
      </LegalSection>
    </LegalDoc>
  );
}
