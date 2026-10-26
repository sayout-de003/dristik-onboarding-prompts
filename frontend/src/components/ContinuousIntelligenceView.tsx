import React, { useCallback, useEffect, useState } from 'react';
import { Activity, CalendarClock, CheckCircle2, CircleAlert, ExternalLink, Globe2, LoaderCircle, Pause, Play, Plus, RefreshCw, Search, Sparkles } from 'lucide-react';
import { PageHeader } from './ui';

type Profile = {
  profile_id: string; website_url: string; domain: string; niche: string; business_model: string;
  target_audience: string; target_markets: string[]; languages: string[]; competitors: string[];
  goals: string[]; max_pages: number; schedule_enabled: boolean; last_scheduled_month?: string | null;
};
type Run = {
  run_id: string; profile_id: string; domain: string; scheduled_month: string; trigger_type: string;
  status: string; analysis_id?: string | null; started_at: string; completed_at?: string | null;
  result?: { report_url?: string; findings_count?: number; trend_status?: string; trend_note?: string; copywriting_status?: string;
    monthly_comparison?: { status: string; findings_count_delta?: number | null; previous_month?: string };
    tracked_keyword_observations?: Array<{ keyword: string; current_position?: number | null; position_delta?: number }>;
  };
};
type Entitlement = { eligible: boolean; max_pages: number; reason?: string; source?: string };

const parseList = (value: string) => value.split(/[\n,;]/).map((part) => part.trim()).filter(Boolean);

