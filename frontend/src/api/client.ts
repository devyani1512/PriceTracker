export const API_URL: string = (
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8080"
).replace(/\/+$/, "");

export const TOKEN_KEY = "pt_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type QueryValue = string | number | boolean | undefined | null;

export interface RequestOptions {
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
}

/**
 * Transient 5xx responses are usually a cold backend, a deploy, or a hiccup.
 * Retry idempotent requests a few times with exponential backoff + jitter
 * before surfacing an error to the UI.
 */
const RETRY_ATTEMPTS = 3;
const RETRY_BASE_DELAY_MS = 400;
const RETRY_MAX_DELAY_MS = 4000;

function isRetryableMethod(method: string): boolean {
  const upper = method.toUpperCase();
  return upper === "GET" || upper === "HEAD" || upper === "OPTIONS";
}

function isRetryableStatus(status: number): boolean {
  return status === 500 || status === 502 || status === 503 || status === 504;
}

function retryDelay(attempt: number): number {
  const backoff = Math.min(
    RETRY_BASE_DELAY_MS * 2 ** attempt,
    RETRY_MAX_DELAY_MS,
  );
  return backoff + Math.random() * RETRY_BASE_DELAY_MS;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const handle = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      window.clearTimeout(handle);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(API_URL + path);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function looksLikeHtml(value: string): boolean {
  return /^\s*<(?:!doctype|html|head|body|pre|div|span|p|h[1-6]|table|center|font)\b/i.test(
    value,
  );
}

function fallbackMessage(status: number): string {
  if (status >= 500) {
    return `Server error (${status}). Please try again in a moment.`;
  }
  return `Request failed (${status})`;
}

function extractDetail(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim()) {
    // Never surface a raw HTML error page (e.g. a proxy/500 page) in the UI.
    if (looksLikeHtml(payload)) return fallbackMessage(status);
    return payload;
  }
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const detail = record.detail ?? record.message ?? record.error;
    if (typeof detail === "string" && detail.trim()) {
      return looksLikeHtml(detail) ? fallbackMessage(status) : detail;
    }
    if (detail !== undefined) return JSON.stringify(detail);
  }
  return fallbackMessage(status);
}

export async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const url = buildUrl(path, options.query);
  const body =
    options.body === undefined ? undefined : JSON.stringify(options.body);
  const maxAttempts = isRetryableMethod(method) ? RETRY_ATTEMPTS : 1;

  let response: Response | null = null;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      response = await fetch(url, {
        method,
        headers,
        body,
        signal: options.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      response = null;
    }

    if (response && !isRetryableStatus(response.status)) break;
    if (attempt === maxAttempts - 1) break;
    await delay(retryDelay(attempt), options.signal);
  }

  if (!response) {
    throw new ApiError(
      `Could not reach the API at ${API_URL}. Is the backend running?`,
      0,
    );
  }

  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("pt:unauthorized"));
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(extractDetail(payload, response.status), response.status);
  }

  return payload as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return String(error);
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
