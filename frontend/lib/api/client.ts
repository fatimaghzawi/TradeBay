import { generateRequestId } from "@/lib/utils";
import { API_BASE_URL } from "@/config/env";
import { getGuestId } from "@/lib/guestId";
import { defaultMessageForStatus, sanitizeApiMessage } from "@/lib/api/userMessage";

const API_V1 = `${API_BASE_URL}/api/v1`;

const NO_REFRESH_PATHS = new Set([
  "/auth/refresh",
  "/auth/login",
  "/auth/logout",
  "/auth/register",
  "/auth/forgot-password",
  "/auth/password/reset",
  "/auth/email/verify",
  "/auth/email/resend",
]);

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(
    message: string,
    options: { code: string; status: number; details?: unknown },
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code;
    this.status = options.status;
    this.details = options.details ?? null;
  }
}

type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

function normalizeError(status: number, body: unknown): ApiError {
  const parsed = body as ApiErrorBody;
  const code = parsed?.error?.code ?? `HTTP_${status}`;
  const raw = parsed?.error?.message ?? defaultMessageForStatus(status);
  const message = sanitizeApiMessage(raw, status, code);
  const details = parsed?.error?.details ?? body;
  return new ApiError(message, { code, status, details });
}

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  
  skipRefresh?: boolean;
};

export type PaginationMeta = {
  page: number;
  page_size: number;
  total: number;
};

export type PaginatedResult<T> = {
  data: T[];
  meta: PaginationMeta;
};

function buildUrl(path: string, params?: ApiRequestOptions["params"]): string {
  const url = path.startsWith("http")
    ? path
    : `${API_V1}${path.startsWith("/") ? path : `/${path}`}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

function applyGuestHeader(headers: Headers) {
  const guestId = getGuestId();
  if (guestId) headers.set("X-TradeBay-Guest", guestId);
}

function canRefresh(path: string): boolean {
  const normalized = path.split("?")[0] ?? path;
  return !NO_REFRESH_PATHS.has(normalized);
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessCookie(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const response = await fetch(buildUrl("/auth/refresh"), {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      return response.ok;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function recoverFromUnauthorized(
  path: string,
  status: number,
  skipRefresh: boolean | undefined,
): Promise<boolean> {
  if (status !== 401 || skipRefresh || !canRefresh(path)) return false;
  return refreshAccessCookie();
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body, params, headers: initHeaders, skipRefresh, ...rest } = options;
  const headers = new Headers(initHeaders);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", generateRequestId());
  applyGuestHeader(headers);

  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (typeof FormData !== "undefined" && body instanceof FormData) {
      payload = body;
    } else {
      headers.set("Content-Type", "application/json");
      payload = JSON.stringify(body);
    }
  }

  const response = await fetch(buildUrl(path, params), {
    ...rest,
    credentials: "include",
    headers,
    body: payload,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const data: unknown = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  if (!response.ok) {
    if (await recoverFromUnauthorized(path, response.status, skipRefresh)) {
      return apiRequest<T>(path, { ...options, skipRefresh: true });
    }
    throw normalizeError(response.status, data);
  }

  if (data && typeof data === "object" && "data" in data) {
    return (data as { data: T }).data;
  }
  return data as T;
}

export async function apiRequestPage<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<PaginatedResult<T>> {
  const { body, params, headers: initHeaders, skipRefresh, ...rest } = options;
  const headers = new Headers(initHeaders);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", generateRequestId());
  applyGuestHeader(headers);

  let payload: BodyInit | undefined;
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path, params), {
    ...rest,
    credentials: "include",
    headers,
    body: payload,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const raw: unknown = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  if (!response.ok) {
    if (await recoverFromUnauthorized(path, response.status, skipRefresh)) {
      return apiRequestPage<T>(path, { ...options, skipRefresh: true });
    }
    throw normalizeError(response.status, raw);
  }

  if (raw && typeof raw === "object" && "data" in raw) {
    const envelope = raw as { data: T[]; meta?: Partial<PaginationMeta> };
    const items = Array.isArray(envelope.data) ? envelope.data : [];
    return {
      data: items,
      meta: {
        page: Number(envelope.meta?.page ?? 1),
        page_size: Number(envelope.meta?.page_size ?? (items.length || 20)),
        total: Number(envelope.meta?.total ?? items.length),
      },
    };
  }

  const fallback = Array.isArray(raw) ? (raw as T[]) : [];
  return {
    data: fallback,
    meta: { page: 1, page_size: fallback.length || 20, total: fallback.length },
  };
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<ApiRequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  getPage: <T>(path: string, options?: Omit<ApiRequestOptions, "method" | "body">) =>
    apiRequestPage<T>(path, { ...options, method: "GET" }),
  post: <T>(
    path: string,
    body?: unknown,
    options?: Omit<ApiRequestOptions, "method" | "body">,
  ) => apiRequest<T>(path, { ...options, method: "POST", body }),
  put: <T>(
    path: string,
    body?: unknown,
    options?: Omit<ApiRequestOptions, "method" | "body">,
  ) => apiRequest<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(
    path: string,
    body?: unknown,
    options?: Omit<ApiRequestOptions, "method" | "body">,
  ) => apiRequest<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<ApiRequestOptions, "method" | "body">) =>
    apiRequest<T>(path, { ...options, method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    apiRequest<T>(path, { method: "POST", body: formData }),
};
