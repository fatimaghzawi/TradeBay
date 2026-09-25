import type { AuditEvent } from "@/lib/api/identityApi";

function metaString(meta: Record<string, unknown>, key: string): string | null {
  const value = meta[key];
  if (typeof value === "string" && value.trim()) return value.trim();
  return null;
}

export function auditActorLabel(event: AuditEvent): string {
  const meta = event.metadata ?? {};
  return (
    metaString(meta, "actor_name") ||
    metaString(meta, "user_name") ||
    metaString(meta, "inviter_name") ||
    metaString(meta, "email") ||
    "Someone"
  );
}

export function auditTargetLabel(event: AuditEvent): string {
  const meta = event.metadata ?? {};
  return (
    metaString(meta, "member_name") ||
    metaString(meta, "target_name") ||
    metaString(meta, "invited_email") ||
    metaString(meta, "email") ||
    metaString(meta, "delivery_email") ||
    "a teammate"
  );
}

function roleLabel(meta: Record<string, unknown>): string | null {
  return (
    metaString(meta, "role_name") ||
    metaString(meta, "name") ||
    metaString(meta, "new_role_name")
  );
}

export function auditHeadline(event: AuditEvent): string {
  const action = (event.action ?? "").toUpperCase();
  const meta = event.metadata ?? {};
  const who = auditActorLabel(event);
  const whom = auditTargetLabel(event);
  const role = roleLabel(meta);
  const fromRole =
    metaString(meta, "previous_role_name") || metaString(meta, "from_role");
  const toRole =
    metaString(meta, "new_role_name") ||
    metaString(meta, "to_role") ||
    role;

  switch (action) {
    case "USER_INVITED":
    case "INVITATION_CREATED":
    case "MEMBER_INVITED":
      return `${who} invited ${whom}${role ? ` as ${role}` : ""}`;
    case "INVITATION_ACCEPTED":
    case "MEMBER_JOINED":
      return `${whom} joined the company${role ? ` as ${role}` : ""}`;
    case "INVITATION_REVOKED":
      return `${who} revoked the invitation for ${whom}`;
    case "INVITATION_DECLINED":
      return `${whom} declined an invitation`;
    case "INVITATION_RESENT":
      return `${who} resent an invitation to ${whom}`;
    case "MEMBER_ROLE_CHANGED":
    case "ROLE_ASSIGNED":
      if (fromRole && toRole) {
        return `${who} changed ${whom}'s role from ${fromRole} to ${toRole}`;
      }
      return `${who} updated ${whom}'s role${toRole ? ` to ${toRole}` : ""}`;
    case "MEMBER_REMOVED":
    case "MEMBERSHIP_REMOVED":
      return `${who} removed ${whom} from the company`;
    case "MEMBER_SUSPENDED":
    case "MEMBERSHIP_SUSPENDED":
    case "USER_SUSPENDED":
      return `${who} suspended ${whom}`;
    case "MEMBER_REACTIVATED":
    case "MEMBERSHIP_REACTIVATED":
    case "USER_REACTIVATED":
      return `${who} reactivated ${whom}`;
    case "ROLE_CREATED":
      return `${who} created the ${role || "new"} role`;
    case "ROLE_UPDATED":
      return `${who} updated the ${role || "role"} permissions`;
    case "ROLE_DELETED":
      return `${who} deleted the ${role || "role"}`;
    case "BUSINESS_CREATED":
      return `${who} established the company`;
    case "BUSINESS_UPDATED":
      return `${who} updated company details`;
    case "BUSINESS_VERIFICATION_SUBMITTED":
    case "SUPPLIER_VERIFICATION_SUBMITTED":
      return `${who} submitted verification documents`;
    case "BUSINESS_VERIFIED":
    case "SUPPLIER_VERIFICATION_APPROVED":
      return `TradeBay verified the company`;
    case "BUSINESS_REJECTED":
    case "SUPPLIER_VERIFICATION_REJECTED":
      return `Verification was rejected`;
    case "SUPPLIER_VERIFICATION_REVOKED":
      return `Selling rights were revoked — listings taken offline`;
    case "SUPPLIER_VERIFICATION_DOCUMENT_WITHDRAWN":
      return `${who} withdrew a verification document`;
    case "LOGIN_FAILED":
    case "AUTH_LOGIN_FAILED":
      return `Failed sign-in attempt${
        metaString(meta, "email") ? ` for ${metaString(meta, "email")}` : ""
      }`;
    case "LOGIN_SUCCESS":
    case "AUTH_LOGIN":
    case "USER_LOGIN":
      return `${who} signed in`;
    case "USER_LOGOUT":
      return `${who} signed out`;
    case "USER_LOGOUT_ALL":
      return `${who} signed out of all sessions`;
    case "SESSION_REVOKED":
      return `${who} revoked a sign-in session`;
    case "SESSION_REFRESHED":
      return `${who} refreshed a session`;
    case "PASSWORD_CHANGED":
    case "USER_PASSWORD_CHANGED":
      return `${who} changed their password`;
    case "USER_PASSWORD_RESET":
      return `${who} reset their password`;
    case "USER_REGISTERED":
      return `${whom === "a teammate" ? who : whom} created an account`;
    case "USER_EMAIL_VERIFIED":
      return `${who} verified their email`;
    case "REFRESH_TOKEN_REUSE_DETECTED":
      return "Suspicious sign-in detected, so related sessions were signed out";
    case "USER_REGISTRATION_RETRY_REJECTED":
      return "Someone tried to sign up again with this unverified email";
    default: {
      const readable = action
        .toLowerCase()
        .split("_")
        .filter(Boolean)
        .join(" ");
      return readable ? `${who}: ${readable}` : `${who} performed an action`;
    }
  }
}

export function auditTone(
  event: AuditEvent,
): "ok" | "warn" | "info" {
  const action = (event.action ?? "").toUpperCase();
  if (
    action.includes("FAILED") ||
    action.includes("REJECTED") ||
    action.includes("REUSE_DETECTED") ||
    action.includes("SUSPENDED") ||
    action.includes("REVOKED") ||
    action.includes("REMOVED")
  ) {
    return "warn";
  }
  if (
    action.includes("JOINED") ||
    action.includes("ACCEPTED") ||
    action.includes("VERIFIED") ||
    action.includes("APPROVED") ||
    action.includes("CREATED") ||
    action.includes("REACTIVATED")
  ) {
    return "ok";
  }
  return "info";
}

export function formatAuditWhen(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const diff = Date.now() - date.getTime();
  const hour = 3600_000;
  const day = 24 * hour;
  if (diff < hour) return "Just now";
  if (diff < day) {
    const h = Math.floor(diff / hour);
    return `${h} hour${h === 1 ? "" : "s"} ago`;
  }
  if (diff < 2 * day) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
