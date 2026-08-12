import React, { useEffect, useRef, useState } from 'react';
import { t } from '../../i18n';
import { login, type MeResponse } from '../../api/auth';
import { ApiError } from '../../api/client';

/**
 * The login screen. Accounts are provisioned by the admin (backend
 * scripts/create_user.py or the in-app admin panel) — there is no signup. On
 * success the backend sets the httpOnly session cookie and we hand the resolved
 * identity up to App.
 */
export function LoginPage({
  onLoggedIn,
  sessionLost = false,
}: {
  onLoggedIn: (me: MeResponse) => void;
  /** The previous session went away mid-use (a 401 on an authenticated call).
   *  Shown as a notice so this never looks like "the login button did nothing". */
  sessionLost?: boolean;
}): React.ReactElement {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const userRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    userRef.current?.focus();
  }, []);

  const submit = async () => {
    if (!username.trim() || !password) {
      setError(t('login_fill_both'));
      return;
    }
    setError('');
    setLoading(true);
    try {
      const me = await login(username.trim(), password);
      onLoggedIn(me);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? t('login_bad_credentials') : t('login_failed'));
      setLoading(false);
    }
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submit();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: '#0f172a',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: "'Inter', system-ui, sans-serif",
        padding: 24,
      }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        {/* Logo / title */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div
              style={{
                width: 36, height: 36, borderRadius: 8,
                background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, flexShrink: 0,
              }}
            >
              🗺
            </div>
            <span style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.3px' }}>
              RM Social Media Map
            </span>
          </div>
          <p style={{ fontSize: 13, color: '#94a3b8', marginLeft: 46 }}>{t('login_subtitle')}</p>
        </div>

        <div
          style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 12,
            padding: '24px 20px',
          }}
        >
          <label style={labelStyle}>{t('login_username')}</label>
          <input
            ref={userRef}
            type="text"
            value={username}
            autoComplete="username"
            onChange={(e) => { setUsername(e.target.value); if (error) setError(''); }}
            onKeyDown={onKey}
            style={inputStyle(false)}
          />

          <label style={{ ...labelStyle, marginTop: 14 }}>{t('login_password')}</label>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(e) => { setPassword(e.target.value); if (error) setError(''); }}
            onKeyDown={onKey}
            style={inputStyle(!!error)}
          />

          {error
            ? <p style={{ fontSize: 12, color: '#ef4444', margin: '8px 0 0' }}>{error}</p>
            : sessionLost && (
                // Amber, not red: nothing was typed wrong — the session just did
                // not survive. Yields to a real error as soon as there is one.
                <p style={{ fontSize: 12, color: '#f59e0b', margin: '8px 0 0' }}>
                  {t('login_session_lost')}
                </p>
              )}

          <button
            onClick={submit}
            disabled={loading}
            style={{
              width: '100%',
              marginTop: 18,
              padding: '10px 0',
              background: loading ? '#1d4ed8' : '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? '…' : t('login_sign_in')}
          </button>
        </div>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 500,
  color: '#94a3b8',
  marginBottom: 6,
};

function inputStyle(hasError: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '9px 12px',
    fontSize: 14,
    border: `1px solid ${hasError ? '#ef4444' : '#334155'}`,
    borderRadius: 8,
    outline: 'none',
    color: '#f1f5f9',
    background: '#0f172a',
    boxSizing: 'border-box',
  };
}
