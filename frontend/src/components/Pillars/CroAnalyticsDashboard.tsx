import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../../services/http';
import { AnalysisSummary, CroIntelligenceReport, CroMetricResult, ExecutiveReport } from '../../types';
import { Card } from '../ui';

type HistoryRange = '30' | '90' | 'all';

interface CroAnalyticsDashboardProps {
  report: ExecutiveReport;
  analysisId?: string;
}

const unavailable = 'Unavailable';

function scoreOf(summary: AnalysisSummary): number | null {
  const score = summary.score_cro;
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 100 ? score : null;
}

function dateLabel(value?: string | null): string {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function metricDisplay(metric?: CroMetricResult): string {
  if (!metric) return unavailable;
  const status = String(metric.status || '').toUpperCase();
  if (status.includes('UNAVAILABLE') || status.includes('NOT_CONFIGURED') || status.includes('DATA_UNAVAILABLE')) return unavailable;
  if (metric.value == null || !Number.isFinite(metric.value)) return metric.display || unavailable;
  return metric.display || String(metric.value);
}

function MetricCard({ label, value, detail, status }: { label: string; value: string; detail?: string; status?: string }) {
  const isUnavailable = value === unavailable || /UNAVAILABLE|NOT_CONFIGURED|DATA_UNAVAILABLE/i.test(status || '');
  return (
    <Card className="p-4 space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</p>
      <p className={`text-2xl font-semibold tracking-tight ${isUnavailable ? 'text-ink-400' : 'text-ink'}`}>{isUnavailable ? unavailable : value}</p>
      {detail ? <p className="text-xs leading-relaxed text-ink-500">{detail}</p> : null}
      {status ? <p className="text-[10px] uppercase tracking-wide text-ink-500">Status: {status.replace(/_/g, ' ')}</p> : null}
    </Card>
  );
}

export function CroAnalyticsDashboard({ report, analysisId }: CroAnalyticsDashboardProps) {
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<HistoryRange>('90');
  const [view, setView] = useState<'overview' | 'history' | 'methodology'>('overview');
  const [selectedMetricKey, setSelectedMetricKey] = useState('');

  const intel = report.cro_audit?.intelligence as CroIntelligenceReport | null | undefined;
  const metrics = intel?.metrics || [];
  const dimensions = intel?.dimensions || [];
  const currentScoreValue = report.cro_audit?.overall_cro_score ?? report.scores?.category_scores?.UX_CONVERSION?.score;
  const currentScore = typeof currentScoreValue === 'number' && Number.isFinite(currentScoreValue) ? currentScoreValue : null;
  const domain = (report.domain || report.website_url || '').replace(/^https?:\/\//, '').replace(/\/$/, '').toLowerCase();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    api<AnalysisSummary[]>('/api/v1/analyses?limit=100', {}, 'Could not load CRO audit history')
      .then((items) => { if (active) setHistory(Array.isArray(items) ? items : []); })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Could not load CRO audit history.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [analysisId]);

  const sameDomainHistory = useMemo(() => {
    const now = Date.now();
    const cutoff = range === 'all' ? 0 : now - Number(range) * 24 * 60 * 60 * 1000;
    return history
      .filter((item) => {
        const itemDomain = (item.domain || item.website_url || '').replace(/^https?:\/\//, '').replace(/\/$/, '').toLowerCase();
        const parsed = item.completed_at || item.started_at;
        const timestamp = parsed ? new Date(parsed).getTime() : Number.NaN;
        return itemDomain === domain && Number.isFinite(timestamp) && timestamp >= cutoff;
      })
      .sort((a, b) => new Date(a.completed_at || a.started_at).getTime() - new Date(b.completed_at || b.started_at).getTime());
  }, [history, domain, range]);

  const comparableHistory = sameDomainHistory.filter((item) => scoreOf(item) !== null);
  const kpiCandidates = useMemo(() => {
    const wanted = [
      { label: 'Conversion rate', match: /conversion rate/i, detail: 'Use the denominator shown in the metric definition.' },
      { label: 'CTA click-through rate', match: /cta.*(click|ctr)|click.?through/i, detail: 'Requires measured CTA clicks and eligible impressions.' },
      { label: 'Form completion rate', match: /form.*completion/i, detail: 'Requires measured form starts and successful submissions.' },
      { label: 'Funnel completion', match: /funnel.*(completion|conversion)/i, detail: 'Requires a measured funnel entry and completion.' },
      { label: 'Revenue per session', match: /revenue.*session/i, detail: 'Requires connected revenue and session data.' },
      { label: 'Checkout abandonment', match: /checkout.*abandon/i, detail: 'Relevant only when checkout events are measured.' },
    ];
    return wanted.map((candidate) => {
      const found = metrics.find((metric) => candidate.match.test(metric.metric));
      return { ...candidate, metric: found };
    });
  }, [metrics]);

  const metricOptions = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string; formula: string; denominator?: string | null; window?: string | null }> = [];
    sameDomainHistory.forEach((item) => {
      (item.cro_metrics || []).forEach((metric) => {
        if (metric.status !== 'MEASURED' || typeof metric.value !== 'number' || !Number.isFinite(metric.value)) return;
        const key = [metric.metric, metric.formula, metric.denominator || '', metric.window || ''].join('|||');
        if (seen.has(key)) return;
        seen.add(key);
        options.push({ key, label: metric.metric, formula: metric.formula, denominator: metric.denominator, window: metric.window });
      });
    });
    return options;
  }, [sameDomainHistory]);
  const selectedMetric = metricOptions.find((option) => option.key === selectedMetricKey) || metricOptions[0];
  const metricSeries = selectedMetric ? sameDomainHistory.flatMap((item) =>
    (item.cro_metrics || [])
      .filter((metric) => [metric.metric, metric.formula, metric.denominator || '', metric.window || ''].join('|||') === selectedMetric.key && metric.status === 'MEASURED' && typeof metric.value === 'number' && Number.isFinite(metric.value))
      .map((metric) => ({ item, metric }))
  ) : [];
  const metricValues = metricSeries.map((point) => point.metric.value as number);
  const metricMin = metricValues.length ? Math.min(...metricValues) : 0;
  const metricMax = metricValues.length ? Math.max(...metricValues) : 0;
  const metricRange = metricMax - metricMin || 1;
  const metricChartPoints = metricSeries.map((point, index) => ({
    ...point,
    x: metricSeries.length <= 1 ? 300 : 32 + (index / (metricSeries.length - 1)) * 536,
    y: 165 - (((point.metric.value as number) - metricMin) / metricRange) * 120,
  }));
  const metricPolyline = metricChartPoints.map((point) => `${point.x},${point.y}`).join(' ');

  const chartPoints = comparableHistory.map((item, index) => {
    const score = scoreOf(item) as number;
    const x = comparableHistory.length <= 1 ? 300 : 32 + (index / (comparableHistory.length - 1)) * 536;
    const y = 178 - (score / 100) * 145;
    return { item, score, x, y };
  });
  const polyline = chartPoints.map((point) => `${point.x},${point.y}`).join(' ');
  const latestHistoryScore = chartPoints.length ? chartPoints[chartPoints.length - 1].score : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-ink">CRO analytics</h3>
          <p className="mt-1 text-sm text-ink-600">Current audit evidence, historical audit ratings, and the score calculation path.</p>
        </div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="CRO analytics views">
          {([
            ['overview', 'Overview'],
            ['history', 'History'],
            ['methodology', 'Score methodology'],
          ] as const).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={view === id} onClick={() => setView(id)}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${view === id ? 'border-ink bg-ink text-white' : 'border-line text-ink-600 hover:bg-surface-muted'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === 'overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Current CRO rating" value={currentScore == null ? unavailable : `${currentScore.toFixed(1)} / 100`} detail="Audit quality rating; not a conversion rate." status={currentScore == null ? 'UNAVAILABLE' : 'MEASURED'} />
            <MetricCard label="Scored dimensions" value={dimensions.length ? String(dimensions.filter((item) => item.score != null).length) : unavailable} detail={dimensions.length ? `of ${dimensions.length} reported dimensions have a numeric score` : 'No dimension breakdown returned by this audit.'} />
            <MetricCard label="Measured CRO metrics" value={String(metrics.filter((item) => item.value != null && Number.isFinite(item.value)).length)} detail={`of ${metrics.length} CRO metric definitions returned by the audit`} />
            <MetricCard label="Historical snapshots" value={String(comparableHistory.length)} detail="Same domain, stored audit ratings only." status={loading ? 'LOADING' : error ? 'ERROR' : 'AVAILABLE'} />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
            <Card className="p-5 space-y-4 xl:col-span-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h4 className="font-semibold text-ink">CRO rating over audit history</h4><p className="mt-1 text-xs text-ink-500">Each point is a saved audit, not daily conversion performance.</p></div>
                <div className="flex gap-1" aria-label="History range">
                  {(['30', '90', 'all'] as const).map((item) => <button key={item} type="button" onClick={() => setRange(item)} className={`rounded-md px-2 py-1 text-xs ${range === item ? 'bg-surface-muted font-semibold text-ink' : 'text-ink-500'}`}>{item === 'all' ? 'All' : `${item}d`}</button>)}
                </div>
              </div>
              {loading ? <p className="py-8 text-sm text-ink-500">Loading saved audit history…</p> : error ? <div className="rounded-lg border border-line p-4 text-sm text-ink-600"><p>History could not be loaded: {error}</p><button type="button" className="mt-2 underline" onClick={() => { setError(null); setLoading(true); api<AnalysisSummary[]>('/api/v1/analyses?limit=100', {}, 'Could not load CRO audit history').then((items) => setHistory(Array.isArray(items) ? items : [])).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'History request failed.')).finally(() => setLoading(false)); }}>Retry</button></div> : chartPoints.length === 0 ? <div className="rounded-lg border border-dashed border-line p-6 text-sm text-ink-500">No saved CRO-scored audits for this domain in the selected period. Historical conversion rates are not reconstructed from audit scores.</div> : (
                <div>
                  <svg viewBox="0 0 600 220" role="img" aria-label="Historical CRO audit scores from zero to one hundred" className="h-56 w-full overflow-visible">
                    {[0, 25, 50, 75, 100].map((tick) => { const y = 178 - tick / 100 * 145; return <g key={tick}><line x1="32" x2="568" y1={y} y2={y} stroke="currentColor" opacity="0.12" strokeDasharray="3 4" /><text x="24" y={y + 4} textAnchor="end" fontSize="10" fill="currentColor" opacity="0.65">{tick}</text></g>; })}
                    {chartPoints.length > 1 && <polyline points={polyline} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />}
                    {chartPoints.map((point) => <g key={point.item.analysis_id}><circle cx={point.x} cy={point.y} r="4.5" fill="currentColor"><title>{`${dateLabel(point.item.completed_at || point.item.started_at)}: ${point.score.toFixed(1)}`}</title></circle></g>)}
                    <text x="32" y="205" fontSize="10" fill="currentColor" opacity="0.65">{dateLabel(chartPoints[0].item.completed_at || chartPoints[0].item.started_at)}</text>
                    <text x="568" y="205" textAnchor="end" fontSize="10" fill="currentColor" opacity="0.65">{dateLabel(chartPoints[chartPoints.length - 1].item.completed_at || chartPoints[chartPoints.length - 1].item.started_at)}</text>
                  </svg>
                  <div className="flex flex-wrap justify-between gap-2 border-t border-line pt-3 text-xs text-ink-500"><span>{chartPoints.length} stored audit snapshots</span><span>Latest stored score: {latestHistoryScore == null ? unavailable : latestHistoryScore.toFixed(1)}</span></div>
                </div>
              )}
            </Card>
            <Card className="p-5 space-y-3 xl:col-span-2">
              <h4 className="font-semibold text-ink">Conversion KPIs</h4>
              <p className="text-xs text-ink-500">Only metrics explicitly returned by the CRO audit are shown as measured.</p>
              <div className="space-y-2">
                {kpiCandidates.map(({ label, detail, metric }) => <div key={label} className="flex items-start justify-between gap-3 border-b border-line py-2 last:border-0"><div><p className="text-sm font-medium text-ink">{label}</p><p className="mt-1 text-xs text-ink-500">{metric?.denominator ? `Denominator: ${metric.denominator}` : detail}</p></div><p className="whitespace-nowrap text-sm font-semibold text-ink">{metric ? metricDisplay(metric) : unavailable}</p></div>)}
              </div>
              <p className="text-[11px] text-ink-500">Unavailable means the required measurement was not supplied; it does not mean zero conversions.</p>
            </Card>
          </div>

          <Card className="p-5 space-y-3">
            <div><h4 className="font-semibold text-ink">CRO rating areas</h4><p className="mt-1 text-xs text-ink-500">Scores and statuses below come from the saved audit report.</p></div>
            {dimensions.length ? <div className="space-y-4">{dimensions.map((dimension) => <div key={dimension.id}><div className="mb-1 flex flex-wrap items-baseline justify-between gap-2"><span className="text-sm font-medium text-ink">{dimension.name}</span><span className="text-xs text-ink-500">{dimension.score == null ? unavailable : `${dimension.score.toFixed(1)} / 100`} · {dimension.status}</span></div><div className="h-2 overflow-hidden rounded-full bg-surface-muted"><div className="h-full rounded-full bg-ink" style={{ width: `${Math.max(0, Math.min(100, dimension.score ?? 0))}%` }} /></div><p className="mt-1 text-xs text-ink-500">{dimension.note}</p></div>)}</div> : <p className="text-sm text-ink-500">This audit did not return a dimension score breakdown.</p>}
          </Card>

          <Card className="p-5">
            <h4 className="font-semibold text-ink">Metric definitions and data status</h4>
            {metrics.length ? <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead><tr className="border-b border-line text-ink-500"><th className="py-2 pr-3">Metric</th><th className="py-2 pr-3">Formula</th><th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Observed value</th><th className="py-2">Denominator</th></tr></thead><tbody>{metrics.map((metric) => <tr key={metric.metric} className="border-b border-line align-top last:border-0"><td className="py-3 pr-3 font-medium text-ink">{metric.metric}</td><td className="py-3 pr-3 text-ink-600">{metric.formula}</td><td className="py-3 pr-3 text-ink-600">{metric.status}</td><td className="py-3 pr-3 font-mono text-ink">{metricDisplay(metric)}</td><td className="py-3 text-ink-500">{metric.denominator || 'Not specified'}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-ink-500">No CRO measurement records were returned for this audit.</p>}
          </Card>
        </div>
      )}

      {view === 'history' && (
        <Card className="p-5 space-y-4">
          <div><h4 className="font-semibold text-ink">Saved audit timeline</h4><p className="mt-1 text-xs text-ink-500">History includes only real saved audits. No interpolated or synthetic values are added.</p></div>
          {loading ? <p className="text-sm text-ink-500">Loading history…</p> : error ? <p className="text-sm text-ink-600">History unavailable: {error}</p> : comparableHistory.length ? <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm"><thead><tr className="border-b border-line text-xs text-ink-500"><th className="py-2 pr-3">Audit date</th><th className="py-2 pr-3">Domain</th><th className="py-2 pr-3">CRO rating</th><th className="py-2">Status</th></tr></thead><tbody>{[...comparableHistory].reverse().map((item) => <tr key={item.analysis_id} className="border-b border-line last:border-0"><td className="py-3 pr-3">{dateLabel(item.completed_at || item.started_at)}</td><td className="py-3 pr-3">{item.domain}</td><td className="py-3 pr-3 font-mono">{(scoreOf(item) as number).toFixed(1)} / 100</td><td className="py-3">{item.status}</td></tr>)}</tbody></table></div> : <p className="rounded-lg border border-dashed border-line p-5 text-sm text-ink-500">No historical CRO scores are available for this domain. Run and save another audit to begin a comparable audit timeline.</p>}
          <div className="space-y-3 border-t border-line pt-5">
            <div className="flex flex-wrap items-end justify-between gap-3"><div><h4 className="font-semibold text-ink">Historical measured CRO KPIs</h4><p className="mt-1 text-xs text-ink-500">Only observations stored with earlier audits are plotted. Series must match metric, formula, denominator, and measurement window.</p></div>{metricOptions.length ? <label className="text-xs text-ink-500">Metric<select aria-label="Historical KPI metric" value={selectedMetric?.key || ''} onChange={(event) => setSelectedMetricKey(event.target.value)} className="mt-1 block max-w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink">{metricOptions.map((option) => <option key={option.key} value={option.key}>{option.label}{option.window ? ` · ${option.window}` : ''}</option>)}</select></label> : null}</div>
            {metricChartPoints.length > 0 && selectedMetric ? <div><p className="text-xs text-ink-500">{selectedMetric.formula}{selectedMetric.denominator ? ` · Denominator: ${selectedMetric.denominator}` : ''}</p><svg viewBox="0 0 600 205" role="img" aria-label={`Historical measured values for ${selectedMetric.label}`} className="mt-3 h-52 w-full"><line x1="32" x2="568" y1="165" y2="165" stroke="currentColor" opacity="0.15" />{metricChartPoints.length > 1 ? <polyline points={metricPolyline} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" /> : null}{metricChartPoints.map((point) => <g key={`${point.item.analysis_id}-${point.metric.metric}`}><circle cx={point.x} cy={point.y} r="4.5" fill="currentColor"><title>{`${dateLabel(point.item.completed_at || point.item.started_at)}: ${point.metric.display}`}</title></circle></g>)}<text x="32" y="193" fontSize="10" fill="currentColor" opacity="0.65">{dateLabel(metricChartPoints[0].item.completed_at || metricChartPoints[0].item.started_at)} · {metricChartPoints[0].metric.display}</text><text x="568" y="193" textAnchor="end" fontSize="10" fill="currentColor" opacity="0.65">{dateLabel(metricChartPoints[metricChartPoints.length - 1].item.completed_at || metricChartPoints[metricChartPoints.length - 1].item.started_at)} · {metricChartPoints[metricChartPoints.length - 1].metric.display}</text></svg></div> : <p className="rounded-lg border border-dashed border-line p-5 text-sm text-ink-500">No comparable historical CRO KPI observations were saved for this domain and date range. Audit ratings can still be reviewed above.</p>}
          </div>
        </Card>
      )}

      {view === 'methodology' && (
        <div className="space-y-4">
          <Card className="p-5 space-y-3"><h4 className="font-semibold text-ink">How the CRO rating is produced</h4><p className="text-sm text-ink-600">This view explains the rating pipeline. The dashboard does not invent category weights: it displays the scores and statuses saved by the scoring engine and labels missing evidence as unavailable.</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-5 md:items-stretch">
              {[
                { n: '01', title: 'Collect evidence', body: 'Crawl pages, rendered elements, forms, CTAs, trust signals, and connected analytics when configured.' },
                { n: '02', title: 'Validate evidence', body: 'Check source, freshness, scope, and whether each observation is actually available.' },
                { n: '03', title: 'Rate checks', body: 'Each observed check receives its recorded outcome. Missing checks remain excluded or unavailable.' },
                { n: '04', title: 'Calculate evidenced dimensions', body: 'Experience quality = 100 × passed checks ÷ (passed + failed checks). Excluded checks do not enter the denominator. Funnel, measurement reliability, and business outcomes remain unscored when the evidence is insufficient.' },
                { n: '05', title: 'Publish total', body: 'Use the stored CRO total, or the UX_CONVERSION category score when the explicit CRO total is absent.' },
              ].map((step, index) => <React.Fragment key={step.n}><div className="rounded-xl border border-line bg-surface-muted/40 p-3"><p className="font-mono text-xs text-ink-500">{step.n}</p><p className="mt-2 text-sm font-semibold text-ink">{step.title}</p><p className="mt-2 text-xs leading-relaxed text-ink-600">{step.body}</p></div>{index < 4 ? <div className="hidden items-center justify-center text-ink-400 md:flex" aria-hidden="true">→</div> : null}</React.Fragment>)}
            </div>
            <div className="rounded-lg border border-line p-4"><p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Score precedence</p><p className="mt-2 font-mono text-sm text-ink">Explicit CRO score → UX_CONVERSION category score → Unavailable</p><p className="mt-2 text-xs text-ink-500">The site-wide composite score is never used as a CRO fallback.</p></div>
            <div className="rounded-lg border border-line p-4"><p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Experience-quality formula</p><p className="mt-2 font-mono text-sm text-ink">100 × passed ÷ (passed + failed)</p><p className="mt-2 text-xs text-ink-500">Only observed pass/fail checks count. Unmeasured or excluded checks are not counted as failures. The overall CRO total is displayed from the stored CRO score (or UX_CONVERSION score fallback); this dashboard does not invent category weights or blend unscored dimensions.</p></div>
          </Card>
          <Card className="p-5 space-y-3"><h4 className="font-semibold text-ink">Performance is not the same as audit quality</h4><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div className="rounded-lg border border-line p-4"><p className="font-semibold text-ink">Audit quality rating</p><p className="mt-2 text-sm text-ink-600">Rates observed conversion experience and UX checks. It does not prove that conversions improved.</p></div><div className="rounded-lg border border-line p-4"><p className="font-semibold text-ink">Measured business outcomes</p><p className="mt-2 text-sm text-ink-600">Conversion rate, qualified leads, revenue, and experiment lift require connected, validated event data and a defined denominator.</p></div></div></Card>
          <Card className="p-5"><h4 className="font-semibold text-ink">Rating areas returned by this audit</h4>{dimensions.length ? <div className="mt-3 space-y-2">{dimensions.map((dimension) => <div key={dimension.id} className="flex flex-wrap items-start justify-between gap-2 border-b border-line py-2 last:border-0"><div><p className="text-sm font-medium text-ink">{dimension.name}</p><p className="mt-1 text-xs text-ink-500">{dimension.note}</p></div><p className="whitespace-nowrap font-mono text-xs text-ink-600">{dimension.score == null ? unavailable : dimension.score.toFixed(1)} · {dimension.status}</p></div>)}</div> : <p className="mt-3 text-sm text-ink-500">No scored dimensions were provided in the current audit.</p>}</Card>
        </div>
      )}
    </div>
  );
}
