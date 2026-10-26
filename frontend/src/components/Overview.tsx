import React from 'react';
import {
  BusinessProfile,
  OverallScoreResult,
  SemanticBusinessRepresentation,
  ContradictionReport,
  HonestScores,
  ExecutiveReport,
  TabId,
} from '../types';
import { synthesizePillars } from '../lib/pillarSynthesis';
import { alignDisplayedStory, buildDisplayedScore } from '../lib/displayedAuditScore';
import { display, scoreTone } from '../lib/format';
import { ExecutiveTopActions } from './ExecutiveTopActions';
import { CalibrationLeaders } from './CalibrationAxes';
import { Card, Section } from './ui';
import {
  Search,
  Sparkles,
  Bot,
  Zap,
  Swords,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Building2,
  Target,
  FileCheck,
  Activity,
  GitBranch,
} from 'lucide-react';

interface OverviewProps {
  scores: OverallScoreResult;
  honestScores?: HonestScores;
  profile: BusinessProfile;
  semantic?: SemanticBusinessRepresentation;
  contradictions?: ContradictionReport[];
  story: string;
  opportunity: string;
  strengths: string[];
  blockers: string[];
  ignore: string;
  report?: ExecutiveReport;
  onNavigate?: (tab: TabId) => void;
  onOpenConnectors?: (tabId?: any) => void;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label mb-1">{label}</p>
      <p className="text-ink-700 font-medium">{value}</p>
    </div>
  );
}

function formatContradictionText(raw: any): string {
  if (!raw) return '';
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed.replace(/'/g, '"'));
        const parts = [];
        if (parsed.contradiction) parts.push(parsed.contradiction);
        if (parsed.evidence) parts.push(parsed.evidence);
        if (parsed.business_impact) parts.push(`Business Impact: ${parsed.business_impact}`);
        if (parts.length > 0) return parts.join(' — ');
      } catch {
        /* fallback */
      }
    }
    return raw;
  }
  if (typeof raw === 'object') {
    const parts = [];
    if (raw.contradiction) parts.push(raw.contradiction);
    if (raw.evidence) parts.push(raw.evidence);
    if (raw.business_impact) parts.push(`Business Impact: ${raw.business_impact}`);
    if (parts.length > 0) return parts.join(' — ');
  }
  return String(raw);
}

