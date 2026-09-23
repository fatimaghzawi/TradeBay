/**
 * Translate API / technical errors into polished B2B product language.
 * Never surface field names, permission codes, stack traces, or status enums.
 */

const TECHNICAL_PATTERNS: RegExp[] = [
  /\b[a-z]+(?:_[a-z0-9]+)+\b/i, // snake_case identifiers
  /\b[a-z]+\.[a-z_]+\b/i, // permission codes like products.read
  /\bObjectId\b/i,
  /\bMongo(?:DB)?\b/i,
  /\bPostgreSQL\b/i,
  /\bECONNREFUSED\b/i,
  /\btraceback\b/i,
  /\bHTTP[_ ]?\d{3}\b/i,
  /\bpayload\b/i,
  /\bendpoint\b/i,
  /\bmutation\b/i,
  /→/,
  /confirm\s*=\s*true/i,
  /\{.*\}/,
  /\[.*\]/,
];

/** Known backend messages → product copy (exact or prefix match). */
const KNOWN: Array<{ match: RegExp | string; message: string }> = [
  { match: /^Permission denied$/i, message: "You don’t have access to this action." },
  { match: /^Forbidden$/i, message: "You don’t have access to this action." },
  { match: /^Unauthorized$/i, message: "Please sign in again." },
  { match: /^Authentication required$/i, message: "Please sign in again." },
  { match: /^Bad request$/i, message: "Please check your details and try again." },
  { match: /^Conflict$/i, message: "That conflicts with an existing record. Please try again." },
  { match: /^Resource not found$/i, message: "We couldn’t find what you’re looking for." },
  { match: /^Not found$/i, message: "We couldn’t find what you’re looking for." },
  { match: /^Request failed$/i, message: "Something went wrong. Please try again." },
  { match: /^Server error$/i, message: "Something went wrong on our side. Please try again." },
  { match: /^Too many requests$/i, message: "Too many attempts. Please wait a moment and try again." },
  {
    match: /Active business context is required/i,
    message: "Select a company to continue.",
  },
  {
    match: /Business context required/i,
    message: "Select a company to continue.",
  },
  {
    match: /Email verification is required/i,
    message: "Verify your email before continuing.",
  },
  {
    match: /Cannot grant permissions outside your own/i,
    message: "You can only assign access you already have.",
  },
  {
    match: /Invalid status transition/i,
    message: "This action isn’t available for the current status.",
  },
  {
    match: /Invalid negotiation transition/i,
    message: "This step isn’t available in the negotiation right now.",
  },
  {
    match: /Invalid .+ transition:/i,
    message: "This action isn’t available right now.",
  },
  {
    match: /RFQ must be published before/i,
    message: "Publish the RFQ before inviting suppliers.",
  },
  {
    match: /Cannot negotiate after the RFQ is awarded/i,
    message: "Negotiation is closed — this RFQ already has an award.",
  },
  {
    match: /Cannot modify an accepted or rejected quotation/i,
    message: "This quotation is finalized and can’t be changed.",
  },
  {
    match: /Handshake requires explicit confirm/i,
    message: "Confirm you want to lock in this deal to continue.",
  },
  {
    match: /Award requires explicit confirm/i,
    message: "Confirm you want to award this quotation.",
  },
  {
    match: /product_id is required/i,
    message: "Select a product to continue.",
  },
  {
    match: /title is required/i,
    message: "Add a title to continue.",
  },
  {
    match: /supplier_business_id/i,
    message: "Supplier information is unavailable. Please try again.",
  },
  {
    match: /quantity must be/i,
    message: "Enter a quantity greater than zero.",
  },
  {
    match: /Money must be string or int/i,
    message: "Enter a valid amount.",
  },
  {
    match: /Invalid identifier/i,
    message: "That link isn’t valid. Please try again.",
  },
  {
    match: /Session has been revoked/i,
    message: "Your session ended. Please sign in again.",
  },
  {
    match: /Account is not active/i,
    message: "This account isn’t active. Contact your administrator.",
  },
  {
    match: /Email is already registered/i,
    message: "An account with this email already exists.",
  },
  {
    match: /Invalid email or password/i,
    message: "Email or password is incorrect.",
  },
  {
    match: /Invalid verification code/i,
    message: "That verification code isn’t correct.",
  },
  {
    match: /Database temporarily unavailable/i,
    message: "We’re having trouble reaching our systems. Please try again shortly.",
  },
  {
    match: /An unexpected error occurred/i,
    message: "Something went wrong. Please try again.",
  },
  {
    match: /Not allowed/i,
    message: "You don’t have access to this action.",
  },
];

