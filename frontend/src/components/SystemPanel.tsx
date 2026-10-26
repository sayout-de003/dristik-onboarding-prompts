import React, { useCallback, useEffect, useState } from 'react';
import { AdminOrganization, ContactRecord, PlatformOverview } from '../types';
import {
  deactivateUser,
  deleteOrganization,
  fetchContacts,
  fetchSystemOrganizations,
  fetchSystemOverview,
  restoreUser,
  runDatabaseCleanup,
  runSessionExpiry,
  setOrgActive,
  setOrgPlan,
  setUserPassword,
} from '../services/auth';

const PLANS = [
  { id: 'starter', label: 'Starter · lowest cost' },
  { id: 'professional', label: 'Professional' },
  { id: 'business', label: 'Business' },
  { id: 'enterprise', label: 'Enterprise' },
];

function when(ts?: number | null): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString();
}

function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function Kpi({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="mt-1 font-sans text-3xl text-ink">{value}</dd>
      {hint && <p className="text-xs text-ink-400 mt-1">{hint}</p>}
    </div>
  );
}

export function SystemPanel() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [contacts, setContacts] = useState<ContactRecord[]>([]);
  const [openOrg, setOpenOrg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [passwordFor, setPasswordFor] = useState<string | null>(null);
  const [tempPassword, setTempPassword] = useState('');

  const load = useCallback(async () => {
    const [kpi, directory, inbox] = await Promise.all([
      fetchSystemOverview(),
      fetchSystemOrganizations(),
      fetchContacts(),
    ]);
    setOverview(kpi);
    setOrgs(directory);
    setContacts(inbox);
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : 'Could not load system console.'));
  }, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await load();
      setNotice(ok);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-10 pt-2">
      <div className="space-y-2">
        <p className="label">Admin</p>
        <h1 className="font-sans text-4xl leading-[1.12] text-ink tracking-tight">System administration</h1>
        <p className="text-ink-500 max-w-2xl leading-relaxed">
          Organizations, users, plans, audits, and database maintenance.
        </p>
      </div>

      {error && <p role="alert" className="text-sm text-bad">{error}</p>}
      {notice && <p role="status" className="text-sm text-good">{notice}</p>}

      {overview && (
        <>
          <section>
            <p className="label mb-4">Overview metrics</p>
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-6">
              <Kpi label="Customer orgs" value={overview.organizations.customer} hint={`${overview.organizations.active} active · ${overview.organizations.deleted} deleted`} />
              <Kpi label="People" value={overview.users.active} hint={`${overview.users.signed_up_7d} new in 7 days · ${overview.users.logged_in_24h} in last day`} />
              <Kpi label="Audits" value={overview.audits.total} hint={`${overview.audits.last_7d} in 7 days · ${overview.audits.last_30d} in 30 days`} />
              <Kpi label="Contact leads" value={overview.contacts.total} hint={`${overview.contacts.last_7d} in 7 days`} />
            </dl>
          </section>

          <section className="grid grid-cols-1 sm:grid-cols-2 gap-10">
            <div>
              <p className="label mb-3">Plans in use</p>
              <ul className="space-y-2 text-sm text-ink-700">
                {Object.entries(overview.plan_mix).map(([plan, count]) => (
                  <li key={plan} className="flex justify-between border-b border-line pb-2">
                    <span className="capitalize">{plan}</span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="label mb-3">User roles</p>
              <ul className="space-y-2 text-sm text-ink-700">
                {Object.entries(overview.role_mix).map(([role, count]) => (
                  <li key={role} className="flex justify-between border-b border-line pb-2">
                    <span className="capitalize">{role.replace(/_/g, ' ')}</span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="space-y-4">
            <p className="label">Database</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 text-sm text-ink-700">
              <p><span className="text-ink-500">Size </span>{bytes(overview.database.size_bytes)}</p>
              <p><span className="text-ink-500">Live sessions </span>{overview.database.live_sessions}</p>
              <p><span className="text-ink-500">Users table </span>{overview.database.tables.users}</p>
              <p><span className="text-ink-500">Orgs table </span>{overview.database.tables.organizations}</p>
            </div>
            <p className="text-xs text-ink-400 font-mono break-all">{overview.database.path}</p>
            <div className="flex flex-wrap gap-4 text-sm">
              <button
                type="button"
                disabled={busy}
                className="text-ink-700 hover:text-ink disabled:opacity-50"
                onClick={() => act(() => runSessionExpiry(), 'Expired sessions cleared.')}
              >
                Expire dead sessions
              </button>
              <button
                type="button"
                disabled={busy}
                className="text-ink-700 hover:text-ink disabled:opacity-50"
                onClick={() => act(() => runDatabaseCleanup(), 'Database cleaned and compacted.')}
              >
                Cleanup + compact DB
              </button>
            </div>
          </section>
        </>
      )}

      <section className="space-y-4">
        <p className="label">Organizations ({orgs.length})</p>
        <ul className="divide-y divide-line border-y border-line">
          {orgs.map((org) => {
            const open = openOrg === org.org_id;
            return (
              <li key={org.org_id} className="py-5">
                <button
                  type="button"
                  className="w-full text-left flex items-start justify-between gap-4"
                  onClick={() => setOpenOrg(open ? null : org.org_id)}
                >
                  <div>
                    <p className="text-ink">
                      {org.name}
                      {!org.is_active && <span className="text-bad text-sm"> · inactive</span>}
                      {org.is_system && <span className="text-ink-400 text-sm"> · Dristik system</span>}
                    </p>
                    <p className="text-sm text-ink-500 font-mono mt-0.5">{org.slug}</p>
                  </div>
                  <p className="text-sm text-ink-500 shrink-0">
                    {org.plan} · {org.member_count} people · {org.audit_count} audits
                    {org.avg_score != null ? ` · avg ${org.avg_score}` : ''}
                  </p>
                </button>

                {open && (
                  <div className="mt-6 space-y-6">
                    <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm text-ink-700">
                      <div>
                        <dt className="text-ink-500">Created</dt>
                        <dd>{when(org.created_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-ink-500">Members</dt>
                        <dd>{org.member_count} active / {org.member_total} total</dd>
                      </div>
                      <div>
                        <dt className="text-ink-500">Audits</dt>
                        <dd>{org.audit_count}{org.avg_score != null ? ` · score ${org.avg_score}` : ''}</dd>
                      </div>
                      <div>
                        <dt className="text-ink-500">Status</dt>
                        <dd>{org.is_active ? 'Active' : 'Deactivated'}</dd>
                      </div>
                    </dl>

                    {!org.is_system && (
                      <div className="flex flex-wrap items-end gap-4">
                        <label className="block">
                          <span className="label block mb-2">Plan</span>
                          <select
                            className="bg-transparent border-0 border-b border-ink-300 py-1 text-ink focus:outline-none"
                            value={org.plan}
                            disabled={busy}
                            onChange={(e) => act(() => setOrgPlan(org.org_id, e.target.value), `Plan set to ${e.target.value}.`)}
                          >
                            {PLANS.map((plan) => (
                              <option key={plan.id} value={plan.id}>
                                {plan.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          type="button"
                          disabled={busy}
                          className="text-sm text-ink-700 hover:text-ink disabled:opacity-50"
                          onClick={() => act(() => setOrgActive(org.org_id, !org.is_active), org.is_active ? 'Organization deactivated.' : 'Organization restored.')}
                        >
                          {org.is_active ? 'Deactivate org' : 'Restore org'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className="text-sm text-bad hover:underline disabled:opacity-50"
                          onClick={() => {
                            const typed = window.prompt(`Type ${org.slug} to deactivate this organization.`);
                            if (typed !== org.slug) return;
                            act(() => deleteOrganization(org.org_id, false), 'Organization deactivated.');
                          }}
                        >
                          Delete org
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className="text-sm text-bad hover:underline disabled:opacity-50"
                          onClick={() => {
                            const typed = window.prompt(`Type ${org.slug} to permanently purge this organization and its users from the database.`);
                            if (typed !== org.slug) return;
                            act(() => deleteOrganization(org.org_id, true), 'Organization purged from the database.');
                          }}
                        >
                          Purge from DB
                        </button>
                      </div>
                    )}

                    <div>
                      <p className="label mb-3">Users</p>
                      <ul className="divide-y divide-line border-y border-line">
                        {org.members.map((member) => (
                          <li key={member.user_id} className="py-4 space-y-2">
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="text-ink">
                                  {member.full_name}
                                  {!member.is_active && <span className="text-bad text-sm"> · inactive</span>}
                                </p>
                                <p className="text-sm text-ink-500">{member.email}</p>
                              </div>
                              <p className="text-sm text-ink-500">{member.role_label}</p>
                            </div>
                            <p className="text-xs text-ink-400">
                              Joined {when(member.created_at)} · Last login {when(member.last_login_at)}
                            </p>
                            {!member.is_system && (
                              <div className="flex flex-wrap gap-4 text-sm">
                                {member.is_active ? (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    className="text-ink-700 hover:text-ink disabled:opacity-50"
                                    onClick={() => act(() => deactivateUser(member.user_id), `${member.email} deactivated.`)}
                                  >
                                    Deactivate
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    className="text-ink-700 hover:text-ink disabled:opacity-50"
                                    onClick={() => act(() => restoreUser(member.user_id), `${member.email} restored.`)}
                                  >
                                    Restore
                                  </button>
                                )}
                                <button
                                  type="button"
                                  className="text-ink-700 hover:text-ink"
                                  onClick={() => {
                                    setPasswordFor(member.user_id);
                                    setTempPassword('');
                                  }}
                                >
                                  Set password
                                </button>
                              </div>
                            )}
                            {passwordFor === member.user_id && (
                              <form
                                className="flex flex-col sm:flex-row sm:items-end gap-3"
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  act(async () => {
                                    await setUserPassword(member.user_id, tempPassword);
                                    setPasswordFor(null);
                                    setTempPassword('');
                                  }, `Password updated for ${member.email}.`);
                                }}
                              >
                                <label className="flex-1 block">
                                  <span className="label block mb-2">Temporary password</span>
                                  <input
                                    type="password"
                                    value={tempPassword}
                                    onChange={(e) => setTempPassword(e.target.value)}
                                    className="w-full bg-transparent border-0 border-b border-ink-300 py-1 text-ink focus:outline-none"
                                    required
                                  />
                                </label>
                                <button type="submit" disabled={busy} className="btn-primary px-4 py-2 text-sm disabled:opacity-50">
                                  Save
                                </button>
                              </form>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="space-y-4">
        <p className="label">Contact form ({contacts.length})</p>
        {contacts.length === 0 ? (
          <p className="text-ink-400">No submissions yet.</p>
        ) : (
          <ul className="space-y-8">
            {contacts.map((item) => (
              <li key={item.contact_id} className="border-t border-line pt-4 space-y-2">
                <p className="text-ink">
                  {item.name} · {item.email}
                </p>
                <p className="text-sm text-ink-500">
                  {[item.job_title, item.company, item.phone, item.website].filter(Boolean).join(' · ')}
                </p>
                <p className="text-xs text-ink-400">{when(item.created_at)}</p>
                <p className="text-ink-700 whitespace-pre-wrap leading-relaxed">{item.message}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
