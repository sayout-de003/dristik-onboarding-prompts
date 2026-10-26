import React, { useState } from 'react';
import { ExecutiveReport } from '../../types';
import { PillarShell, Card } from '../ui';
import { SectionExportButtons } from '../ui/SectionExportButtons';
import {
  Bot,
  FileCode,
  Network,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  ShieldCheck,
} from 'lucide-react';
import { DynamicQuestionSandboxView } from '../DynamicQuestionSandboxView';
import { AeoAuditBook } from '../../report/aeoIndex/AeoAuditBook';
import { AeoAnalyticsDashboard } from '../AeoAnalyticsDashboard';

interface AeoWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
  onOpenPatchPack?: () => void;
}

type AeoSubTab = 'audit' | 'analytics' | 'directives' | 'schema' | 'questions' | 'triples';

export const QUESTION_KEY_CATEGORY_MAP: Record<string, string> = {
  identity_what: 'Entity Identity',
  identity_leadership: 'Entity Identity',
  identity_headquarters: 'Entity Identity',
  identity_category: 'Entity Identity',
  identity_mission: 'Entity Identity',

  caps_primary_offerings: 'Core Capabilities & Services',
  caps_tech_stack: 'Core Capabilities & Services',
  caps_custom_integrations: 'Core Capabilities & Services',
  caps_key_deliverables: 'Core Capabilities & Services',
  caps_how_it_works: 'Core Capabilities & Services',
  caps_deployment_model: 'Core Capabilities & Services',
  caps_problem_solved: 'Core Capabilities & Services',
  caps_automation: 'Core Capabilities & Services',
  caps_maintenance_support: 'Core Capabilities & Services',
  caps_prerequisites: 'Core Capabilities & Services',

  icp_target_customer: 'Target Audience & ICP',
  icp_enterprise_suitability: 'Target Audience & ICP',
  icp_smb_startup_suitability: 'Target Audience & ICP',
  icp_buyer_roles: 'Target Audience & ICP',
  icp_verticals: 'Target Audience & ICP',

  price_cost: 'Pricing & Commercial Terms',
  price_tiers: 'Pricing & Commercial Terms',
  price_free_trial: 'Pricing & Commercial Terms',
  price_setup_fees: 'Pricing & Commercial Terms',
  price_billing_cycle: 'Pricing & Commercial Terms',
  price_volume_discounts: 'Pricing & Commercial Terms',
  price_refund_cancellation: 'Pricing & Commercial Terms',

  trust_data_security: 'Security, Trust & Compliance',
  trust_compliance_standards: 'Security, Trust & Compliance',
  trust_data_privacy: 'Security, Trust & Compliance',
  trust_testimonials: 'Security, Trust & Compliance',
  trust_client_logos: 'Security, Trust & Compliance',
  trust_uptime_sla: 'Security, Trust & Compliance',
  trust_support_channels: 'Security, Trust & Compliance',
  trust_third_party_audits: 'Security, Trust & Compliance',

  diff_alternatives: 'Comparative & Differentiators',
  diff_core_moat: 'Comparative & Differentiators',
  diff_traditional_vs_brand: 'Comparative & Differentiators',
  diff_limitations: 'Comparative & Differentiators',
  diff_migration: 'Comparative & Differentiators',

  impl_setup_time: 'Implementation & Onboarding',
  impl_engineering_effort: 'Implementation & Onboarding',
  impl_business_roi: 'Implementation & Onboarding',
  impl_dedicated_success: 'Implementation & Onboarding',
  impl_documentation: 'Implementation & Onboarding',

  intent_schedule_demo: 'High-Intent Purchase Actions',
  intent_self_serve: 'High-Intent Purchase Actions',
  intent_status_changelog: 'High-Intent Purchase Actions',
  intent_global_currencies: 'High-Intent Purchase Actions',
  intent_next_steps: 'High-Intent Purchase Actions',
};

export function resolveQuestionCategory(q: any): string {
  if (q?.category && q.category !== 'General') return q.category;
  if (q?.question_key && QUESTION_KEY_CATEGORY_MAP[q.question_key]) {
    return QUESTION_KEY_CATEGORY_MAP[q.question_key];
  }
  return q?.category || 'General';
}

