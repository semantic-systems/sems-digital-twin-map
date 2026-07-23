import React, { useEffect, useState } from 'react';
import { t } from '../../i18n';
import { listUsers, createUser, updateUser, deleteUser, type AdminUser } from '../../api/admin';
import { ApiError } from '../../api/client';

/**
 * Admin-only user management modal: create accounts, toggle the admin role,
 * activate/deactivate, reset a password, and delete. Every action hits an
 * admin-gated endpoint (403 for non-admins). `self` is the current admin's
 * username — the backend forbids self-demote/deactivate/delete, and we also hide
 * those controls for the own row.
 */
export function UserManagement({ self, onClose }: { self: string; onClose: () => void }): React.ReactElement {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create form
  const [newName, setNewName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newAdmin, setNewAdmin] = useState(false);
  const [creating, setCreating] = useState(false);

  const refresh = async () => {
    try {
      setUsers(await listUsers());
      setError('');
    } catch {
      setError(t('users_load_failed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const wrap = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError && e.status === 400 ? t('users_action_forbidden') : t('users_action_failed'));
    }
  };

  const handleCreate = async () => {
    if (!newName.trim() || newPassword.length < 8) {
      setError(t('users_create_invalid'));
      return;
    }
    setCreating(true);
    try {
      await createUser(newName.trim(), newPassword, newAdmin);
      setNewName(''); setNewPassword(''); setNewAdmin(false);
      setError('');
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError && e.status === 409 ? t('users_exists') : t('users_action_failed'));
    } finally {
      setCreating(false);
    }
  };

  const resetPassword = (u: AdminUser) => {
    const pw = window.prompt(t('users_new_password_for', { name: u.username }));
    if (pw == null) return;
    if (pw.length < 8) { setError(t('users_create_invalid')); return; }
    void wrap(() => updateUser(u.username, { password: pw }));
  };

  const confirmDelete = (u: AdminUser) => {
    if (window.confirm(t('users_delete_confirm', { name: u.username }))) {
      void wrap(() => deleteUser(u.username));
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 10000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#12151f', border: '1px solid #252836', borderRadius: 12,
          width: '100%', maxWidth: 560, maxHeight: '80vh', display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #252836' }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#f0f2f7' }}>{t('users_title')}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#9ca3af', fontSize: 18, cursor: 'pointer', lineHeight: 1 }}>✕</button>
        </div>

        <div style={{ padding: '14px 18px', overflowY: 'auto' }}>
          {error && <p style={{ color: '#f87171', fontSize: 12, margin: '0 0 10px' }}>{error}</p>}

          {/* Create form */}
          <div style={{ background: '#0f1117', border: '1px solid #252836', borderRadius: 8, padding: 12, marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 8 }}>{t('users_add')}</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                value={newName} onChange={(e) => setNewName(e.target.value)}
                placeholder={t('login_username')} autoComplete="off"
                style={inputStyle(150)}
              />
              <input
                type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t('users_password_min')} autoComplete="new-password"
                style={inputStyle(170)}
              />
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#9ca3af', cursor: 'pointer' }}>
                <input type="checkbox" checked={newAdmin} onChange={(e) => setNewAdmin(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
                {t('users_admin')}
              </label>
              <button onClick={handleCreate} disabled={creating} style={primaryBtn(creating)}>{t('users_create')}</button>
            </div>
          </div>

          {/* User list */}
          {loading ? (
            <p style={{ color: '#6b7280', fontSize: 13 }}>{t('loading')}</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: '#6b7280', textAlign: 'left', fontSize: 11 }}>
                  <th style={thStyle}>{t('login_username')}</th>
                  <th style={thStyle}>{t('users_admin')}</th>
                  <th style={thStyle}>{t('users_active')}</th>
                  <th style={thStyle}></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = u.username === self;
                  return (
                    <tr key={u.username} style={{ borderTop: '1px solid #1e2230', color: '#e5e7eb' }}>
                      <td style={tdStyle}>
                        {u.username}{isSelf && <span style={{ color: '#6b7280', fontSize: 11 }}> {t('users_you')}</span>}
                      </td>
                      <td style={tdStyle}>
                        <input
                          type="checkbox" checked={u.is_admin} disabled={isSelf}
                          onChange={(e) => wrap(() => updateUser(u.username, { is_admin: e.target.checked }))}
                          style={{ accentColor: '#3b82f6', cursor: isSelf ? 'not-allowed' : 'pointer' }}
                        />
                      </td>
                      <td style={tdStyle}>
                        <input
                          type="checkbox" checked={u.active} disabled={isSelf}
                          onChange={(e) => wrap(() => updateUser(u.username, { active: e.target.checked }))}
                          style={{ accentColor: '#22c55e', cursor: isSelf ? 'not-allowed' : 'pointer' }}
                        />
                      </td>
                      <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <button onClick={() => resetPassword(u)} style={linkBtn}>{t('users_reset_pw')}</button>
                        {!isSelf && (
                          <button onClick={() => confirmDelete(u)} style={{ ...linkBtn, color: '#f87171' }}>{t('users_delete')}</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function inputStyle(width: number): React.CSSProperties {
  return {
    width, padding: '7px 10px', fontSize: 13, background: '#0f1117',
    border: '1px solid #374151', borderRadius: 6, color: '#f0f2f7', outline: 'none',
  };
}
function primaryBtn(disabled: boolean): React.CSSProperties {
  return {
    padding: '7px 14px', background: disabled ? '#1d4ed8' : '#3b82f6', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.7 : 1,
  };
}
const thStyle: React.CSSProperties = { padding: '4px 6px', fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: '7px 6px' };
const linkBtn: React.CSSProperties = {
  background: 'none', border: 'none', color: '#93c5fd', fontSize: 12,
  cursor: 'pointer', padding: '2px 6px', fontFamily: "'Inter', system-ui, sans-serif",
};
