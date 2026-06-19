import React, { useEffect, useRef, useState } from 'react';
import { t } from '../../i18n';
import { verifyPassword, fetchAuthConfig } from '../../api/auth';
import { initUser } from '../../api/user';
import { useUserStore } from '../../store/useUserStore';
import heroImg from '../../assets/hero.png';

type Step = 'mode' | 'username';

export function LandingPage(): React.ReactElement {
  const { username: storedUsername, setUsername, setIsDemo } = useUserStore();

  // If username already exists (returning user switching modes), skip to mode selection
  // and pre-fill the username field.
  const [step, setStep] = useState<Step>('mode');
  const [pendingDemo, setPendingDemo] = useState<boolean | null>(null);
  const [passwordRequired, setPasswordRequired] = useState(true);

  // Mode step state
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  // Username step state — pre-fill with stored username if returning user
  const [username, setUsernameValue] = useState(storedUsername ?? '');
  const [usernameError, setUsernameError] = useState('');
  const [usernameLoading, setUsernameLoading] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchAuthConfig()
      .then((cfg) => setPasswordRequired(cfg.password_required))
      .catch(() => setPasswordRequired(false));
  }, []);

  useEffect(() => {
    if (step === 'mode') passwordRef.current?.focus();
    if (step === 'username') usernameRef.current?.focus();
  }, [step]);

  const handlePasswordSubmit = async () => {
    setPasswordError('');
    setPasswordLoading(true);
    try {
      await verifyPassword(password);
      setPendingDemo(false);
      // Returning user with stored username: skip straight to app
      if (storedUsername) {
        setIsDemo(false);
      } else {
        setStep('username');
      }
    } catch {
      setPasswordError(t('wrong_password'));
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleDemoClick = () => {
    setPendingDemo(true);
    // Returning user with stored username: skip straight to app
    if (storedUsername) {
      setIsDemo(true);
    } else {
      setStep('username');
    }
  };

  const handleUsernameSubmit = async () => {
    const trimmed = username.trim();
    if (!trimmed) {
      setUsernameError(t('err_empty'));
      return;
    }
    if (trimmed.length > 64) {
      setUsernameError(t('err_too_long'));
      return;
    }
    setUsernameError('');
    setUsernameLoading(true);
    try {
      await initUser(trimmed);
    } catch {
      // proceed anyway
    }
    setIsDemo(pendingDemo ?? true);
    setUsername(trimmed);
    setUsernameLoading(false);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: '#0f172a',
        display: 'flex',
        fontFamily: "'Inter', system-ui, sans-serif",
        overflow: 'hidden',
      }}
    >
      {/* Left panel — hero */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          display: 'none',
          minWidth: 0,
        }}
        className="landing-hero"
      >
        <img
          src={heroImg}
          alt=""
          style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.5 }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(to right, transparent, #0f172a)',
          }}
        />
      </div>

      {/* Right panel — form */}
      <div
        style={{
          width: '100%',
          maxWidth: 480,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '40px 32px',
          gap: 0,
        }}
      >
        {/* Logo / title */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 18,
                flexShrink: 0,
              }}
            >
              🗺
            </div>
            <span style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.3px' }}>
              SEMS Digital Twin Map
            </span>
          </div>
          <p style={{ fontSize: 13, color: '#94a3b8', marginLeft: 46 }}>
            {t('landing_subtitle')}
          </p>
        </div>

        {step === 'mode' && (
          <ModeStep
            passwordRef={passwordRef}
            password={password}
            setPassword={setPassword}
            passwordError={passwordError}
            setPasswordError={setPasswordError}
            passwordLoading={passwordLoading}
            passwordRequired={passwordRequired}
            onPasswordSubmit={handlePasswordSubmit}
            onDemoClick={handleDemoClick}
          />
        )}

        {step === 'username' && (
          <UsernameStep
            usernameRef={usernameRef}
            username={username}
            setUsername={setUsernameValue}
            usernameError={usernameError}
            setUsernameError={setUsernameError}
            usernameLoading={usernameLoading}
            isDemo={pendingDemo ?? true}
            onSubmit={handleUsernameSubmit}
            onBack={() => setStep('mode')}
          />
        )}
      </div>

      <style>{`
        @media (min-width: 900px) {
          .landing-hero { display: block !important; }
        }
      `}</style>
    </div>
  );
}

