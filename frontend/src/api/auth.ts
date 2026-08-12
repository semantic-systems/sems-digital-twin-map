import { apiFetch } from './client';

export interface MeResponse {
  username: string;
  is_admin: boolean;
}

/** Log in with account credentials; the backend sets the httpOnly session cookie.
 *  authOptional: a 401 here means "wrong credentials", not "session expired" —
 *  the login form shows it inline, so it must not trip the global handler. */
export async function login(username: string, password: string): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }, { authOptional: true });
}

export async function logout(): Promise<void> {
  await apiFetch<{ ok: boolean }>('/auth/logout', { method: 'POST' });
}

/** Who am I — resolves the current session on app load. Throws ApiError(401) when
 *  not logged in, which on a first visit is the normal answer rather than a lost
 *  session, so it does not trip the global handler either. */
export async function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me', undefined, { authOptional: true });
}
