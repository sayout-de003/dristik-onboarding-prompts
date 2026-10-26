import React from 'react';
import { ExecutiveReport, Finding } from '../../../types';
import { Card } from '../../ui';
import { SeoScoreMethodology } from './SeoScoreMethodology';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Layers,
  ArrowRight,
  TrendingUp,
  FileCode,
  Image as ImageIcon,
  Sparkles,
  Search,
  ExternalLink,
  ChevronRight,
  Zap,
} from 'lucide-react';

interface SeoExecutiveOverviewProps {
  report: ExecutiveReport;
  seoFindings: Finding[];
  onNavigateTab: (tabId: string) => void;
  onSelectFinding?: (f: Finding) => void;
}

export function SeoExecutiveOverview({
  report,
  seoFindings,
  onNavigateTab,
  onSelectFinding,
}: SeoExecutiveOverviewProps) {
  const crawl = report.crawl_manifest;
  const pages = crawl?.pages || [];
  const httpStatus = report.http_status_breakdown;
  const canonicalAudit = report.canonical_audit;
  const clickDepth = report.click_depth;
  const headings = report.heading_hierarchy;
  const media = report.media_assets;
  const localSeo = report.local_seo;
  const intlSeo = report.international_seo;
  const redirects = report.host_and_redirects;

  const technicalSeoCategory = report.scores?.category_scores?.['TECHNICAL_SEO'] as ({ score?: number; status?: string } | undefined);
  const technicalScoreStatus = String(technicalSeoCategory?.status || 'MEASURED').toUpperCase();
  const rawScore = technicalSeoCategory && !['NOT_MEASURED', 'UNAVAILABLE', 'NOT_CONNECTED', 'NOT_CONFIGURED', 'SIMULATION_ONLY', 'DATA_UNAVAILABLE', 'NOT_TESTED'].includes(technicalScoreStatus)
    ? technicalSeoCategory.score
    : null;
  const seoScore = rawScore != null && Number.isFinite(rawScore) ? Math.round(rawScore) : null;

  const crawlHealth = httpStatus && httpStatus.total_urls_checked > 0
    ? Math.round((httpStatus.count_2xx / httpStatus.total_urls_checked) * 100)
    : null;

  const onPageHealth = headings?.h1_health_score != null && Number.isFinite(headings.h1_health_score)
    ? Math.round(headings.h1_health_score)
    : null;

  const assetHealth = media?.total_images_analyzed && media.total_images_analyzed > 0
    ? Math.max(0, Math.round(100 - ((media.missing_alt_count + media.missing_dimensions_count) / (media.total_images_analyzed * 2)) * 100))
    : null;

  const localHealth = localSeo?.nap_consistency_score != null && Number.isFinite(localSeo.nap_consistency_score)
    ? Math.round(localSeo.nap_consistency_score)
    : null;

  const compHealth = null;

  // Filter top critical/high findings
  const criticalFindings = seoFindings.filter((f) => f.severity === 'CRITICAL');
  const highFindings = seoFindings.filter((f) => f.severity === 'HIGH');
  const priorityFindings = [...criticalFindings, ...highFindings].slice(0, 3);

  const gapGroups = [
    {
      key: 'TECHNICAL_SEO',
      title: 'Crawlability and indexation',
      description: 'Can search engines discover the right URLs, access them, and interpret canonical and response directives?',
    },
    {
      key: 'ON_PAGE_SEO',
      title: 'Page relevance and search snippets',
      description: 'Do page titles, headings, metadata, and on-page structure accurately describe the page and its search intent?',
    },
    {
      key: 'CONTENT',
      title: 'Content depth and intent',
      description: 'Does the checked content satisfy the visitor’s question clearly and cover the page’s intended topic?',
    },
  ].map((group) => ({
    ...group,
    findings: seoFindings.filter((finding) => finding.category === group.key),
  }));

  const getScoreGrade = (score: number) => {
    if (score >= 90) return { label: 'Optimal', badge: 'bg-good/10 text-good border-good/20' };
    if (score >= 75) return { label: 'Good', badge: 'bg-pine-500/10 text-pine-600 dark:text-pine-400 border-pine-500/20' };
    if (score >= 60) return { label: 'Fair', badge: 'bg-warn/10 text-warn border-warn/20' };
    return { label: 'Needs Attention', badge: 'bg-bad/10 text-bad border-bad/20' };
  };

  const grade = seoScore != null ? getScoreGrade(seoScore) : { label: 'Not scored', badge: 'bg-paper-100 text-ink-500 border-line' };

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HERO EXECUTIVE SCORECARD & SUB-PILLAR HEALTH
          ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Main Scorecard Tile */}
        <Card className="p-6 lg:col-span-5 bg-gradient-to-br from-paper-50 via-paper-50 to-paper-100/60 border border-line shadow-sm relative overflow-hidden flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-[0.05em] text-ink-500 font-semibold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-pine-600" />
                Technical SEO Rating
              </span>
              <span className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${grade.badge}`}>
                {grade.label}
              </span>
            </div>

            <div className="flex items-baseline gap-3 pt-1">
              <span className="font-mono text-5xl font-extrabold tracking-tight text-ink">
                {seoScore != null ? seoScore : '—'}
              </span>
              <span className="text-sm font-mono text-ink-400 font-medium">/ 100</span>
            </div>

            <p className="text-xs text-ink-600 leading-relaxed">
              Evaluating crawl access, canonical URLs, page metadata, headings, and search directives for <strong className="text-ink font-medium">{report.domain}</strong>.
            </p>
          </div>

          <div className="pt-5 mt-4 border-t border-line/60 flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className="font-mono text-ink-500">Flagged Issues:</span>
              <span className="font-mono font-bold text-bad bg-bad/10 px-2 py-0.5 rounded">
                {criticalFindings.length} Critical
              </span>
              <span className="font-mono font-bold text-warn bg-warn/10 px-2 py-0.5 rounded">
                {highFindings.length} High
              </span>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTab('issues')}
              className="text-pine-600 dark:text-pine-400 font-medium hover:underline flex items-center gap-1 font-sans"
            >
              View Ledger <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </Card>

        {/* 5 Sub-Discipline Health Meters */}
        <Card className="p-6 lg:col-span-7 bg-paper-50 border border-line flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-line/60">
              <h3 className="font-sans text-sm font-semibold text-ink flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-ink-700" />
                Discipline Health Breakdown
              </h3>
              <span className="text-[11px] font-mono text-ink-400">
                Observed sub-metrics · not score weights
              </span>
            </div>

            <div className="space-y-3.5 pt-3">
              {[
                { label: 'Crawlability & HTTP Codes', score: crawlHealth, tab: 'architecture', desc: 'Share of stored responses that are HTTP 2xx' },
                { label: 'On-Page Content & SERP', score: onPageHealth, tab: 'onpage', desc: 'Stored H1 health score, when the heading audit saved one' },
                { label: 'Image alt and dimensions', score: assetHealth, tab: 'onpage', desc: 'Stored image audit. Not Core Web Vitals.' },
                { label: 'Local NAP consistency', score: localHealth, tab: 'market', desc: 'Stored NAP score, when the local module ran' },
                { label: 'Competitive comparison', score: compHealth, tab: 'market', desc: 'No competitor score is invented from rank' },
              ].map((sub, idx) => (
                <div
                  key={idx}
                  onClick={() => onNavigateTab(sub.tab)}
                  className="group cursor-pointer p-2 rounded hover:bg-paper-100 transition-colors"
                >
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-medium text-ink-700 group-hover:text-ink transition-colors flex items-center gap-1.5">
                      {sub.label}
                      <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity text-pine-600" />
                    </span>
                    <span className="font-mono font-bold text-ink">{sub.score != null ? `${sub.score}%` : 'Not measured'}</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-paper-200 overflow-hidden">
                    {sub.score != null ? (
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          sub.score >= 85
                            ? 'bg-good'
                            : sub.score >= 70
                            ? 'bg-pine-500'
                            : sub.score >= 50
                            ? 'bg-warn'
                            : 'bg-bad'
                        }`}
                        style={{ width: `${sub.score}%` }}
                      />
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <SeoScoreMethodology
        score={seoScore}
        status={technicalSeoCategory?.status}
        checkedUrls={pages.length}
        findingCount={seoFindings.length}
        onNavigate={onNavigateTab}
      />

      {/* ─────────────────────────────────────────────────────────────
          2. ENTERPRISE VITALS GRID (6 Core KPIs)
          ───────────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-sans text-sm font-semibold text-ink uppercase tracking-wider text-[11px] text-ink-500">
            Enterprise Search Vitals
          </h3>
          <span className="text-[11px] font-mono text-ink-400">
            {pages.length} URLs Crawled & Evaluated
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5">
          {/* Tile 1: HTTP 200 Pass Rate */}
          <Card
            onClick={() => onNavigateTab('architecture')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              HTTP 200 Success
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-xl font-bold text-good">
                {httpStatus && httpStatus.total_urls_checked > 0
                  ? `${Math.round((httpStatus.count_2xx / httpStatus.total_urls_checked) * 100)}%`
                  : '—'}
              </span>
              <span className="text-[11px] font-mono text-ink-400">OK</span>
            </div>
            <p className="text-[11px] text-ink-500 truncate group-hover:text-pine-600 transition-colors">
              {httpStatus?.count_2xx != null ? `${httpStatus.count_2xx} successful URLs →` : 'HTTP response data unavailable'}
            </p>
          </Card>

          {/* Tile 2: Canonical Health */}
          <Card
            onClick={() => onNavigateTab('architecture')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              Canonical Health
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-xl font-bold text-ink">
                {canonicalAudit?.canonical_health_score != null && Number.isFinite(canonicalAudit.canonical_health_score)
                  ? `${Math.round(canonicalAudit.canonical_health_score)}%`
                  : '—'}
              </span>
              <span className="text-[11px] font-mono text-good font-semibold">
                {canonicalAudit?.broken_canonical_count != null ? (canonicalAudit.broken_canonical_count ? `${canonicalAudit.broken_canonical_count} broken` : 'No broken canonicals reported') : 'Not measured'}
              </span>
            </div>
            <p className="text-[11px] text-ink-500 truncate group-hover:text-pine-600 transition-colors">
              {canonicalAudit?.self_canonical_count != null ? `${canonicalAudit.self_canonical_count} self-canonical URLs →` : 'Canonical inventory unavailable'}
            </p>
          </Card>

          {/* Tile 3: XML Sitemap */}
          <Card
            onClick={() => onNavigateTab('architecture')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              Sitemap & Robots
            </span>
            <div className="flex items-center gap-1.5">
              {crawl?.sitemap_found ? (
                <CheckCircle2 className="w-4 h-4 text-good shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-warn shrink-0" />
              )}
              <span className="font-mono text-sm font-bold text-ink">
                {crawl?.sitemap_found == null ? 'Not measured' : crawl.sitemap_found ? 'Found' : 'Not found'}
              </span>
            </div>
            <p className="text-[11px] text-ink-500 truncate font-mono group-hover:text-pine-600 transition-colors">
              {crawl?.sitemap_url ? 'Sitemap URL recorded' : crawl?.sitemap_found === false ? 'Review sitemap discovery' : 'Sitemap data unavailable'}
            </p>
          </Card>

          {/* Tile 4: Max Click Depth */}
          <Card
            onClick={() => onNavigateTab('architecture')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              Max Click Depth
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-xl font-bold text-ink">
                {clickDepth?.max_click_depth != null ? `${clickDepth.max_click_depth}` : '—'}
              </span>
              <span className="text-[11px] font-mono text-ink-500">Hops</span>
            </div>
            <p className="text-[11px] text-ink-500 truncate group-hover:text-pine-600 transition-colors">
              {clickDepth?.high_depth_warning_count != null
                ? (clickDepth.high_depth_warning_count ? `${clickDepth.high_depth_warning_count} deep pages (>3) →` : 'No deep-page warnings reported')
                : 'Click-depth data unavailable'}
            </p>
          </Card>

          {/* Tile 5: H1 Heading Structure */}
          <Card
            onClick={() => onNavigateTab('onpage')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              H1 Heading Health
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-xl font-bold text-ink">
                {headings?.h1_health_score != null && Number.isFinite(headings.h1_health_score) ? `${Math.round(headings.h1_health_score)}%` : '—'}
              </span>
              <span className="text-[11px] font-mono text-ink-500">Score</span>
            </div>
            <p className="text-[11px] text-ink-500 truncate group-hover:text-pine-600 transition-colors">
              {headings?.missing_h1 != null
                ? (headings.missing_h1.length ? `${headings.missing_h1.length} missing H1 →` : 'No missing H1 reported')
                : 'Heading data unavailable'}
            </p>
          </Card>

          {/* Tile 6: Image Optimization */}
          <Card
            onClick={() => onNavigateTab('onpage')}
            className="p-4 space-y-1.5 hover:border-pine-500/40 hover:shadow-sm transition-all cursor-pointer group"
          >
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              Image Optimization
            </span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-xl font-bold text-good">
                {media?.modern_format_count != null ? media.modern_format_count : '—'}
              </span>
              <span className="text-[11px] font-mono text-ink-400">WebP</span>
            </div>
            <p className="text-[11px] text-ink-500 truncate group-hover:text-pine-600 transition-colors">
              {media?.missing_alt_count != null
                ? (media.missing_alt_count ? `${media.missing_alt_count} missing alt →` : 'No missing alt reported')
                : 'Image alt data unavailable'}
            </p>
          </Card>
        </div>
      </div>

      <Card className="space-y-4 border-line bg-paper-50 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-pine-600">SEO gap analysis</p>
            <h3 className="mt-1 text-base font-semibold text-ink">Where the checked site needs attention</h3>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-ink-500">
              These counts come from validated findings in this report, not estimates for pages that were not checked.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab('issues')}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-pine-600 hover:underline"
          >
            Open issue ledger <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {gapGroups.map((group) => (
            <button
              type="button"
              key={group.key}
              onClick={() => onNavigateTab(group.key === 'TECHNICAL_SEO' ? 'architecture' : 'onpage')}
              className="rounded-lg border border-line bg-paper-100/60 p-4 text-left transition-colors hover:border-pine-500/40 hover:bg-paper-100"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-semibold text-ink">{group.title}</h4>
                <span className={`rounded-full px-2 py-0.5 font-mono text-xs font-bold ${group.findings.length ? 'bg-warn/10 text-warn' : 'bg-paper-200 text-ink-500'}`}>
                  {group.findings.length}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-ink-500">{group.description}</p>
              {group.findings.length > 0 ? (
                <ul className="mt-3 space-y-2 border-t border-line pt-3">
                  {group.findings.slice(0, 2).map((finding) => (
                    <li key={finding.finding_id} className="text-xs leading-5 text-ink-700">
                      <span className="font-semibold">{finding.severity}:</span> {finding.title}
                    </li>
                  ))}
                  {group.findings.length > 2 && (
                    <li className="text-[11px] font-medium text-pine-600">+{group.findings.length - 2} more findings in issue ledger</li>
                  )}
                </ul>
              ) : (
                <p className="mt-3 border-t border-line pt-3 text-[11px] leading-5 text-ink-500">
                  No validated finding published for this category in the returned report. This is not proof that every URL is issue-free.
                </p>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* ─────────────────────────────────────────────────────────────
          3. TOP PRIORITY ACTION BLOCKERS
          ───────────────────────────────────────────────────────────── */}
      {priorityFindings.length > 0 && (
        <Card className="p-5 border-line bg-paper-50 space-y-4">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-bad" />
              <h3 className="font-sans text-base font-semibold text-ink">
                High-Impact Technical Blockers
              </h3>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTab('issues')}
              className="text-xs font-medium text-pine-600 dark:text-pine-400 hover:underline flex items-center gap-1 font-sans"
            >
              All {seoFindings.length} Issues &rarr;
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {priorityFindings.map((finding) => (
              <div
                key={finding.finding_id}
                onClick={() => onSelectFinding?.(finding)}
                className="p-3.5 rounded-lg border border-line bg-paper-100/70 hover:bg-paper-100 hover:border-pine-500/40 transition-all cursor-pointer flex flex-col justify-between space-y-2 group"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded ${
                      finding.severity === 'CRITICAL' ? 'bg-bad/10 text-bad' : 'bg-warn/10 text-warn'
                    }`}>
                      {finding.severity}
                    </span>
                    <span className="text-[10px] font-mono text-ink-400">
                      {finding.category}
                    </span>
                  </div>
                  <h4 className="text-xs font-semibold text-ink group-hover:text-pine-600 transition-colors line-clamp-2">
                    {finding.title}
                  </h4>
                  <p className="text-[11px] text-ink-500 line-clamp-2 leading-relaxed">
                    {finding.description}
                  </p>
                </div>

                <div className="pt-2 border-t border-line/60 flex items-center justify-between text-[11px] text-pine-600 dark:text-pine-400 font-medium">
                  <span>Inspect evidence</span>
                  <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
