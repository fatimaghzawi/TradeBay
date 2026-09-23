import type { AuthBusiness } from "@/lib/api/authApi";

export function companyMark(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "CO";
  const first = parts[0] ?? "";
  if (parts.length === 1) return first.slice(0, 2).toUpperCase();
  const second = parts[1] ?? "";
  return `${first[0] ?? ""}${second[0] ?? ""}`.toUpperCase() || "CO";
}

export function companyLocation(business: AuthBusiness): string | null {
  const city = business.address?.city?.trim();
  const gov = business.address?.governorate?.trim();
  const country = business.address?.country?.trim() || "Lebanon";
  if (city && gov) return `${city}, ${gov}`;
  if (city) return `${city}, ${country}`;
  if (gov) return `${gov}, ${country}`;
  return null;
}

export function companyTypeLabel(type: string): string {
  if (type === "supplier") return "Supplier";
  if (type === "buyer") return "Buyer";
  if (type === "platform") return "Platform";
  return type;
}

export function companyVerificationLabel(business: AuthBusiness): {
  label: string;
  tone: "ok" | "wait" | "bad";
} {
  const isSupplier = business.type === "supplier";
  if (isSupplier) {
    if (business.verification_status === "verified") {
      return { label: "Verified business", tone: "ok" };
    }
    if (business.verification_status === "pending") {
      return { label: "Verification in review", tone: "wait" };
    }
    if (business.verification_status === "rejected") {
      return { label: "Verification rejected", tone: "bad" };
    }
    return { label: "Verification needed", tone: "bad" };
  }
  if (business.status === "verified" || business.status === "active") {
    return { label: "Active buyer", tone: "ok" };
  }
  return { label: business.status || "Active", tone: "ok" };
}

export function companyStoryLine(business: AuthBusiness): string {
  const type = companyTypeLabel(business.type).toLowerCase();
  const location = companyLocation(business);
  if (location) {
    return `${companyTypeLabel(business.type)} company based in ${location}.`;
  }
  return `Your ${type} company workspace on TradeBay.`;
}

export type SetupItem = {
  key: string;
  label: string;
  done: boolean;
  href: string;
  cta: string;
};

export function companySetupItems(input: {
  business: AuthBusiness;
  memberCount: number;
  roleCount: number;
  pendingInvites: number;
  emailVerified: boolean;
  routes: {
    members: string;
    roles: string;
    invitations: string;
    verify: string;
    profile: string;
  };
}): SetupItem[] {
  const { business, memberCount, roleCount, pendingInvites, emailVerified, routes } =
    input;
  const isSupplier = business.type === "supplier";
  const verified =
    isSupplier
      ? business.verification_status === "verified"
      : business.status === "verified" || business.status === "active";

  return [
    {
      key: "profile",
      label: "Company details complete",
      done: Boolean(business.name && (business.contact_email || business.tax_number)),
      href: routes.profile,
      cta: "Edit company",
    },
    {
      key: "email",
      label: "Your email verified",
      done: emailVerified,
      href: routes.profile,
      cta: "Verify email",
    },
    ...(isSupplier
      ? [
          {
            key: "verify",
            label: "Supplier verification",
            done: verified,
            href: routes.verify,
            cta: verified ? "View status" : "Upload documents",
          },
        ]
      : []),
    {
      key: "team",
      label: memberCount > 1 ? "Team taking shape" : "Invite your first teammate",
      done: memberCount > 1 || pendingInvites > 0,
      href: pendingInvites > 0 ? routes.invitations : routes.members,
      cta: "Build team",
    },
    {
      key: "roles",
      label: "Roles defined for your team",
      done: roleCount > 0,
      href: routes.roles,
      cta: "Define roles",
    },
  ];
}
