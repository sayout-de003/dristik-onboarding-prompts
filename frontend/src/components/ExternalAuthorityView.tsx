import React from 'react';
import { ExternalAuthorityReport } from '../types';

function formatMetric(value: unknown): string {
  if (value == null || value === '') return 'Not measured';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  return String(value);
}

const PILLARS = [
  ['search_authority', 'Search Authority'],
  ['link_authority', 'Link Authority'],
  ['brand_authority', 'Brand Authority'],
  ['entity_local_authority', 'Entity & Local Authority'],
  ['market_authority', 'Market Authority'],
] as const;

export function ExternalAuthorityView({ report }: { report?: ExternalAuthorityReport | null }) {
  if (!report) {
    return (
      <section className="card p-6 space-y-2">
        <h2 className="section-title">External search and brand signals</h2>
        <p className="text-sm text-ink-500">This audit has no external-authority attachment. Crawl findings are unchanged.</p>
      </section>
    );
  }

  const search = report.sections?.search_performance || {};
  const analytics = report.sections?.analytics || {};
  const brand = report.sections?.brand_mentions || {};
  const local = report.sections?.local_authority || {};
  const links = report.sections?.backlink_profile || {};

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="label">Measured providers only</p>
        <h2 className="section-title">{report.title || 'External Authority & Entity Intelligence'}</h2>
        <p className="text-sm text-ink-500">{report.score_note || 'Only data returned by the available providers is shown. Missing metrics remain unavailable; no universal authority score is calculated.'}</p>
        <p className="text-sm text-ink-700">Period: {report.period_label || (report.period_days != null ? `${report.period_days} days` : 'Not specified')}. No universal authority score is calculated.</p>
      </header>

      <section className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {PILLARS.map(([key, label]) => (
          <div key={key} className="card p-3">
            <p className="text-xs text-ink-500">{label}</p>
            <p className="text-sm font-semibold mt-1">{report.pillars?.[key]?.data_state || 'UNAVAILABLE'}</p>
          </div>
        ))}
      </section>

      <section className="card p-5 space-y-3">
        <h3 className="font-semibold">Search Performance</h3>
        <dl className="grid sm:grid-cols-2 gap-2 text-sm">
          <Metric label="Organic clicks" value={search.organic_clicks} />
          <Metric label="Impressions" value={search.impressions} />
          <Metric label="CTR" value={search.ctr} />
          <Metric label="Average position" value={search.average_position} />
          <Metric label="GA4 organic sessions" value={analytics.organic_sessions} />
          <Metric label="GA4 key events" value={analytics.organic_conversions} />
        </dl>
        {typeof analytics.note === 'string' && <p className="text-xs text-ink-500">{analytics.note}</p>}
      </section>

      <section className="card p-5 space-y-3">
        <h3 className="font-semibold">Backlinks and referring domains</h3>
        {Object.keys(links).length === 0 && (
          <p className="text-sm text-ink-500">Backlink authority could not be measured because no backlink data provider is connected.</p>
        )}
        {Object.entries(links).map(([provider, values]) => (
          <div key={provider} className="text-sm border-t border-line pt-2">
            <p className="font-medium">{provider}</p>
            <p>Backlinks: {formatMetric(values.backlinks)} · Referring domains: {formatMetric(values.referring_domains)}</p>
            {(['domain_rating', 'authority_score', 'trust_flow', 'citation_flow'] as const).map((metric) => {
              const item = values[metric] as { value?: number; label?: string } | undefined;
              if (!item) return null;
              return <p key={metric}>{item.label || metric}: {formatMetric(item.value)}</p>;
            })}
            {typeof values.label === 'string' && <p>{values.label}</p>}
          </div>
        ))}
      </section>

      <section className="grid lg:grid-cols-2 gap-4">
        <div className="card p-5 space-y-2 text-sm">
          <h3 className="font-semibold">Brand mentions</h3>
          <p>Mentions: {formatMetric(brand.mentions)}</p>
          <p>Linked: {formatMetric(brand.linked)} · Unlinked: {formatMetric(brand.unlinked)}</p>
        </div>
        <div className="card p-5 space-y-2 text-sm">
          <h3 className="font-semibold">Local authority</h3>
          <p>Search impressions: {formatMetric(local.search_impressions)}</p>
          <p>Website clicks: {formatMetric(local.website_clicks)} · Calls: {formatMetric(local.calls)}</p>
          <p>Direction requests: {formatMetric(local.direction_requests)}</p>
        </div>
      </section>

      <section className="card p-5 space-y-2">
        <h3 className="font-semibold">Entity signals</h3>
        {(report.entity_signals || []).map((signal) => (
          <p key={signal.signal} className="text-sm">
            <span className="font-medium">{signal.signal}</span> · {signal.status}. {signal.detail}
          </p>
        ))}
      </section>

      <section className="card p-5 space-y-2">
        <h3 className="font-semibold">Competitor gap</h3>
        {(report.competitor_gap || []).map((gap, index) => (
          <p key={index} className="text-sm text-ink-700">{gap.statement}</p>
        ))}
      </section>

      <section className="card p-5 space-y-2">
        <h3 className="font-semibold">Data coverage</h3>
        <ul className="text-sm space-y-1">
          {(report.coverage || []).map((row) => (
            <li key={row.provider} className="flex flex-wrap justify-between gap-2 border-b border-line/60 py-1">
              <span>{row.display_name}</span>
              <span className="font-mono text-xs">{row.connection_status} · {row.data_state}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <h3 className="font-semibold">Findings</h3>
        {(report.findings || []).length === 0 && <p className="text-sm text-ink-500">No external findings for this period.</p>}
        {(report.findings || []).map((finding) => (
          <article key={finding.finding_id || finding.title} className="card p-4 space-y-1">
            <p className="text-xs font-mono text-ink-500">{finding.severity} · {finding.evidence_basis} · {finding.data_state}</p>
            <h4 className="font-medium">{finding.title}</h4>
            {finding.description && <p className="text-sm text-ink-600">{finding.description}</p>}
            {finding.vendor_metric_label && <p className="text-xs text-ink-500">{finding.vendor_metric_label}</p>}
          </article>
        ))}
      </section>

      {(report.notes || []).map((note) => (
        <p key={note} className="text-xs text-ink-500">{note}</p>
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <dt className="text-ink-500">{label}</dt>
      <dd className="font-medium">{formatMetric(value)}</dd>
    </div>
  );
}
