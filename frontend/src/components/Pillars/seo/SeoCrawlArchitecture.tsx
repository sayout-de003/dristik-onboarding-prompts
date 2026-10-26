import React, { useState } from 'react';
import { ExecutiveReport } from '../../../types';
import { Card } from '../../ui';
import {
  Globe,
  Layers,
  Code2,
  FileCode,
  Shield,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Filter,
} from 'lucide-react';

interface SeoCrawlArchitectureProps {
  report: ExecutiveReport;
}

export function SeoCrawlArchitecture({ report }: SeoCrawlArchitectureProps) {
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<'ALL' | '2xx' | '3xx' | '4xx' | '5xx'>('ALL');
  const [showRedirectChains, setShowRedirectChains] = useState(false);

  const crawl = report.crawl_manifest;
  const pages = crawl?.pages || [];
  const httpStatus = report.http_status_breakdown;
  const canonicalAudit = report.canonical_audit;
  const redirects = report.host_and_redirects;
  const clickDepth = report.click_depth;
  const orphanPages = report.orphan_pages;
  const security = report.security_audit;

  // Only derive status metrics from observed HTTP codes or a populated status summary.
  const observedStatusPages = pages.filter((page) => page.status_code != null);
  const totalUrls = httpStatus?.total_urls_checked ?? observedStatusPages.length;
  const hasHttpData = totalUrls > 0;
  const count2xx = httpStatus?.count_2xx ?? observedStatusPages.filter((p) => p.status_code >= 200 && p.status_code < 300).length;
  const count3xx = httpStatus?.count_3xx ?? observedStatusPages.filter((p) => p.status_code >= 300 && p.status_code < 400).length;
  const count4xx = httpStatus?.count_4xx ?? observedStatusPages.filter((p) => p.status_code >= 400 && p.status_code < 500).length;
  const count5xx = httpStatus?.count_5xx ?? observedStatusPages.filter((p) => p.status_code >= 500 && p.status_code < 600).length;

  const pct2xx = hasHttpData ? Math.round((count2xx / totalUrls) * 100) : null;
  const pct3xx = hasHttpData ? Math.round((count3xx / totalUrls) * 100) : null;
  const pct4xx = hasHttpData ? Math.round((count4xx / totalUrls) * 100) : null;
  const pct5xx = hasHttpData ? Math.round((count5xx / totalUrls) * 100) : null;

  // Crawl depth must come from the depth analyzer, not a URL-count heuristic.
  const hasDepthData = Boolean(clickDepth && clickDepth.total_pages_analyzed > 0);
  const depth1 = hasDepthData ? (clickDepth?.depth_1_count ?? 0) : null;
  const depth2 = hasDepthData ? (clickDepth?.depth_2_count ?? 0) : null;
  const depth3 = hasDepthData ? (clickDepth?.depth_3_count ?? 0) : null;
  const depth4Plus = hasDepthData ? (clickDepth?.depth_4_plus_count ?? 0) : null;
  const totalAnalyzed = hasDepthData ? (clickDepth?.total_pages_analyzed ?? 0) : 0;

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. 100% STACKED HTTP STATUS BAR & STATUS BREAKDOWN
          ───────────────────────────────────────────────────────────── */}
      <Card className="p-6 space-y-5 border-line bg-paper-50">
        <div className="flex flex-wrap items-center justify-between border-b border-line pb-3 gap-2">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-ink-700" />
            <h3 className="font-sans text-base font-semibold text-ink">
              Observed HTTP Response Codes
            </h3>
          </div>
          <span className="text-xs font-mono text-ink-500">
            {hasHttpData ? `${totalUrls} URLs with HTTP status data` : 'HTTP status data unavailable'}
          </span>
        </div>

        {/* Visual 100% Stacked Distribution Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-ink-600">
            <span>Crawler Status Distribution</span>
            <span>{pct2xx == null ? 'No measured status distribution' : `${pct2xx}% returned 2xx`}</span>
          </div>

          {hasHttpData ? <div className="w-full h-4 rounded-full overflow-hidden flex bg-paper-200 border border-line">
            {pct2xx != null && pct2xx > 0 && (
              <div
                style={{ width: `${pct2xx}%` }}
                className="bg-good hover:opacity-90 transition-opacity"
                title={`2xx Success: ${count2xx} URLs (${pct2xx}%)`}
              />
            )}
            {pct3xx != null && pct3xx > 0 && (
              <div
                style={{ width: `${pct3xx}%` }}
                className="bg-pine-500 hover:opacity-90 transition-opacity"
                title={`3xx Redirects: ${count3xx} URLs (${pct3xx}%)`}
              />
            )}
            {pct4xx != null && pct4xx > 0 && (
              <div
                style={{ width: `${pct4xx}%` }}
                className="bg-warn hover:opacity-90 transition-opacity"
                title={`4xx Client Errors: ${hasHttpData ? count4xx : '—'} URLs (${pct4xx}%)`}
              />
            )}
            {pct5xx != null && pct5xx > 0 && (
              <div
                style={{ width: `${pct5xx}%` }}
                className="bg-bad hover:opacity-90 transition-opacity"
                title={`5xx Server Errors: ${hasHttpData ? count5xx : '—'} URLs (${pct5xx}%)`}
              />
            )}
          </div> : <p className="rounded-lg border border-dashed border-line p-4 text-xs text-ink-500">HTTP response codes were not returned for this audit. Run a crawl that records response statuses to populate this chart.</p>}

          {hasHttpData && <div className="flex items-center justify-between text-[11px] font-mono text-ink-400 pt-0.5">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-good inline-block" /> 2xx Success ({count2xx})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-pine-500 inline-block" /> 3xx Redirect ({count3xx})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-warn inline-block" /> 4xx Client Err ({count4xx})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-bad inline-block" /> 5xx Server Err ({count5xx})</span>
          </div>}
        </div>

        {/* Granular HTTP Status KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div
            onClick={() => setSelectedStatusFilter(selectedStatusFilter === '2xx' ? 'ALL' : '2xx')}
            className={`p-3.5 rounded border transition-all cursor-pointer ${
              selectedStatusFilter === '2xx' ? 'border-good ring-1 ring-good bg-good/10' : 'border-line bg-paper-100/60 hover:bg-paper-100'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-good uppercase font-bold">2xx Success</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-good" />
            </div>
            <span className={`text-2xl font-mono font-bold block my-1 ${hasHttpData ? 'text-good' : 'text-ink-500'}`}>{hasHttpData ? count2xx : '—'}</span>
            <p className="text-[11px] text-ink-500 leading-tight">HTTP 2xx responses</p>
          </div>

          <div
            onClick={() => setSelectedStatusFilter(selectedStatusFilter === '3xx' ? 'ALL' : '3xx')}
            className={`p-3.5 rounded border transition-all cursor-pointer ${
              selectedStatusFilter === '3xx' ? 'border-pine-500 ring-1 ring-pine-500 bg-pine-500/10' : 'border-line bg-paper-100/60 hover:bg-paper-100'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-pine-600 dark:text-pine-400 uppercase font-bold">3xx Redirects</span>
              <Layers className="w-3.5 h-3.5 text-pine-600 dark:text-pine-400" />
            </div>
            <span className="text-2xl font-mono font-bold text-ink block my-1">{hasHttpData ? count3xx : '—'}</span>
            <p className="text-[11px] text-ink-500 leading-tight">Permanent 301 / 302 hops</p>
          </div>

          <div
            onClick={() => setSelectedStatusFilter(selectedStatusFilter === '4xx' ? 'ALL' : '4xx')}
            className={`p-3.5 rounded border transition-all cursor-pointer ${
              selectedStatusFilter === '4xx' ? 'border-warn ring-1 ring-warn bg-warn/10' : 'border-line bg-paper-100/60 hover:bg-paper-100'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-warn uppercase font-bold">4xx Client Errors</span>
              <AlertTriangle className="w-3.5 h-3.5 text-warn" />
            </div>
            <span className={`text-2xl font-mono font-bold block my-1 ${!hasHttpData ? 'text-ink-500' : count4xx > 0 ? 'text-warn' : 'text-good'}`}>
              {hasHttpData ? count4xx : '—'}
            </span>
            <p className="text-[11px] text-ink-500 leading-tight">404 Not Found / 403 Forbidden</p>
          </div>

          <div
            onClick={() => setSelectedStatusFilter(selectedStatusFilter === '5xx' ? 'ALL' : '5xx')}
            className={`p-3.5 rounded border transition-all cursor-pointer ${
              selectedStatusFilter === '5xx' ? 'border-bad ring-1 ring-bad bg-bad/10' : 'border-line bg-paper-100/60 hover:bg-paper-100'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-bad uppercase font-bold">5xx Server Errors</span>
              <XCircle className="w-3.5 h-3.5 text-bad" />
            </div>
            <span className={`text-2xl font-mono font-bold block my-1 ${!hasHttpData ? 'text-ink-500' : count5xx > 0 ? 'text-bad' : 'text-good'}`}>
              {hasHttpData ? count5xx : '—'}
            </span>
            <p className="text-[11px] text-ink-500 leading-tight">Backend timeouts & 500 crashes</p>
          </div>
        </div>

        {/* Broken Links Table */}
        {httpStatus?.broken_links && httpStatus.broken_links.length > 0 && (
          <div className="mt-4 pt-3 border-t border-line space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-bad flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Flagged Broken Links Inventory ({httpStatus.broken_links.length})
              </span>
              <span className="text-[10px] font-mono text-ink-400">Degrades PageRank Equity</span>
            </div>
            <div className="space-y-1.5 text-xs font-mono max-h-48 overflow-y-auto">
              {httpStatus.broken_links.map((bl, idx) => (
                <div key={idx} className="p-2.5 rounded bg-bad/5 border border-bad/20 flex items-center justify-between gap-3 text-ink-700">
                  <div className="truncate">
                    <span className="text-ink-400">Origin:</span> {bl.source_url} &rarr; <strong className="text-ink">{bl.target_url}</strong>
                    {bl.anchor_text && <span className="text-[10px] text-ink-500 ml-2 block sm:inline font-sans">Anchor: &ldquo;{bl.anchor_text}&rdquo;</span>}
                  </div>
                  <span className="text-bad font-bold shrink-0 px-2 py-0.5 rounded bg-bad/10">HTTP {bl.status_code}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* ─────────────────────────────────────────────────────────────
          2. CANONICAL TAG ARCHITECTURE MATRIX
          ───────────────────────────────────────────────────────────── */}
      <Card className="p-6 space-y-4 border-line bg-paper-50">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <Code2 className="w-4 h-4 text-ink-700" />
            <h3 className="font-sans text-base font-semibold text-ink">
              Canonical Tag Routing Integrity
            </h3>
          </div>
          <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-paper-200 text-ink-700">
            Health: {canonicalAudit?.canonical_health_score != null && Number.isFinite(canonicalAudit.canonical_health_score) ? `${Math.round(canonicalAudit.canonical_health_score)}/100` : 'Not measured'}
          </span>
        </div>

        <p className="text-xs text-ink-600 leading-relaxed">
          Verifies whether every indexed page defines a self-referencing absolute canonical URL or delegates equity to the authoritative master URL, preventing duplicate content penalties and split link equity.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3.5 rounded border border-line bg-paper-100/60 space-y-1">
            <span className="text-[10px] font-mono text-ink-400 block uppercase font-bold">Self-Referential</span>
            <span className="text-xl font-mono font-bold text-good">
              {canonicalAudit?.self_canonical_count ?? '—'}
            </span>
            <p className="text-[10px] text-ink-500">Authoritative master URLs</p>
          </div>

          <div className="p-3.5 rounded border border-line bg-paper-100/60 space-y-1">
            <span className="text-[10px] font-mono text-ink-400 block uppercase font-bold">Consolidated</span>
            <span className="text-xl font-mono font-bold text-ink">
              {canonicalAudit?.canonicalized_count ?? '—'}
            </span>
            <p className="text-[10px] text-ink-500">Points to parent cluster</p>
          </div>

          <div className="p-3.5 rounded border border-line bg-paper-100/60 space-y-1">
            <span className="text-[10px] font-mono text-ink-400 block uppercase font-bold">Missing Tag</span>
            <span className={`text-xl font-mono font-bold ${
              canonicalAudit?.missing_canonical_count == null ? 'text-ink-500' : canonicalAudit.missing_canonical_count > 0 ? 'text-warn' : 'text-good'
            }`}>
              {canonicalAudit?.missing_canonical_count ?? '—'}
            </span>
            <p className="text-[10px] text-ink-500">At risk of index fragmentation</p>
          </div>

          <div className="p-3.5 rounded border border-line bg-paper-100/60 space-y-1">
            <span className="text-[10px] font-mono text-ink-400 block uppercase font-bold">Broken / 404 Targets</span>
            <span className={`text-xl font-mono font-bold ${
              canonicalAudit?.broken_canonical_count == null ? 'text-ink-500' : canonicalAudit.broken_canonical_count > 0 ? 'text-bad' : 'text-good'
            }`}>
              {canonicalAudit?.broken_canonical_count ?? '—'}
            </span>
            <p className="text-[10px] text-ink-500">Direct traffic & crawl blackhole</p>
          </div>
        </div>
      </Card>

      {/* ─────────────────────────────────────────────────────────────
          3. HOST VARIANT & CANONICAL 301 CONSOLIDATION
          ───────────────────────────────────────────────────────────── */}
      {redirects && (
        <Card className="p-6 space-y-4 border-line bg-paper-50">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-ink-700" />
              <h3 className="font-sans text-base font-semibold text-ink">
                Host Variant & Apex Canonical 301 Routing
              </h3>
            </div>
            <span className={`text-xs font-mono px-2.5 py-0.5 rounded font-semibold ${
              redirects.proper_301_consolidation ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'
            }`}>
              {redirects.proper_301_consolidation ? '✓ 301 Consolidated' : 'Fragmented Variants'}
            </span>
          </div>

          <p className="text-xs text-ink-600 leading-relaxed">
            Ensures that www, non-www, HTTP, and HTTPS all 301-redirect cleanly to a single primary destination domain without redirect loops or multi-hop chains.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            {Object.entries(redirects.host_variants || {}).map(([variant, result]: [string, any]) => (
              <div key={variant} className="p-3 rounded border border-line bg-paper-100/60 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-ink-700">{variant}</span>
                  <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded font-bold ${
                    result.status_code === 200 || result.status_code === 301
                      ? 'bg-good/10 text-good'
                      : 'bg-warn/10 text-warn'
                  }`}>
                    HTTP {result.status_code}
                  </span>
                </div>
                <p className="text-[11px] text-ink-500 truncate" title={result.final_destination}>
                  &rarr; {result.final_destination || 'Resolved'}
                </p>
                <p className="text-[10px] text-ink-400 font-mono">
                  {result.hop_count ?? 1} hop(s) · {result.proper_canonical_redirect ? 'Clean' : 'Multiple Hops'}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ─────────────────────────────────────────────────────────────
          4. CRAWL CLICK DEPTH & ORPHAN PAGES
          ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Click Depth Funnel */}
        <Card className="p-6 space-y-4 border-line bg-paper-50">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-ink-700" />
              <h4 className="font-sans text-base font-semibold text-ink">
                Crawl Hierarchy & Click Depth
              </h4>
            </div>
            <span className="text-xs text-ink-500 font-mono">
              Max Depth: {clickDepth?.max_click_depth ?? 'Not measured'}
            </span>
          </div>

          <p className="text-xs text-ink-600">
            Pages requiring &gt;3 clicks from the homepage suffer severe crawl budget drops and delayed indexing.
          </p>

          <div className="space-y-2.5 pt-1 text-xs">
            {[
              { label: 'Depth 1 (Homepage & Primary Header)', count: depth1, pct: depth1 == null ? null : Math.round((depth1 / Math.max(1, totalAnalyzed)) * 100), color: 'bg-good' },
              { label: 'Depth 2 (Key Pillars & Categories)', count: depth2, pct: depth2 == null ? null : Math.round((depth2 / Math.max(1, totalAnalyzed)) * 100), color: 'bg-pine-500' },
              { label: 'Depth 3 (Sub-pages & Deep Articles)', count: depth3, pct: depth3 == null ? null : Math.round((depth3 / Math.max(1, totalAnalyzed)) * 100), color: 'bg-warn' },
              { label: 'Depth 4+ (Deep Crawl Risk)', count: depth4Plus, pct: depth4Plus == null ? null : Math.round((depth4Plus / Math.max(1, totalAnalyzed)) * 100), color: 'bg-bad' },
            ].map((tier, idx) => (
              <div key={idx} className="p-2.5 rounded bg-paper-100/60 border border-line space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-ink-700 font-medium">{tier.label}</span>
                  <span className="font-mono font-bold text-ink">{tier.count == null || tier.pct == null ? 'Not measured' : `${tier.count} pages (${tier.pct}%)`}</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-paper-200 overflow-hidden">
                  <div className={`h-full rounded-full ${tier.color}`} style={{ width: `${tier.pct ?? 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Orphan Pages */}
        <Card className="p-6 space-y-4 border-line bg-paper-50 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-ink-700" />
                <h4 className="font-sans text-base font-semibold text-ink">
                  Orphan Page Scanner
                </h4>
              </div>
              <span className={`text-xs font-mono px-2 py-0.5 rounded font-semibold ${
                orphanPages?.orphan_count == null ? 'bg-paper-100 text-ink-500' : orphanPages.orphan_count === 0 ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'
              }`}>
                {orphanPages?.orphan_count == null ? 'Not measured' : `${orphanPages.orphan_count} Orphan URLs`}
              </span>
            </div>

            <p className="text-xs text-ink-600 leading-relaxed">
              Orphan URLs have no incoming internal links in the checked crawl. This can make discovery less reliable, so confirm the URL inventory and crawl scope before prioritizing a fix.
            </p>

            {orphanPages?.orphan_urls && orphanPages.orphan_urls.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto pt-1 font-mono text-xs">
                {orphanPages.orphan_urls.map((url, idx) => (
                  <div key={idx} className="p-2 rounded bg-warn/5 border border-warn/20 text-ink-700 truncate">
                    {url}
                  </div>
                ))}
              </div>
            ) : orphanPages?.orphan_count === 0 ? (
              <div className="p-4 rounded-lg bg-good/5 border border-good/20 text-center text-xs text-good font-medium">
                ✓ No orphan URLs reported by the analyzer.
              </div>
            ) : orphanPages?.orphan_count == null ? (
              <div className="p-4 rounded-lg border border-dashed border-line text-center text-xs text-ink-500">Orphan-page analysis was not available for this run.</div>
            ) : null}
          </div>

          {/* Security & Directives Summary Footer */}
          <div className="pt-3 border-t border-line/60 flex items-center justify-between text-xs text-ink-500">
            <span className="flex items-center gap-1.5">
              <Shield className={`w-3.5 h-3.5 ${security?.score != null ? 'text-ink-500' : 'text-ink-400'}`} />
              Security audit
            </span>
            <span className="font-mono text-good font-bold">
              Score: {security?.score != null && Number.isFinite(security.score) ? `${Math.round(security.score)}/100` : 'Not measured'}
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}
