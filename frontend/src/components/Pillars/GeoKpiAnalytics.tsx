import React, { useEffect, useState } from 'react';
import { Card } from '../ui';

type Point = {
  snapshot_id: string; timestamp: string; score: number | null; observations: number;
  attempted: number; mentions: number; citations: number; mention_rate_pct: number | null;
  citation_rate_pct: number | null; status: string;
};
type Metric = {
  status: string; observations: number; attempted: number; failed_or_empty: number;
  mentions: number; citations: number; mention_rate_pct: number | null;
  citation_rate_pct: number | null; score: number | null;
};
type Engine = Metric & { engine: string };
type Intent = Metric & { intent: string };
type Analytics = {
  domain: string; methodology_version: string; status: string; snapshot_count: number;
  current: Metric; history: Point[]; engines: Engine[]; intents: Intent[];
  formula: { name: string; description: string; citation_response_points: number;
    mention_without_citation_points: number; no_mention_or_citation_points: number;
    failed_response_treatment: string; denominator: string };
  data_quality: { successful_observations: number; failed_or_empty_attempts: number;
    scope: string; limitations: string[] };
};

const pct = (value: number | null | undefined) => value == null ? 'Not measured' : `${value.toFixed(1)}%`;
const dateLabel = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

function TrendChart({ history }: { history: Point[] }) {
  const points = history.filter(p => p.score != null);
  if (points.length < 2) return <div className="py-12 text-center text-sm text-ink-500">At least two measured snapshots are needed to show a trend line. Current measured snapshots: {points.length}.</div>;
  const width = 720, height = 220, padX = 36, padY = 24;
  const coords = points.map((p, i) => ({
    x: padX + i * (width - padX * 2) / Math.max(1, points.length - 1),
    y: height - padY - (Number(p.score) / 100) * (height - padY * 2), p,
  }));
  return <div className="w-full overflow-x-auto">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Measured live GEO visibility score over time" className="w-full min-w-[520px]">
      {[0, 25, 50, 75, 100].map(v => {
        const y = height - padY - (v / 100) * (height - padY * 2);
        return <g key={v}><line x1={padX} x2={width - padX} y1={y} y2={y} stroke="currentColor" opacity=".12" strokeDasharray="3 4" /><text x="4" y={y + 4} fontSize="10" fill="currentColor" opacity=".65">{v}</text></g>;
      })}
      <polyline fill="none" stroke="currentColor" strokeWidth="2.5" points={coords.map(c => `${c.x},${c.y}`).join(' ')} />
      {coords.map(c => <g key={c.p.snapshot_id}><circle cx={c.x} cy={c.y} r="4" fill="currentColor"><title>{dateLabel(c.p.timestamp)}: {c.p.score}/100</title></circle><text x={c.x} y={height - 4} textAnchor="middle" fontSize="10" fill="currentColor" opacity=".75">{dateLabel(c.p.timestamp)}</text></g>)}
    </svg>
  </div>;
}

