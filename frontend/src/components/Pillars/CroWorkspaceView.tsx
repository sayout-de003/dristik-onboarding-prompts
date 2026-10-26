import React, { useState } from 'react';
import { ExecutiveReport, Finding, CtaAuditItem } from '../../types';
import { LifecycleRevenueIntelligenceView } from '../LifecycleRevenueIntelligenceView';
import { LeadGenOpportunitiesView } from '../LeadGenOpportunitiesView';
import { CroIntelligencePanel } from './CroIntelligencePanel';
import { CroAnalyticsDashboard } from './CroAnalyticsDashboard';
import { PillarShell, Card } from '../ui';
import { SectionExportButtons } from '../ui/SectionExportButtons';
import {
  Zap,
  MousePointerClick,
  Eye,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  DollarSign,
  Layers,
  Sparkles,
  Search,
  Scale,
  Award,
  Lock,
  FileCheck,
} from 'lucide-react';

interface CroWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
  onDeployRemediation?: () => void;
  onSelectFinding?: (f: Finding) => void;
}

type CroSubTab =
  | 'overview'
  | 'ctas'
  | 'valueprop'
  | 'trust'
  | 'pricing'
  | 'forms'
  | 'findings'
  | 'revenue'
  | 'leadgen'
  | 'analytics'
  | 'index';

