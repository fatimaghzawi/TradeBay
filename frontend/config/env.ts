/**
 * API origin for browser calls.
 * Empty string = same-origin (`/api/v1/...`) via Next rewrites — required for httpOnly
 * cookie auth (avoids localhost vs 127.0.0.1 / port cross-site cookie drops).
 * Set NEXT_PUBLIC_API_URL only when the API is on a different public host.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