function RateTrendChart({ history }: { history: Point[] }) {
  const points = history.filter(p => p.mention_rate_pct != null || p.citation_rate_pct != null);
  if (points.length < 2) return <p className="py-6 text-sm text-ink-500">Two or more measured snapshots are needed for mention/citation rate trends.</p>;
  const width = 720, height = 190, padX = 36, padY = 20;
  const coords = points.map((p, i) => ({
    x: padX + i * (width - padX * 2) / Math.max(1, points.length - 1),
    mentionY: p.mention_rate_pct == null ? null : height - padY - (p.mention_rate_pct / 100) * (height - padY * 2),
    citationY: p.citation_rate_pct == null ? null : height - padY - (p.citation_rate_pct / 100) * (height - padY * 2),
    p,
  }));
  return <div className="w-full overflow-x-auto">
    <div className="flex gap-4 text-xs text-ink-600 mb-2"><span>— Brand mention rate</span><span className="opacity-70">╌ Citation rate</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Brand mention and citation rates over time" className="w-full min-w-[520px]">
      {[0, 25, 50, 75, 100].map(v => {
        const y = height - padY - (v / 100) * (height - padY * 2);
        return <g key={v}><line x1={padX} x2={width - padX} y1={y} y2={y} stroke="currentColor" opacity=".12" strokeDasharray="3 4" /><text x="2" y={y + 4} fontSize="10" fill="currentColor" opacity=".65">{v}%</text></g>;
      })}
      <polyline fill="none" stroke="currentColor" strokeWidth="2.5" points={coords.filter(c => c.mentionY != null).map(c => `${c.x},${c.mentionY}`).join(' ')} />
      <polyline fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" opacity=".55" points={coords.filter(c => c.citationY != null).map(c => `${c.x},${c.citationY}`).join(' ')} />
      {coords.map(c => <g key={c.p.snapshot_id}><text x={c.x} y={height - 3} textAnchor="middle" fontSize="10" fill="currentColor" opacity=".75">{dateLabel(c.p.timestamp)}</text>{c.mentionY != null && <circle cx={c.x} cy={c.mentionY} r="3" fill="currentColor"><title>{dateLabel(c.p.timestamp)} mention rate: {c.p.mention_rate_pct}%</title></circle>}{c.citationY != null && <circle cx={c.x} cy={c.citationY} r="3" fill="currentColor" opacity=".55"><title>{dateLabel(c.p.timestamp)} citation rate: {c.p.citation_rate_pct}%</title></circle>}</g>)}
    </svg>
  </div>;
}

function BarRow({ label, value, detail }: { label: string; value: number | null; detail?: string }) {
  return <div className="space-y-1.5">
    <div className="flex justify-between gap-3 text-xs"><span className="font-medium text-ink">{label}</span><span className="font-mono text-ink-600">{pct(value)}{detail ? ` · ${detail}` : ''}</span></div>
    <div className="h-2.5 rounded bg-ink/10 overflow-hidden"><div className="h-full rounded bg-ink-700" style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }} /></div>
  </div>;
}

function MethodFlow() {
  const steps = [
    ['1', 'Collect live answers', 'Only configured engines that actually return responses are eligible.'],
    ['2', 'Validate observations', 'Empty/error responses are excluded and counted as failed attempts.'],
    ['3', 'Classify each answer', 'Citation = 100 points; brand mention without citation = 55; neither = 0.'],
    ['4', 'Calculate snapshot score', 'Sum points for successful responses ÷ successful response count.'],
    ['5', 'Persist and compare', 'Store timestamped snapshots; compare only measured points and show evidence counts.'],
  ];
  return <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
    {steps.map((step, i) => <div key={step[0]} className="relative rounded-lg border border-line p-4 bg-paper-50">
      <div className="flex items-center gap-2 mb-2"><span className="inline-flex w-7 h-7 items-center justify-center rounded-full bg-ink text-paper text-xs font-bold">{step[0]}</span><span className="text-sm font-semibold text-ink">{step[1]}</span></div>
      <p className="text-xs leading-relaxed text-ink-600">{step[2]}</p>
      {i < steps.length - 1 && <span aria-hidden="true" className="hidden md:block absolute -right-3 top-6 z-10 text-ink-500">→</span>}
    </div>)}
  </div>;
}

