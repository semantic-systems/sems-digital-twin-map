import { apiFetch } from './client';
import type { UserStateResponse } from '../types';

export async function initUser(username: string): Promise<void> {
  await apiFetch<void>('/user/init', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}

export async function fetchUserState(username: string): Promise<UserStateResponse> {
  return apiFetch<UserStateResponse>(`/user/${encodeURIComponent(username)}/state`);
}
