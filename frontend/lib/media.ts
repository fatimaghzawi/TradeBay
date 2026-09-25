
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
    
    
    return API_BASE_URL ? `${API_BASE_URL}${url}` : url;
  }
  return url;
}

export function verificationDocumentHref(url: string | null | undefined): string {
  if (!url || url.startsWith("pending:")) return "";
  return mediaUrl(url);
}

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
