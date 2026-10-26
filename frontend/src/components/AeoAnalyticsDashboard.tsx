import React, { useEffect, useMemo, useState } from 'react';
import { Card } from './ui';
import { GeoAeoTrendTracker } from './GeoAeoTrendTracker';
import { api } from '../services/http';

type Props = { report: any; analysisId?: string };

const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;
const pct = (value: unknown) => {
  const n = num(value);
  return n === null ? 'Not measured' : `${n.toFixed(1)}%`;
};
const score = (value: unknown) => {
  const n = num(value);
  return n === null ? '—' : `${n.toFixed(1)} / 100`;
};

/** Evidence-first AEO analytics. Never turns absent measurements into zero. */
export function AeoAnalyticsDashboard({ report, analysisId }: Props) {
  const geo = report?.geo_readiness;
  const [loadedScorecard, setLoadedScorecard] = useState<any>(report?.aeo_four_pillars_scorecard ?? null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [historySnapshots, setHistorySnapshots] = useState<any[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const effectiveAnalysisId = analysisId || report?.analysis_id || report?.report_id;
  useEffect(() => {
    let active = true;
    if (!effectiveAnalysisId) return;
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    api<any>(`/api/v1/reports/${encodeURIComponent(effectiveAnalysisId)}/aeo-analytics`, {}, 'Could not load AEO analytics')
      .then((payload) => { if (active) setLoadedScorecard(payload); })
      .catch((error: any) => { if (active) setAnalyticsError(error?.message || 'AEO analytics endpoint is unavailable.'); })
      .finally(() => { if (active) setAnalyticsLoading(false); });
    api<any>(`/api/v1/reports/${encodeURIComponent(effectiveAnalysisId)}/aeo-analytics/history?limit=100`, {}, 'Could not load AEO analytics history')
      .then((payload) => { if (active) setHistorySnapshots(Array.isArray(payload?.history) ? payload.history : []); })
      .catch((error: any) => { if (active) setHistoryError(error?.message || 'AEO history endpoint is unavailable.'); });
    return () => { active = false; };
  }, [effectiveAnalysisId]);
  const scorecard = loadedScorecard;
  const metrics = scorecard?.core_metrics ?? [];
  const readiness = scorecard?.pillar_a_content_readiness;
  const technical = scorecard?.pillar_b_technical_eligibility;
  const visibility = scorecard?.pillar_c_observed_visibility;
  const outcomes = scorecard?.pillar_d_business_outcomes;
  const schemaScore = num(report?.scores?.category_scores?.SCHEMA?.score);
  const extractability = num(geo?.extractability_score);
  const answerable = Array.isArray(report?.dynamic_sandbox_evaluations)
    ? report.dynamic_sandbox_evaluations.filter((q: any) => q?.answerability_status === 'ANSWERABLE' && q?.is_answerable !== false).length
    : null;
  const sandboxTotal = Array.isArray(report?.dynamic_sandbox_evaluations) ? report.dynamic_sandbox_evaluations.length : null;
  const questionTotal = num(geo?.questions_total) ?? (Array.isArray(geo?.questions) ? geo.questions.length : null);
  const questionSupported = num(geo?.questions_supported);
  const questionPartial = num(geo?.questions_partial);
  const questionCoverage = questionTotal && questionSupported !== null
    ? ((questionSupported + 0.5 * (questionPartial ?? 0)) / questionTotal) * 100
    : null;
  const domain = String(report?.domain || report?.website_url || '').replace(/^https?:\/\//, '').split('/')[0];

  const pillars = useMemo(() => [
    { name: 'Content readiness', description: 'Can the content answer relevant questions clearly and with support?', value: num(readiness?.composite_readiness_score), display: undefined, state: readiness?.state ?? 'NOT_TESTED' },
    { name: 'Technical eligibility', description: 'Can crawlers access, index and interpret the relevant pages?', value: num(technical?.composite_eligibility_score), display: undefined, state: technical?.state ?? 'NOT_TESTED' },
    { name: 'Observed answer visibility', description: 'Was the brand actually mentioned or cited in live, recorded engine tests?', value: null, display: num(visibility?.brand_mention_rate_pct) === null ? 'Not measured' : `${num(visibility?.brand_mention_rate_pct)?.toFixed(1)}% mention rate`, state: visibility?.state ?? 'NOT_TESTED' },
    { name: 'Business outcomes', description: 'Are AI referral visits or conversions measured by connected analytics?', value: null, display: num(outcomes?.ai_referral_sessions) === null ? 'Not measured' : `${num(outcomes?.ai_referral_sessions)} referral sessions`, state: outcomes?.state ?? 'DATA_UNAVAILABLE' },
  ], [readiness, technical, visibility, outcomes]);

  const readinessMetrics = [
    { label: 'Question coverage', value: pct(questionCoverage), detail: 'Supported questions + half credit for partial answers / assessed questions' },
    { label: 'Answer completeness', value: pct(questionTotal && questionSupported !== null ? questionSupported / questionTotal * 100 : null), detail: 'Fully supported questions / assessed questions' },
    { label: 'Extractability', value: score(extractability), detail: 'Existing crawl/report extractability measurement' },
    { label: 'Schema quality', value: score(schemaScore), detail: 'Existing schema category score; not AI visibility' },
    { label: 'Sandbox answerable', value: sandboxTotal !== null && answerable !== null ? `${answerable} / ${sandboxTotal}` : 'Not measured', detail: 'Stored sandbox evaluation records only' },
    { label: 'Brand mention rate', value: pct(visibility?.brand_mention_rate_pct), detail: 'Live engine measurement only; no live test means not measured' },
    { label: 'Citation rate', value: pct(visibility?.citation_rate_pct), detail: 'Recorded answer tests with a qualifying citation' },
    { label: 'AI referral conversion', value: pct(outcomes?.ai_referral_conversion_rate_pct), detail: 'Requires connected, attributable analytics data' },
  ];

  return (
    <div className="space-y-6">
      <div className="sheet border border-line rounded-xl p-5 sm:p-7 space-y-2">
        <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-ink-500">AEO measurement workspace</div>
        <h3 className="text-2xl font-semibold text-ink">AEO KPIs & Analytics</h3>
        <p className="text-sm text-ink-600 max-w-3xl">
          Separate source readiness, technical eligibility, observed AI answer visibility and business outcomes.
          These are different measurements. Dristik does not combine unmeasured visibility or revenue into a fabricated total score.
        </p>
        <div className="flex flex-wrap gap-2 text-[10px] font-mono">
          <span className="px-2 py-1 rounded border border-line">Analysis: {analysisId || report?.analysis_id || 'current report'}</span>
          <span className="px-2 py-1 rounded border border-line">Evidence-first · missing ≠ zero</span>
        </div>
        {analyticsLoading && <p className="text-xs text-ink-500">Loading calculated AEO metrics from the analysis report…</p>}
        {analyticsError && <p className="text-xs text-ink-500">Calculated metrics endpoint: {analyticsError}. Showing report-level measurements where available.</p>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {pillars.map((pillar) => (
          <Card key={pillar.name} className="p-4 space-y-2">
            <div className="text-xs font-semibold text-ink">{pillar.name}</div>
            <div className="text-xl font-bold text-ink">{pillar.value === null ? (pillar.display || 'Not scored') : score(pillar.value)}</div>
            <div className="text-[11px] leading-relaxed text-ink-500">{pillar.description}</div>
            <div className="text-[10px] font-mono text-ink-500">State: {String(pillar.state)}</div>
          </Card>
        ))}
      </div>

      <section className="sheet border border-line rounded-xl p-5 space-y-4">
        <div>
          <h4 className="text-lg font-semibold text-ink">Measured component scores</h4>
          <p className="text-xs text-ink-500">Only complete, measured composites are charted. A missing component is shown as unavailable, not zero.</p>
        </div>
        <div className="space-y-4">
          {[
            { label: 'Content readiness', value: num(readiness?.composite_readiness_score) },
            { label: 'Technical eligibility', value: num(technical?.composite_eligibility_score) },
          ].map((item) => (
            <div key={item.label} className="space-y-1.5">
              <div className="flex justify-between gap-3 text-xs"><span className="font-medium text-ink">{item.label}</span><span className="font-mono text-ink-500">{item.value === null ? 'Not measured' : `${item.value.toFixed(1)} / 100`}</span></div>
              <div className="h-3 rounded bg-paper-200 dark:bg-ink-800 overflow-hidden">
                {item.value !== null && <div className="h-full rounded bg-pine" style={{ width: `${Math.max(0, Math.min(100, item.value))}%` }} />}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="sheet border border-line rounded-xl p-5 space-y-4">
        <div>
          <h4 className="text-lg font-semibold text-ink">Current KPI detail</h4>
          <p className="text-xs text-ink-500">Values are read from this report's stored evidence. Unavailable data is displayed as unavailable.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {readinessMetrics.map((metric) => (
            <div key={metric.label} className="rounded-lg border border-line bg-paper-50 dark:bg-ink-900/30 p-3 space-y-1">
              <div className="text-[11px] font-semibold text-ink-600">{metric.label}</div>
              <div className="text-xl font-bold text-ink">{metric.value}</div>
              <p className="text-[10px] leading-relaxed text-ink-500">{metric.detail}</p>
            </div>
          ))}
        </div>
        {metrics.length > 0 && (
          <div className="overflow-x-auto border border-line rounded-lg">
            <table className="w-full text-left text-xs">
              <thead className="bg-paper-100 dark:bg-ink-900 text-ink-600">
                <tr><th className="p-3">Metric</th><th className="p-3">Value</th><th className="p-3">Evidence state</th><th className="p-3">Formula / note</th></tr>
              </thead>
              <tbody>
                {metrics.map((metric: any, index: number) => (
                  <tr key={metric.code || index} className="border-t border-line">
                    <td className="p-3 font-medium text-ink">{metric.name || metric.code || 'Metric'}</td>
                    <td className="p-3 text-ink">{metric.value == null ? 'Not measured' : `${metric.value}${metric.unit === '%' ? '%' : metric.unit ? ` ${metric.unit}` : ''}`}</td>
                    <td className="p-3 font-mono text-ink-500">{String(metric.state || 'UNKNOWN')}</td>
                    <td className="p-3 text-ink-500">{metric.formula || metric.notes || 'No formula metadata stored'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="sheet border border-line rounded-xl p-5 space-y-4">
        <div>
          <h4 className="text-lg font-semibold text-ink">How AEO measurement is calculated</h4>
          <p className="text-xs text-ink-500">This reflects the current four-pillar measurement contract. It deliberately does not invent one blended AEO total.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-9 gap-2 items-stretch">
          {[
            ['1 · Collect', 'Crawled page reports, question assessments, schema checks, live answer tests and connected analytics.'],
            ['2 · Validate', 'Check denominators, evidence state, source coverage and whether a live test actually ran.'],
            ['3 · Calculate', 'Calculate only metrics with valid observations and explicit denominators.'],
            ['4 · Preserve', 'Keep content, technical, visibility and outcome results separate.'],
            ['5 · Explain', 'Show values, formulas, timestamps, scope and unavailable reasons with each result.'],
          ].map((step, index) => (
            <React.Fragment key={step[0]}>
              <div className="rounded-lg border border-line p-3 bg-paper-50 dark:bg-ink-900/30">
                <div className="text-xs font-bold text-ink mb-2">{step[0]}</div>
                <p className="text-[11px] leading-relaxed text-ink-500">{step[1]}</p>
              </div>
              {index < 4 && <div className="hidden md:flex items-center justify-center text-ink-400">→</div>}
            </React.Fragment>
          ))}
        </div>
        <div className="rounded-lg border border-line p-4 space-y-2">
          <div className="text-xs font-semibold text-ink">Example formula: question coverage</div>
          <code className="block whitespace-normal text-xs text-ink-700">((fully supported questions + 0.5 × partially supported questions) ÷ assessed questions) × 100</code>
          <p className="text-[11px] leading-relaxed text-ink-500">The content-readiness composite is published only when every required component in its configured formula is measured. The technical-eligibility composite follows the same complete-component rule. No missing component is silently treated as zero or dropped to inflate the score.</p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div className="border border-line rounded-lg p-4 space-y-3">
            <div className="text-sm font-semibold text-ink">Content readiness composite</div>
            <p className="text-[11px] text-ink-500">Published only when all four components have valid measurements.</p>
            {[
              ['Question coverage', 30],
              ['Answer completeness', 20],
              ['Clarity / extractability', 30],
              ['Factual support', 20],
            ].map(([label, weight]) => (
              <div key={String(label)} className="space-y-1">
                <div className="flex justify-between text-[11px]"><span className="text-ink-600">{label}</span><span className="font-mono text-ink-500">{weight}%</span></div>
                <div className="h-2 rounded bg-paper-200 dark:bg-ink-800 overflow-hidden"><div className="h-full bg-pine rounded" style={{ width: `${weight}%` }} /></div>
              </div>
            ))}
            <code className="block text-[10px] text-ink-600 whitespace-normal">0.30 × coverage + 0.20 × completeness + 0.30 × extractability + 0.20 × factual support</code>
          </div>
          <div className="border border-line rounded-lg p-4 space-y-3">
            <div className="text-sm font-semibold text-ink">Technical eligibility composite</div>
            <p className="text-[11px] text-ink-500">Published only when all five components have valid measurements.</p>
            {[
              ['Crawlability', 25],
              ['Indexability', 25],
              ['Structured-data validity', 20],
              ['Internal discovery', 15],
              ['URL stability', 15],
            ].map(([label, weight]) => (
              <div key={String(label)} className="space-y-1">
                <div className="flex justify-between text-[11px]"><span className="text-ink-600">{label}</span><span className="font-mono text-ink-500">{weight}%</span></div>
                <div className="h-2 rounded bg-paper-200 dark:bg-ink-800 overflow-hidden"><div className="h-full bg-pine rounded" style={{ width: `${weight}%` }} /></div>
              </div>
            ))}
            <code className="block text-[10px] text-ink-600 whitespace-normal">0.25 × crawlability + 0.25 × indexability + 0.20 × schema + 0.15 × discovery + 0.15 × URL stability</code>
          </div>
        </div>
        <div className="rounded-lg border border-line p-4">
          <div className="text-xs font-semibold text-ink mb-1">Why there is no single total AEO number</div>
          <p className="text-[11px] leading-relaxed text-ink-500">The implementation intentionally does not average readiness, technical eligibility, live visibility and business outcomes into one score. Those pillars have different evidence sources, denominators and measurement states. A single blended total would conceal missing data and imply a comparability that the measurement contract does not establish.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="border border-line rounded-lg p-3">
            <div className="text-xs font-semibold text-ink mb-1">Observed answer visibility</div>
            <p className="text-[11px] text-ink-500 leading-relaxed">Requires recorded live engine tests. No tests means NOT_TESTED—not 0% visibility.</p>
          </div>
          <div className="border border-line rounded-lg p-3">
            <div className="text-xs font-semibold text-ink mb-1">Business outcomes</div>
            <p className="text-[11px] text-ink-500 leading-relaxed">Requires connected and attributable analytics. Missing connector data means DATA_UNAVAILABLE—not zero revenue.</p>
          </div>
        </div>
      </section>

      <section className="sheet border border-line rounded-xl p-5 space-y-4">
        <div>
          <h4 className="text-lg font-semibold text-ink">Historical AEO readiness & eligibility</h4>
          <p className="text-xs text-ink-500">Snapshots are recorded after a completed audit is durably saved. Older runs are not estimated or backfilled.</p>
        </div>
        {historyError && <p className="text-xs text-ink-500">{historyError}</p>}
        {historySnapshots.length === 0 ? (
          <div className="rounded-lg border border-dashed border-line p-5 text-sm text-ink-500">
            No completed AEO scorecard snapshots are stored for this domain yet. This history begins as completed audits run after this feature is deployed.
          </div>
        ) : (
          <div className="space-y-4">
            {historySnapshots.map((snap) => {
              const a = num(snap?.scorecard?.pillar_a_content_readiness?.composite_readiness_score);
              const b = num(snap?.scorecard?.pillar_b_technical_eligibility?.composite_eligibility_score);
              return (
                <div key={snap.analysis_id} className="rounded-lg border border-line p-3 space-y-3">
                  <div className="flex flex-wrap justify-between gap-2 text-xs">
                    <span className="font-semibold text-ink">{snap.analysis_id}</span>
                    <span className="font-mono text-ink-500">{snap.captured_at ? new Date(snap.captured_at).toLocaleString() : 'Timestamp unavailable'}</span>
                  </div>
                  {[
                    { label: 'Content readiness', value: a },
                    { label: 'Technical eligibility', value: b },
                  ].map((item) => (
                    <div key={item.label} className="space-y-1">
                      <div className="flex justify-between text-[11px]"><span className="text-ink-600">{item.label}</span><span className="font-mono text-ink-500">{item.value === null ? 'Not measured' : `${item.value.toFixed(1)} / 100`}</span></div>
                      <div className="h-2.5 rounded bg-paper-200 dark:bg-ink-800 overflow-hidden">
                        {item.value !== null && <div className="h-full rounded bg-pine" style={{ width: `${Math.max(0, Math.min(100, item.value))}%` }} />}
                      </div>
                    </div>
                  ))}
                  <div className="text-[10px] text-ink-500 font-mono">Formula version: {snap.formula_version || 'unknown'} · No unified AEO total is calculated</div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h4 className="text-lg font-semibold text-ink">Historical live answer-engine observations</h4>
          <p className="text-xs text-ink-500">The trend tracker below is the existing live GEO/AEO pipeline history. Its score is an observed citation/visibility score, not the content-readiness or technical-eligibility score above.</p>
        </div>
        {domain ? <GeoAeoTrendTracker domain={domain} brandName={report?.business_profile?.business_name} industry={report?.business_profile?.industry} /> : (
          <div className="rounded-lg border border-dashed border-line p-6 text-sm text-ink-500">A domain is required to load the live answer-engine history.</div>
        )}
      </section>
    </div>
  );
}
