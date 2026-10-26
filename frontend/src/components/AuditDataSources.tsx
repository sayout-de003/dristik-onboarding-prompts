import React, { useEffect, useState } from 'react';
import { fetchExternalCoverage } from '../services/externalAuthority';

const LABELS: Record<string, string> = {
  google_search_console: 'Google Search Console',
  google_analytics_4: 'Google Analytics',
  bing_webmaster: 'Bing Webmaster',
  ahrefs: 'Ahrefs',
  semrush: 'Semrush',
  majestic: 'Majestic',
  dataforseo: 'DataForSEO',
  serpapi: 'SERP provider',
  google_business_profile: 'Google Business',
  citations: 'Citations',
  brand_mentions: 'Brand mentions',
};

export function AuditDataSources({ domain }: { domain: string }) {
  const [rows, setRows] = useState<Array<{ provider: string; connection_status: string; data_state: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setLoadError(false);
    const handle = window.setTimeout(() => {
      fetchExternalCoverage(domain || '')
        .then((payload) => { setRows((payload.matrix || []) as Array<{ provider: string; connection_status: string; data_state: string }>); setLoading(false); })
        .catch(() => { setRows([]); setLoadError(true); setLoading(false); });
    }, 400);
    return () => window.clearTimeout(handle);
  }, [domain]);

  const visible = ['google_search_console', 'google_analytics_4', 'bing_webmaster', 'ahrefs', 'google_business_profile', 'brand_mentions'];

  return (
    <div className="mt-4 pt-3 border-t border-line/60">
      <p className="label mb-2">Data sources and coverage</p>
      <ul className="flex flex-wrap gap-2 text-xs">
        <li className="px-2 py-1 rounded-md border border-line">Website crawl · checked when audit runs</li>
        {visible.map((id) => {
          const row = rows.find((item) => item.provider === id);
          const on = row && (row.connection_status === 'CONNECTED' || row.data_state === 'MEASURED' || row.data_state === 'PARTIALLY_MEASURED');
          const mark = row?.data_state === 'NOT_APPLICABLE' ? 'n/a' : on ? 'Connected' : row ? 'Not connected' : '?';
          return (
            <li key={id} className="px-2 py-1 rounded-md border border-line">
              {LABELS[id] || id} {mark}
            </li>
          );
        })}
      </ul>
      {loading ? <p className="text-xs text-ink-500 mt-2" role="status">Checking provider connection and coverage status…</p> : loadError ? <p className="text-xs text-warn mt-2" role="status">Provider status could not be loaded. “?” means unknown; it does not mean disconnected or a failed SEO check.</p> : <p className="text-xs text-ink-500 mt-2">“Not connected” means no usable connection was reported. “?” means no status was returned. Missing provider data is not treated as zero or as an SEO failure.</p>}
    </div>
  );
}
