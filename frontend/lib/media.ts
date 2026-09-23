/** Resolve catalog media URLs (seeded public paths + API uploads). */
import { API_BASE_URL } from "@/config/env";

export function mediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("blob:") ||
    url.startsWith("data:")
  ) {
    return url;
  }
  if (url.startsWith("/uploads/") || url.startsWith("/api/v1/")) {
    // Prefer same-origin `/uploads/...` so Next rewrites hit the API (cookie-safe).
    // Only prefix an absolute API host when explicitly configured.
    return API_BASE_URL ? `${API_BASE_URL}${url}` : url;
  }
  return url;
}

/** KYC files are never `pending://` placeholders — those cannot be opened. */
export function verificationDocumentHref(url: string | null | undefined): string {
  if (!url || url.startsWith("pending:")) return "";
  return mediaUrl(url);
}

/** Cache-bust uploaded assets so the browser shows the newest file immediately. */
export function mediaUrlFresh(
  url: string | null | undefined,
  version?: string | number | null,
): string {
  const base = mediaUrl(url);
  if (!base || base.startsWith("blob:") || base.startsWith("data:")) return base;
  if (version == null || version === "") return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}v=${encodeURIComponent(String(version))}`;
}
