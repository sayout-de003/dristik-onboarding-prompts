import React, { FormEvent, useEffect, useState } from 'react';
import { AppView } from '../types';
import { fetchAuthProviders, forgotPassword, login, resetPassword, signup, startSSOAuth } from '../services/auth';

const fieldClass = 'field';

const GoogleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
  </svg>
);

const GitHubIcon = () => (
  <svg className="w-4 h-4 shrink-0 fill-current" viewBox="0 0 24 24">
    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
  </svg>
);

function OAuthSSOButtons({ onAuthed }: { onAuthed: () => void }) {
  const [ssoBusy, setSsoBusy] = useState<string | null>(null);
  const [ssoNotice, setSsoNotice] = useState<string | null>(null);
  const [providers, setProviders] = useState<Record<string, { configured: boolean; client_id_env: string }> | null>(null);

  useEffect(() => {
    fetchAuthProviders()
      .then((res) => {
        if (res?.providers) setProviders(res.providers);
      })
      .catch(() => {});
  }, []);

  const handleSSO = (provider: 'google' | 'github') => {
    setSsoNotice(null);
    const provInfo = providers?.[provider];
    if (provInfo && !provInfo.configured) {
      setSsoNotice(`${provider === 'google' ? 'Google' : 'GitHub'} sign-in is not configured for this workspace.`);
      return;
    }

    setSsoBusy(provider);
    // Same-tab redirect. Google's consent page drops window.opener, so a popup
    // comes back as a second tab and the original page never signs in.
    startSSOAuth(provider, () => {
      setSsoBusy(null);
      onAuthed();
    }, 'redirect');
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <button
          type="button"
          onClick={() => handleSSO('google')}
          disabled={ssoBusy !== null}
          className="w-full py-2.5 px-3 bg-paper-50 hover:bg-paper-100 text-ink font-medium rounded border border-line text-xs sm:text-sm transition flex items-center justify-center gap-2 shadow-xs cursor-pointer disabled:opacity-50"
        >
          <GoogleIcon />
          <span>{ssoBusy === 'google' ? 'Connecting…' : 'Continue with Google'}</span>
        </button>

        <button
          type="button"
          onClick={() => handleSSO('github')}
          disabled={ssoBusy !== null}
          className="w-full py-2.5 px-3 bg-ink text-paper-50 hover:bg-ink-800 font-medium rounded text-xs sm:text-sm transition flex items-center justify-center gap-2 shadow-xs cursor-pointer disabled:opacity-50"
        >
          <GitHubIcon />
          <span>{ssoBusy === 'github' ? 'Connecting…' : 'Continue with GitHub'}</span>
        </button>
      </div>

      {ssoNotice && (
        <div className="p-3 text-xs bg-warn/10 border border-warn/30 text-warn dark:text-warn rounded leading-relaxed">
          {ssoNotice}
        </div>
      )}

      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-line" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-paper-50 px-2.5 text-ink-400 font-mono tracking-[0.04em]">or continue with email</span>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  type = 'text',
  value,
  onChange,
  autoComplete,
  required = true,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="label block mb-2">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className={fieldClass}
      />
    </label>
  );
}

function AuthShell({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="max-w-md mx-auto space-y-8 pt-4">
      <div data-page-header className="space-y-2">
        <p className="label">{kicker}</p>
        <h1 className="font-sans text-4xl leading-[1.12] text-ink tracking-tight">{title}</h1>
      </div>
      <div className="card p-6 sm:p-7 space-y-6">{children}</div>
    </div>
  );
}

export function LoginScreen({
  onAuthed,
  onView,
}: {
  onAuthed: () => void;
  onView: (view: AppView) => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      onAuthed();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell kicker="Account" title="Sign in">
      <OAuthSSOButtons onAuthed={onAuthed} />
      <form className="space-y-6" onSubmit={submit}>
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        {error && <p className="text-sm text-bad" role="alert">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in with password'}
        </button>
      </form>
      <p className="text-sm text-ink-500 space-x-3">
        <button type="button" onClick={() => onView('signup')} className="text-ink hover:underline">
          Create a workspace
        </button>
        <button type="button" onClick={() => onView('forgot')} className="hover:underline">
          Forgot password
        </button>
      </p>
    </AuthShell>
  );
}

export function SignupScreen({
  onAuthed,
  onView,
}: {
  onAuthed: () => void;
  onView: (view: AppView) => void;
}) {
  const [fullName, setFullName] = useState('');
  const [organization, setOrganization] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signup({
        full_name: fullName,
        organization_name: organization,
        email,
        password,
      });
      onAuthed();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the account.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell kicker="Organizations" title="Create your workspace">
      <p className="text-ink-500 leading-relaxed">
        You become the organization owner. Admins and staff can be added after you sign in.
      </p>
      <OAuthSSOButtons onAuthed={onAuthed} />
      <form className="space-y-6" onSubmit={submit}>
        <Field label="Your name" value={fullName} onChange={setFullName} autoComplete="name" />
        <Field label="Organization" value={organization} onChange={setOrganization} autoComplete="organization" />
        <Field label="Work email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
        <p className="text-xs text-ink-400">At least 8 characters, with upper and lower case and a number.</p>
        {error && <p className="text-sm text-bad" role="alert">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p className="text-sm text-ink-500">
        Already have an account?{' '}
        <button type="button" onClick={() => onView('login')} className="text-ink hover:underline">
          Sign in
        </button>
      </p>
    </AuthShell>
  );
}

export function ForgotScreen({ onView }: { onView: (view: AppView) => void }) {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [resetPath, setResetPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await forgotPassword(email);
      setMessage(res.message);
      setResetPath(res.reset_path || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start a reset.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell kicker="Password" title="Reset your password">
      <form className="space-y-6" onSubmit={submit}>
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        {error && <p className="text-sm text-bad" role="alert">{error}</p>}
        {message && <p className="text-sm text-ink-700">{message}</p>}
        {import.meta.env.DEV && resetPath && (
          <p className="text-sm text-ink-500">
            Development reset link:{' '}
            <button type="button" className="text-ink underline" onClick={() => { window.location.hash = resetPath.replace(/^#/, ''); }}>
              open reset form
            </button>
          </p>
        )}
        <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
          {busy ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
      <button type="button" onClick={() => onView('login')} className="text-sm text-ink-500 hover:text-ink">
        Back to sign in
      </button>
    </AuthShell>
  );
}

export function ResetScreen({
  token,
  onView,
}: {
  token?: string;
  onView: (view: AppView) => void;
}) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError('This reset link is missing a token.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the password.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell kicker="Password" title="Set a new password">
      {done ? (
        <div className="space-y-4">
          <p className="text-ink-700">Password updated. Sign in with the new password.</p>
          <button type="button" onClick={() => onView('login')} className="btn-primary px-5 py-2.5 text-sm">
            Sign in
          </button>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={submit}>
          <Field label="New password" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
          {error && <p className="text-sm text-bad" role="alert">{error}</p>}
          <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
            {busy ? 'Saving…' : 'Update password'}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
