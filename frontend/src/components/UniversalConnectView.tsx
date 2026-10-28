import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Bot, CheckCircle2, CircleAlert, Loader2, PlugZap, Send, ShieldCheck } from 'lucide-react';

type Provider = { id: string; provider: string; label: string; model: string; status: string; created_at: number };
type Task = { id: string; goal: string; status: string; created_at: number; execution_started?: boolean };
type AIConnection = { id: string; name: string; connection_email: string; grant_profile: string; status: string; expires_at?: number | null; last_used_at?: number | null };
type IssuedCredential = { id: string; name?: string; connection_email: string; api_key: string; grant_profile?: string; mcp_endpoint?: string; key_display_policy?: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'include', ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  return data as T;
}

const PROVIDERS = [
  { value: 'anthropic', label: 'Claude (Anthropic)', placeholder: 'claude-sonnet-4-20250514' },
  { value: 'openai', label: 'OpenAI', placeholder: 'gpt-4.1-mini' },
  { value: 'gemini', label: 'Google Gemini', placeholder: 'gemini-2.5-flash' },
  { value: 'grok', label: 'Grok (xAI)', placeholder: 'grok-3-mini' },
  { value: 'deepseek', label: 'DeepSeek', placeholder: 'deepseek-chat' },
  { value: 'openrouter', label: 'OpenRouter', placeholder: 'provider/model' },
];

