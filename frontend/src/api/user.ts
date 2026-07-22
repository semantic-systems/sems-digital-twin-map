import { apiFetch } from './client';

export async function initUser(username: string): Promise<void> {
  await apiFetch<void>('/user/init', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}