function ModeStep({
  passwordRef,
  password,
  setPassword,
  passwordError,
  setPasswordError,
  passwordLoading,
  passwordRequired,
  onPasswordSubmit,
  onDemoClick,
}: {
  passwordRef: React.RefObject<HTMLInputElement | null>;
  password: string;
  setPassword: (v: string) => void;
  passwordError: string;
  setPasswordError: (v: string) => void;
  passwordLoading: boolean;
  passwordRequired: boolean;
  onPasswordSubmit: () => void;
  onDemoClick: () => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Full access card */}
      <div
        style={{
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 12,
          padding: '20px 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 16 }}>🔑</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>{t('full_access')}</span>
        </div>
        <p style={{ fontSize: 12, color: '#64748b', marginBottom: 14 }}>{t('full_access_desc')}</p>

        {passwordRequired ? (
          <>
            <input
              ref={passwordRef}
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(''); }}
              onKeyDown={(e) => { if (e.key === 'Enter') onPasswordSubmit(); }}
              placeholder={t('password_ph')}
              style={{
                width: '100%',
                padding: '9px 12px',
                fontSize: 14,
                border: passwordError ? '1px solid #ef4444' : '1px solid #334155',
                borderRadius: 8,
                outline: 'none',
                color: '#f1f5f9',
                background: '#0f172a',
                marginBottom: passwordError ? 6 : 10,
                boxSizing: 'border-box',
              }}
            />
            {passwordError && (
              <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 10 }}>{passwordError}</p>
            )}
            <button
              onClick={onPasswordSubmit}
              disabled={passwordLoading}
              style={primaryBtn(passwordLoading)}
            >
              {passwordLoading ? '…' : t('sign_in')}
            </button>
          </>
        ) : (
          <button onClick={onPasswordSubmit} disabled={passwordLoading} style={primaryBtn(passwordLoading)}>
            {passwordLoading ? '…' : t('sign_in')}
          </button>
        )}
      </div>

      {/* Divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, height: 1, background: '#1e293b' }} />
        <span style={{ fontSize: 12, color: '#475569' }}>{t('or')}</span>
        <div style={{ flex: 1, height: 1, background: '#1e293b' }} />
      </div>

      {/* Demo card */}
      <div
        style={{
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: 12,
          padding: '20px 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 16 }}>🧭</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>{t('demo_access')}</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#f97316',
              background: 'rgba(249,115,22,0.15)',
              padding: '2px 6px',
              borderRadius: 4,
              marginLeft: 4,
            }}
          >
            {t('demo_badge')}
          </span>
        </div>
        <p style={{ fontSize: 12, color: '#64748b', marginBottom: 14 }}>{t('demo_access_desc')}</p>
        <button onClick={onDemoClick} style={secondaryBtn()}>
          {t('try_demo')}
        </button>
      </div>
    </div>
  );
}

function UsernameStep({
  usernameRef,
  username,
  setUsername,
  usernameError,
  setUsernameError,
  usernameLoading,
  isDemo,
  onSubmit,
  onBack,
}: {
  usernameRef: React.RefObject<HTMLInputElement | null>;
  username: string;
  setUsername: (v: string) => void;
  usernameError: string;
  setUsernameError: (v: string) => void;
  usernameLoading: boolean;
  isDemo: boolean;
  onSubmit: () => void;
  onBack: () => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {/* Back link */}
      <button
        onClick={onBack}
        style={{
          background: 'none',
          border: 'none',
          color: '#64748b',
          fontSize: 13,
          cursor: 'pointer',
          padding: '0 0 20px 0',
          textAlign: 'left',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        ← {t('back')}
      </button>

      <div
        style={{
          background: '#1e293b',
          border: `1px solid ${isDemo ? '#7c3aed' : '#334155'}`,
          borderRadius: 12,
          padding: '24px 20px',
        }}
      >
        {/* Mode indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: isDemo ? '#a78bfa' : '#60a5fa',
              background: isDemo ? 'rgba(124,58,237,0.15)' : 'rgba(59,130,246,0.15)',
              padding: '3px 8px',
              borderRadius: 4,
            }}
          >
            {isDemo ? `🧭 ${t('demo_access')}` : `🔑 ${t('full_access')}`}
          </span>
        </div>

        <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16, lineHeight: 1.5 }}>
          {t('account_prompt')}
        </p>

        <input
          ref={usernameRef}
          type="text"
          value={username}
          onChange={(e) => { setUsername(e.target.value); if (usernameError) setUsernameError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter') onSubmit(); }}
          placeholder={t('account_ph')}
          maxLength={64}
          style={{
            width: '100%',
            padding: '9px 12px',
            fontSize: 14,
            border: usernameError ? '1px solid #ef4444' : '1px solid #334155',
            borderRadius: 8,
            outline: 'none',
            color: '#f1f5f9',
            background: '#0f172a',
            marginBottom: usernameError ? 6 : 12,
            boxSizing: 'border-box',
          }}
        />
        {usernameError && (
          <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 10 }}>{usernameError}</p>
        )}
        <button onClick={onSubmit} disabled={usernameLoading} style={primaryBtn(usernameLoading)}>
          {usernameLoading ? '…' : t('continue')}
        </button>
      </div>
    </div>
  );
}

function primaryBtn(disabled: boolean): React.CSSProperties {
  return {
    width: '100%',
    padding: '10px 0',
    background: disabled ? '#1d4ed8' : '#3b82f6',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.7 : 1,
  };
}

function secondaryBtn(): React.CSSProperties {
  return {
    width: '100%',
    padding: '10px 0',
    background: 'transparent',
    color: '#cbd5e1',
    border: '1px solid #475569',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
  };
}
