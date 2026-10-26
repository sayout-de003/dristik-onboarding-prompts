import React, { useState } from 'react';
import { ExecutiveReport } from '../types';
import { categoryLabel, display, formatPercent, humanize, scoreTone } from '../lib/format';
import { alignDisplayedStory, buildDisplayedScore } from '../lib/displayedAuditScore';
import { ReQueryDiffView } from './ReQueryDiffView';
import { OutcomeTrackingView } from './OutcomeTrackingView';
import { CommercialBakeoffView } from './CommercialBakeoffView';
import { DeveloperPatchPackModal } from './DeveloperPatchPackModal';
import { CharacterSafeCopyWidget } from './CharacterSafeCopyWidget';
import { WhatsAppShareButton } from './WhatsAppShareButton';
import { GstInvoiceModal } from './GstInvoiceModal';
import { ScoringRubricModal } from './ScoringRubricModal';
import { CalibrationLeaders } from './CalibrationAxes';

interface ReportProps {
  report: ExecutiveReport;
  printable?: boolean;
  onPreviewDeck?: () => void;
  onExportPdf?: () => void;
}

export function Report({
  report,
  printable = false,
  onPreviewDeck,
  onExportPdf,
}: ReportProps) {
  const [isPatchModalOpen, setIsPatchModalOpen] = useState(false);
  const [isGstModalOpen, setIsGstModalOpen] = useState(false);
  const [showRubricModal, setShowRubricModal] = useState(false);
  const profile = report.business_profile;
  const scores = report.scores;
  const categories = Object.entries(scores.category_scores || {});
  const honest = report.honest_scores;
  const commEvals = report.commercial_evaluations || [];
  const targetAnalysisId = report.analysis_id || report.report_id;

  // Honest score values if present, or category scores if present, else null
  const humanScore = honest?.human_score ?? (scores.category_scores?.['UX_CONVERSION']?.score != null ? Math.round(scores.category_scores['UX_CONVERSION'].score * 0.95) : null);
  const googleScore = honest?.google_score ?? (scores.category_scores?.['TECHNICAL_SEO']?.score != null ? Math.round(scores.category_scores['TECHNICAL_SEO'].score * 0.95) : null);
  const aiScore = honest?.ai_citation_score != null
    ? honest.ai_citation_score
    : (honest?.ai_visibility_status === 'MEASURED' ? honest?.ai_visibility_score ?? null : null);
  const scoreBand = honest?.score_band ?? (aiScore != null ? (aiScore >= 75 ? 'Citation Ready' : aiScore >= 50 ? 'Fragile Presence' : 'Low readiness') : 'Pending Verification');
  const evidenceRefs = honest?.evidence_refs || report.findings.slice(0, 6).flatMap((f) => f.evidence_refs || []);
  const uniqueEvRefs = Array.from(new Set(evidenceRefs)).slice(0, 8);
  const integrityGate = (report.quality_gate_results?.final_report_integrity ?? null) as {
    status?: string;
    certified?: boolean;
    finding_count?: number;
    evidence_id_count?: number;
    unsupported_finding_ids?: string[];
    warnings?: string[];
  } | null;
  const crawledPages = Number(report.crawl_summary?.total_pages_crawled ?? 0);
  const discoveredPages = Number(report.crawl_summary?.total_pages_discovered ?? 0);
  const evidenceRecordCount = Object.keys(report.evidence_ledger || {}).length;
  const integrityLabel = integrityGate?.certified
    ? 'Evidence integrity passed'
    : report.certification_status === 'NOT_CERTIFIED' || integrityGate?.status === 'PASS_WITH_EVIDENCE_GAPS'
      ? 'Evidence gaps disclosed'
      : 'Integrity certification unavailable';

  return (
    <article className={printable ? 'space-y-10' : 'space-y-10'}>
      {!printable && (
        <section
          aria-label="Audit evidence and coverage status"
          className={`rounded-xl border p-4 md:p-5 ${integrityGate?.certified ? 'border-emerald-200 bg-emerald-50/70' : 'border-amber-200 bg-amber-50/70'}`}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-ink-500">Audit integrity</p>
              <h3 className="mt-1 text-base font-semibold text-ink">{integrityLabel}</h3>
              <p className="mt-1 max-w-3xl text-sm text-ink-600">
                {integrityGate?.certified
                  ? 'The final report passed deterministic identity, score and evidence-link checks.'
                  : integrityGate?.warnings?.length
                    ? integrityGate.warnings.join(' ')
                    : 'This report has no recorded final integrity-gate result. Do not interpret missing measurements as zero or as a passing result.'}
              </p>
            </div>
            <span className="rounded-full border border-line bg-white/80 px-2.5 py-1 text-xs font-semibold text-ink-700">
              {report.certification_status || 'NOT_ASSESSED'}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-lg border border-line/70 bg-white/80 p-3">
              <p className="text-xs text-ink-500">Pages inspected</p>
              <p className="mt-1 text-xl font-semibold text-ink">{crawledPages || '—'}</p>
            </div>
            <div className="rounded-lg border border-line/70 bg-white/80 p-3">
              <p className="text-xs text-ink-500">Pages discovered</p>
              <p className="mt-1 text-xl font-semibold text-ink">{discoveredPages || '—'}</p>
            </div>
            <div className="rounded-lg border border-line/70 bg-white/80 p-3">
              <p className="text-xs text-ink-500">Evidence records</p>
              <p className="mt-1 text-xl font-semibold text-ink">{evidenceRecordCount || integrityGate?.evidence_id_count || '—'}</p>
            </div>
            <div className="rounded-lg border border-line/70 bg-white/80 p-3">
              <p className="text-xs text-ink-500">Findings checked</p>
              <p className="mt-1 text-xl font-semibold text-ink">{integrityGate?.finding_count ?? '—'}</p>
            </div>
          </div>
          {integrityGate?.unsupported_finding_ids?.length ? (
            <p className="mt-3 text-sm font-medium text-amber-900">
              {integrityGate.unsupported_finding_ids.length} finding(s) lack linked evidence and must not be treated as verified.
            </p>
          ) : null}
          {discoveredPages > crawledPages && crawledPages > 0 ? (
            <p className="mt-3 text-sm text-ink-600">
              Sampled coverage: inspected {crawledPages} of {discoveredPages} discovered pages. Site-wide conclusions must be labeled as inferred unless the full relevant scope was verified.
            </p>
          ) : null}
          {integrityGate?.warnings?.length ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-600">
              {integrityGate.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
            </ul>
          ) : null}
        </section>
      )}
      {/* Header with Title and Global Action Buttons */}
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-6">
        <div className="space-y-1">
          <p className="label">Report</p>
          <h2 className="font-sans text-3xl md:text-4xl text-ink tracking-tight">
            {display(report.domain)}
          </h2>
          <p className="text-sm text-ink-500">
            {display(report.generated_at)} · {display(report.website_url)}
          </p>
        </div>

        {!printable && (
          <div className="no-print flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsPatchModalOpen(true)}
              className="btn-primary px-3.5 py-2 text-sm"
            >
              Developer fixes
            </button>
            <WhatsAppShareButton
              analysisId={targetAnalysisId}
              domain={report.domain}
              summaryText={report.whatsapp_summary}
            />
            <button
              type="button"
              onClick={() => setShowRubricModal(true)}
              className="btn-secondary px-3 py-2 text-sm"
            >
              Scoring method
            </button>
            <button
              type="button"
              onClick={() => setIsGstModalOpen(true)}
              className="btn-secondary px-3 py-2 text-sm"
            >
              Billing receipt
            </button>
            <button
              type="button"
              onClick={() => {
                const id = report.analysis_id || report.report_id;
                if (id) window.open(`/api/v1/reports/${id}/audit-book?format=pdf`, '_blank');
              }}
              className="btn-primary px-3 py-2 text-sm flex items-center gap-1.5 font-bold shadow-sm"
              title="Download Complete Master Audit Book PDF (All Disciplines: SEO, GEO, AEO, CRO, Competitors, Roadmap)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              Download full audit PDF
            </button>
            {onPreviewDeck && (
              <button
                type="button"
                onClick={onPreviewDeck}
                className="btn-secondary px-3 py-2 text-sm"
              >
                Deck
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                const id = report.analysis_id || report.report_id;
                if (id) window.open(`/api/v1/reports/${id}/deck.pptx`, '_blank');
              }}
              className="btn-primary px-3.5 py-2 text-sm flex items-center gap-1.5"
              title="Download 70+ Slide PowerPoint Presentation Deck (.pptx)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              PPT Deck (70+ Slides)
            </button>
          </div>
        )}
      </header>

      {/* ========================================================================= */}
      {/* FEATURE 7 (PINNED PAGE-1): WHAT TO IGNORE THIS MONTH                      */}
      {/* ========================================================================= */}
      <section className="card p-5 border-l-2 border-warn rounded-l-none">
        <h3 className="label text-warn mb-2">Ignore for now</h3>
        <p className="text-sm text-ink leading-relaxed">
          {display(report.consultant_advice_what_to_ignore)}
        </p>
      </section>

      {/* ========================================================================= */}
      {/* FEATURE 6: HONEST 3-SCORES (HUMAN, GOOGLE, AI CITATION)                    */}
      {/* ========================================================================= */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-line pb-2">
          <div>
            <h3 className="section-title">Honest scores</h3>
            <p className="text-sm text-ink-500 mt-1">Human, search, and AI citation. No invented revenue loss.</p>
          </div>
          <span className="score-pill">{scoreBand}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Score 1: Human */}
          <div className="p-4 sheet border border-line rounded-lg shadow-2xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="label text-ink-700">
                1. Human Score
              </span>
              <span className="text-xs font-semibold text-ink-400">5-Sec Clarity + CTA</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-sans font-bold text-ink">{humanScore != null ? Math.round(humanScore) : '—'}</span>
              <span className="text-xs text-ink-400">/ 100</span>
            </div>
            <p className="text-xs text-ink-700 leading-relaxed">
              {honest?.human_summary || 'No human-score summary was stored.'}
            </p>
          </div>

          {/* Score 2: Google */}
          <div className="p-4 sheet border border-line rounded-lg shadow-2xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="label text-ink-700">
                2. Google Score
              </span>
              <span className="text-xs font-semibold text-ink-400">Technical & Schema</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-sans font-bold text-ink">{googleScore != null ? Math.round(googleScore) : '—'}</span>
              <span className="text-xs text-ink-400">/ 100</span>
            </div>
            <p className="text-xs text-ink-700 leading-relaxed">
              {honest?.google_summary || 'No search-score summary was stored.'}
            </p>
          </div>

          {/* Score 3: AI Citation */}
          <div className="p-4 bg-good/10 border border-good/30 rounded-lg shadow-2xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="label text-good">
                3. AI Citation Score
              </span>
              <span className="text-xs font-semibold text-good">ChatGPT & Perplexity</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-sans font-bold text-good">{aiScore != null ? Math.round(aiScore) : '—'}</span>
              <span className="text-xs text-good/70">/ 100</span>
            </div>
            <p className="text-xs text-ink-700 leading-relaxed">
              {honest?.ai_citation_summary || 'No AI-score summary was stored.'}
            </p>
          </div>
        </div>

        {/* Evidence Verification Footnote */}
        {uniqueEvRefs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] text-ink-500">
            <span className="font-semibold">Verified DOM Evidence IDs:</span>
            {uniqueEvRefs.map((ref) => (
              <span key={ref} className="font-mono bg-paper-50 text-ink px-1.5 py-0.5 rounded border border-line">
                {ref}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* ========================================================================= */}
      {/* FEATURE 1: RE-QUERY AFTER PATCH (BEFORE -> AFTER CITATION READINESS)      */}
      {/* ========================================================================= */}
      <section>
        <ReQueryDiffView
          analysisId={targetAnalysisId}
          evaluations={commEvals}
          onRequerySuccess={() => {}}
        />
      </section>

      <section>
        <OutcomeTrackingView analysisId={targetAnalysisId} />
      </section>

      {/* ========================================================================= */}
      {/* FEATURE 2: 1-COMPETITOR BAKE-OFF ON THE 6 COMMERCIAL QUESTIONS            */}
      {/* ========================================================================= */}
      <section>
        <CommercialBakeoffView
          analysisId={targetAnalysisId}
          targetDomain={report.domain}
          initialBakeoff={report.competitor_bakeoff}
        />
      </section>

      {/* ========================================================================= */}
      {/* FEATURE 4: CHARACTER-SAFE COPY WITH LIVE COUNTS                           */}
      {/* ========================================================================= */}
      <section>
        <CharacterSafeCopyWidget initialCopy={report.character_safe_copy} />
      </section>

      {/* Strategic Story & Business Profile Grid */}
      <section className="sheet border border-line rounded-lg p-6 space-y-4">
        <div>
          <span className="label text-ink-500">Executive Narrative</span>
          <p className="text-base leading-relaxed text-ink font-sans mt-1">
            {display(alignDisplayedStory(report.story_summary, report.scores?.overall_score, buildDisplayedScore(report)))}
          </p>
          <div className="mt-4">
            <CalibrationLeaders findings={report.findings || []} />
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs border-t border-line pt-4">
          <div>
            <span className="label text-[10px] block">Business Name</span>
            <p className="font-medium text-ink mt-0.5">{display(profile.business_name)}</p>
          </div>
          <div>
            <span className="label text-[10px] block">Commercial Intent</span>
            <p className="font-medium text-ink capitalize mt-0.5">{humanize(profile.primary_intent)}</p>
          </div>
          <div>
            <span className="label text-[10px] block">Niche & Industry</span>
            <p className="font-medium text-ink mt-0.5">{display(profile.industry)}</p>
          </div>
          <div>
            <span className="label text-[10px] block">Target Audience</span>
            <p className="font-medium text-ink mt-0.5">{display(profile.target_audience)}</p>
          </div>
        </div>
      </section>

      {/* Strengths vs Bottlenecks */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border border-good/30 bg-good/10 p-5 rounded-lg space-y-2">
          <span className="label text-good flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-good"></span>
            What The Site Gets Right
          </span>
          <ul className="space-y-1.5 text-xs text-ink-700">
            {report.what_site_gets_right?.map((item, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-good font-bold">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="border border-bad/30 bg-bad/10 p-5 rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <span className="label text-bad flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-bad"></span>
              What Is Holding It Back
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-good/10 text-good border border-good/30">
               Verified DOM Evidence
            </span>
          </div>
          <ul className="space-y-1.5 text-xs text-ink-700">
            {report.what_is_holding_it_back?.map((item, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-bad font-bold">×</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Exploratory Hypotheses (Segregated unverified inferences) */}
      {report.exploratory_hypotheses && report.exploratory_hypotheses.length > 0 && (
        <section className="border border-line bg-paper-100 p-5 rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <span className="label text-ink-700 flex items-center gap-1.5 font-bold">
              <span></span>
              Exploratory Hypotheses (Single-Source Cognitive Deductions)
            </span>
            <span className="font-mono text-[9px] px-2 py-0.5 rounded bg-paper-100 text-ink-700 border border-line">
              Gated From Executive Blockers · Max Medium Severity
            </span>
          </div>
          <p className="text-xs text-ink-700">
            These deductions are advisory hypotheses based on copy positioning and buyer psychology. They require empirical user research or first-party analytics (GA4) before being elevated to verified engineering constraints.
          </p>
          <ul className="space-y-1.5 text-xs text-ink-700">
            {report.exploratory_hypotheses.slice(0, 4).map((h, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-ink-700 font-bold">~</span>
                <span className="font-medium">{h.title}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Verified Findings Log */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-line pb-2">
          <span className="label text-ink">
            Verified Findings ({report.findings.length})
          </span>
          <span className="text-xs text-ink-500">Strict DOM-anchored evidence</span>
        </div>

        <div className="space-y-3">
          {report.findings.slice(0, 10).map((f) => (
            <div key={f.finding_id} className="border border-line rounded-md p-4 space-y-1 sheet">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ink">{f.title}</span>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-paper-50 text-ink border border-line">
                  {f.severity} · {categoryLabel(f.category)}
                </span>
              </div>
              <p className="text-xs text-ink-700 leading-relaxed">{f.description}</p>
              <p className="text-xs text-good font-medium pt-1">
                Recommendation: {f.recommendation}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Developer Patch Pack Modal */}
      <DeveloperPatchPackModal
        analysisId={targetAnalysisId}
        domain={report.domain}
        isOpen={isPatchModalOpen}
        onClose={() => setIsPatchModalOpen(false)}
      />

      {/* India Commercial Receipt & UPI Modal */}
      <GstInvoiceModal
        isOpen={isGstModalOpen}
        onClose={() => setIsGstModalOpen(false)}
        domain={report.domain}
      />

      {/* Scoring Rubric Modal */}
      <ScoringRubricModal
        isOpen={showRubricModal}
        onClose={() => setShowRubricModal(false)}
      />
    </article>
  );
}
