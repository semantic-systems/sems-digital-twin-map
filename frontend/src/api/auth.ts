import { apiFetch } from './client';

export interface MeResponse {
  username: string;
}

/** Log in with account credentials; the backend sets the httpOnly session cookie. */
export async function login(username: string, password: string): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<{ ok: boolean }>('/auth/logout', { method: 'POST' });
}

/** Who am I — resolves the current session on app load. Throws ApiError(401) when
 *  not logged in. */
export async function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me');
}
