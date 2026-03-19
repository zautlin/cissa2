/**
 * CISSA Query Client
 * ------------------
 * Lightweight fetch wrapper used by pages that want graceful fallback
 * when the FastAPI backend is not running.
 *
 * Usage:
 *   const data = await apiFetch<MyType>("/api/v1/metrics/health");
 *
 * All functions throw on HTTP errors so callers can catch and fall back
 * to mock data as needed.
 */

/** Base prefix — works both in dev (Vite proxies /api → localhost:8000)
 *  and in production (same-origin serving). */
export const API_BASE = "/api/v1";

/**
 * Generic JSON fetch helper with error reporting.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = path.startsWith("http") ? path : path;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/**
 * Probe whether the backend is reachable.
 * Returns true if /api/v1/metrics/health responds with 200.
 */
export async function isBackendAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/metrics/health`, {
      signal: AbortSignal.timeout(2000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
