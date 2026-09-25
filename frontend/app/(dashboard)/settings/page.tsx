"use client";

import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";

const LINKS = [
  {
    href: ROUTES.profile,
    title: "My profile",
    body: "Update your name and check email verification.",
    glyph: "☺",
    tone: "sales",
  },
  {
    href: ROUTES.changePassword,
    title: "Change password",
    body: "Update your password. Other sessions will be signed out.",
    glyph: "⛨",
    tone: "admin",
  },
  {
    href: ROUTES.sessions,
    title: "Active sessions",
    body: "Review devices and revoke sessions you don’t recognize.",
    glyph: "◉",
    tone: "viewer",
  },
  {
    href: ROUTES.businesses,
    title: "Business settings",
    body: "Company profile, domain, and verification.",
    glyph: "◈",
    tone: "manager",
  },
  {
    href: ROUTES.members,
    title: "Team & access",
    body: "Members, invitations, and role assignments.",
    glyph: "◎",
    tone: "teal",
  },
  {
    href: ROUTES.roles,
    title: "Roles & permissions",
    body: "System and custom roles for this business.",
    glyph: "★",
    tone: "finance",
  },
  {
    href: ROUTES.audit,
    title: "Audit logs",
    body: "Security and business events for the active company.",
    glyph: "☰",
    tone: "custom",
  },
] as const;

export default function SettingsPage() {
  const { user, business, hasPermission, roleName } = useAuth();
  const verified = Boolean(user?.email_verified_at);
  const links = LINKS.filter((link) => {
    if (link.href === ROUTES.audit) return hasPermission("audit_logs.read");
    if (link.href === ROUTES.members) return hasPermission("users.read");
    if (link.href === ROUTES.roles) return hasPermission("roles.read");
    return true;
  });

  return (
    <IdentityPageShell
      crumb="Account / Settings"
      title="Account & Security"
      lede={
        <>
          {user?.email ?? "Your account"}
          {roleName ? ` · ${roleName}` : ""}
          {business ? ` · ${business.name}` : ""}.
        </>
      }
      banner={{
        icon: verified ? "✓" : "!",
        title: verified ? "Email verified." : "Email not verified.",
        body: verified
          ? "You can use trading features when your role includes the right access."
          : "Verify your email before using trading features.",
      }}
      stats={[
        {
          icon: "☺",
          tone: "teal",
          value: user?.first_name
            ? `${user.first_name} ${(user.last_name ?? "").slice(0, 1)}.`
            : "You",
          label: "Signed in as",
        },
        {
          icon: verified ? "✓" : "!",
          tone: verified ? "green" : "rose",
          value: verified ? "Verified" : "Pending",
          label: "Email",
        },
        {
          icon: "◈",
          tone: "orange",
          value: business?.name ?? "—",
          label: "Company",
        },
        {
          icon: "★",
          tone: "rose",
          value: roleName ?? "—",
          label: "Role",
        },
      ]}
      quote="“A secure account is the first desk on the quay.”"
    >
      {!verified ? (
        <div className="mt-2">
          <FeedbackBanner tone="error" title="Email not verified">
            Verify your email before using trading features.{" "}
            <Link
              href={`${ROUTES.verifyEmail}?email=${encodeURIComponent(user?.email ?? "")}`}
              className="font-semibold underline underline-offset-2"
            >
              Enter verification code
            </Link>
          </FeedbackBanner>
        </div>
      ) : null}

      <ul className="tb-roles-list">
        {links.map((link) => (
          <li key={link.href} className="tb-roles-row">
            <span
              className="tb-roles-glyph"
              data-tone={link.tone === "teal" ? "sales" : link.tone}
              aria-hidden
            >
              {link.glyph}
            </span>
            <div className="tb-roles-row-main min-w-0 flex-1">
              <Link href={link.href} className="tb-roles-row-name">
                {link.title}
              </Link>
              <p className="tb-roles-row-desc">{link.body}</p>
            </div>
            <Link
              href={link.href}
              className="text-sm font-bold text-accent hover:underline"
            >
              Open →
            </Link>
          </li>
        ))}
      </ul>
    </IdentityPageShell>
  );
}