export function Overview({
  scores,
  honestScores,
  profile,
  semantic,
  contradictions,
  story,
  opportunity,
  strengths,
  blockers,
  ignore,
  report,
  onNavigate,
}: OverviewProps) {
  const rollup = synthesizePillars(report);
  const activeContradictions = contradictions || (semantic?.contradiction ? [semantic.contradiction] : []);
  const displayed = report ? buildDisplayedScore(report) : null;
  const overallScore = displayed?.composite ?? null;

  const disciplineCards = [
    {
      id: 'seo' as TabId,
      name: 'SEO: Search performance',
      shortName: 'SEO',
      icon: Search,
      score: rollup.seo.score,
      grade: rollup.seo.grade,
      summary: 'Checks how search engines can crawl, understand, and navigate the site, including metadata, links, redirects, and sitemaps.',
      issuesCount: rollup.seo.findingsCount,
      color: 'text-ink-700',
    },
    {
      id: 'geo' as TabId,
      name: 'GEO: AI search readiness',
      shortName: 'GEO',
      icon: Sparkles,
      score: rollup.geo.score,
      grade: rollup.geo.grade,
      summary: 'Checks whether site content is easy for AI systems to interpret. Actual AI citations require separate live measurement.',
      issuesCount: rollup.geo.findingsCount,
      color: 'text-good',
    },
    {
      id: 'aeo' as TabId,
      name: 'AEO: Answers and structured data',
      shortName: 'AEO',
      icon: Bot,
      score: rollup.aeo.score,
      grade: rollup.aeo.grade,
      summary: 'Checks structured data and how clearly pages answer specific questions. Coverage depends on the data available to this audit.',
      issuesCount: rollup.aeo.findingsCount,
      color: 'text-ink-700',
    },
    {
      id: 'cro' as TabId,
      name: 'CRO: Conversion experience',
      shortName: 'CRO',
      icon: Zap,
      score: rollup.cro.score,
      grade: rollup.cro.grade,
      summary: 'Reviews the clarity of key messages, calls to action, forms, and other factors that can affect conversion.',
      issuesCount: rollup.cro.findingsCount,
      color: 'text-warn',
    },
    {
      id: 'competitors' as TabId,
      name: 'Competitor comparison',
      shortName: 'Competitors',
      icon: Swords,
      score: rollup.competitors.score,
      grade: rollup.competitors.grade,
      summary: 'Compares available competitor signals to identify differences and possible opportunities.',
      issuesCount: rollup.competitors.findingsCount,
      color: 'text-bad',
    },
  ];

  return (
    <div className="space-y-8">
      {/* ─────────────────────────────────────────────────────────────
          1. ENTERPRISE SCORECARD HERO
          ───────────────────────────────────────────────────────────── */}
      <Card className="p-6 sm:p-8 bg-paper-100/90 border border-line relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-700 font-bold">
                Audit summary
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-paper-50 border border-line text-ink-500 font-semibold">
                {report ? 'Report snapshot' : 'Awaiting report'}
              </span>
            </div>
            <h1 className="font-sans text-3xl sm:text-4xl text-ink font-semibold tracking-tight">
              {report?.domain || profile?.business_name || 'Website Audit Intelligence'}
            </h1>
            <p className="text-xs text-ink-600 leading-relaxed">
              A summary of the pages checked in this audit. A readiness score is not the same as proof that AI search engines cite the site.
            </p>
            {typeof report?.crawl_manifest?.crawl_health?.sampling_note === 'string' && (
              <p className="text-xs text-ink-700 leading-relaxed border-l-2 border-line pl-3">
                {String(report.crawl_manifest.crawl_health.sampling_note)}
              </p>
            )}
          </div>

          <div className="flex items-center gap-4 shrink-0 bg-paper-50 p-4 rounded-xl border border-line">
            <div className="text-right">
              <span className="label text-[10px] text-ink-500 block">Overall Score</span>
              <span className={`font-sans text-4xl sm:text-5xl font-bold leading-none ${overallScore != null ? scoreTone(overallScore) : 'text-ink-400'}`}>
                {overallScore != null ? overallScore.toFixed(1) : '—'}
              </span>
              <span className="text-xs text-ink-400 block mt-0.5">/ 100</span>
            </div>
            <div className="h-12 w-px bg-line" />
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-1.5 font-mono">
                <span className="text-ink-400">Pages:</span>
                <span className="font-bold text-ink">{report?.crawl_manifest?.pages?.length ?? '—'}</span>
              </div>
              <div className="flex items-center gap-1.5 font-mono">
                <span className="text-ink-400">Issues:</span>
                <span className="font-bold text-ink">{report?.findings?.length ?? '—'}</span>
              </div>
              <div className="flex items-center gap-1.5 font-mono">
                <span className="text-ink-400">Patches:</span>
                <span className="font-bold text-good">{Array.isArray(report?.code_patches) || Array.isArray(report?.remediation_patches) ? (report?.code_patches?.length || 0) + (report?.remediation_patches?.length || 0) : '—'} {Array.isArray(report?.code_patches) || Array.isArray(report?.remediation_patches) ? 'ready' : 'not reported'}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* ─────────────────────────────────────────────────────────────
          1b. SCORING PERSPECTIVE & HARMONY BRIDGE
          ───────────────────────────────────────────────────────────── */}
      {report?.scoring_explanation && (
        <Card className="p-4 bg-paper-50 border-l-2 border-line rounded-l-none text-xs space-y-1.5">
          <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold text-ink-700 uppercase tracking-[0.04em]">
            <Activity className="w-3.5 h-3.5" /> Multi-Perspective Scoring Harmony
          </div>
          <p className="text-ink-700 leading-relaxed">
            {report.scoring_explanation}
          </p>
        </Card>
      )}

      {/* ─────────────────────────────────────────────────────────────
          1c. CAUSAL GROWTH BOTTLENECKS (Root-Cause Attribution)
          ───────────────────────────────────────────────────────────── */}
      {report?.causal_diagnostic_chains && report.causal_diagnostic_chains.length > 0 && (
        <Section title="Causal Growth Bottlenecks & Strategic Attribution">
          <div className="space-y-4">
            <p className="text-xs text-ink-500">
              Causal intelligence models the exact mechanism linking observed defects to business consequences, verifiable remediations, and measured outcomes.
            </p>
            <div className="grid grid-cols-1 gap-4">
              {report.causal_diagnostic_chains.map((chain, idx) => (
                <div key={chain.bottleneck_id || idx} className="card p-5 border border-line hover:border-ink transition-all space-y-4 bg-paper-50/60">
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-line">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-paper-200 text-ink-700 uppercase">
                        {chain.primary_category}
                      </span>
                      <h3 className="font-sans text-base font-semibold text-ink">
                        {chain.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-warn/10 text-warn font-semibold">
                        {chain.severity}
                      </span>
                      <span className="text-[11px] font-mono text-ink-500">
                        {Math.round((chain.confidence || 0.9) * 100)}% confidence
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-2 p-3 rounded-lg bg-paper-100 border border-line/60">
                      <span className="label text-ink-500 block font-mono text-[10px]">1. Observed Symptoms</span>
                      <ul className="list-disc pl-4 space-y-1 text-ink-700">
                        {chain.observed_symptoms.map((sym, sIdx) => (
                          <li key={sIdx}>{sym}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="space-y-2 p-3 rounded-lg bg-paper-100 border border-line/60">
                      <span className="label text-ink-500 block font-mono text-[10px]">2. Inferred Root Cause</span>
                      <p className="text-ink-700 font-medium leading-relaxed">
                        {chain.inferred_root_cause}
                      </p>
                      <div className="pt-2 border-t border-line/40">
                        <span className="label text-warn block font-mono text-[10px]">Business Consequence:</span>
                        <p className="text-ink-600 mt-0.5">{chain.business_consequence}</p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pt-1">
                    <div className="p-3 rounded-lg bg-paper-100 border border-line space-y-1">
                      <span className="label text-ink-700 block font-mono text-[10px]">3. Prescribed Remediation</span>
                      <p className="text-ink-700 font-medium">{chain.prescribed_remediation}</p>
                      <p className="text-[11px] text-ink-500 mt-1 italic">{chain.expected_mechanism}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-paper-100 border border-line/60 space-y-1">
                      <span className="label text-ink-500 block font-mono text-[10px]">4. Automated Verification</span>
                      <p className="text-ink-700">{chain.verification_step}</p>
                      {chain.external_verification && (
                        <p className="text-[11px] text-ink-500 mt-1">{chain.external_verification}</p>
                      )}
                    </div>

                    <div className="p-3 rounded-lg bg-good/5 border border-good/20 space-y-1">
                      <span className="label text-good block font-mono text-[10px]">5. Target Outcome Shift</span>
                      <p className="text-ink-700 font-bold">{chain.projected_outcome}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Section>
      )}

      {/* ─────────────────────────────────────────────────────────────
          2. CORE DISCIPLINE WORKSPACE TILES (Direct Jump Links)
          ───────────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3 px-1">
          <p className="text-xs font-mono font-bold uppercase tracking-[0.04em] text-ink-500">
            Core Disciplines (Separated)
          </p>
          <span className="text-xs text-ink-400">Click card to open dedicated workspace</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {disciplineCards.map((disc) => {
            const Icon = disc.icon;
            return (
              <div
                key={disc.id}
                role="button"
                tabIndex={0}
                aria-label={`Open ${disc.name} assessment`}
                onClick={() => onNavigate?.(disc.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onNavigate?.(disc.id);
                  }
                }}
                className="card p-5 hover:border-ink hover:shadow-md transition-all cursor-pointer space-y-3 flex flex-col justify-between group focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className={`w-4 h-4 ${disc.color}`} />
                      <span className="font-semibold text-ink text-sm">{disc.shortName}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={`font-mono text-sm font-bold ${disc.score != null ? scoreTone(disc.score) : "text-ink-400"}`}>
                        {disc.score != null ? Math.round(disc.score) : '—'}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-paper-200 text-ink-600">
                        {disc.score != null ? disc.grade : "Not measured"}
                      </span>
                    </div>
                  </div>
                  <h3 className="font-sans text-base font-semibold text-ink group-hover:text-ink transition-colors">
                    {disc.name}
                  </h3>
                  <p className="text-xs text-ink-500 line-clamp-2 leading-relaxed">
                    {disc.summary}
                  </p>
                </div>

                <div className="pt-2 border-t border-line/60 flex items-center justify-between text-xs">
                  <span className="font-mono text-ink-400 text-[11px]">
                    {disc.issuesCount} findings logged
                  </span>
                  <span className="text-ink-700 font-medium flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                    Inspect <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. IDENTITY CONFLICTS (If Any)
          ───────────────────────────────────────────────────────────── */}
      {activeContradictions.length > 0 && (
        <Card className="border-l-2 border-warn rounded-l-none">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <p className="label text-warn flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> Identity & Categorization Conflict
            </p>
            <span className="text-xs text-ink-500">
              {activeContradictions[0].confidence != null
                ? `${Math.round(activeContradictions[0].confidence * 100)}% confidence`
                : 'Calibrating'}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs mb-2">
            <Field label="Declared Site Type" value={activeContradictions[0].declared_type || 'Unspecified'} />
            <Field label="Detected DOM Signals" value={display(activeContradictions[0].detected_type)} />
          </div>
          <p className="text-xs text-ink-700 leading-relaxed">
            {formatContradictionText(activeContradictions[0].reason)}
          </p>
        </Card>
      )}

      {/* ─────────────────────────────────────────────────────────────
          4. EXECUTIVE STORY & PRIMARY OPPORTUNITY
          ───────────────────────────────────────────────────────────── */}
      <Section title="Executive Summary & Opportunity">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2 space-y-2 p-5">
            <p className="label text-ink-500">Executive Narrative</p>
            <p className="text-sm text-ink-700 leading-relaxed font-sans text-[15px]">
              {display(displayed ? alignDisplayedStory(story, scores?.overall_score, displayed) : story)}
            </p>
            <CalibrationLeaders findings={report?.findings || []} />
          </Card>
          <Card className="space-y-2 p-5 bg-paper-100 border-line">
            <p className="label text-ink-700 flex items-center gap-1">
              <Lightbulb className="w-3.5 h-3.5" /> Primary Strategic Opportunity
            </p>
            <p className="text-xs text-ink-700 leading-relaxed font-medium">
              {display(opportunity)}
            </p>
          </Card>
        </div>
      </Section>

      {/* ─────────────────────────────────────────────────────────────
          5. STRATEGIC SIGNALS: WORKING VS BLOCKERS VS WHAT TO IGNORE
          ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 space-y-3">
          <div className="flex items-center gap-1.5 text-good">
            <CheckCircle2 className="w-4 h-4" />
            <h4 className="label text-good">What Site Gets Right</h4>
          </div>
          {strengths.length === 0 ? (
            <p className="text-xs text-ink-400">—</p>
          ) : (
            <ul className="space-y-2 text-xs text-ink-700 list-disc pl-4">
              {strengths.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <div className="flex items-center gap-1.5 text-warn">
            <AlertTriangle className="w-4 h-4" />
            <h4 className="label text-warn">What Is Holding It Back</h4>
          </div>
          {blockers.length === 0 ? (
            <p className="text-xs text-ink-400">—</p>
          ) : (
            <ul className="space-y-2 text-xs text-ink-700 list-disc pl-4">
              {blockers.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <div className="flex items-center gap-1.5 text-ink-500">
            <FileCheck className="w-4 h-4" />
            <h4 className="label text-ink-500">What to Ignore (Low ROI)</h4>
          </div>
          <p className="text-xs text-ink-600 leading-relaxed">
            {display(ignore)}
          </p>
        </Card>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          6. BUSINESS PROFILE & SEMANTIC GROUNDING
          ───────────────────────────────────────────────────────────── */}
      <Section title="Business Profile & Positioning">
        <Card className="p-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <Field label="Business Name" value={profile.business_name || report?.domain || '—'} />
            <Field label="Industry / Niche" value={`${profile.industry || 'General'} · ${profile.niche || 'Web'}`} />
            <Field label="Target Audience" value={profile.target_audience || 'General Commercial'} />
            <Field label="Business Model" value={profile.business_model || 'Enterprise / B2B'} />
          </div>

          <div className="pt-3 border-t border-line text-xs grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="label mb-1">5-Second Value Proposition</p>
              <p className="text-ink-700 italic">&quot;{profile.value_proposition || 'Not explicitly extracted'}&quot;</p>
            </div>
            <div>
              <p className="label mb-1">Primary Call to Action (CTA)</p>
              <p className="text-good font-mono font-bold">&quot;{profile.primary_cta || 'Not extracted'}&quot;</p>
            </div>
          </div>
        </Card>
      </Section>

      {/* ─────────────────────────────────────────────────────────────
          7. TOP 10 EXECUTIVE PRIORITY ACTIONS
          ───────────────────────────────────────────────────────────── */}
      {report && (
        <Section title="Priority Remediation Plan">
          <ExecutiveTopActions
            report={report}
          />
        </Section>
      )}
    </div>
  );
}