export function GeoKpiAnalytics({ domain }: { domain: string }) {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(30);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    fetch(`/api/v1/geo-analytics?domain=${encodeURIComponent(domain)}&limit=${limit}`)
      .then(async response => {
        if (!response.ok) throw new Error(`Analytics API returned HTTP ${response.status}`);
        return response.json() as Promise<Analytics>;
      })
      .then(value => { if (!cancelled) setData(value); })
      .catch(err => { if (!cancelled) setError(err?.message || 'Could not load GEO analytics.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [domain, limit]);

  if (loading) return <Card className="p-8 text-sm text-ink-600">Loading persisted GEO observations and historical snapshots…</Card>;
  if (error) return <Card className="p-6 space-y-2"><h3 className="font-semibold text-ink">GEO analytics unavailable</h3><p className="text-sm text-ink-600">{error}</p><p className="text-xs text-ink-500">No values have been fabricated. Check the backend route and stored GEO snapshots.</p></Card>;
  if (!data) return null;

  const m = data.current;
  const hasHistory = data.history.length > 0;
  return <div className="space-y-5">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div><h3 className="text-xl font-semibold text-ink">GEO KPI & historical analytics</h3><p className="text-sm text-ink-600 mt-1">Live AI-answer visibility for {data.domain}. Kept separate from on-page GEO readiness.</p></div>
      <label className="text-xs text-ink-600 flex items-center gap-2">Snapshots
        <select value={limit} onChange={e => setLimit(Number(e.target.value))} className="rounded border border-line bg-paper px-2 py-1.5"><option value={10}>Latest 10</option><option value={30}>Latest 30</option><option value={60}>Latest 60</option><option value={100}>Latest 100</option></select>
      </label>
    </div>
    {data.status === 'UNAVAILABLE' || data.status === 'NO_HISTORY' ? <Card className="p-5 border border-dashed border-line space-y-2"><h4 className="font-semibold text-ink">Live visibility is not measured</h4><p className="text-sm text-ink-600">{hasHistory ? 'Snapshots exist, but no successful non-empty live responses were stored in the latest snapshot.' : 'No persisted GEO pipeline snapshots exist for this domain yet. Run the live GEO pipeline to begin a historical series.'}</p><p className="text-xs text-ink-500">Scores and rates stay blank until real responses are available.</p></Card> : null}
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
      {[['Live visibility score', m.score == null ? '—' : `${m.score.toFixed(1)}/100`, 'Successful responses only'],['Brand mention rate', pct(m.mention_rate_pct), `${m.mentions} mentions`],['First-party citation rate', pct(m.citation_rate_pct), `${m.citations} cited responses`],['Successful observations', String(m.observations), `${m.failed_or_empty} failed/empty of ${m.attempted} attempts`]].map(k => <Card key={k[0]} className="p-4 space-y-1"><span className="text-xs text-ink-500">{k[0]}</span><p className="text-2xl font-bold text-ink">{k[1]}</p><p className="text-xs text-ink-500">{k[2]}</p></Card>)}
    </div>
    <Card className="p-5 space-y-3"><div><h4 className="font-semibold text-ink">Visibility score over time</h4><p className="text-xs text-ink-500">Each point is recomputed from successful response records in that stored snapshot.</p></div><TrendChart history={data.history} /><div className="text-xs text-ink-500">{data.history.length} snapshots returned · {data.history.filter(p => p.score != null).length} measured scores · methodology {data.methodology_version}</div></Card>
    <Card className="p-5 space-y-3"><div><h4 className="font-semibold text-ink">Brand mentions vs citations over time</h4><p className="text-xs text-ink-500">Rates use successful response counts as their denominator; failed attempts are excluded.</p></div><RateTrendChart history={data.history} /></Card>
    <Card className="p-5 space-y-3"><h4 className="font-semibold text-ink">Historical snapshot ledger</h4><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-line text-ink-500"><th className="py-2 pr-3">Snapshot time</th><th className="py-2 pr-3">Score</th><th className="py-2 pr-3">Measured</th><th className="py-2 pr-3">Mentions</th><th className="py-2 pr-3">Citations</th><th className="py-2">Status</th></tr></thead><tbody>{[...data.history].reverse().map(point => <tr key={point.snapshot_id} className="border-b border-line/70"><td className="py-2 pr-3">{new Date(point.timestamp).toLocaleString()}</td><td className="py-2 pr-3 font-mono">{point.score == null ? '—' : point.score.toFixed(1)}</td><td className="py-2 pr-3">{point.observations}/{point.attempted}</td><td className="py-2 pr-3">{point.mentions} · {pct(point.mention_rate_pct)}</td><td className="py-2 pr-3">{point.citations} · {pct(point.citation_rate_pct)}</td><td className="py-2">{point.status}</td></tr>)}</tbody></table></div></Card>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <Card className="p-5 space-y-4"><div><h4 className="font-semibold text-ink">AI engine comparison</h4><p className="text-xs text-ink-500">Latest snapshot; only successful responses enter each denominator.</p></div>
        {data.engines.length ? data.engines.map(engine => <div key={engine.engine} className="space-y-2 border-b border-line pb-3 last:border-0"><div className="flex justify-between gap-3"><span className="text-sm font-medium text-ink">{engine.engine}</span><span className="text-xs text-ink-500">{engine.observations} measured / {engine.attempted} attempted</span></div><BarRow label="Visibility score" value={engine.score} /><div className="grid grid-cols-2 gap-3"><BarRow label="Mention rate" value={engine.mention_rate_pct} /><BarRow label="Citation rate" value={engine.citation_rate_pct} /></div></div>) : <p className="text-sm text-ink-500">No engine records are available.</p>}
      </Card>
      <Card className="p-5 space-y-4"><div><h4 className="font-semibold text-ink">Buyer-intent coverage</h4><p className="text-xs text-ink-500">Intent groups from the latest snapshot, not synthetic query categories.</p></div>
        {data.intents.length ? data.intents.map(intent => <div key={intent.intent} className="border-b border-line pb-3 last:border-0 space-y-2"><div className="flex justify-between gap-3 text-sm"><span className="font-medium text-ink">{intent.intent}</span><span className="text-xs text-ink-500">{intent.observations} observed</span></div><div className="grid grid-cols-2 gap-3"><BarRow label="Mention rate" value={intent.mention_rate_pct} /><BarRow label="Citation rate" value={intent.citation_rate_pct} /></div></div>) : <p className="text-sm text-ink-500">No intent observations are available.</p>}
      </Card>
    </div>
    <Card className="p-5 space-y-4"><div><h4 className="font-semibold text-ink">How the live GEO visibility score is calculated</h4><p className="text-xs text-ink-500">Versioned measured-response rubric. This is not the on-page extractability/readiness rating.</p></div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[['100 points','Response contains a first-party citation'],['55 points','Brand/domain mentioned, without a first-party citation'],['0 points','Successful response contains neither a detected mention nor citation']].map(row => <div key={row[0]} className="rounded-lg border border-line p-4"><p className="text-2xl font-bold text-ink">{row[0]}</p><p className="text-xs text-ink-600 mt-1">{row[1]}</p></div>)}
      </div>
      <div className="rounded-lg bg-ink/5 p-4"><p className="font-mono text-sm text-ink">Score = Σ(response points) ÷ number of successful responses</p><p className="text-xs text-ink-600 mt-2">Denominator: {data.formula.denominator}</p><p className="text-xs text-ink-600 mt-1">Failure rule: {data.formula.failed_response_treatment}</p></div>
      <MethodFlow />
      <div className="rounded-lg border border-line p-4 space-y-2">
        <h5 className="font-semibold text-ink">Separate rating: on-page GEO readiness</h5>
        <p className="text-xs text-ink-600">The repository's readiness helper uses normalized inputs on a 0–1 scale; it is not the live visibility score above.</p>
        <p className="font-mono text-sm text-ink">Readiness = (citation_rate × 0.70 + sentiment_score × 0.30) × 100</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-ink-600">
          <p className="rounded bg-paper-50 p-3"><strong className="text-ink">70% weight</strong><br />Citation-rate input</p>
          <p className="rounded bg-paper-50 p-3"><strong className="text-ink">30% weight</strong><br />Sentiment-score input</p>
        </div>
        <p className="text-xs text-ink-500">This dashboard does not invent those input values or combine this readiness rating with live visibility. The two ratings have different meanings and denominators.</p>
      </div>
    </Card>
    <Card className="p-5 space-y-3"><h4 className="font-semibold text-ink">Data quality & limitations</h4><div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs"><div className="rounded border border-line p-3"><p className="font-semibold text-ink">Measured responses</p><p className="mt-1 text-ink-600">{data.data_quality.successful_observations}</p></div><div className="rounded border border-line p-3"><p className="font-semibold text-ink">Failed/empty attempts</p><p className="mt-1 text-ink-600">{data.data_quality.failed_or_empty_attempts}</p></div><div className="rounded border border-line p-3"><p className="font-semibold text-ink">Measurement scope</p><p className="mt-1 text-ink-600">{data.data_quality.scope}</p></div></div><ul className="list-disc pl-5 space-y-1 text-xs text-ink-600">{data.data_quality.limitations.map(item => <li key={item}>{item}</li>)}</ul></Card>
  </div>;
}
