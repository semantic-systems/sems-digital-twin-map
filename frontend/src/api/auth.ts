import { apiFetch } from './client';

export async function verifyPassword(password: string): Promise<void> {
  await apiFetch<{ ok: boolean }>('/auth/verify', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export async function fetchAuthConfig(): Promise<{ password_required: boolean }> {
  return apiFetch<{ password_required: boolean }>('/auth/config');
}
