import { apiFetch } from './client';

export interface AdminUser {
  username: string;
  active: boolean;
  is_admin: boolean;
  created_at: string;
}

export async function listUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>('/admin/users');
}

export async function createUser(
  username: string,
  password: string,
  is_admin: boolean,
): Promise<AdminUser> {
  return apiFetch<AdminUser>('/admin/users', {
    method: 'POST',
    body: JSON.stringify({ username, password, is_admin }),
  });
}

/** Partial update — only the provided fields change. */
export async function updateUser(
  username: string,
  changes: { password?: string; is_admin?: boolean; active?: boolean },
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${encodeURIComponent(username)}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  });
}

export async function deleteUser(username: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/admin/users/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  });
}
