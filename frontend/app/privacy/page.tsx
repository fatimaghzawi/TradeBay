import { LegalDoc, LegalSection } from "@/components/legal/LegalDoc";
import { ROUTES } from "@/lib/constants";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How TradeBay collects, uses, and protects personal and business data.",
};

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy" effectiveDate="17 September 2026">
      <LegalSection title="1. Who we are">
        <p>
          TradeBay (“we”, “us”) operates a B2B marketplace that helps Lebanese businesses
          source, negotiate, and trade with verified suppliers. This Privacy Policy
          explains how we process personal data when you register, invite teammates, or
          use the platform.
        </p>
      </LegalSection>

      <LegalSection title="2. Data we collect">
        <p>We may process:</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            <span className="font-medium text-[#0c1612]">Account data</span> — name, email,
            password hash, phone (if provided), verification status.
          </li>
          <li>
            <span className="font-medium text-[#0c1612]">Business data</span> — company
            name, type (buyer/supplier), tax and contact details, addresses, verification
            documents.
          </li>
          <li>
            <span className="font-medium text-[#0c1612]">Membership &amp; access data</span>{" "}
            — roles, invitations, permissions, session devices, IP address, user agent.
          </li>
          <li>
            <span className="font-medium text-[#0c1612]">Transactional &amp; support data</span>{" "}
            — RFQs, quotations, messages, audit logs, dispute evidence, and communications
            with support.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="3. How we use data">
        <p>We use data to:</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Create and secure accounts, memberships, and sessions</li>
          <li>Send email verification and password-reset codes</li>
          <li>Operate marketplace features and enforce permissions</li>
          <li>Verify suppliers and prevent fraud or abuse</li>
          <li>Keep audit trails required for trust and compliance</li>
          <li>Improve product reliability and notify you of service changes</li>
        </ul>
      </LegalSection>

      <LegalSection title="4. Legal bases">
        <p>
          Where applicable law requires a legal basis, we process data to perform our
          contract with you, comply with legal obligations, pursue legitimate interests
          (security, platform integrity, product improvement), and — where needed — with
          your consent (for example optional communications).
        </p>
      </LegalSection>

      <LegalSection title="5. Sharing">
        <p>
          We share data with: other members of your business account as needed for team
          collaboration; trading counterparties when you participate in RFQs, quotes, or
          orders; processors that host email, infrastructure, or analytics under contract;
          and authorities when required by law. We do not sell personal data.
        </p>
      </LegalSection>

      <LegalSection title="6. Retention &amp; security">
        <p>
          We retain account and audit data for as long as needed to operate TradeBay,
          resolve disputes, and meet legal requirements, then delete or anonymize where
          feasible. We use access controls, encrypted transport, hashed passwords, and
          session revocation to protect accounts.
        </p>
      </LegalSection>

      <LegalSection title="7. Your rights">
        <p>
          Subject to applicable law, you may request access, correction, deletion, or
          restriction of your personal data, and object to certain processing. Contact{" "}
          <a
            href="mailto:privacy@tradebay.app"
            className="font-semibold text-[#0d3b2a] underline underline-offset-2"
          >
            privacy@tradebay.app
          </a>
          . You may also close your account through support where available.
        </p>
      </LegalSection>

      <LegalSection title="8. Cookies &amp; sessions">
        <p>
          TradeBay uses HttpOnly cookies for authentication sessions. These are necessary
          for login state and security (refresh rotation and revocation). Disabling them
          will prevent signed-in use of the product.
        </p>
      </LegalSection>

      <LegalSection title="9. Changes &amp; related terms">
        <p>
          We may update this Policy by posting a revised version with a new effective
          date. Related obligations appear in our{" "}
          <Link
            href={ROUTES.terms}
            className="font-semibold text-[#0d3b2a] underline underline-offset-2"
          >
            Terms &amp; Conditions
          </Link>
          .
        </p>
      </LegalSection>
    </LegalDoc>
  );
}
