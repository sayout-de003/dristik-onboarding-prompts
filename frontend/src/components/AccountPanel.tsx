import React, { FormEvent, useEffect, useState } from 'react';
import { AuthUser } from '../types';
import { can, changeStaffRole, deleteAccount, fetchOrg, inviteStaff, removeStaff } from '../services/auth';

const fieldClass = 'field';

const STAFF_ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'analyst', label: 'Staff · analyst' },
  { value: 'viewer', label: 'Staff · viewer' },
  { value: 'auditor', label: 'Staff · auditor' },
];

export function AccountPanel({
  user,
  onDeleted,
}: {
  user: AuthUser;
  onDeleted: () => void;
}) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await deleteAccount(password);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the account.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-8 pt-2">
      <div data-page-header className="space-y-2">
        <p className="label">Account</p>
        <h1 className="font-sans text-4xl leading-[1.12] text-ink tracking-tight">{user.full_name}</h1>
        <p className="text-ink-500">
          {user.email} · {user.role_label} · {user.org_name}
        </p>
      </div>

      <section className="card p-6 space-y-4">
        <p className="label">Account deactivation</p>
        <p className="text-sm text-ink-500 leading-relaxed">
          This action cannot be undone from this screen. It signs you out and deactivates your account. If you are the last organization owner, the organization is deactivated as well.
        </p>
        <form className="space-y-4 max-w-md" onSubmit={submit}>
          <label className="block">
            <span className="label block mb-2">Enter your password to confirm</span>
            <input
              type="password"
              className={fieldClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="text-sm text-bad">{error}</p>}
          <button type="submit" disabled={busy} className="text-sm text-bad hover:underline disabled:opacity-50">
            {busy ? 'Deleting…' : 'Delete my account'}
          </button>
        </form>
      </section>
    </div>
  );
}

export function TeamPanel({ user }: { user: AuthUser }) {
  const [members, setMembers] = useState<AuthUser[]>([]);
  const [orgName, setOrgName] = useState(user.org_name);
  const [error, setError] = useState<string | null>(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('analyst');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const data = await fetchOrg();
    setMembers(data.members);
    setOrgName(data.org_name);
  };

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : 'Could not load the team.'));
  }, []);

  const invite = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await inviteStaff({ full_name: fullName, email, password, role });
      setFullName('');
      setEmail('');
      setPassword('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add staff.');
    } finally {
      setBusy(false);
    }
  };

  if (!can(user, 'staff:invite')) {
    return (
      <div className="pt-6">
        <p className="text-ink-500">Your current role does not allow team management. Ask an organization admin to invite or update team members.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-8 pt-2">
      <div className="space-y-2">
        <p className="label">Team</p>
        <h1 className="font-sans text-4xl leading-[1.12] text-ink tracking-tight">{orgName} team</h1>
        <p className="text-ink-500 leading-relaxed">
          Manage who can access this workspace. Assign the least-privileged role that gives each person the access they need.
        </p>
      </div>

      <ul className="card divide-y divide-line">
        {members.map((member) => (
          <li key={member.user_id} className="px-5 py-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-ink">{member.full_name}</p>
              <p className="text-sm text-ink-500">{member.email}</p>
            </div>
            <div className="text-right space-y-2">
              <p className="text-sm text-ink-500">{member.role_label}</p>
              {member.user_id !== user.user_id && member.role !== 'owner' && !member.is_system && (
                <div className="flex items-center gap-3 justify-end text-sm">
                  <select
                    value={member.role}
                    onChange={(e) => {
                      changeStaffRole(member.user_id, e.target.value)
                        .then(load)
                        .catch((err) => setError(err instanceof Error ? err.message : 'Could not change role.'));
                    }}
                    className="bg-transparent border-0 border-b border-ink-300 text-ink-700 focus:outline-none"
                  >
                    {STAFF_ROLES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="text-bad"
                    onClick={() => {
                      removeStaff(member.user_id)
                        .then(load)
                        .catch((err) => setError(err instanceof Error ? err.message : 'Could not remove staff.'));
                    }}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>

      <form className="card p-6 space-y-5 max-w-md" onSubmit={invite}>
        <p className="label">Add staff</p>
        <label className="block">
          <span className="label block mb-2">Name</span>
          <input className={fieldClass} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </label>
        <label className="block">
          <span className="label block mb-2">Email</span>
          <input className={fieldClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="block">
          <span className="label block mb-2">Temporary password</span>
          <input className={fieldClass} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <label className="block">
          <span className="label block mb-2">Role</span>
          <select className={fieldClass} value={role} onChange={(e) => setRole(e.target.value)}>
            {STAFF_ROLES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="text-sm text-bad">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary px-5 py-2.5 text-sm tracking-wide disabled:opacity-50">
          {busy ? 'Adding…' : 'Add staff member'}
        </button>
      </form>
    </div>
  );
}
