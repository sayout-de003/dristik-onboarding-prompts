import React, { useState, useEffect } from 'react';
import { ExecutiveReport, DristikCompetitiveReport } from '../../types';
import { CommercialBakeoffView } from '../CommercialBakeoffView';
import { CompetitorSideBySideBenchmark } from '../CompetitorSideBySideBenchmark';
import { CompetitorDiscoveryView } from '../CompetitorDiscoveryView';
import { CompetitorKeywordGapView } from '../CompetitorKeywordGapView';
import { CompetitiveLandscapeMap } from '../CompetitiveLandscapeMap';
import { CompetitiveEvidenceTable } from '../CompetitiveEvidenceTable';
import { Perspectives } from '../Perspectives';
import { PillarShell, Card } from '../ui';
import { SectionExportButtons } from '../ui/SectionExportButtons';
import { Compass, Loader2 } from 'lucide-react';

interface CompetitorWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
  websiteUrl?: string;
}

type CompSubTab = 'landscape_gaps' | 'bakeoff' | 'benchmark' | 'discovery' | 'keyword_gap' | 'perspectives';

export function CompetitorWorkspaceView({
  report,
  analysisId,
  websiteUrl,
}: CompetitorWorkspaceViewProps) {
  const [activeSubTab, setActiveSubTab] = useState<CompSubTab>('landscape_gaps');
  const [compReport, setCompReport] = useState<DristikCompetitiveReport | null>(
    report.competitive_report || null
  );
  const [loadingReport, setLoadingReport] = useState<boolean>(false);

  useEffect(() => {
    if (report.competitive_report) {
      setCompReport(report.competitive_report);
      return;
    }

    let isMounted = true;
    const fetchCompetitiveReport = async () => {
      setLoadingReport(true);
      try {
        const params = new URLSearchParams();
        if (analysisId) params.append('analysis_id', analysisId);
        if (report.domain) params.append('domain', report.domain);

        const res = await fetch(`/api/v1/intelligence/competitors/report?${params.toString()}`);
        if (res.ok) {
          const data: DristikCompetitiveReport = await res.json();
          if (isMounted) setCompReport(data);
        }
      } catch (err) {
        // Fall back gracefully
      } finally {
        if (isMounted) setLoadingReport(false);
      }
    };

    fetchCompetitiveReport();
    return () => {
      isMounted = false;
    };
  }, [analysisId, report.domain, report.competitive_report]);

  const bakeoff = report.competitor_bakeoff;
  const totalBakeoff = (bakeoff?.target_wins || 0) + (bakeoff?.competitor_wins || 0) + (bakeoff?.ties || 0);
  const winRate = totalBakeoff > 0 ? Math.round(((bakeoff?.target_wins || 0) / totalBakeoff) * 100) : null;

  return (
    <PillarShell
      kicker="Compare your website with competitors"
      title="Competitor comparison"
      description="Compare the available evidence for your site and selected competitors. Review search gaps, side-by-side checks and query comparisons; a difference alone does not prove what caused it."
      scoreLabel="Observed query win rate"
      score={winRate != null ? `${winRate}%` : '—'}
      metaLabel="Competitors"
      meta={bakeoff?.competitor_domain || compReport?.competitors?.[0]?.company_name || 'Not assessed'}
      actions={
        <SectionExportButtons
          analysisId={analysisId || report.analysis_id || report.report_id}
          sectionKey="competitors"
          sectionLabel="Competitors"
        />
      }
      tabs={[
        { id: 'landscape_gaps', label: 'Market comparison' },
        { id: 'bakeoff', label: 'Query comparison' },
        { id: 'benchmark', label: 'Side-by-side results' },
        { id: 'keyword_gap', label: 'Keyword gaps' },
        { id: 'discovery', label: 'Opportunity discovery' },
        { id: 'perspectives', label: 'Compare perspectives' },
      ]}
      activeTab={activeSubTab}
      onTab={(id) => setActiveSubTab(id as CompSubTab)}
    >
      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 1: UNIFIED LANDSCAPE & EVIDENCE MATRIX
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'landscape_gaps' && (
        <div className="space-y-6">
          {loadingReport && !compReport ? (
            <div className="flex items-center justify-center p-12 text-muted-foreground gap-2">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-xs">Reconstructing competitive search and AI landscape...</span>
            </div>
          ) : compReport ? (
            <>
              <CompetitiveLandscapeMap
                targetDomain={compReport.target_domain}
                targetBrand={compReport.target_brand}
                coordinates={compReport.landscape_coordinates}
                competitors={compReport.competitors}
              />

              <CompetitiveEvidenceTable
                targetDomain={compReport.target_domain}
                targetBrand={compReport.target_brand}
                competitors={compReport.competitors}
                evidenceRows={compReport.evidence_table}
                gapMatrix={compReport.gap_matrix}
                causalExplanations={compReport.causal_explanations}
              />
            </>
          ) : (
            <Card className="p-8 text-center space-y-3">
              <Compass className="w-8 h-8 text-muted-foreground mx-auto" />
              <h4 className="text-sm font-semibold text-ink">Competitive Intelligence Not Generated Yet</h4>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Crawl the website and competitor URLs or trigger a live analysis to generate continuous 2D coordinates and empirical evidence tables.
              </p>
            </Card>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 2: COMMERCIAL QUERY BAKE-OFF
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'bakeoff' && (
        <CommercialBakeoffView
          analysisId={analysisId || 'latest'}
          targetDomain={report.domain}
          initialBakeoff={report.competitor_bakeoff}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 3: SIDE-BY-SIDE BENCHMARK
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'benchmark' && (
        <CompetitorSideBySideBenchmark
          targetDomain={report.domain}
          analysisId={analysisId}
          niche={report.business_profile?.industry}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 4: KEYWORD GAP ANALYSIS
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'keyword_gap' && (
        <CompetitorKeywordGapView
          targetDomain={report.domain}
          initialCompetitors={report.business_profile?.competitors || []}
          projectId={report.project_id || 'default_project'}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 5: MARKET GAP DISCOVERY
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'discovery' && (
        <CompetitorDiscoveryView
          websiteUrl={report.website_url}
          analysisId={analysisId}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 6: THREE-WAY PERSPECTIVE
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'perspectives' && (
        <div className="space-y-6">
          <Card className="p-5 space-y-4">
            <h3 className="font-sans text-lg text-ink font-semibold">
              Three-Way Alignment Matrix
            </h3>
            <p className="text-xs text-ink-600">
              Evaluates alignment between (1) What your website declares, (2) What search and AI engines perceive, and (3) What competitors communicate.
            </p>
            <Perspectives comparison={report.three_way_comparison} />
          </Card>
        </div>
      )}
    </PillarShell>
  );
}
