import React, { useState } from 'react';
import { ExecutiveReport, Finding } from '../../types';
import { SearchConsoleAttributionView } from '../SearchConsoleAttributionView';
import { PillarShell } from '../ui';
import { SectionExportButtons } from '../ui/SectionExportButtons';
import { SeoExecutiveOverview } from './seo/SeoExecutiveOverview';
import { SeoCrawlArchitecture } from './seo/SeoCrawlArchitecture';
import { SeoOnPageExperience } from './seo/SeoOnPageExperience';
import { SeoMarketIntelligence } from './seo/SeoMarketIntelligence';
import { SeoIssuesAndAppendix } from './seo/SeoIssuesAndAppendix';
import { AuditIndex } from '../../report/auditIndex/AuditIndex';
import { EnterpriseSeoAudit } from './seo/EnterpriseSeoAudit';

interface SeoWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
  onSelectFinding?: (f: Finding) => void;
  onOpenConnectors?: (tabId?: string) => void;
}

export type EnterpriseSeoTab =
  | 'overview'
  | 'architecture'
  | 'onpage'
  | 'market'
  | 'gsc'
  | 'issues'
  | 'index'
  | 'enterprise';

export function SeoWorkspaceView({
  report,
  analysisId,
  onSelectFinding,
  onOpenConnectors,
}: SeoWorkspaceViewProps) {
  const [activeTab, setActiveTab] = useState<EnterpriseSeoTab>('overview');

  const seoFindings = (report.findings || []).filter(
    (f) => f.category === 'TECHNICAL_SEO' || f.category === 'ON_PAGE_SEO' || f.category === 'CONTENT'
  );

  const rawScore = report.scores?.category_scores?.['TECHNICAL_SEO']?.score ?? report.honest_scores?.google_score;
  const seoScore = rawScore != null && Number.isFinite(rawScore) ? Math.round(rawScore) : null;

  // Handle tab switching with backward compatibility normalization
  const handleTabChange = (rawId: string) => {
    switch (rawId) {
      case 'crawl':
      case 'security':
        setActiveTab('architecture');
        break;
      case 'assets':
      case 'links':
        setActiveTab('onpage');
        break;
      case 'local':
      case 'international':
      case 'competitors':
        setActiveTab('market');
        break;
      case 'findings':
      case 'appendix':
        setActiveTab('issues');
        break;
      case 'overview':
      case 'architecture':
      case 'onpage':
      case 'market':
      case 'gsc':
      case 'issues':
      case 'index':
      case 'enterprise':
        setActiveTab(rawId as EnterpriseSeoTab);
        break;
      default:
        setActiveTab('overview');
    }
  };

  return (
    <PillarShell
      kicker="Discipline 1 · Technical & On-Page SEO"
      title="Search Engine Optimization (SEO)"
      description="Crawl topology, HTTP status codes, canonical routing, Google SERP truncation, heading hierarchy, local NAP consistency, and international targeting."
      scoreLabel="SEO Index"
      score={seoScore != null ? `${seoScore}/100` : '—'}
      metaLabel="Issues"
      meta={`${seoFindings.length} flagged`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <SectionExportButtons
            analysisId={analysisId || report.analysis_id || report.report_id}
            sectionKey="seo"
            sectionLabel="SEO"
          />
          {(analysisId || report.analysis_id || report.report_id) && (
            <>
              <a
                href={`/api/v1/reports/${analysisId || report.analysis_id || report.report_id}/seo-report?format=pdf&download=true`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-line bg-paper-100 hover:bg-paper-200 text-ink transition-colors"
                title="Open the dedicated SEO master audit book as a PDF"
              >
                SEO Book PDF
              </a>
              <a
                href={`/api/v1/reports/${analysisId || report.analysis_id || report.report_id}/seo-report?format=print`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-line bg-paper-100 hover:bg-paper-200 text-ink transition-colors"
                title="Open the dedicated SEO master audit book for printing"
              >
                SEO Book Print
              </a>
            </>
          )}
        </div>
      }
      tabs={[
        { id: 'overview', label: 'Executive Overview' },
        { id: 'architecture', label: 'Crawl & Architecture' },
        { id: 'onpage', label: 'On-Page & SERP' },
        { id: 'market', label: 'Local, Global & Peers' },
        { id: 'gsc', label: 'Search Console' },
        { id: 'issues', label: `Issues & URLs (${seoFindings.length})` },
        { id: 'index', label: 'Full SEO index' },
        { id: 'enterprise', label: 'Enterprise assessment' },
      ]}
      activeTab={activeTab}
      onTab={handleTabChange}
    >
      {/* ─────────────────────────────────────────────────────────────
          1. EXECUTIVE OVERVIEW TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <SeoExecutiveOverview
          report={report}
          seoFindings={seoFindings}
          onNavigateTab={handleTabChange}
          onSelectFinding={onSelectFinding}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          2. CRAWL & ARCHITECTURE TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'architecture' && (
        <SeoCrawlArchitecture report={report} />
      )}

      {/* ─────────────────────────────────────────────────────────────
          3. ON-PAGE & SERP TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'onpage' && (
        <SeoOnPageExperience report={report} />
      )}

      {/* ─────────────────────────────────────────────────────────────
          4. LOCAL, GLOBAL & COMPETITORS TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'market' && (
        <SeoMarketIntelligence report={report} />
      )}

      {/* ─────────────────────────────────────────────────────────────
          5. SEARCH CONSOLE TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'gsc' && (
        <SearchConsoleAttributionView
          domain={report.domain}
          analysisId={analysisId}
          onOpenConnectors={() => onOpenConnectors?.('google_search_console')}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          6. ISSUES & TECHNICAL URL APPENDIX TAB
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'issues' && (
        <SeoIssuesAndAppendix
          report={report}
          seoFindings={seoFindings}
          onSelectFinding={onSelectFinding}
        />
      )}

      {activeTab === 'index' && (
        <AuditIndex report={report} />
      )}

      {activeTab === 'enterprise' && (
        <EnterpriseSeoAudit analysisId={analysisId || report.analysis_id || report.report_id} />
      )}
    </PillarShell>
  );
}