export function AeoWorkspaceView({ report, analysisId, onOpenPatchPack }: AeoWorkspaceViewProps) {
  const [activeSubTab, setActiveSubTab] = useState<AeoSubTab>('audit');
  const [copiedLlms, setCopiedLlms] = useState(false);

  const geo = report.geo_readiness;
  const perEngine = report.per_engine_geo;
  const botDirectives = perEngine?.ai_bot_directives;
  const sandboxEvals = report.dynamic_sandbox_evaluations || [];
  const answerableCount = sandboxEvals.filter(
    (q) => q.answerability_status === 'ANSWERABLE' && q.is_answerable !== false
  ).length;
  const botsMeasured = botDirectives?.robots_measured === true;

  const schemaTypes = geo?.schema_types || [];
  const schemaCrosscheck = geo?.schema_crosscheck;
  const typeAssessments = schemaCrosscheck?.type_assessments || [];
  const graphConflicts = schemaCrosscheck?.conflicts || [];

  const handleCopyLlms = async () => {
    const text = botDirectives?.llms_txt_generated || `# ${report.business_profile?.business_name || report.domain}\n\n> ${report.business_profile?.value_proposition || 'Enterprise Web Services'}\n\n## Overview\nWebsite: ${report.website_url}\nIndustry: ${report.business_profile?.industry || 'Technology'}\n`;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedLlms(true);
      setTimeout(() => setCopiedLlms(false), 2000);
    } catch {
      /* ignore */
    }
  };

  const schemaCategory = report.scores?.category_scores?.SCHEMA?.score;
  const aeoScore = typeof schemaCrosscheck?.quality_score === 'number'
    ? Math.round(schemaCrosscheck.quality_score)
    : typeof geo?.extractability_score === 'number'
      ? Math.round(geo.extractability_score)
      : typeof schemaCategory === 'number'
        ? Math.round(schemaCategory)
        : '—';

  return (
    <PillarShell
      kicker="Answer quality and structured data"
      title="Answer Engine & Agent Optimization (AEO)"
      description="Review whether important questions have clear answers and whether structured data helps machines interpret the site. The score reflects stored schema quality or page extractability—not a live AI visibility rate."
      scoreLabel="Schema / extractability"
      score={aeoScore}
      metaLabel={sandboxEvals.length > 0 ? 'Sandbox Grounding' : 'Q&A Answers'}
      meta={
        sandboxEvals.length > 0
          ? `${answerableCount} of ${sandboxEvals.length} usable`
          : geo?.questions?.length
            ? `${geo.questions_supported} of ${geo.questions.length} supported`
            : 'No question set stored'
      }
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <SectionExportButtons
            analysisId={analysisId || report.analysis_id || report.report_id}
            sectionKey="aeo"
            sectionLabel="AEO"
          />
          {(analysisId || report.analysis_id || report.report_id) && (
            <a
              href={`/api/v1/reports/${analysisId || report.analysis_id || report.report_id}/aeo-report?format=html`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-line bg-paper-100 hover:bg-paper-200 text-ink transition-colors"
              title="Open the dedicated AEO master report with its own chapters and appendices"
            >
              AEO Master Report
            </a>
          )}
        </div>
      }
      tabs={[
        { id: 'audit', label: 'Full AEO audit' },
        { id: 'analytics', label: 'AEO KPIs & Analytics' },
        { id: 'directives', label: 'AI crawler settings' },
        { id: 'schema', label: `Schema Graph (${schemaTypes.length})` },
        { id: 'questions', label: `AI Question Sandbox (${sandboxEvals.length})` },
        { id: 'triples', label: 'Entity facts and evidence' },
      ]}
      activeTab={activeSubTab}
      onTab={(id) => setActiveSubTab(id as AeoSubTab)}
    >
      {activeSubTab === 'audit' && <AeoAuditBook report={report} />}
      {activeSubTab === 'analytics' && <AeoAnalyticsDashboard report={report} analysisId={analysisId} />}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 1: AI BOTS & LLMS.TXT DIRECTIVES
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'directives' && (
        <div className="space-y-6">
          {/* Crawler Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                bot: 'GPTBot (OpenAI)',
                allowed: botsMeasured ? botDirectives?.gptbot_allowed === true : null,
                purpose: 'ChatGPT Search & Answers',
              },
              {
                bot: 'PerplexityBot',
                allowed: botsMeasured ? botDirectives?.perplexitybot_allowed === true : null,
                purpose: 'Perplexity Search Indexing',
              },
              {
                bot: 'ClaudeBot (Anthropic)',
                allowed: botsMeasured ? botDirectives?.claudebot_allowed === true : null,
                purpose: 'Claude Artifacts & Research',
              },
              {
                bot: 'Google-Extended',
                allowed: botsMeasured ? botDirectives?.google_extended_allowed === true : null,
                purpose: 'Gemini & Google AI Overviews',
              },
            ].map((item, idx) => (
              <Card key={idx} className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-ink text-xs">{item.bot}</span>
                  {item.allowed == null ? (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded bg-paper-200 text-ink-500 font-bold">
                      Not measured
                    </span>
                  ) : item.allowed ? (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded bg-good/10 text-good font-bold">
                      <CheckCircle2 className="w-3 h-3" /> Allowed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded bg-bad/10 text-bad font-bold">
                      <XCircle className="w-3 h-3" /> Blocked
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-ink-500">{item.purpose}</p>
              </Card>
            ))}
          </div>

          {/* llms.txt Generated Directives */}
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-ink-700" />
                <h3 className="font-sans text-lg text-ink font-semibold">
                  Machine-Readable Documentation (`/llms.txt`)
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-mono px-2 py-0.5 rounded font-semibold ${
                  botDirectives?.llms_txt_found ? 'bg-good/10 text-good' : 'bg-warn/10 text-warn'
                }`}>
                  {botDirectives?.llms_txt_found ? '✓ Detected on site' : ' Generated Template Ready'}
                </span>
                <button
                  type="button"
                  onClick={handleCopyLlms}
                  className="btn-secondary text-xs px-2.5 py-1 flex items-center gap-1.5"
                >
                  {copiedLlms ? <Check className="w-3.5 h-3.5 text-good" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedLlms ? 'Copied' : 'Copy llms.txt'}</span>
                </button>
              </div>
            </div>
            <p className="text-xs text-ink-600 leading-relaxed">
              `llms.txt` is the emerging industry standard for autonomous AI agents (Cursor, Anthropic, OpenAI) to ingest site architecture and core business documentation without parsing noisy HTML.
            </p>

            <div className="bg-paper-100 p-4 rounded-lg border border-line font-mono text-xs overflow-x-auto max-h-72">
              <pre className="text-ink-700 whitespace-pre-wrap">
                {botDirectives?.llms_txt_generated || `# ${report.business_profile?.business_name || report.domain}\n\n> ${report.business_profile?.value_proposition || 'Enterprise Web Services'}\n\n## Core Offerings\n${report.business_profile?.services?.map(s => `- ${s}`).join('\n') || '- Enterprise platform'}\n\n## Target Audience\n- ${report.business_profile?.target_audience || 'Professionals and organizations'}\n\n## Contact & Primary CTA\n- Primary Action: ${report.business_profile?.primary_cta || 'Get Started'}\n- Official Website: ${report.website_url}\n`}
              </pre>
            </div>
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 2: SCHEMA.ORG KNOWLEDGE GRAPH
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'schema' && (
        <div className="space-y-6">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-ink-700" />
                <h3 className="font-sans text-lg text-ink font-semibold">Structured Data (JSON-LD) Graph</h3>
              </div>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-paper-200 text-ink-700">
                {schemaTypes.length} Types Discovered
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded border border-line bg-paper-50 space-y-1">
                <span className="text-[10px] font-mono text-ink-500 uppercase">Entity graph quality</span>
                <p className="font-mono text-2xl font-bold text-ink">
                  {typeof schemaCrosscheck?.quality_score === 'number' ? Math.round(schemaCrosscheck.quality_score) : '—'}
                  <span className="text-sm text-ink-400 font-normal">/100</span>
                </p>
                <p className="text-[11px] text-ink-500">
                  {schemaCrosscheck?.present_properties ?? 0} of {schemaCrosscheck?.applicable_properties ?? 0} applicable properties
                </p>
              </div>
              <div className="p-3 rounded border border-line bg-paper-50 space-y-1">
                <span className="text-[10px] font-mono text-ink-500 uppercase">Stated-property grounding</span>
                <p className="font-mono text-2xl font-bold text-ink">
                  {typeof schemaCrosscheck?.grounding_score === 'number' ? Math.round(schemaCrosscheck.grounding_score) : '—'}
                  <span className="text-sm text-ink-400 font-normal">/100</span>
                </p>
                <p className="text-[11px] text-ink-500">Only properties the schema already states</p>
              </div>
              <div className="p-3 rounded border border-line bg-paper-50 space-y-1">
                <span className="text-[10px] font-mono text-ink-500 uppercase">Identity consistency</span>
                <p className="font-mono text-2xl font-bold text-ink">
                  {typeof schemaCrosscheck?.consistency_score === 'number' ? Math.round(schemaCrosscheck.consistency_score) : '—'}
                  <span className="text-sm text-ink-400 font-normal">/100</span>
                </p>
                <p className="text-[11px] text-ink-500">{graphConflicts.length} cross-schema conflicts</p>
              </div>
            </div>

            {schemaCrosscheck?.summary && (
              <p className="text-xs text-ink-700 leading-relaxed">{schemaCrosscheck.summary}</p>
            )}

            {graphConflicts.length > 0 && (
              <div className="space-y-2">
                {graphConflicts.map((conflict: any, idx: number) => (
                  <div key={idx} className="p-3 rounded border border-bad/30 bg-bad/5 text-xs text-ink-700">
                    <span className="font-mono text-[10px] font-bold text-bad uppercase">{conflict.severity} {conflict.field}</span>
                    <p className="mt-1">
                      {conflict.left_surface} says {conflict.left_value}. {conflict.right_surface} says {conflict.right_value}.
                    </p>
                  </div>
                ))}
              </div>
            )}

            {typeAssessments.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {typeAssessments.map((row: any) => (
                  <div key={row.schema_type} className="p-3 rounded border border-line bg-paper-50 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-ink-700 font-bold">{row.schema_type}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                        row.status === 'PRESENT' ? 'bg-good/10 text-good' :
                        row.status === 'NOT_APPLICABLE' ? 'bg-paper-200 text-ink-500' :
                        row.status === 'PARTIAL' ? 'bg-warn/10 text-warn' : 'bg-warn/10 text-warn'
                      }`}>
                        {row.status === 'NOT_APPLICABLE' ? 'Not applicable' : row.status === 'PRESENT' ? `${row.present_properties} of ${row.applicable_properties}` : row.status === 'PARTIAL' ? `${row.present_properties} of ${row.applicable_properties}` : 'Absent'}
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-500">{row.reason}</p>
                  </div>
                ))}
              </div>
            ) : schemaTypes.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                {schemaTypes.map((st: string, idx: number) => (
                  <div key={idx} className="p-3 rounded border border-line bg-paper-50 space-y-1">
                    <span className="font-mono text-ink-700 font-bold block">{st}</span>
                    <p className="text-[11px] text-ink-500">Type observed. Property fill was not scored on this report.</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded border border-warn/30 bg-warn/5 text-xs text-ink-700 space-y-1">
                <p className="font-bold text-warn">No JSON-LD in this sample</p>
                <p>Organization and WebSite identity properties are unstated. FAQPage is expected only when the sample shows a visible FAQ.</p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 3: DYNAMIC 100-QUESTION AI SANDBOX & GROUNDED AUDIT
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'questions' && (
        <div className="space-y-4">
          <DynamicQuestionSandboxView
            analysisId={analysisId || report.analysis_id || report.report_id || ''}
            initialEvaluations={report.dynamic_sandbox_evaluations}
            initialKieGraphSummary={report.kie_graph_summary}
            initialFiveDimensions={report.five_dimension_ai_visibility}
            onEvaluationsUpdate={() => {}}
          />
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUB-TAB 4: ENTITY TRIPLES & GROUNDING
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'triples' && (
        <div className="space-y-6">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-ink-700" />
                <h3 className="font-sans text-lg text-ink font-semibold">
                  Entity Knowledge Triples (Subject · Predicate · Object)
                </h3>
              </div>
              <span className="text-xs font-mono text-ink-500">Semantic Grounding</span>
            </div>
            <p className="text-xs text-ink-600">
              Knowledge graphs represent facts about your business as unambiguous triples. This ensures AI models don&apos;t hallucinate services or capabilities you don&apos;t offer.
            </p>

            <div className="space-y-2 text-xs font-mono">
              <div className="p-3 rounded bg-paper-50 border border-line flex items-center gap-2">
                <span className="font-bold text-ink-700">{report.business_profile?.business_name || report.domain}</span>
                <span className="text-ink-400">→ isA →</span>
                <span className="font-semibold text-ink">{report.business_profile?.industry || 'Enterprise Service'}</span>
              </div>
              <div className="p-3 rounded bg-paper-50 border border-line flex items-center gap-2">
                <span className="font-bold text-ink-700">{report.business_profile?.business_name || report.domain}</span>
                <span className="text-ink-400">→ offersPrimaryCTA →</span>
                <span className="font-semibold text-good">{report.business_profile?.primary_cta || 'Contact / Get Started'}</span>
              </div>
              <div className="p-3 rounded bg-paper-50 border border-line flex items-center gap-2">
                <span className="font-bold text-ink-700">{report.business_profile?.business_name || report.domain}</span>
                <span className="text-ink-400">→ targetsAudience →</span>
                <span className="font-semibold text-ink">{report.business_profile?.target_audience || 'Commercial buyers'}</span>
              </div>
            </div>
          </Card>
        </div>
      )}
    </PillarShell>
  );
}
