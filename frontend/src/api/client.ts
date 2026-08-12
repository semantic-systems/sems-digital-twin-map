const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(path: string, status: number) {
    super(`API ${path}: ${status}`);
    this.status = status;
  }
}

// Called whenever any request comes back 401 — the session is gone/expired, so
// the app should drop to the login screen. Registered by App on mount to avoid
// this module depending on the store.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export interface ApiOptions {
  /** Don't treat a 401 as "the session died" — for calls that legitimately answer
   *  401 as a normal result. Logging in with a wrong password is not an expired
   *  session, and letting it fire the global handler wipes the auth state (and
   *  with it the login form's error message) instead of showing it. */
  authOptional?: boolean;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  { authOptional = false }: ApiOptions = {},
): Promise<T> {
  // Content-Type only when there is a body to describe. It is not a
  // CORS-safelisted request header, so sending it on plain GETs turns any
  // request that ends up cross-origin (e.g. a redirect that changes the scheme)
  // into a preflighted one -- and a preflight is not allowed to redirect.
  const headers: HeadersInit = {
    ...(options?.body === undefined ? {} : { 'Content-Type': 'application/json' }),
    ...options?.headers,
  };
  const res = await fetch(BASE + path, {
    // Send/receive the session cookie on every request.
    credentials: 'include',
    ...options,
    headers,
  });
  if (res.status === 401) {
    if (!authOptional) onUnauthorized?.();
    throw new ApiError(path, 401);
  }
  if (!res.ok) throw new ApiError(path, res.status);
  return res.json() as Promise<T>;
}

export function buildQuery(params: Record<string, unknown>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        qs.append(key, String(item));
      }
    } else if (typeof value === 'boolean') {
      qs.append(key, value ? 'true' : 'false');
    } else {
      qs.append(key, String(value));
    }
  }
  const str = qs.toString();
  return str ? `?${str}` : '';
}
