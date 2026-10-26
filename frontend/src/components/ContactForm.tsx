import React, { FormEvent, useState } from 'react';
import { AuthUser } from '../types';
import { submitContact } from '../services/auth';

const fieldClass = 'field';

export function ContactForm({ user }: { user: AuthUser | null }) {
  const [name, setName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [phone, setPhone] = useState('');
  const [company, setCompany] = useState(user?.org_name || '');
  const [website, setWebsite] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await submitContact({
        name,
        email,
        phone,
        company,
        website,
        job_title: jobTitle,
        message,
      });
      setDone(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send the message.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-xl space-y-8 pt-2">
      <div data-page-header className="space-y-2">
        <p className="label">Contact</p>
        <h1 className="font-sans text-4xl leading-[1.12] text-ink tracking-tight">Contact the Dristik team.</h1>
        <p className="text-ink-500 leading-relaxed">
          Tell us about the site, the team, and what you want from the audit.
        </p>
      </div>

      {done ? (
        <p role="status" className="rounded-lg border border-good/30 bg-good/5 p-4 text-ink-700">{done}</p>
      ) : (
        <form className="card p-6 sm:p-7 space-y-5" onSubmit={submit}>
          <label className="block">
            <span className="label block mb-2">Name</span>
            <input className={fieldClass} value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="block">
            <span className="label block mb-2">Email</span>
            <input className={fieldClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <label className="block">
              <span className="label block mb-2">Phone</span>
              <input className={fieldClass} value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>
            <label className="block">
              <span className="label block mb-2">Job title</span>
              <input className={fieldClass} value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
            </label>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <label className="block">
              <span className="label block mb-2">Company</span>
              <input className={fieldClass} value={company} onChange={(e) => setCompany(e.target.value)} />
            </label>
            <label className="block">
              <span className="label block mb-2">Website</span>
              <input className={fieldClass} value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" />
            </label>
          </div>
          <label className="block">
            <span className="label block mb-2">Message</span>
            <textarea
              className={`${fieldClass} min-h-32 resize-y`}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
            />
          </label>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
            {busy ? 'Sending…' : 'Send message'}
          </button>
        </form>
      )}
    </div>
  );
}