export function UniversalConnectView() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [aiConnections, setAiConnections] = useState<AIConnection[]>([]);
  const [connectionName, setConnectionName] = useState('Claude — Full Audit Access');
  const [grantProfile, setGrantProfile] = useState('full_access');
  const [issuedCredential, setIssuedCredential] = useState<IssuedCredential | null>(null);
  const [provider, setProvider] = useState('anthropic');
  const [label, setLabel] = useState('My AI provider');
  const [model, setModel] = useState('claude-sonnet-4-20250514');
  const [apiKey, setApiKey] = useState('');
  const [selected, setSelected] = useState('');
  const [prompt, setPrompt] = useState('Review this website audit and summarize evidence-backed issues.');
  const [websiteUrl, setWebsiteUrl] = useState('https://example.com');
  const [result, setResult] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [p, t, c] = await Promise.all([
        request<{ providers: Provider[] }>('/api/v1/connect/providers'),
        request<{ tasks: Task[] }>('/api/v1/connect/tasks'),
        request<{ connections: AIConnection[] }>('/api/v1/connect/ai-connections'),
      ]);
      setProviders(p.providers); setTasks(t.tasks); setAiConnections(c.connections);
      if (!selected && p.providers[0]) setSelected(p.providers[0].id);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load Connect data.'); }
  }, [selected]);

  useEffect(() => { void refresh(); }, [refresh]);
  const createAIConnection = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice(''); setIssuedCredential(null);
    try {
      const created = await request<IssuedCredential>('/api/v1/connect/ai-connections', {
        method: 'POST', body: JSON.stringify({ name: connectionName, grant_profile: grantProfile, expires_in_days: 90 }),
      });
      setIssuedCredential(created);
      setNotice('Dristik connection created. Copy the identity and API key now; the key is shown only once.');
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create AI connection.'); }
    finally { setBusy(false); }
  };

  const rotateAIConnection = async (id: string) => {
    setBusy(true); setError(''); setNotice(''); setIssuedCredential(null);
    try {
      const rotated = await request<IssuedCredential>(\`/api/v1/connect/ai-connections/\${id}/rotate\`, { method: 'POST' });
      setIssuedCredential(rotated);
      setNotice('Connection key rotated. The previous key is invalid; update the AI client now.');
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not rotate connection key.'); }
    finally { setBusy(false); }
  };

  const revokeAIConnection = async (id: string) => {
    if (!window.confirm('Revoke this AI connection? Its API key will stop working immediately.')) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await request(\`/api/v1/connect/ai-connections/\${id}/revoke\`, { method: 'POST' });
      setNotice('AI connection revoked.');
      if (issuedCredential?.id === id) setIssuedCredential(null);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not revoke connection.'); }
    finally { setBusy(false); }
  };

  const copyCredential = async (value: string) => {
    try { await navigator.clipboard.writeText(value); setNotice('Copied to clipboard. Treat connection credentials as secrets.'); }
    catch { setError('Clipboard access is unavailable. Select and copy the credential manually.'); }
  };

  const chooseProvider = (value: string) => {
    setProvider(value);
    const item = PROVIDERS.find((p) => p.value === value);
    if (item) setModel(item.placeholder);
  };

  const addProvider = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const created = await request<Provider>('/api/v1/connect/providers', { method: 'POST', body: JSON.stringify({ provider, label, model, api_key: apiKey }) });
      setApiKey(''); setSelected(created.id); setNotice('Credential encrypted and saved. Run a test prompt to verify connectivity.');
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save provider.'); }
    finally { setBusy(false); }
  };

  const invoke = async (event: React.FormEvent) => {
    event.preventDefault(); if (!selected) return;
    setBusy(true); setError(''); setNotice(''); setResult('');
    try {
      const response = await request<{ text: string; provider: string; model: string; execution_status: string }>(`/api/v1/connect/providers/${selected}/invoke`, { method: 'POST', body: JSON.stringify({ prompt, max_tokens: 1200 }) });
      setResult(response.text || '(Provider returned an empty response)');
      setNotice(`Live response received from ${response.provider} · ${response.model}`);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Provider invocation failed.'); }
    finally { setBusy(false); }
  };

  const createTask = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const task = await request<Task>('/api/v1/connect/tasks', { method: 'POST', body: JSON.stringify({ goal: prompt, inputs: { source: 'connect-ui', url: websiteUrl } }) });
      setNotice(`Task ${task.id} was durably recorded. You can submit it to the canonical Dristik audit pipeline from the task actions.`);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create task.'); }
    finally { setBusy(false); }
  };

  const executeAudit = async (taskId: string) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await request<{ audit: { analysis_id: string; website_url: string } }>('/api/v1/connect/tasks/' + taskId + '/execute-audit', { method: 'POST' });
      setNotice('Dristik audit started for ' + response.audit.website_url + '. Analysis ID: ' + response.audit.analysis_id);
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not start audit.'); }
    finally { setBusy(false); }
  };
  return <main className="mx-auto max-w-6xl space-y-7 p-4 sm:p-8">
    <header className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-emerald-600"><PlugZap size={18}/> DRISTIK CONNECT</div>
      <h1 className="text-3xl font-semibold tracking-tight text-ink">Universal AI & software connections</h1>
      <p className="max-w-3xl text-sm leading-6 text-ink-500">Connect model providers, verify a live response, and create collaboration task records. Credentials are encrypted at rest; provider calls are made only to fixed official HTTPS endpoints.</p>
      <div className="flex flex-wrap gap-2 text-xs text-ink-500"><span className="rounded-full border border-line px-3 py-1"><ShieldCheck className="mr-1 inline" size={13}/>Tenant-scoped</span><span className="rounded-full border border-line px-3 py-1">Claude · OpenAI · Gemini · Grok · DeepSeek · OpenRouter</span></div>
    </header>
    {error && <div role="alert" className="flex gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800"><CircleAlert size={18}/>{error}</div>}
    {notice && <div role="status" className="flex gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 size={18}/>{notice}</div>}
    <section className="card space-y-4 p-5">
      <div className="flex items-center gap-2"><ShieldCheck size={20}/><h2 className="text-lg font-semibold text-ink">Connect an external AI to Dristik</h2></div>
      <p className="max-w-3xl text-sm leading-6 text-ink-500">Dristik issues a connection identity and a one-time API key. Give both to your compatible MCP client. The key authenticates the AI to Dristik; it is separate from any model-provider API key configured below.</p>
      <form onSubmit={createAIConnection} className="grid gap-3 md:grid-cols-[1fr_190px_auto] md:items-end">
        <label className="block space-y-1 text-sm"><span className="text-ink-600">Connection name</span><input className="input w-full" value={connectionName} onChange={(e) => setConnectionName(e.target.value)} required maxLength={120}/></label>
        <label className="block space-y-1 text-sm"><span className="text-ink-600">Permission profile</span><select className="input w-full" value={grantProfile} onChange={(e) => setGrantProfile(e.target.value)}><option value="read_only">Read only</option><option value="audit_operator">Audit operator</option><option value="workflow_admin">Workflow admin</option><option value="full_access">Full Dristik access</option></select></label>
        <button disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{busy ? <Loader2 className="animate-spin" size={16}/> : <PlugZap size={16}/>} Generate credentials</button>
      </form>
      {issuedCredential && <div className="space-y-3 rounded-xl border border-emerald-300 bg-emerald-50/40 p-4">
        <div><p className="font-semibold text-ink">Copy these credentials into your AI client now</p><p className="text-xs text-ink-500">The API key is only returned at creation or rotation and cannot be retrieved later.</p></div>
        <label className="block space-y-1 text-sm"><span className="text-ink-600">Connection email / identity</span><div className="flex gap-2"><input className="input min-w-0 flex-1" readOnly value={issuedCredential.connection_email}/><button type="button" onClick={() => void copyCredential(issuedCredential.connection_email)} className="rounded-lg border border-line px-3 text-sm">Copy</button></div></label>
        <label className="block space-y-1 text-sm"><span className="text-ink-600">Dristik API key</span><div className="flex gap-2"><input className="input min-w-0 flex-1 font-mono" type="password" readOnly value={issuedCredential.api_key}/><button type="button" onClick={() => void copyCredential(issuedCredential.api_key)} className="rounded-lg border border-line px-3 text-sm">Copy key</button></div></label>
        <label className="block space-y-1 text-sm"><span className="text-ink-600">MCP endpoint</span><div className="flex gap-2"><input className="input min-w-0 flex-1" readOnly value={issuedCredential.mcp_endpoint || '/api/v1/mcp'}/><button type="button" onClick={() => void copyCredential(issuedCredential.mcp_endpoint || '/api/v1/mcp')} className="rounded-lg border border-line px-3 text-sm">Copy</button></div></label>
        <button type="button" onClick={() => setIssuedCredential(null)} className="text-xs font-medium text-ink-500 underline">Hide credentials</button>
      </div>}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-ink">AI connections</h3>
        {aiConnections.length === 0 ? <p className="text-sm text-ink-500">No external AI credentials created yet.</p> : aiConnections.map((c) => <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3">
          <div><p className="text-sm font-medium text-ink">{c.name}</p><p className="text-xs text-ink-500">{c.connection_email} · {c.grant_profile.replace(/_/g, ' ')} · {c.status}</p><p className="text-xs text-ink-500">{c.last_used_at ? \`Last used \${new Date(c.last_used_at * 1000).toLocaleString()}\` : 'Not used yet'}</p></div>
          {c.status === 'active' && <div className="flex gap-2"><button type="button" disabled={busy} onClick={() => void rotateAIConnection(c.id)} className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50">Rotate key</button><button type="button" disabled={busy} onClick={() => void revokeAIConnection(c.id)} className="rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 disabled:opacity-50">Revoke</button></div>}
        </div>)}
      </div>
    </section>
    <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="card space-y-4 p-5">
        <div className="flex items-center gap-2"><Bot size={20}/><h2 className="text-lg font-semibold text-ink">Add a provider</h2></div>
        <form onSubmit={addProvider} className="space-y-3">
          <label className="block space-y-1 text-sm"><span className="text-ink-600">Provider</span><select className="input w-full" value={provider} onChange={(e) => chooseProvider(e.target.value)}>{PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select></label>
          <label className="block space-y-1 text-sm"><span className="text-ink-600">Connection label</span><input className="input w-full" value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={120}/></label>
          <label className="block space-y-1 text-sm"><span className="text-ink-600">Model ID</span><input className="input w-full" value={model} onChange={(e) => setModel(e.target.value)} required maxLength={160}/></label>
          <label className="block space-y-1 text-sm"><span className="text-ink-600">API key (never displayed again)</span><input className="input w-full" type="password" autoComplete="new-password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required minLength={8}/></label>
          <button disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{busy ? <Loader2 className="animate-spin" size={16}/> : <PlugZap size={16}/>} Save encrypted connection</button>
        </form>
        <div className="border-t border-line pt-4"><h3 className="mb-2 text-sm font-semibold text-ink">Saved providers</h3>{providers.length === 0 ? <p className="text-sm text-ink-500">No providers configured yet.</p> : <div className="space-y-2">{providers.map((p) => <button key={p.id} onClick={() => setSelected(p.id)} className={`flex w-full items-center justify-between rounded-lg border p-3 text-left ${selected === p.id ? 'border-emerald-500 bg-emerald-50/40' : 'border-line'}`}><span><span className="block text-sm font-medium text-ink">{p.label}</span><span className="text-xs text-ink-500">{p.provider} · {p.model}</span></span><span className="text-xs text-ink-500">{p.status.replace(/_/g, ' ')}</span></button>)}</div>}</div>
      </section>
      <section className="card space-y-4 p-5">
        <div className="flex items-center gap-2"><Send size={20}/><h2 className="text-lg font-semibold text-ink">Test a live model call</h2></div>
        <form onSubmit={invoke} className="space-y-3"><label className="block space-y-1 text-sm"><span className="text-ink-600">Website to audit</span><input className="input w-full" type="url" value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)} required placeholder="https://example.com"/></label>
          <label className="block space-y-1 text-sm"><span className="text-ink-600">Prompt</span><textarea className="input min-h-36 w-full" value={prompt} onChange={(e) => setPrompt(e.target.value)} required maxLength={30000}/></label>
          <div className="flex flex-wrap gap-2"><button disabled={busy || !selected} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{busy ? <Loader2 className="animate-spin" size={16}/> : <Activity size={16}/>} Invoke selected provider</button><button type="button" disabled={busy} onClick={() => void createTask()} className="rounded-lg border border-line px-4 py-2.5 text-sm font-medium text-ink disabled:opacity-50">Record collaboration task</button></div>
        </form>
        {result && <div className="rounded-xl border border-line bg-surface p-4"><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">Live provider response</p><pre className="whitespace-pre-wrap break-words text-sm text-ink">{result}</pre></div>}
      </section>
    </div>
    <section className="card p-5"><div className="mb-4 flex items-center gap-2"><Activity size={20}/><h2 className="text-lg font-semibold text-ink">Recent collaboration tasks</h2></div>{tasks.length ? <div className="divide-y divide-line">{tasks.map((t) => <div key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-medium text-ink">{t.goal}</p><p className="text-xs text-ink-500">{t.id} · {new Date(t.created_at * 1000).toLocaleString()}</p></div><div className="flex items-center gap-2"><span className="rounded-full border border-line px-3 py-1 text-xs text-ink-500">{t.status}</span><button type="button" disabled={busy} onClick={() => void executeAudit(t.id)} className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50">Run website audit</button></div></div>)}</div> : <p className="text-sm text-ink-500">No collaboration tasks yet.</p>}</section>
  </main>;
}