export function CroWorkspaceView({
  report,
  analysisId,
  onDeployRemediation,
  onSelectFinding,
}: CroWorkspaceViewProps) {
  const [activeSubTab, setActiveSubTab] = useState<CroSubTab>('overview');
  const [ctaFilter, setCtaFilter] = useState<'ALL' | 'HIGH_INTENT' | 'EXPLORATORY' | 'PASSIVE_GENERIC'>('ALL');
  const [ctaSearch, setCtaSearch] = useState<string>('');
  const [findingSeverityFilter, setFindingSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');

  const profile = report.business_profile;
  const croAudit = report.cro_audit;
  const formAudit = report.form_audit || croAudit?.form_friction;
  const honest = report.honest_scores;

  const categoryCroScore = report.scores?.category_scores?.['UX_CONVERSION']?.score;
  // Use only CRO-specific measured scores; never substitute a general site score.
  const croScore: number | null = croAudit?.overall_cro_score != null
    ? Math.round(croAudit.overall_cro_score)
    : (categoryCroScore != null ? Math.round(categoryCroScore) : null);

  // Grades require an explicit CRO grade from the scoring engine; thresholds are not calibrated here.
  const croGrade = croAudit?.cro_grade || 'Not calibrated';

  // Category UX_CONVERSION findings
  const croFindings = (report.findings || []).filter(
    (f) => f.category === 'UX_CONVERSION' || (f.category as any) === 'CRO'
  );

  // CTA Data
  const ctaData = croAudit?.cta_analysis;
  const ctasList: CtaAuditItem[] = ctaData?.ctas || [];
  const filteredCtas = ctasList.filter((c) => {
    if (ctaFilter !== 'ALL' && c.intent_category !== ctaFilter) return false;
    if (ctaSearch && !c.cta_text.toLowerCase().includes(ctaSearch.toLowerCase()) && !c.page_url.toLowerCase().includes(ctaSearch.toLowerCase())) {
      return false;
    }
    return true;
  });

  // Social Proof Data
  const socialProof = croAudit?.social_proof;

  // Pricing Data
  const pricingData = croAudit?.pricing_psychology;

  // Value Prop Data
  const valueProp = croAudit?.value_prop;
  const heroHeadline = valueProp?.hero_headline || profile?.value_proposition || 'No observed value proposition';
  const heroSubhead = valueProp?.hero_subhead;

  // Filtered Findings
  const filteredFindings = croFindings.filter((f) => {
    if (findingSeverityFilter === 'ALL') return true;
    return String(f.severity).toUpperCase() === findingSeverityFilter;
  });

  return (
    <PillarShell
      kicker="Conversion experience"
      title="Conversion Rate & UX Optimization (CRO)"
      description="Review whether visitors understand the offer, trust the business, find the next step, and can complete forms without unnecessary friction. Analytics-backed outcomes appear only when supporting data is available."
      scoreLabel="CRO Score"
      score={croScore == null ? 'Unmeasured' : croScore}
      metaLabel="Form Grade"
      meta={formAudit ? `Grade ${formAudit.cro_friction_grade}` : `Grade ${croGrade}`}
      actions={
        <SectionExportButtons
          analysisId={analysisId || report.analysis_id || report.report_id}
          sectionKey="cro"
          sectionLabel="CRO"
        />
      }
      tabs={[
        { id: 'overview', label: 'Overview and checks' },
        { id: 'ctas', label: `CTA Studio (${ctaData?.total_ctas_detected ?? (ctaData ? ctasList.length : 'Not measured')})` },
        { id: 'valueprop', label: 'Message clarity' },
        { id: 'trust', label: `Trust & Social Proof (${socialProof?.trust_authority_score == null ? 'Not measured' : `${socialProof.trust_authority_score}%`})` },
        { id: 'pricing', label: 'Pricing and reassurance' },
        { id: 'forms', label: `Form Friction (${formAudit?.total_forms_detected == null ? 'Not measured' : formAudit.total_forms_detected})` },
        { id: 'findings', label: `Findings (${croFindings.length})` },
        { id: 'revenue', label: 'Funnel and revenue' },
        { id: 'leadgen', label: 'Lead opportunities' },
        { id: 'analytics', label: 'Analytics & score method' },
        { id: 'index', label: 'Full CRO audit' },
      ]}
      activeTab={activeSubTab}
      onTab={(id) => setActiveSubTab(id as CroSubTab)}
    >
      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 1: OVERVIEW & SCORECARD
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'overview' && (
        <div className="space-y-6">
          {/* Top CRO Vitals */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <Card className="p-4 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Overall CRO Score
              </span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-ink">{croScore == null ? 'Unmeasured' : croScore}</span>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-paper-200 text-ink-700 font-bold">
                  Grade {croGrade}
                </span>
              </div>
              <p className="text-xs text-ink-500">Nominal 20% audit weight</p>
            </Card>

            <Card className="p-4 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Action Clarity
              </span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-good">
                  {ctaData?.action_clarity_score == null ? 'Not measured' : Math.round(ctaData.action_clarity_score)}{ctaData?.action_clarity_score == null ? '' : '%'}
                </span>
              </div>
              <p className="text-xs text-ink-500">
                {ctaData ? `${ctaData.high_intent_count} high-intent / ${ctaData.total_ctas_detected} total CTAs` : 'CTA observations unavailable'}
              </p>
            </Card>

            <Card className="p-4 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Trust Index
              </span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-ink-700">
                  {socialProof?.trust_authority_score == null ? 'Not measured' : Math.round(socialProof.trust_authority_score)}/100
                </span>
                <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded font-bold ${
                  socialProof?.risk_level === 'LOW' ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'
                }`}>
                  {socialProof?.risk_level ? `${socialProof.risk_level} RISK` : 'Not measured'}
                </span>
              </div>
              <p className="text-xs text-ink-500">Social proof & compliance</p>
            </Card>

            <Card className="p-4 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Form Friction
              </span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-ink">
                  {formAudit ? formAudit.cro_friction_grade : 'Unmeasured'}
                </span>
                <span className="text-xs text-ink-500">
                  ({formAudit?.total_forms_detected == null ? 'Not measured' : formAudit.total_forms_detected} forms)
                </span>
              </div>
              <p className="text-xs text-ink-500">
                {formAudit?.forms_with_missing_labels == null ? 'Label status not measured' : (formAudit.forms_with_missing_labels === 0 ? 'No unlabeled inputs detected in sample' : `${formAudit.forms_with_missing_labels} unlabeled`)}
              </p>
            </Card>

            <Card className="p-4 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Value Prop Hook
              </span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-ink">
                  {valueProp?.clarity_grade || 'Unmeasured'}
                </span>
                <span className="text-xs text-ink-500">
                  {valueProp?.headline_word_count == null ? 'Not measured' : valueProp.headline_word_count} words
                </span>
              </div>
              <p className="text-xs text-ink-500">
                {valueProp?.has_adjacent_cta == null ? 'Hero CTA status not measured' : valueProp.has_adjacent_cta ? 'Hero CTA paired' : 'No adjacent hero CTA observed'}
              </p>
            </Card>
          </div>

          {/* High Priority Friction Alert Banner */}
          {ctaData && (ctaData.passive_generic_count ?? 0) > 0 && (
            <div className="p-4 rounded-lg bg-warn/5 border border-warn/30 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-warn shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h4 className="font-sans text-sm font-bold text-ink">
                  {ctaData?.passive_generic_count} Passive CTA Buttons Identified
                </h4>
                <p className="text-xs text-ink-700 leading-relaxed">
                  Buttons labeled with generic verbs like &quot;Submit&quot; or &quot;Learn More&quot; create cognitive hesitation. Replace them with value-focused action verbs to boost click-through intent.
                </p>
                <button
                  onClick={() => { setActiveSubTab('ctas'); setCtaFilter('PASSIVE_GENERIC'); }}
                  className="font-mono text-xs text-warn font-semibold flex items-center gap-1 hover:underline pt-1"
                >
                  Inspect passive buttons in CTA Studio <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* 5 Dimensions Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('ctas')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MousePointerClick className="w-4 h-4 text-good" />
                  <h4 className="font-sans text-sm font-bold text-ink">CTA &amp; Action Hierarchy</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Audits all interactive conversion triggers across the crawl. Identifies primary above-the-fold placement and flags ambiguous button copy.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span>{ctaData?.high_intent_count ?? 'Not measured'} High-Intent</span>
                <span>·</span>
                <span className={ctaData && (ctaData.passive_generic_count ?? 0) > 0 ? 'text-warn font-bold' : ''}>
                  {ctaData?.passive_generic_count ?? 'Not measured'} Passive
                </span>
              </div>
            </Card>

            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('valueprop')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-primary" />
                  <h4 className="font-sans text-sm font-bold text-ink">5-Second Value Prop Hook</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Evaluates whether arriving visitors grasp what you do, who it is for, and why to care within 5 seconds without reading paragraph blocks.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span>Headline: {valueProp?.headline_word_count == null ? 'Not measured' : valueProp.headline_word_count} words</span>
                <span>·</span>
                <span>Centricity: {valueProp?.customer_centricity_ratio == null ? 'Not measured' : valueProp.customer_centricity_ratio}x</span>
              </div>
            </Card>

            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('trust')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-indigo-500" />
                  <h4 className="font-sans text-sm font-bold text-ink">Social Proof &amp; Trust</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Audits evidence of market validation: client logos, customer testimonials, quantified ROI metrics, and security credentials.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span>{socialProof?.client_logos_detected ?? 'Not measured'} Logos</span>
                <span>·</span>
                <span>{socialProof?.total_testimonials ?? 'Not measured'} Testimonials</span>
                <span>·</span>
                <span>{socialProof?.quantified_proof_claims?.length ?? 'Not measured'} ROI Claims</span>
              </div>
            </Card>

            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('pricing')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-emerald-500" />
                  <h4 className="font-sans text-sm font-bold text-ink">Pricing Psychology</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Verifies commercial transparency: discoverability of packages, annual vs monthly savings toggles, and risk reversal guarantees.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span>{pricingData?.pricing_page_detected ? 'Pricing Page Found' : 'No Public Pricing'}</span>
                <span>·</span>
                <span>{pricingData?.has_billing_toggle ? 'Toggle Present' : 'No Toggle'}</span>
              </div>
            </Card>

            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('forms')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-amber-500" />
                  <h4 className="font-sans text-sm font-bold text-ink">Form Usability &amp; WCAG</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Analyzes input counts, missing label associations, spam defense traps, and conversion friction across lead generation forms.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span>{formAudit?.total_forms_detected ?? 'Not measured'} Forms</span>
                <span>·</span>
                <span>Grade {formAudit?.cro_friction_grade ?? 'A'}</span>
              </div>
            </Card>

            <Card className="p-5 space-y-3 cursor-pointer hover:border-ink-300 transition-colors" onClick={() => setActiveSubTab('findings')}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-warn" />
                  <h4 className="font-sans text-sm font-bold text-ink">Conversion Findings Register</h4>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-400" />
              </div>
              <p className="text-xs text-ink-600 leading-relaxed">
                Full ledger of prioritized conversion defects identified from DOM and content evidence, complete with recommended code/copy remedies.
              </p>
              <div className="flex items-center gap-2 pt-2 border-t border-line font-mono text-[11px] text-ink-500">
                <span className="font-bold text-ink-700">{croFindings.length} Audited Issues</span>
              </div>
            </Card>
          </div>

          {/* Actionable Remedies Card */}
          {croAudit?.actionable_remedies && croAudit.actionable_remedies.length > 0 && (
            <Card className="p-5 space-y-3 border-l-2 border-l-pine">
              <h4 className="text-xs font-bold text-ink-700 uppercase tracking-[0.04em]">
                Recommended CRO Strategic Interventions
              </h4>
              <ul className="text-xs text-ink-700 space-y-2 list-disc pl-5">
                {croAudit.actionable_remedies.map((rem, i) => (
                  <li key={i} className="leading-relaxed">{rem}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 2: CTA & ACTION HIERARCHY STUDIO
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'ctas' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="font-sans text-lg font-bold text-ink">Call-to-Action (CTA) Architecture Studio</h3>
              <p className="text-xs text-ink-500">
                Audited {ctaData?.total_ctas_detected ?? (ctaData ? ctasList.length : 'Not measured')} interactive conversion triggers across the crawl.
              </p>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-ink-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter buttons..."
                  value={ctaSearch}
                  onChange={(e) => setCtaSearch(e.target.value)}
                  className="pl-8 pr-3 py-1 text-xs border border-line rounded bg-paper-50 text-ink focus:outline-none focus:ring-1 focus:ring-pine"
                />
              </div>

              <div className="flex rounded border border-line p-0.5 bg-paper-100 text-xs">
                {(['ALL', 'HIGH_INTENT', 'EXPLORATORY', 'PASSIVE_GENERIC'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setCtaFilter(mode)}
                    className={`px-2.5 py-1 rounded font-mono text-[11px] font-semibold transition-colors ${
                      ctaFilter === mode
                        ? 'bg-paper-50 text-ink shadow-sm'
                        : 'text-ink-500 hover:text-ink'
                    }`}
                  >
                    {mode === 'ALL' ? 'All' : mode === 'HIGH_INTENT' ? 'High-Intent' : mode === 'EXPLORATORY' ? 'Exploratory' : 'Passive'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Passive CTA Warning Notice with Suggestions */}
          {ctaData && (ctaData.passive_generic_count ?? 0) > 0 && (
            <Card className="p-4 bg-warn/5 border-warn/30 space-y-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-warn font-bold block">
                High Priority: Replace Passive Microcopy
              </span>
              <p className="text-xs text-ink-700">
                Detected buttons relying on generic verbs (&quot;Submit&quot;, &quot;Click Here&quot;, &quot;Learn More&quot;). Use outcome-driven rewrites to increase intent.
              </p>
            </Card>
          )}

          {/* CTA Items List */}
          {filteredCtas.length > 0 ? (
            <div className="space-y-3">
              {filteredCtas.map((c, idx) => (
                <Card key={idx} className="p-4 space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-ink">&quot;{c.cta_text}&quot;</span>
                      <span className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                        c.intent_category === 'HIGH_INTENT'
                          ? 'bg-good/10 text-good border border-good/20'
                          : c.intent_category === 'EXPLORATORY'
                            ? 'bg-blue-500/10 text-blue-600 border border-blue-500/20'
                            : 'bg-warn/10 text-warn border border-warn/20'
                      }`}>
                        {c.intent_category.replace('_', ' ')}
                      </span>
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-paper-200 text-ink-600">
                        {c.placement_zone}
                      </span>
                    </div>

                    {c.suggested_rewrite && (
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="text-ink-500">Suggested Rewrite:</span>
                        <span className="font-mono font-bold text-good px-2 py-0.5 rounded bg-good/5 border border-good/20">
                          &quot;{c.suggested_rewrite}&quot;
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs text-ink-500 pt-1 border-t border-line/60">
                    <span className="font-mono truncate max-w-md">{c.page_url}</span>
                    {c.target_url && (
                      <span className="font-mono text-[11px] text-ink-400 truncate max-w-xs">
                        Target: {c.target_url}
                      </span>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="p-8 text-center space-y-2">
              <MousePointerClick className="w-8 h-8 text-ink-400 mx-auto" />
              <p className="text-sm font-medium text-ink">No matching CTAs found</p>
              <p className="text-xs text-ink-500">Adjust your search or category filter to inspect all extracted buttons.</p>
            </Card>
          )}

          {/* Pages Missing CTAs */}
          {(ctaData?.pages_without_ctas && ctaData.pages_without_ctas.length > 0) && (
            <Card className="p-5 space-y-3 border-l-2 border-l-warn">
              <h4 className="font-sans text-sm font-bold text-ink">
                Pages Missing Primary Conversion Actions ({ctaData.pages_without_ctas.length})
              </h4>
              <p className="text-xs text-ink-600">
                These content-dense pages contain over 100 words but offer no interactive next step for arriving visitors:
              </p>
              <div className="space-y-1 font-mono text-xs text-warn">
                {ctaData.pages_without_ctas.map((url, i) => (
                  <div key={i} className="truncate p-1.5 rounded bg-warn/5">{url}</div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 3: 5-SECOND VALUE PROPOSITION CLARITY
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'valueprop' && (
        <div className="space-y-6">
          <Card className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-700 font-bold block">
                5-Second Value Proposition Clarity Test
              </span>
              <span className="font-mono text-xs px-2.5 py-1 rounded bg-paper-200 text-ink font-bold">
                Clarity Grade: {valueProp?.clarity_grade || 'Unmeasured'}
              </span>
            </div>

            <blockquote className="font-sans text-2xl text-ink leading-relaxed font-medium italic border-l-4 border-pine pl-4">
              &quot;{heroHeadline}&quot;
            </blockquote>

            {heroSubhead && (
              <p className="font-sans text-sm text-ink-600 pl-4 border-l-4 border-transparent">
                Sub-headline: &quot;{heroSubhead}&quot;
              </p>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-line text-xs">
              <div className="p-3.5 rounded bg-paper-50 border border-line space-y-1">
                <span className="text-[10px] font-mono uppercase text-ink-500 block">Headline Word Count</span>
                <p className="font-sans font-bold text-ink text-lg">
                  {valueProp?.headline_word_count == null ? 'Not measured' : valueProp.headline_word_count} words
                </p>
                <p className="text-[11px] text-ink-500">Ideal range: 6–10 punchy words</p>
              </div>

              <div className="p-3.5 rounded bg-paper-50 border border-line space-y-1">
                <span className="text-[10px] font-mono uppercase text-ink-500 block">Customer Centricity Ratio</span>
                <p className="font-sans font-bold text-good text-lg">
                  {valueProp?.customer_centricity_ratio == null ? 'Not measured' : valueProp.customer_centricity_ratio}x
                </p>
                <p className="text-[11px] text-ink-500">Ratio of &quot;you/your&quot; vs &quot;we/our&quot;</p>
              </div>

              <div className="p-3.5 rounded bg-paper-50 border border-line space-y-1">
                <span className="text-[10px] font-mono uppercase text-ink-500 block">Hero CTA Proximity</span>
                <p className={`font-sans font-bold text-lg ${valueProp?.has_adjacent_cta ? 'text-good' : 'text-warn'}`}>
                  {valueProp?.has_adjacent_cta ? 'Paired Above-Fold' : 'Missing Action Button'}
                </p>
                <p className="text-[11px] text-ink-500">High-intent action near main headline</p>
              </div>
            </div>

            {/* Observations */}
            {valueProp?.observations && valueProp.observations.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-line text-xs">
                <span className="font-bold text-ink-700 uppercase tracking-[0.04em] text-[10px] block">
                  Diagnostic Heuristic Observations
                </span>
                <ul className="space-y-1.5 list-disc pl-5 text-ink-600">
                  {valueProp.observations.map((obs, i) => (
                    <li key={i}>{obs}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {/* Business Positioning Metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-ink-500 block">Target Audience / ICP</span>
              <p className="font-semibold text-ink text-sm">{profile?.target_audience || 'Unspecified'}</p>
            </Card>
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-ink-500 block">Primary Intent</span>
              <p className="font-semibold text-ink text-sm">{profile?.primary_intent || 'Commercial Solution'}</p>
            </Card>
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-ink-500 block">Business Model</span>
              <p className="font-semibold text-ink text-sm">{profile?.business_model || 'B2B SaaS / Services'}</p>
            </Card>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 4: SOCIAL PROOF & TRUST ARCHITECTURE
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'trust' && (
        <div className="space-y-6">
          {/* Trust Score Header */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Trust Index
              </span>
              <p className="font-sans text-3xl font-bold text-ink">
                {socialProof?.trust_authority_score == null ? 'Not measured' : Math.round(socialProof.trust_authority_score)}/100
              </p>
              <p className="text-xs text-ink-500">Third-party validation score</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Client Logos Detected
              </span>
              <p className="font-sans text-3xl font-bold text-good">
                {socialProof?.client_logos_detected ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">Recognizable customer logo badges</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Customer Testimonials
              </span>
              <p className="font-sans text-3xl font-bold text-ink-700">
                {socialProof?.total_testimonials ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">Quotes &amp; review blocks extracted</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Quantified ROI Metrics
              </span>
              <p className="font-sans text-3xl font-bold text-ink">
                {socialProof?.quantified_proof_claims?.length ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">Specific percentage &amp; dollar outcomes</p>
            </Card>
          </div>

          {/* Quantified Proof Claims */}
          {socialProof?.quantified_proof_claims && socialProof.quantified_proof_claims.length > 0 && (
            <Card className="p-5 space-y-3">
              <h3 className="font-sans text-sm font-bold text-ink flex items-center gap-2">
                <Award className="w-4 h-4 text-good" />
                Discovered Quantified Outcome Proof
              </h3>
              <div className="flex flex-wrap gap-2">
                {socialProof.quantified_proof_claims.map((claim, idx) => (
                  <span key={idx} className="font-mono text-xs px-3 py-1.5 rounded-lg bg-good/10 text-good border border-good/20 font-bold">
                    &quot;{claim}&quot;
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* Trust Seals & Security Credentials Checklist */}
          <Card className="p-5 space-y-4">
            <h3 className="font-sans text-sm font-bold text-ink flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-500" />
              Corporate Legitimacy &amp; Trust Credentials
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded border border-line bg-paper-50 flex items-center justify-between">
                <span>Privacy Policy Link</span>
                {socialProof?.has_privacy_policy ? (
                  <span className="font-mono text-good font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Present
                  </span>
                ) : (
                  <span className="font-mono text-warn font-bold flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Missing
                  </span>
                )}
              </div>

              <div className="p-3 rounded border border-line bg-paper-50 flex items-center justify-between">
                <span>Terms of Service Link</span>
                {socialProof?.has_terms_of_service ? (
                  <span className="font-mono text-good font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Present
                  </span>
                ) : (
                  <span className="font-mono text-warn font-bold flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Missing
                  </span>
                )}
              </div>

              {socialProof?.trust_badges_detected.map((badge, idx) => (
                <div key={idx} className="p-3 rounded border border-line bg-paper-50 flex items-center justify-between">
                  <span>{badge}</span>
                  <span className="font-mono text-good font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Verified
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 5: PRICING PSYCHOLOGY & RISK REVERSAL
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'pricing' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Pricing Discovery
              </span>
              <p className={`font-sans text-xl font-bold ${pricingData?.pricing_page_detected ? 'text-good' : 'text-ink-700'}`}>
                {pricingData?.pricing_page_detected ? 'Public Pricing' : 'Contact / Sales'}
              </p>
              <p className="text-xs text-ink-500 truncate">
                {pricingData?.pricing_url ? pricingData.pricing_url : 'No public pricing page'}
              </p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Tiers Detected
              </span>
              <p className="font-sans text-3xl font-bold text-ink">
                {pricingData?.detected_tiers_count ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">Plan packaging structures</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Billing Cycle Toggle
              </span>
              <p className={`font-sans text-xl font-bold ${pricingData?.has_billing_toggle ? 'text-good' : 'text-warn'}`}>
                {pricingData?.has_billing_toggle ? 'Annual vs Monthly' : 'No Toggle Detected'}
              </p>
              <p className="text-xs text-ink-500">Annual savings switch</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Risk Reversal Guarantee
              </span>
              <p className={`font-sans text-xl font-bold ${pricingData?.has_free_trial || pricingData?.has_money_back_guarantee ? 'text-good' : 'text-warn'}`}>
                {pricingData?.has_free_trial ? 'Free Trial / No Card' : (pricingData?.has_money_back_guarantee ? 'Money-Back Guarantee' : 'Unspecified')}
              </p>
              <p className="text-xs text-ink-500">Customer purchase protection</p>
            </Card>
          </div>

          {/* Pricing Psychology Details */}
          <Card className="p-5 space-y-3">
            <h3 className="font-sans text-sm font-bold text-ink">Detected Guarantee &amp; De-Risking Signals</h3>
            {pricingData?.guarantee_signals && pricingData.guarantee_signals.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {pricingData.guarantee_signals.map((sig, i) => (
                  <span key={i} className="px-3 py-1 rounded bg-paper-100 border border-line text-xs font-mono font-medium text-ink-700">
                    {sig}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-ink-500">
                No explicit money-back guarantee, free trial terms, or &quot;no credit card required&quot; signals were found in the crawl. Introducing risk reversal elements directly mitigates buyer friction.
              </p>
            )}
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 6: FORM FRICTION AUDIT
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'forms' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Total Forms Detected
              </span>
              <p className="font-sans text-3xl font-bold text-ink">
                {formAudit?.total_forms_detected ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">Lead capture, demo, contact, or checkout</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Friction Grade
              </span>
              <p className="font-sans text-3xl font-bold text-ink-700">
                {formAudit?.cro_friction_grade || 'A'}
              </p>
              <p className="text-xs text-ink-500">Input complexity rating</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Missing Input Labels
              </span>
              <p className={`font-sans text-3xl font-bold ${formAudit?.forms_with_missing_labels == null ? 'text-ink' : formAudit.forms_with_missing_labels > 0 ? 'text-warn' : 'text-good'}`}>
                {formAudit?.forms_with_missing_labels ?? 'Not measured'}
              </p>
              <p className="text-xs text-ink-500">WCAG label compliance</p>
            </Card>

            <Card className="p-4 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
                Spam Defense &amp; Bot Filter
              </span>
              <div className="flex items-center gap-1.5 pt-1">
                {formAudit?.forms_without_captcha == null ? (
                  <span className="font-mono text-sm text-ink-500">Not measured</span>
                ) : formAudit.forms_without_captcha === 0 ? (
                  <span className="font-mono text-sm text-good font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Defense detected
                  </span>
                ) : (
                  <span className="font-mono text-sm text-warn font-bold flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4" /> Defense not detected
                  </span>
                )}
              </div>
              <p className="text-xs text-ink-500">Honeypot or Turnstile captcha</p>
            </Card>
          </div>

          {/* Form Breakdown List */}
          {formAudit?.forms && formAudit.forms.length > 0 ? (
            <Card className="p-5 space-y-4">
              <h3 className="font-sans text-lg text-ink font-semibold">Detected Form Specifications</h3>
              <div className="space-y-3">
                {formAudit.forms.map((f, idx) => (
                  <div key={idx} className="p-4 rounded-lg border border-line bg-paper-50 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-ink-700">Form #{idx + 1} ({f.input_count} inputs)</span>
                      <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-paper-200 text-ink-700 font-semibold">
                        Submit: &quot;{f.submit_button_text || 'Submit'}&quot;
                      </span>
                    </div>
                    <p className="font-mono text-[11px] text-ink-500 truncate">Page: {f.page_url}</p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {f.input_types?.map((t, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-paper-100 border border-line text-ink-600 font-mono text-[10px]">
                          type=&quot;{t}&quot;
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card className="p-5 space-y-2">
              <h3 className="font-sans text-lg text-ink font-semibold">Form Analysis Summary</h3>
              <p className="text-xs text-ink-600">
                Primary conversion relies on direct links or modal triggers. Keep submission forms under 4 fields to maximize completion rate.
              </p>
            </Card>
          )}

          {/* Actionable Remedies */}
          {formAudit?.actionable_remedies && formAudit.actionable_remedies.length > 0 && (
            <Card className="p-5 space-y-3 border-l-2 border-l-pine">
              <h4 className="text-xs font-bold text-ink-700 uppercase tracking-[0.04em]">
                Recommended CRO Form Remedies
              </h4>
              <ul className="text-xs text-ink-700 space-y-1.5 list-disc pl-5">
                {formAudit.actionable_remedies.map((rem, i) => (
                  <li key={i}>{rem}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 7: FINDINGS & REMEDIATION REGISTER
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'findings' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-sans text-lg font-bold text-ink">Conversion Experience Findings ({croFindings.length})</h3>
              <p className="text-xs text-ink-500">Prioritized conversion obstacles derived from DOM and copywriting evidence.</p>
            </div>

            <div className="flex rounded border border-line p-0.5 bg-paper-100 text-xs">
              {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((sev) => (
                <button
                  key={sev}
                  onClick={() => setFindingSeverityFilter(sev)}
                  className={`px-2.5 py-1 rounded font-mono text-[11px] font-semibold transition-colors ${
                    findingSeverityFilter === sev
                      ? 'bg-paper-50 text-ink shadow-sm'
                      : 'text-ink-500 hover:text-ink'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>

          {filteredFindings.length > 0 ? (
            <div className="space-y-3">
              {filteredFindings.map((f, idx) => (
                <Card key={idx} className="p-5 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                          f.severity === 'CRITICAL' ? 'bg-critical/10 text-critical border border-critical/20' :
                          f.severity === 'HIGH' ? 'bg-warn/10 text-warn border border-warn/20' :
                          'bg-paper-200 text-ink-700'
                        }`}>
                          {f.severity}
                        </span>
                        <h4 className="font-sans text-base font-bold text-ink">{f.title}</h4>
                      </div>
                      <p className="text-xs text-ink-600 leading-relaxed">{f.description}</p>
                    </div>

                    {f.impact != null && (
                      <div className="text-right shrink-0">
                        <span className="font-mono text-xs text-ink-500 block">Impact / Effort</span>
                        <span className="font-mono font-bold text-sm text-ink">{f.impact ?? 'Not measured'} / {f.effort ?? 'Not rated'}</span>
                      </div>
                    )}
                  </div>

                  {f.recommendation && (
                    <div className="p-3 rounded bg-good/5 border border-good/20 text-xs text-good space-y-1">
                      <span className="font-bold uppercase tracking-[0.04em] text-[10px] block">Recommended Action</span>
                      <p className="font-mono text-ink-800">{f.recommendation}</p>
                    </div>
                  )}

                  {f.evidence && f.evidence.length > 0 && (
                    <div className="pt-2 border-t border-line text-xs font-mono text-ink-500 flex items-center justify-between">
                      <span className="truncate max-w-lg">Selector: {f.evidence[0].element || 'DOM'}</span>
                      <span className="text-ink-400 truncate max-w-sm">{f.evidence[0].url}</span>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <Card className="p-8 text-center space-y-2">
              <CheckCircle2 className="w-8 h-8 text-good mx-auto" />
              <p className="text-sm font-medium text-ink">No findings match this severity level</p>
              <p className="text-xs text-ink-500">All conversion checks passed for the selected filter.</p>
            </Card>
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 8: REVENUE & FUNNEL LEAKAGE
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'revenue' && (
        <LifecycleRevenueIntelligenceView
          lifecycleData={report.lifecycle_revenue}
        />
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 9: LEAD GEN OPPORTUNITIES
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'leadgen' && (
        <LeadGenOpportunitiesView
          domain={report.domain}
          bizName={profile?.business_name}
          niche={profile?.industry}
          analysisId={analysisId}
          onDeployRequested={onDeployRemediation}
        />
      )}

      {activeSubTab === 'analytics' && (
        <CroAnalyticsDashboard report={report} analysisId={analysisId} />
      )}

      {activeSubTab === 'index' && (
        <CroIntelligencePanel report={report} analysisId={analysisId} />
      )}
    </PillarShell>
  );
}
