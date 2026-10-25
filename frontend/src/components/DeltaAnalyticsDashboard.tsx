import React, { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowDownRight, ArrowUpRight, CalendarDays, CheckCircle2, CircleAlert, Clock3, Download, Gauge, RefreshCw, Search, ShieldCheck, Target, WifiOff } from 'lucide-react';
import { getAnalysis, listAnalyses } from '../services/api';

type AnyRecord = Record<string, any>;
type Snapshot = {
  id: string; domain: string; date: string; status: string; pages: number;
  overall: number | null; seo: number | null; geo: number | null; aeo: number | null; cro: number | null;
  findings: number; critical: number; high: number; medium: number; low: number;
  verified: number; resolved: number; source: string; raw: AnyRecord;
};
const num = (...values: unknown[]): number | null => {
  for (const value of values) if (typeof value === 'number' && Number.isFinite(value)) return value;
  return null;
};
const read = (obj: AnyRecord | null | undefined, ...paths: string[]): unknown => {
  for (const path of paths) {
    const value = path.split('.').reduce<any>((v, key) => v && typeof v === 'object' ? v[key] : undefined, obj);
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
};
const score = (report: AnyRecord, pillar: string): number | null => {
  const aliases: Record<string, string[]> = {
    overall: ['overall_score', 'overallScore', 'composite_score', 'score', 'scores.overall', 'summary.overall_score'],
    seo: ['seo_score', 'scores.seo', 'pillar_scores.seo', 'scores.technical_seo', 'summary.seo_score'],
    geo: ['geo_score', 'scores.geo', 'pillar_scores.geo', 'summary.geo_score'],
    aeo: ['aeo_score', 'scores.aeo', 'pillar_scores.aeo', 'summary.aeo_score'],
    cro: ['cro_score', 'scores.cro', 'pillar_scores.cro', 'summary.cro_score'],
  };
  return num(...aliases[pillar].map((key) => read(report, key)));
};
const toSnapshot = (raw: AnyRecord): Snapshot => {
  const report = (raw.report || raw.data?.report || raw) as AnyRecord;
  const findings = Array.isArray(report.findings) ? report.findings : [];
  const pages = read(report, 'crawl_manifest.pages', 'pages', 'crawl.pages');
  const status = String(raw.status || report.status || 'unknown').toLowerCase();
  const date = String(raw.created_at || raw.started_at || raw.updated_at || report.created_at || report.generated_at || '');
  const domain = String(raw.domain || raw.website_url || report.website_url || report.target_url || 'Unknown domain').replace(/^https?:\/\//, '').replace(/\/$/, '');
  return {
    id: String(raw.analysis_id || raw.id || report.analysis_id || report.report_id || domain + date),
    domain, date, status, pages: Array.isArray(pages) ? pages.length : num(read(report, 'pages_crawled', 'crawl_manifest.pages_crawled')) || 0,
    overall: score(report, 'overall'), seo: score(report, 'seo'), geo: score(report, 'geo'), aeo: score(report, 'aeo'), cro: score(report, 'cro'),
    findings: findings.length,
    critical: findings.filter((f: AnyRecord) => String(f.severity).toUpperCase() === 'CRITICAL').length,
    high: findings.filter((f: AnyRecord) => String(f.severity).toUpperCase() === 'HIGH').length,
    medium: findings.filter((f: AnyRecord) => String(f.severity).toUpperCase() === 'MEDIUM').length,
    low: findings.filter((f: AnyRecord) => String(f.severity).toUpperCase() === 'LOW').length,
    verified: findings.filter((f: AnyRecord) => /verified|corroborated|measured/i.test(String(f.verification_status || f.source_integrity_label || ''))).length,
    resolved: findings.filter((f: AnyRecord) => /resolved|fixed/i.test(String(f.resolution_status || f.verification_status || ''))).length,
    source: String(read(report, 'data_quality.status', 'source_status', 'provenance.status') || 'Audit report'), raw,
  };
};
const fmt = (value: number | null, suffix = '') => value === null ? '—' : `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;
const delta = (current: number | null, previous: number | null) => current === null || previous === null ? null : current - previous;
const dateLabel = (value: string) => {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? 'Date unavailable' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
};
const tone = (value: number | null) => value === null ? 'text-slate-400' : value > 0 ? 'text-emerald-400' : value < 0 ? 'text-rose-400' : 'text-slate-400';

function Delta({ value, suffix = '', inverse = false }: { value: number | null; suffix?: string; inverse?: boolean }) {
  if (value === null) return <span className="text-xs text-slate-500">No comparable baseline</span>;
  const good = inverse ? value < 0 : value > 0;
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Activity;
  return <span className={`inline-flex items-center gap-1 text-xs font-semibold ${value === 0 ? 'text-slate-400' : good ? 'text-emerald-400' : 'text-rose-400'}`}><Icon size={13}/>{value > 0 ? '+' : ''}{value.toFixed(1)}{suffix} vs prior</span>;
}
function MiniLine({ values }: { values: number[] }) {
  const usable = values.filter(Number.isFinite);
  if (usable.length < 2) return <div className="h-8 flex items-center text-[10px] text-slate-500">Insufficient history</div>;
  const min = Math.min(...usable), max = Math.max(...usable), span = max - min || 1;
  const points = usable.map((v, i) => `${(i / (usable.length - 1)) * 100},${27 - ((v - min) / span) * 23}`).join(' ');
  return <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="h-8 w-full overflow-visible" role="img" aria-label="Metric trend"><polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round"/></svg>;
}
function MetricCard({ label, value, sub, icon: Icon, trend, inverse = false }: { label: string; value: string; sub: string; icon: React.ElementType; trend?: number | null; inverse?: boolean }) {
  return <article className="relative overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br from-slate-800/90 via-slate-900/80 to-slate-950/90 p-4 shadow-lg shadow-black/10 min-w-0">
    <div className="flex items-start justify-between gap-3"><div className="text-xs font-medium text-slate-400">{label}</div><span className="rounded-lg bg-white/5 p-2 text-cyan-300"><Icon size={16}/></span></div>
    <div className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">{value}</div>
    <div className="mt-2 flex min-h-5 items-center justify-between gap-2"><span className="text-[11px] text-slate-500">{sub}</span>{trend !== undefined && <span className={tone(inverse && trend !== null ? -trend : trend)}>{trend === null ? '—' : `${trend > 0 ? '+' : ''}${trend.toFixed(1)}`}</span>}</div>
  </article>;
}
export function DeltaAnalyticsDashboard() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [windowDays, setWindowDays] = useState('30');
  const [domain, setDomain] = useState('all');
  const [query, setQuery] = useState('');
  const [includeFailed, setIncludeFailed] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<'overall'|'seo'|'geo'|'aeo'|'cro'>('overall');
  const load = async () => {
    setLoading(true); setError('');
    try {
      const items = await listAnalyses(100);
      const summaries = Array.isArray(items) ? items as AnyRecord[] : [];
      const details = await Promise.all(summaries.slice(0, 40).map(async (item) => {
        if (item.report || item.findings || item.scores) return item;
        try { return await getAnalysis(String(item.analysis_id || item.id)); } catch { return item; }
      }));
      setSnapshots(details.map((item) => toSnapshot(item as unknown as AnyRecord)).sort((a,b) => new Date(a.date).getTime() - new Date(b.date).getTime()));
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load audit history.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const domains = useMemo(() => [...new Set(snapshots.map(s => s.domain).filter(d => d !== 'Unknown domain'))].sort(), [snapshots]);
  const filtered = useMemo(() => {
    const cutoff = Date.now() - Number(windowDays) * 86400000;
    return snapshots.filter(s => {
      const ts = new Date(s.date).getTime();
      if (!includeFailed && ['failed','error','cancelled'].some(x => s.status.includes(x))) return false;
      if (!Number.isFinite(ts) || ts < cutoff) return false;
      if (domain !== 'all' && s.domain !== domain) return false;
      return s.domain.toLowerCase().includes(query.toLowerCase());
    });
  }, [snapshots, windowDays, domain, query, includeFailed]);
  const latestByDomain = useMemo(() => {
    const groups = new Map<string, Snapshot[]>();
    filtered.forEach(s => groups.set(s.domain, [...(groups.get(s.domain) || []), s]));
    return [...groups.entries()].map(([name, rows]) => ({ name, rows: rows.sort((a,b) => new Date(b.date).getTime()-new Date(a.date).getTime()) })).sort((a,b) => (b.rows[0]?.date || '').localeCompare(a.rows[0]?.date || ''));
  }, [filtered]);
  const latest = filtered[filtered.length - 1];
  const previous = latestByDomain.length ? latestByDomain[0].rows[1] : undefined;
  const currentScore = latest?.overall ?? null;
  const scoreDelta = delta(currentScore, previous?.overall ?? null);
  const chartValues = filtered.map(s => s[selectedMetric]).filter((v): v is number => v !== null);
  const scoreTrend = chartValues.length > 1 ? chartValues[chartValues.length - 1] - chartValues[0] : null;
  const exportCsv = () => {
    const rows = [['date','domain','status','pages','overall','seo','geo','aeo','cro','findings','critical','high','medium','low','verified','resolved'], ...filtered.map(s=>[s.date,s.domain,s.status,s.pages,s.overall,s.seo,s.geo,s.aeo,s.cro,s.findings,s.critical,s.high,s.medium,s.low,s.verified,s.resolved])];
    const csv = rows.map(row => row.map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8;'}));
    const a = document.createElement('a'); a.href=url; a.download='dristik-delta-analytics.csv'; a.click(); URL.revokeObjectURL(url);
  };
  const metricLabel: Record<string,string> = { overall:'Overall score', seo:'SEO score', geo:'GEO readiness', aeo:'AEO score', cro:'CRO score' };
  const chartMax = Math.max(100, ...chartValues);
  return <main className="min-h-full bg-[radial-gradient(ellipse_at_top,rgba(14,116,144,.12),transparent_38%),#070b13] text-slate-100 -m-4 md:-m-6 p-4 md:p-6 space-y-5">
    <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div><div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[.2em] text-cyan-300"><Activity size={14}/> Performance intelligence / longitudinal analytics</div><h1 className="text-2xl md:text-3xl font-semibold tracking-tight">Delta Analytics</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">Measure what changed between real audit runs. Compare score movement, risk mix, evidence coverage and site-level performance without inventing missing history.</p></div>
      <div className="flex flex-wrap gap-2"><button onClick={exportCsv} disabled={!filtered.length} className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5 disabled:opacity-40"><Download size={15}/> Export CSV</button><button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300"><RefreshCw size={15} className={loading?'animate-spin':''}/> Refresh</button></div>
    </header>
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Audit runs in window" value={String(filtered.length)} sub={`of ${snapshots.length} retrieved runs`} icon={Activity}/>
      <MetricCard label="Latest overall score" value={fmt(currentScore,'/100')} sub={latest ? latest.domain : 'No audit in selected window'} icon={Gauge} trend={scoreDelta}/>
      <MetricCard label="Findings in scope" value={fmt(filtered.reduce((n,s)=>n+s.findings,0))} sub="Counted from available report findings" icon={CircleAlert}/>
      <MetricCard label="Verified findings" value={fmt(filtered.reduce((n,s)=>n+s.verified,0))} sub="Only statuses identifiable in report payloads" icon={ShieldCheck}/>
    </section>
    <section className="flex flex-col gap-3 rounded-xl border border-white/10 bg-slate-900/50 p-3 md:flex-row md:items-center">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-300"><CalendarDays size={15}/> Compare window</div>
      <div className="flex flex-wrap gap-1">{[['7','7 days'],['14','14 days'],['30','30 days'],['90','90 days'],['365','12 months']].map(([v,label])=><button key={v} onClick={()=>setWindowDays(v)} className={`rounded-md px-3 py-2 text-xs ${windowDays===v?'bg-cyan-400 font-semibold text-slate-950':'bg-white/5 text-slate-300 hover:bg-white/10'}`}>{label}</button>)}</div>
      <div className="relative min-w-0 flex-1"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Filter domain..." className="w-full rounded-md border border-white/10 bg-slate-950 py-2 pl-9 pr-3 text-xs outline-none focus:border-cyan-400"/></div>
      <select value={domain} onChange={e=>setDomain(e.target.value)} className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-xs"><option value="all">All domains</option>{domains.map(d=><option key={d} value={d}>{d}</option>)}</select>
      <label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={includeFailed} onChange={e=>setIncludeFailed(e.target.checked)}/> Include failed</label>
    </section>
    {error && <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error} <button className="ml-2 underline" onClick={()=>void load()}>Try again</button></div>}
    {loading && <div className="rounded-xl border border-white/10 bg-slate-900/50 p-8 text-center text-sm text-slate-400"><RefreshCw className="mx-auto mb-3 animate-spin" size={20}/>Loading recent audit history and report details…</div>}
    {!loading && !error && !filtered.length && <div className="rounded-xl border border-dashed border-white/15 p-10 text-center"><WifiOff className="mx-auto mb-3 text-slate-500" size={24}/><h2 className="font-semibold">No comparable audit data</h2><p className="mt-2 text-sm text-slate-400">Run an audit or widen the date window. Scores and deltas remain blank until reports contain comparable measurements.</p></div>}
    {!loading && !!filtered.length && <>
      <section className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1.8fr)_minmax(320px,1fr)]">
        <article className="rounded-xl border border-white/10 bg-gradient-to-br from-slate-900/95 to-slate-950/90 p-4 shadow-lg shadow-black/10 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">Score movement</h2><p className="mt-1 text-xs text-slate-500">Run-level sequence; not interpolated daily history</p></div><select value={selectedMetric} onChange={e=>setSelectedMetric(e.target.value as any)} className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-xs">{Object.entries(metricLabel).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
          <div className="mt-5 flex items-end justify-between gap-4"><div><div className="text-3xl font-semibold">{fmt(chartValues[chartValues.length - 1] ?? null,'/100')}</div><div className="mt-1 text-xs text-slate-500">Latest available {metricLabel[selectedMetric].toLowerCase()}</div></div><div className={`text-sm font-semibold ${tone(scoreTrend)}`}>{scoreTrend===null?'No baseline':`${scoreTrend>0?'+':''}${scoreTrend.toFixed(1)} points across selected runs`}</div></div>
          <div className="mt-4 h-56 w-full md:h-64">{chartValues.length>1 ? <svg viewBox="0 0 720 190" preserveAspectRatio="none" className="h-full w-full" role="img" aria-label={`${metricLabel[selectedMetric]} over audit runs`}><defs><linearGradient id="deltaFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#22d3ee" stopOpacity=".28"/><stop offset="100%" stopColor="#22d3ee" stopOpacity="0"/></linearGradient></defs>{[0,25,50,75,100].map(y=><g key={y}><line x1="36" x2="710" y1={170-y*1.45} y2={170-y*1.45} stroke="rgba(148,163,184,.12)"/><text x="2" y={174-y*1.45} fill="#64748b" fontSize="10">{y}</text></g>)}{(()=>{const vals=filtered.map(s=>s[selectedMetric]); const pts=vals.map((v,i)=>v===null?null:[36+(i/Math.max(1,vals.length-1))*674,170-(v/100)*145] as [number,number]); const segments:string[]=[]; let current:string[]=[]; pts.forEach(p=>{if(p)current.push(p.join(','));else if(current.length){segments.push(current.join(' '));current=[];}});if(current.length)segments.push(current.join(' '));return <>{segments.map((p,i)=><polyline key={i} points={p} fill="none" stroke="#22d3ee" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"/>)}{pts.map((p,i)=>p&&<circle key={i} cx={p[0]} cy={p[1]} r="3.5" fill="#080d18" stroke="#67e8f9" strokeWidth="2"><title>{filtered[i].domain} · {dateLabel(filtered[i].date)} · {fmt(filtered[i][selectedMetric])}</title></circle>)}</>})()}</svg> : <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-white/10 text-xs text-slate-500">Need at least two measured runs for a trend line.</div>}</div>
          <div className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-slate-500"><span>{filtered[0]?.date ? dateLabel(filtered[0].date) : '—'}</span><span>{filtered.length} audit snapshots · missing values are gaps</span><span>{latest?.date ? dateLabel(latest.date) : '—'}</span></div>
        </article>
        <article className="rounded-xl border border-white/10 bg-gradient-to-br from-slate-900/95 to-slate-950/90 p-4 shadow-lg shadow-black/10 md:p-5"><h2 className="font-semibold">Pillar score comparison</h2><p className="mt-1 text-xs text-slate-500">Latest measured value vs previous run for the selected domain</p>
          <div className="mt-5 space-y-5">{(['overall','seo','geo','aeo','cro'] as const).map(key=>{const current=latest?.[key]??null; const prior=previous?.[key]??null;return <div key={key}><div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="text-slate-300">{metricLabel[key]}</span><span className="font-medium">{fmt(current)} <span className="text-slate-500">/100</span></span></div><div className="h-2 overflow-hidden rounded-full bg-white/5"><div className="h-full rounded-full bg-cyan-400" style={{width:`${Math.max(0,Math.min(100,current??0))}%`}}/></div><div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>Previous: {fmt(prior)}</span><Delta value={delta(current,prior)} suffix=" pts"/></div></div>})}</div>
        </article>
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <article className="rounded-xl border border-white/10 bg-gradient-to-br from-slate-900/95 to-slate-950/90 p-4 shadow-lg shadow-black/10 md:p-5"><h2 className="font-semibold">Finding risk mix</h2><p className="mt-1 text-xs text-slate-500">Severity counts from report payloads; not estimated across uncrawled URLs.</p><div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">{[{label:'Critical',n:filtered.reduce((a,s)=>a+s.critical,0),color:'bg-rose-500'},{label:'High',n:filtered.reduce((a,s)=>a+s.high,0),color:'bg-orange-400'},{label:'Medium',n:filtered.reduce((a,s)=>a+s.medium,0),color:'bg-amber-300'},{label:'Low',n:filtered.reduce((a,s)=>a+s.low,0),color:'bg-sky-400'}].map(item=><div key={item.label} className="rounded-lg bg-white/[.03] p-3"><div className="flex items-center gap-2 text-xs text-slate-400"><span className={`h-2 w-2 rounded-full ${item.color}`}/>{item.label}</div><div className="mt-2 text-2xl font-semibold">{item.n.toLocaleString()}</div></div>)}</div><div className="mt-5 h-2 overflow-hidden rounded-full bg-white/5 flex">{[{n:filtered.reduce((a,s)=>a+s.critical,0),c:'bg-rose-500'},{n:filtered.reduce((a,s)=>a+s.high,0),c:'bg-orange-400'},{n:filtered.reduce((a,s)=>a+s.medium,0),c:'bg-amber-300'},{n:filtered.reduce((a,s)=>a+s.low,0),c:'bg-sky-400'}].map((x,i)=><div key={i} className={x.c} style={{width:`${x.n/Math.max(1,filtered.reduce((a,s)=>a+s.findings,0))*100}%`}}/>)}</div></article>
        <article className="rounded-xl border border-white/10 bg-gradient-to-br from-slate-900/95 to-slate-950/90 p-4 shadow-lg shadow-black/10 md:p-5"><h2 className="font-semibold">Data quality & coverage</h2><p className="mt-1 text-xs text-slate-500">Coverage indicators only use fields found in returned reports.</p><div className="mt-4 space-y-3">{[{label:'Runs with overall score',n:filtered.filter(s=>s.overall!==null).length},{label:'Runs with SEO score',n:filtered.filter(s=>s.seo!==null).length},{label:'Runs with GEO score',n:filtered.filter(s=>s.geo!==null).length},{label:'Runs with AEO score',n:filtered.filter(s=>s.aeo!==null).length},{label:'Runs with CRO score',n:filtered.filter(s=>s.cro!==null).length},{label:'Runs with page inventory',n:filtered.filter(s=>s.pages>0).length}].map(x=><div key={x.label}><div className="mb-1 flex justify-between gap-2 text-xs"><span className="text-slate-300">{x.label}</span><span className="text-slate-400">{x.n}/{filtered.length}</span></div><div className="h-1.5 rounded-full bg-white/5"><div className="h-full rounded-full bg-indigo-400" style={{width:`${x.n/Math.max(1,filtered.length)*100}%`}}/></div></div>)}</div></article>
      </section>
      <section className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 p-4"><div><h2 className="font-semibold">Domain performance ledger</h2><p className="mt-1 text-xs text-slate-500">One row per domain, based on the newest run in the selected window.</p></div><span className="text-xs text-slate-500">{latestByDomain.length} domains</span></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-white/[.03] text-slate-400"><tr>{['Domain / latest run','Status','Pages','Overall','SEO','GEO','AEO','CRO','Findings','vs prior'].map(h=><th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead><tbody>{latestByDomain.map(group=>{const s=group.rows[0], p=group.rows[1];return <tr key={group.name} className="border-t border-white/[.06] hover:bg-white/[.025]"><td className="px-4 py-3"><div className="max-w-[220px] truncate font-medium text-slate-200" title={s.domain}>{s.domain}</div><div className="mt-1 text-[10px] text-slate-500">{dateLabel(s.date)}</div></td><td className="px-4 py-3"><span className={`rounded px-2 py-1 text-[10px] ${s.status.includes('complete')?'bg-emerald-500/10 text-emerald-300':'bg-white/5 text-slate-400'}`}>{s.status}</span></td><td className="px-4 py-3">{s.pages || '—'}</td>{(['overall','seo','geo','aeo','cro'] as const).map(k=><td key={k} className="px-4 py-3">{fmt(s[k])}</td>)}<td className="px-4 py-3">{s.findings}</td><td className="px-4 py-3"><Delta value={delta(s.overall,p?.overall??null)} suffix=" pts"/></td></tr>})}</tbody></table></div></section>
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3"><article className="rounded-xl border border-white/10 bg-slate-900/60 p-4"><div className="flex items-center gap-2 text-sm font-semibold"><Target size={16} className="text-cyan-300"/>Executive interpretation</div><p className="mt-3 text-xs leading-5 text-slate-400">{scoreTrend===null?'There is not enough measured score history to make a directional statement.':scoreTrend>0?'Measured score movement is positive across the selected runs. Confirm that the same domain, crawl scope and score rubric were used before attributing the change to remediation.':scoreTrend<0?'Measured score movement is negative across the selected runs. Inspect domain-level changes and severity distribution before assuming a regression.':'The measured score is unchanged across the selected runs.'}</p></article><article className="rounded-xl border border-white/10 bg-slate-900/60 p-4"><div className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 size={16} className="text-emerald-300"/>Outcome verification</div><p className="mt-3 text-xs leading-5 text-slate-400">{filtered.reduce((a,s)=>a+s.resolved,0)} findings have a report status identifiable as resolved/fixed. This is a report-derived count, not proof that every change shipped to production; use live verification records for that claim.</p></article><article className="rounded-xl border border-white/10 bg-slate-900/60 p-4"><div className="flex items-center gap-2 text-sm font-semibold"><Clock3 size={16} className="text-amber-300"/>Attribution guardrail</div><p className="mt-3 text-xs leading-5 text-slate-400">A before/after score difference is correlation, not causal proof. Remediation attribution requires matched snapshots, equivalent crawl coverage, a recorded change, and successful live re-verification.</p></article></section>
    </>}
    <footer className="flex flex-col gap-2 border-t border-white/10 pt-4 text-[11px] text-slate-500 sm:flex-row sm:justify-between"><span>Source: Dristik audit history and available report payloads · refreshed on demand</span><span>Missing connector/history data is shown as unavailable, never as zero performance.</span></footer>
  </main>;
}