export function ContinuousIntelligenceView() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [niche, setNiche] = useState('');
  const [businessModel, setBusinessModel] = useState('');
  const [audience, setAudience] = useState('');
  const [markets, setMarkets] = useState('');
  const [languages, setLanguages] = useState('en');
  const [competitors, setCompetitors] = useState('');
  const [goals, setGoals] = useState('');
  const [maxPages, setMaxPages] = useState(10);

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [profileRes, runsRes, entitlementRes] = await Promise.all([
        fetch('/api/v1/continuous-intelligence/profiles'),
        fetch('/api/v1/continuous-intelligence/runs?limit=50'),
        fetch('/api/v1/continuous-intelligence/entitlement'),
      ]);
      const [profileBody, runsBody, entitlementBody] = await Promise.all([
        profileRes.json(), runsRes.json(), entitlementRes.json(),
      ]);
      if (!profileRes.ok) throw new Error(profileBody.detail || 'Could not load website profiles.');
      if (!runsRes.ok) throw new Error(runsBody.detail || 'Could not load monthly runs.');
      setProfiles(profileBody.profiles || []);
      setRuns(runsBody.runs || []);
      setEntitlement(entitlementBody);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Continuous intelligence could not be loaded.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setNotice('');
    try {
      const res = await fetch('/api/v1/continuous-intelligence/profiles', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          website_url: websiteUrl, niche, business_model: businessModel, target_audience: audience,
          target_markets: parseList(markets), languages: parseList(languages), competitors: parseList(competitors),
          goals: parseList(goals), max_pages: maxPages, schedule_enabled: true,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not save the website profile.');
      setNotice('Website profile saved. Monthly scheduling is enabled.');
      setWebsiteUrl(''); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Profile save failed.'); }
    finally { setSaving(false); }
  };

  const runNow = async (profileId: string) => {
    setError(''); setNotice('');
    try {
      const res = await fetch(`/api/v1/continuous-intelligence/profiles/${profileId}/run`, { method: 'POST' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not queue the audit.');
      setNotice(`Audit queued: ${body.run_id}`); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not queue the audit.'); }
  };

  const toggleSchedule = async (profile: Profile) => {
    try {
      const res = await fetch(`/api/v1/continuous-intelligence/profiles/${profile.profile_id}/schedule`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !profile.schedule_enabled }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not update schedule.');
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : 'Schedule update failed.'); }
  };

  const runStatus = (status: string) => {
    const normalized = status.toUpperCase();
    if (normalized === 'COMPLETED') return 'text-good';
    if (normalized === 'FAILED' || normalized === 'DATA_UNAVAILABLE') return 'text-bad';
    return 'text-ink-500';
  };

  return (
    <div className="space-y-7">
      <PageHeader kicker="Continuous website intelligence" title="Track website changes over time."
        description="Save your website context and schedule recurring audits. Compare runs only when the underlying evidence is comparable; missing analytics, keyword trends, or AI-engine measurements remain clearly marked as unavailable." />
      {error && <div role="alert" className="rounded-lg border border-bad/30 bg-bad/5 p-3 text-sm text-bad">{error}</div>}
      {notice && <div role="status" className="rounded-lg border border-good/30 bg-good/5 p-3 text-sm text-good">{notice}</div>}
      {entitlement && !entitlement.eligible && (
        <div className="rounded-xl border border-line bg-paper-50 p-5 flex gap-3">
          <CircleAlert className="h-5 w-5 text-warn shrink-0" />
          <div><h3 className="font-semibold text-ink">Continuous audits require an eligible plan</h3>
            <p className="text-sm text-ink-500 mt-1">{entitlement.reason}</p></div>
        </div>
      )}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)] gap-6">
        <section className="rounded-xl border border-line bg-paper p-5 space-y-4">
          <div className="flex items-center gap-2"><Globe2 className="h-5 w-5 text-ink-600" /><h2 className="text-lg font-semibold text-ink">Website profile and audit settings</h2></div>
          <p className="text-sm text-ink-500">Describe who the business serves and where it operates. Keep the profile current so future audits have useful context.</p>
          <form onSubmit={saveProfile} className="space-y-3">
            <label className="block text-xs font-medium text-ink-600">Website URL<input required type="url" placeholder="https://example.com" value={websiteUrl} onChange={e=>setWebsiteUrl(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block text-xs font-medium text-ink-600">Industry / niche<input value={niche} onChange={e=>setNiche(e.target.value)} placeholder="B2B SaaS, local dentistry…" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
              <label className="block text-xs font-medium text-ink-600">Business model<input value={businessModel} onChange={e=>setBusinessModel(e.target.value)} placeholder="Subscription, services, ecommerce…" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            </div>
            <label className="block text-xs font-medium text-ink-600">Target audience and buyer roles<textarea value={audience} onChange={e=>setAudience(e.target.value)} rows={2} placeholder="Who buys, what they need, what they compare…" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block text-xs font-medium text-ink-600">Markets / locations<input value={markets} onChange={e=>setMarkets(e.target.value)} placeholder="India, UK, Kolkata" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
              <label className="block text-xs font-medium text-ink-600">Languages<input value={languages} onChange={e=>setLanguages(e.target.value)} placeholder="en, hi" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            </div>
            <label className="block text-xs font-medium text-ink-600">Competitor domains<input value={competitors} onChange={e=>setCompetitors(e.target.value)} placeholder="rival.com, alternative.com" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            <label className="block text-xs font-medium text-ink-600">Business goals<input value={goals} onChange={e=>setGoals(e.target.value)} placeholder="Qualified leads, demo bookings, ecommerce sales" className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm" /></label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="text-xs font-medium text-ink-600">Pages per monthly audit
                <select value={maxPages} onChange={e=>setMaxPages(Number(e.target.value))} className="ml-2 rounded-lg border border-line bg-paper px-2 py-2 text-sm">
                  {[3,5,10,15,25,50,100,200,500].map(n=><option key={n} value={n}>{n} pages</option>)}
                </select>
                {entitlement?.eligible && <span className="ml-2 text-ink-400">Plan cap: {entitlement.max_pages}</span>}
              </label>
              <button disabled={saving || entitlement?.eligible === false} className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-paper disabled:opacity-50">
                {saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Save and schedule
              </button>
            </div>
          </form>
        </section>
        <section className="rounded-xl border border-line bg-paper p-5 space-y-4">
          <div className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-ink-600" /><h2 className="text-lg font-semibold text-ink">What each monthly review covers</h2></div>
          {[
            ['SEO', 'Technical health, crawlability, content, metadata, internal links and page opportunities.'],
            ['GEO', 'AI-search extractability, entity clarity and measured citations where available.'],
            ['AEO', 'Answer intent, question coverage, direct answers and relevant structured data.'],
            ['CRO', 'Page messaging, conversion friction and analytics-backed outcomes when connected.'],
            ['Trend intelligence', 'Tracked SERP positions and AI features. Broader search-demand trends are labelled unavailable until a live trend source is connected.'],
          ].map(([title, description])=><div key={title} className="border-b border-line pb-3 last:border-0"><div className="font-semibold text-sm text-ink">{title}</div><p className="text-xs text-ink-500 mt-1">{description}</p></div>)}
          <div className="rounded-lg bg-paper-50 p-3 text-xs text-ink-500">Monthly jobs run against the active organization plan. This uses the current plan entitlement; recurring payment lifecycle webhooks must be connected before it can enforce provider-confirmed subscription expiry.</div>
        </section>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-ink">Websites being monitored</h2><p className="text-sm text-ink-500">Review schedules, saved context and the latest run status.</p></div><button onClick={()=>void refresh()} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button></div>
        {loading ? <div className="rounded-xl border border-line p-8 text-center text-sm text-ink-500"><LoaderCircle className="mx-auto mb-2 h-5 w-5 animate-spin" />Loading intelligence profiles…</div> :
          profiles.length === 0 ? <div className="rounded-xl border border-dashed border-line p-8 text-center"><Search className="mx-auto h-7 w-7 text-ink-400" /><p className="mt-2 font-medium text-ink">No managed websites yet</p><p className="text-sm text-ink-500 mt-1">Create a profile above to start the monthly intelligence cycle.</p></div> :
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{profiles.map(profile=><article key={profile.profile_id} className="rounded-xl border border-line bg-paper p-4 space-y-3">
            <div className="flex items-start justify-between gap-2"><div className="min-w-0"><h3 className="font-semibold text-ink truncate">{profile.domain}</h3><a href={profile.website_url} target="_blank" rel="noreferrer" className="text-xs text-ink-500 hover:underline">{profile.website_url}</a></div><span className={profile.schedule_enabled?'rounded-full bg-good/10 px-2 py-1 text-[10px] font-semibold text-good':'rounded-full bg-paper-100 px-2 py-1 text-[10px] font-semibold text-ink-500'}>{profile.schedule_enabled?'Monthly active':'Paused'}</span></div>
            <p className="text-xs text-ink-500">{profile.niche || 'Niche not specified'} · {profile.max_pages} pages · {profile.target_markets.join(', ') || 'Markets not specified'}</p>
            <p className="text-xs text-ink-500">Audience: {profile.target_audience || 'Not specified'}</p>
            <div className="flex gap-2"><button onClick={()=>void runNow(profile.profile_id)} className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-ink px-3 py-2 text-xs font-semibold text-paper"><Play className="h-3.5 w-3.5" /> Run now</button><button onClick={()=>void toggleSchedule(profile)} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink">{profile.schedule_enabled?<Pause className="h-3.5 w-3.5" />:<CalendarClock className="h-3.5 w-3.5" />}{profile.schedule_enabled?'Pause':'Resume'}</button></div>
          </article>)}</div>}
      </section>

      <section className="space-y-3">
        <div><h2 className="text-lg font-semibold text-ink">Run history</h2><p className="text-sm text-ink-500">Monthly snapshots, tracked keyword observations and previous-run comparisons.</p></div>
        {runs.length===0 ? <div className="rounded-xl border border-dashed border-line p-6 text-sm text-ink-500">No runs yet. The scheduler checks for due websites and you can also start a run manually.</div> :
          <div className="overflow-x-auto rounded-xl border border-line"><table className="w-full text-left text-sm"><thead className="bg-paper-50 text-[11px] uppercase tracking-wide text-ink-500"><tr><th className="px-4 py-3">Website</th><th className="px-4 py-3">Cycle</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Findings</th><th className="px-4 py-3">Copywriting</th><th className="px-4 py-3">Trend data</th><th className="px-4 py-3">Comparison</th><th className="px-4 py-3">Report</th></tr></thead><tbody>{runs.map(run=><tr key={run.run_id} className="border-t border-line"><td className="px-4 py-3 font-medium text-ink">{run.domain}</td><td className="px-4 py-3 text-xs text-ink-500">{run.scheduled_month}<br/>{run.trigger_type}</td><td className={`px-4 py-3 text-xs font-semibold ${runStatus(run.status)}`}>{run.status}</td><td className="px-4 py-3 tabular-nums">{run.result?.findings_count ?? '—'}</td><td className="px-4 py-3 text-xs text-ink-500">{run.result?.copywriting_status || 'Pending'}</td><td className="px-4 py-3 text-xs text-ink-500">{run.result?.trend_status || 'Pending'}</td><td className="px-4 py-3 text-xs text-ink-500">{run.result?.monthly_comparison?.status==='COMPARABLE_SNAPSHOT' ? <>{run.result.monthly_comparison.findings_count_delta==null?'Compared':`${run.result.monthly_comparison.findings_count_delta>0?'+':''}${run.result.monthly_comparison.findings_count_delta} findings`}<br/>vs {run.result.monthly_comparison.previous_month}</> : 'Baseline pending'}</td><td className="px-4 py-3">{run.result?.report_url ? <a className="inline-flex items-center gap-1 text-xs font-semibold text-ink underline" href={run.result.report_url} target="_blank" rel="noreferrer">Open report <ExternalLink className="h-3 w-3"/></a> : run.analysis_id ? <a className="text-xs underline" href={`/api/v1/analyses/${run.analysis_id}/report`} target="_blank" rel="noreferrer">Open report</a> : '—'}</td></tr>)}</tbody></table></div>}
      </section>
      <p className="text-xs text-ink-400 flex items-center gap-2"><Activity className="h-3.5 w-3.5"/>Audit reports remain evidence-led: absent keyword-trend providers, analytics, or AI-engine measurements are marked unavailable rather than inferred.</p>
    </div>
  );
}
