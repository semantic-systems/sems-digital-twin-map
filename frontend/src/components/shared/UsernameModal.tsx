import React, { useState, useRef, useEffect } from 'react';
import { t } from '../../i18n';
import { initUser } from '../../api/user';
import { useUserStore } from '../../store/useUserStore';

export function UsernameModal(): React.ReactElement {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setUsername = useUserStore((s) => s.setUsername);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError(t('err_empty'));
      return;
    }
    if (trimmed.length > 64) {
      setError(t('err_too_long'));
      return;
    }
    setError('');
    setLoading(true);
    try {
      await initUser(trimmed);
    } catch {
      // If init fails, still allow the user to proceed — server may catch up
    }
    setUsername(trimmed);
    setLoading(false);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSubmit();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '32px 28px',
          width: 380,
          maxWidth: '90vw',
          boxShadow: '0 25px 50px rgba(0,0,0,0.35)',
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <h2
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: '#111827',
              marginBottom: 8,
            }}
          >
            {t('welcome')}
          </h2>
          <p style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.5 }}>
            {t('username_prompt')}
          </p>
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) setError('');
          }}
          onKeyDown={handleKey}
          placeholder={t('username_ph')}
          maxLength={64}
          style={{
            width: '100%',
            padding: '10px 12px',
            fontSize: 14,
            border: error ? '1px solid #ef4444' : '1px solid #d1d5db',
            borderRadius: 8,
            outline: 'none',
            color: '#111827',
            background: '#f9fafb',
            marginBottom: error ? 6 : 16,
            transition: 'border-color 0.15s',
          }}
        />

        {/* Error */}
        {error && (
          <p
            style={{
              fontSize: 12,
              color: '#ef4444',
              marginBottom: 12,
            }}
          >
            {error}
          </p>
        )}

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            width: '100%',
            padding: '10px 0',
            background: loading ? '#93c5fd' : '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => {
            if (!loading)
              (e.currentTarget as HTMLButtonElement).style.background = '#2563eb';
          }}
          onMouseLeave={(e) => {
            if (!loading)
              (e.currentTarget as HTMLButtonElement).style.background = '#3b82f6';
          }}
        >
          {loading ? '…' : t('continue')}
        </button>
      </div>
    </div>
  );
}
