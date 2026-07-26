/**
 * HTTP client.
 *
 * One place that knows the base URL, attaches the access token, unwraps the
 * error envelope, and transparently refreshes an expired session. Components
 * never call `fetch` directly, so none of them has to think about any of it.
 */

import type { ApiErrorBody } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PREFIX = "/api/v1";

/** Thrown for every non-2xx response, carrying the backend's stable error code. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fields?: { field: string; reason: string }[],
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the failure is the user's input rather than a system fault. */
  get isValidation(): boolean {
    return this.status === 422;
  }
}

/**
 * The access token lives in memory only.
 *
 * Not localStorage: anything readable by JavaScript is readable by an XSS
 * payload. Losing it on refresh is fine, because the refresh token is in an
 * httpOnly cookie and `bootstrapSession` trades it for a new one on load.
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

type RefreshListener = (token: string | null) => void;
const refreshListeners = new Set<RefreshListener>();

export function onTokenChange(listener: RefreshListener): () => void {
  refreshListeners.add(listener);
  return () => refreshListeners.delete(listener);
}

function announce(token: string | null): void {
  accessToken = token;
  refreshListeners.forEach((listener) => listener(token));
}

/**
 * In-flight refresh, shared by every caller.
 *
 * Without this, a page that fires five queries at once on a stale token would
 * start five refreshes; the first rotates the token and the other four then
 * present an already-rotated one — which the backend treats as theft and
 * responds to by revoking every session. Deduplicating is not an optimisation
 * here, it is what stops the app logging itself out.
 */
let refreshInFlight: Promise<string | null> | null = null;

async function refreshSession(): Promise<string | null> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API_URL}${PREFIX}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        announce(null);
        return null;
      }
      const body = (await response.json()) as { access_token: string };
      announce(body.access_token);
      return body.access_token;
    } catch {
      announce(null);
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Set for FormData uploads, where the browser must choose the boundary. */
  raw?: BodyInit;
  signal?: AbortSignal;
  /** Internal: prevents a refresh loop when the refresh itself 401s. */
  retrying?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, raw, signal, retrying = false } = options;

  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_URL}${PREFIX}${path}`, {
    method,
    headers,
    credentials: "include",
    body: raw ?? (body !== undefined ? JSON.stringify(body) : undefined),
    signal,
  });

  // A 401 on a normal call usually means the short-lived access token expired.
  // Refresh once and replay; a second failure is a real sign-out.
  if (response.status === 401 && !retrying && !path.startsWith("/auth/")) {
    const token = await refreshSession();
    if (token) return request<T>(path, { ...options, retrying: true });
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const envelope = payload as ApiErrorBody | null;
    throw new ApiError(
      response.status,
      envelope?.error?.code ?? "unknown",
      envelope?.error?.message ?? "Something went wrong.",
      envelope?.error?.details?.fields,
    );
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", raw: form }),
  refresh: refreshSession,
};

export { API_URL };