const STATUS_DEFAULTS: Record<number, string> = {
  400: "Please check your details and try again.",
  401: "Please sign in again.",
  403: "You don’t have access to this action.",
  404: "We couldn’t find what you’re looking for.",
  409: "That conflicts with existing information. Please try again.",
  422: "Please check your details and try again.",
  429: "Too many attempts. Please wait a moment and try again.",
  500: "Something went wrong. Please try again.",
  502: "Something went wrong. Please try again.",
  503: "TradeBay is temporarily unavailable. Please try again shortly.",
};

function looksTechnical(message: string): boolean {
  const trimmed = message.trim();
  if (!trimmed) return true;
  if (trimmed.length > 220) return true;
  return TECHNICAL_PATTERNS.some((re) => re.test(trimmed));
}

function matchKnown(message: string): string | null {
  for (const entry of KNOWN) {
    if (typeof entry.match === "string") {
      if (message === entry.match) return entry.message;
    } else if (entry.match.test(message)) {
      return entry.message;
    }
  }
  return null;
}

/** Sanitize a raw API message for display. */
export function sanitizeApiMessage(
  message: string | null | undefined,
  status = 0,
  code?: string | null,
): string {
  const raw = (message ?? "").trim();
  const known = raw ? matchKnown(raw) : null;
  if (known) return known;

  if (raw && !looksTechnical(raw)) {
    // Already readable product copy from the API.
    return raw;
  }

  if (code) {
    const byCode = matchKnown(code.replace(/_/g, " "));
    if (byCode) return byCode;
    if (/PERMISSION/i.test(code)) return "You don’t have access to this action.";
    if (/NOT_FOUND|RESOURCE/i.test(code)) return "We couldn’t find what you’re looking for.";
    if (/UNAUTHORIZED|CREDENTIAL|SESSION|TOKEN/i.test(code)) return "Please sign in again.";
    if (/VALIDATION/i.test(code)) return "Please check your details and try again.";
  }

  const statusMessage = status ? STATUS_DEFAULTS[status] : undefined;
  if (statusMessage) return statusMessage;
  if (status >= 500) {
    return STATUS_DEFAULTS[500] ?? "Something went wrong. Please try again.";
  }
  return "Something went wrong. Please try again.";
}

/** Default message when the API returns no body for a status. */
export function defaultMessageForStatus(status: number): string {
  const statusMessage = STATUS_DEFAULTS[status];
  if (statusMessage) return statusMessage;
  if (status >= 500) {
    return STATUS_DEFAULTS[500] ?? "Something went wrong. Please try again.";
  }
  return "Something went wrong. Please try again.";
}

/** Prefer ApiError (already sanitized) or a contextual fallback. */
export function userFacingError(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "message" in err) {
    const msg = String((err as { message?: unknown }).message ?? "").trim();
    if (msg) {
      const status =
        "status" in err && typeof (err as { status?: unknown }).status === "number"
          ? (err as { status: number }).status
          : 0;
      const code =
        "code" in err && typeof (err as { code?: unknown }).code === "string"
          ? (err as { code: string }).code
          : null;
      return sanitizeApiMessage(msg, status, code);
    }
  }
  return fallback;
}
