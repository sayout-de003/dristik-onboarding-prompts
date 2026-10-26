import React, { useState, useMemo } from 'react';
import {
  ExecutiveReport,
  TelemetryData,
  StageCostRecord,
  SubStepCostRecord,
  AgentCallRecord,
  TabId,
} from '../types';
import { formatAuditCost, formatMs, costBasisCaption } from '../lib/format';
import {
  Coins,
  Cpu,
  Layers,
  ChevronDown,
  ChevronRight,
  Download,
  Copy,
  Check,
  Calculator,
  ShieldCheck,
  Sparkles,
  Zap,
  Info,
  Clock,
  ArrowRight,
  ExternalLink,
  Search,
  CheckCircle2,
  FileSpreadsheet,
} from 'lucide-react';

interface CostLedgerViewProps {
  report?: ExecutiveReport;
  telemetry?: TelemetryData;
  onNavigateToTab?: (tab: TabId) => void;
}

// Canonical List Price Reference per 1M tokens (USD)
const OFFICIAL_RATE_CARD: Array<{
  provider: string;
  model: string;
  inputPer1M: number;
  outputPer1M: number;
  tier: 'High Reasoning' | 'Fast / Balanced' | 'Ultra-Fast';
}> = [
  { provider: 'Anthropic', model: 'claude-3-5-sonnet', inputPer1M: 3.00, outputPer1M: 15.00, tier: 'High Reasoning' },
  { provider: 'Anthropic', model: 'claude-3-7-sonnet', inputPer1M: 3.00, outputPer1M: 15.00, tier: 'High Reasoning' },
  { provider: 'Anthropic', model: 'claude-3-5-haiku', inputPer1M: 0.80, outputPer1M: 4.00, tier: 'Fast / Balanced' },
  { provider: 'Anthropic', model: 'claude-haiku-4-5', inputPer1M: 1.00, outputPer1M: 5.00, tier: 'Fast / Balanced' },
  { provider: 'OpenAI', model: 'gpt-4o', inputPer1M: 2.50, outputPer1M: 10.00, tier: 'High Reasoning' },
  { provider: 'OpenAI', model: 'gpt-4o-mini', inputPer1M: 0.15, outputPer1M: 0.60, tier: 'Ultra-Fast' },
  { provider: 'Google', model: 'gemini-2.0-flash', inputPer1M: 0.10, outputPer1M: 0.40, tier: 'Ultra-Fast' },
  { provider: 'Google', model: 'gemini-2.5-pro', inputPer1M: 1.25, outputPer1M: 10.00, tier: 'High Reasoning' },
  { provider: 'Groq', model: 'llama-3.3-70b-versatile', inputPer1M: 0.59, outputPer1M: 0.79, tier: 'Fast / Balanced' },
  { provider: 'Perplexity', model: 'sonar', inputPer1M: 1.00, outputPer1M: 1.00, tier: 'Fast / Balanced' },
  { provider: 'Perplexity', model: 'sonar-pro', inputPer1M: 3.00, outputPer1M: 15.00, tier: 'High Reasoning' },
  { provider: 'DeepSeek', model: 'deepseek-chat', inputPer1M: 0.14, outputPer1M: 0.28, tier: 'Ultra-Fast' },
];

export function CostLedgerView({ report, telemetry: propTelemetry, onNavigateToTab }: CostLedgerViewProps) {
  const telemetry = propTelemetry || report?.telemetry || {
    total_tokens: 0,
    input_tokens: 0,
    output_tokens: 0,
    estimated_cost_usd: 0,
    actual_cost_usd: 0,
    calculated_cost_usd: 0,
    total_latency_ms: 0,
    model_calls_count: 0,
    agent_timings: {},
    stage_costs: {},
  };

  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({
    specialist_execution: true,
    page_intelligence: true,
    business_understanding: true,
    ai_visibility_monitor: true,
  });
  const [showCallRecords, setShowCallRecords] = useState(false);
  const [showRateCard, setShowRateCard] = useState(false);
  const [copiedLedger, setCopiedLedger] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const stageEntries: StageCostRecord[] = useMemo(() => {
    if (!telemetry.stage_costs) return [];
    return Object.values(telemetry.stage_costs);
  }, [telemetry.stage_costs]);

  const totalCost = telemetry.estimated_cost_usd ?? 0;
  const actualCost = telemetry.actual_cost_usd ?? 0;
  const calculatedCost = telemetry.calculated_cost_usd ?? (totalCost - actualCost);
  const totalCalls = telemetry.model_calls_count || 0;
  const inTokens = telemetry.input_tokens || 0;
  const outTokens = telemetry.output_tokens || 0;
  const totalTokens = telemetry.total_tokens || (inTokens + outTokens);
  const totalLatency = telemetry.total_latency_ms || 0;
  const avgLatency = totalCalls > 0 ? totalLatency / totalCalls : 0;
  const hasActual = Boolean(telemetry.has_actual_costs && actualCost > 0);

  const toggleStage = (stageKey: string) => {
    setExpandedStages((prev) => ({ ...prev, [stageKey]: !prev[stageKey] }));
  };

  const expandAll = () => {
    const all: Record<string, boolean> = {};
    stageEntries.forEach((s) => { all[s.stage] = true; });
    setExpandedStages(all);
  };

  const collapseAll = () => {
    setExpandedStages({});
  };

  const handleCopyLedger = () => {
    const data = {
      domain: report?.domain,
      analysis_id: report?.analysis_id,
      generated_at: new Date().toISOString(),
      summary: {
        total_cost_usd: totalCost,
        actual_cost_usd: actualCost,
        calculated_cost_usd: calculatedCost,
        total_tokens: totalTokens,
        input_tokens: inTokens,
        output_tokens: outTokens,
        model_calls_count: totalCalls,
        total_latency_ms: totalLatency,
        cost_basis: telemetry.cost_basis,
      },
      stages: stageEntries,
      raw_calls: telemetry.agent_calls || [],
    };
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedLedger(true);
    setTimeout(() => setCopiedLedger(null as any), 2500);
  };

  const handleDownloadCsv = () => {
    const rows = [
      ['Stage', 'Sub-Step', 'Capability', 'Models', 'Calls', 'Input Tokens', 'Output Tokens', 'Latency (ms)', 'Basis', 'Formula / Rate', 'Cost (USD)'],
    ];

    stageEntries.forEach((s) => {
      const subSteps = s.sub_steps ? Object.values(s.sub_steps) : [];
      if (subSteps.length > 0) {
        subSteps.forEach((sub) => {
          rows.push([
            `"${s.display_name || s.stage}"`,
            `"${sub.display_name || sub.sub_step}"`,
            `"${sub.capability || ''}"`,
            `"${(sub.models || []).join(';')}"`,
            String(sub.calls_count),
            String(sub.input_tokens),
            String(sub.output_tokens),
            String(Math.round(sub.latency_ms)),
            `"${sub.is_actual ? 'Actual Provider Charge' : 'Calculated List Rate'}"`,
            `"${sub.formula_rate || ''}"`,
            sub.cost_usd.toFixed(6),
          ]);
        });
      } else {
        rows.push([
          `"${s.display_name || s.stage}"`,
          '"Primary Execution"',
          '""',
          `"${(s.models || []).join(';')}"`,
          String(s.calls_count),
          String(s.input_tokens),
          String(s.output_tokens),
          String(Math.round(s.latency_ms)),
          `"${telemetry.cost_basis || 'list_price'}"`,
          '""',
          s.cost_usd.toFixed(6),
        ]);
      }
    });

    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((e) => e.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `dristik_cost_ledger_${report?.domain || 'audit'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Provider breakdown calculation
  const providerBreakdown = useMemo(() => {
    const stats: Record<string, { calls: number; cost: number; tokens: number }> = {};
    if (telemetry.agent_calls && telemetry.agent_calls.length > 0) {
      telemetry.agent_calls.forEach((c: AgentCallRecord) => {
        const prov = (c.provider || 'unknown').toLowerCase();
        if (!stats[prov]) stats[prov] = { calls: 0, cost: 0, tokens: 0 };
        stats[prov].calls += 1;
        stats[prov].cost += (c.cost_usd || 0);
        stats[prov].tokens += ((c.input_tokens || 0) + (c.output_tokens || 0));
      });
    } else {
      // Derive from stage models
      stageEntries.forEach((s) => {
        const prov = s.models && s.models[0] ? s.models[0].split('/')[0] : 'orchestrator';
        if (!stats[prov]) stats[prov] = { calls: 0, cost: 0, tokens: 0 };
        stats[prov].calls += s.calls_count;
        stats[prov].cost += s.cost_usd;
        stats[prov].tokens += s.total_tokens;
      });
    }
    return stats;
  }, [telemetry.agent_calls, stageEntries]);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-line">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.04em] text-ink-700 mb-1">
            <Coins className="w-4 h-4 text-ink-700" />
            <span>Audit cost details</span>
            <span className="text-ink-400">·</span>
            <span className="text-ink-500 font-mono">Reported and estimated values</span>
          </div>
          <h1 className="text-2xl font-sans font-bold text-ink">
            AI audit cost ledger
          </h1>
          <p className="text-sm text-ink-500 mt-1 max-w-3xl">
            Review the cost data returned for each pipeline stage. Provider-billed amounts are separated from estimates calculated using token counts and the selected rate card.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRateCard(!showRateCard)}
            className="text-xs px-3 py-1.5 rounded-md border border-line bg-surface hover:bg-paper-50 font-medium text-ink-700 flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Calculator className="w-3.5 h-3.5 text-ink-700" />
            {showRateCard ? 'Hide rate reference' : 'View rate reference'}
          </button>
          <button
            type="button"
            onClick={handleCopyLedger}
            className="text-xs px-3 py-1.5 rounded-md border border-line bg-surface hover:bg-paper-50 font-medium text-ink-700 flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            {copiedLedger ? <Check className="w-3.5 h-3.5 text-ink-700" /> : <Copy className="w-3.5 h-3.5 text-ink-500" />}
            {copiedLedger ? 'Copied Ledger JSON' : 'Copy JSON'}
          </button>
          <button
            type="button"
            onClick={handleDownloadCsv}
            className="text-xs px-3 py-1.5 rounded-md bg-pine text-white hover:bg-pine/90 font-medium flex items-center gap-1.5 shadow-sm transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            Download CSV Ledger
          </button>
        </div>
      </div>

      {/* 2. Top-Level Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Cost */}
        <div className="p-4 rounded-xl border border-line bg-paper-100 shadow-sm relative overflow-hidden">
          <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-ink-700 flex items-center justify-between">
            <span>Total AI Audit Cost</span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-paper-200 text-ink-700 font-semibold">
              {hasActual ? 'Provider Billed' : 'Calculated Token Math'}
            </span>
          </div>
          <div className="text-3xl font-mono font-bold text-ink-700 mt-2">
            ${totalCost.toFixed(4)}
          </div>
          <div className="text-[11px] text-ink-500 mt-1 flex items-center justify-between font-mono">
            <span>Actual: ${actualCost.toFixed(4)}</span>
            <span>Calc: ${calculatedCost.toFixed(4)}</span>
          </div>
        </div>

        {/* Total Tokens */}
        <div className="p-4 rounded-xl border border-line bg-surface shadow-sm">
          <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-ink-500 flex items-center justify-between">
            <span>Total Tokens Processed</span>
            <Cpu className="w-3.5 h-3.5 text-ink-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-ink mt-2">
            {totalTokens.toLocaleString()}
          </div>
          <div className="text-[11px] text-ink-500 mt-1 font-mono">
            <span>{inTokens.toLocaleString()} in</span>
            <span className="text-ink-300 mx-1">·</span>
            <span>{outTokens.toLocaleString()} out</span>
          </div>
        </div>

        {/* Model Calls */}
        <div className="p-4 rounded-xl border border-line bg-surface shadow-sm">
          <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-ink-500 flex items-center justify-between">
            <span>Total Model Dispatches</span>
            <Zap className="w-3.5 h-3.5 text-warn" />
          </div>
          <div className="text-2xl font-mono font-bold text-ink mt-2">
            {totalCalls}
          </div>
          <div className="text-[11px] text-ink-500 mt-1">
            Across {stageEntries.length} execution stages
          </div>
        </div>

        {/* Latency */}
        <div className="p-4 rounded-xl border border-line bg-surface shadow-sm">
          <div className="text-[11px] font-bold uppercase tracking-[0.04em] text-ink-500 flex items-center justify-between">
            <span>Inference Latency</span>
            <Clock className="w-3.5 h-3.5 text-ink-700" />
          </div>
          <div className="text-2xl font-mono font-bold text-ink mt-2">
            {formatMs(totalLatency)}
          </div>
          <div className="text-[11px] text-ink-500 mt-1 font-mono">
            avg {Math.round(avgLatency)}ms / call
          </div>
        </div>
      </div>

      {/* 3. Mathematical Formula Guarantee Note */}
      <div className="p-3.5 rounded-lg border border-line bg-paper-50/70 text-xs text-ink-600 flex items-start gap-3">
        <Info className="w-4 h-4 text-ink-700 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-semibold text-ink-700">
            Zero-Fake Real Pricing Guarantee
          </div>
          <p className="text-ink-500 leading-relaxed">
            Local steps (Chromium page crawling, DOM parsing, schema verification, and rule scoring) consume <strong className="text-ink-700">$0.00 compute</strong>.
            For each model invocation, cost is computed via <code className="bg-paper-200/60 px-1 py-0.5 rounded text-[11px] font-mono text-ink-700">(Input Tokens / 1M × Rate) + (Output Tokens / 1M × Rate)</code> using official published list cards, or exact dollar amounts billed by OpenRouter.
          </p>
        </div>
      </div>

      {/* 4. Official Model Rate Card Modal/Drawer (Toggled) */}
      {showRateCard && (
        <div className="p-4 rounded-xl border border-line bg-paper-50 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calculator className="w-4 h-4 text-ink-700" />
              <h3 className="text-xs font-bold uppercase tracking-[0.04em] text-ink-700">
                Official Price Card Rates (Per 1 Million Tokens)
              </h3>
            </div>
            <span className="text-[10px] text-ink-400 font-mono">Checked 2026-09-27</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-[10px] uppercase tracking-[0.04em] text-ink-500 font-semibold">
                  <th className="py-2 px-2">Provider</th>
                  <th className="py-2 px-2">Model</th>
                  <th className="py-2 px-2">Tier</th>
                  <th className="py-2 px-2 text-right">Prompt (Input / 1M)</th>
                  <th className="py-2 px-2 text-right">Completion (Output / 1M)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/40 font-mono text-[11px]">
                {OFFICIAL_RATE_CARD.map((r) => (
                  <tr key={`${r.provider}-${r.model}`} className="hover:bg-paper-100/60">
                    <td className="py-1.5 px-2 font-sans font-medium text-ink-700">{r.provider}</td>
                    <td className="py-1.5 px-2 font-semibold text-ink-700">{r.model}</td>
                    <td className="py-1.5 px-2 font-sans text-ink-500">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                        r.tier === 'High Reasoning' ? 'bg-paper-100 text-ink-700' :
                        r.tier === 'Fast / Balanced' ? 'bg-paper-100 text-ink-700' :
                        'bg-good/10 text-good'
                      }`}>
                        {r.tier}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-right text-ink-700">${r.inputPer1M.toFixed(2)}</td>
                    <td className="py-1.5 px-2 text-right text-ink-700">${r.outputPer1M.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Provider & Model Spend Distribution */}
      <div className="p-4 rounded-xl border border-line bg-surface shadow-sm space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-[0.04em] text-ink-700 flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-ink-700" />
          Spend Distribution by Provider & Engine Family
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          {Object.entries(providerBreakdown).map(([prov, stat]) => {
            const pct = totalCost > 0 ? (stat.cost / totalCost * 100) : 0;
            return (
              <div key={prov} className="p-3 rounded-lg border border-line bg-paper-50/50">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold capitalize text-ink-700">{prov}</span>
                  <span className="font-mono text-ink-500">{pct.toFixed(1)}%</span>
                </div>
                <div className="text-lg font-mono font-bold text-ink-700">
                  ${stat.cost.toFixed(4)}
                </div>
                <div className="text-[10px] text-ink-400 font-mono mt-0.5 flex justify-between">
                  <span>{stat.calls} calls</span>
                  <span>{stat.tokens.toLocaleString()} tokens</span>
                </div>
                <div className="w-full h-1 bg-line/60 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-ink" style={{ width: `${Math.min(100, Math.max(2, pct))}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. Comprehensive Stage and Sub-Step Tree Table */}
      <div className="rounded-xl border border-line bg-surface shadow-sm overflow-hidden space-y-0">
        <div className="p-4 border-b border-line bg-paper-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-ink-700" />
            <h3 className="text-sm font-bold text-ink">
              Step & Sub-Step Cost Ledger
            </h3>
            <span className="text-xs text-ink-400 font-mono">({stageEntries.length} Stages)</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={expandAll}
              className="text-xs text-ink-600 hover:text-ink px-2 py-1 rounded border border-line bg-surface hover:bg-paper-50 transition-colors"
            >
              Expand All
            </button>
            <button
              type="button"
              onClick={collapseAll}
              className="text-xs text-ink-600 hover:text-ink px-2 py-1 rounded border border-line bg-surface hover:bg-paper-50 transition-colors"
            >
              Collapse All
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] uppercase tracking-[0.04em] text-ink-500 font-semibold bg-paper-100/50">
                <th className="py-2.5 px-3">Pipeline Stage / Sub-Step</th>
                <th className="py-2.5 px-3">Engine / Model</th>
                <th className="py-2.5 px-3 text-right">Calls</th>
                <th className="py-2.5 px-3 text-right">Tokens (In / Out)</th>
                <th className="py-2.5 px-3 text-right">Latency</th>
                <th className="py-2.5 px-3 text-right">Accounting Basis</th>
                <th className="py-2.5 px-3 text-right">Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60 font-mono">
              {stageEntries.map((stage) => {
                const isExpanded = Boolean(expandedStages[stage.stage]);
                const subSteps = stage.sub_steps ? Object.values(stage.sub_steps) : [];
                const stageCost = stage.cost_usd || 0;
                const stagePct = totalCost > 0 ? (stageCost / totalCost * 100) : 0;

                return (
                  <React.Fragment key={stage.stage}>
                    {/* Stage Header Row */}
                    <tr
                      onClick={() => toggleStage(stage.stage)}
                      className="bg-paper-50/70 hover:bg-paper-100/70 transition-colors cursor-pointer font-semibold text-ink-900 border-t border-line"
                    >
                      <td className="py-2.5 px-3 font-sans flex items-center gap-2">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-ink-700 shrink-0" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-ink-400 shrink-0" />
                        )}
                        <div>
                          <div className="font-bold text-ink-900 text-xs">
                            {stage.display_name || stage.stage}
                          </div>
                          <div className="text-[10px] text-ink-400 font-mono font-normal">
                            stage_id: {stage.stage} {subSteps.length > 0 ? `· ${subSteps.length} sub-steps` : ''}
                          </div>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-ink-600 font-mono text-[11px]">
                        {(stage.models || []).join(', ') || '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right text-ink-700">{stage.calls_count}</td>
                      <td className="py-2.5 px-3 text-right text-ink-700">
                        <span>{stage.input_tokens.toLocaleString()}</span>
                        <span className="text-ink-400"> / </span>
                        <span>{stage.output_tokens.toLocaleString()}</span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-ink-700">
                        {formatMs(stage.latency_ms)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-paper-200/60 text-ink-700">
                          {stagePct.toFixed(1)}% of audit
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-ink-700 text-sm">
                        ${stageCost.toFixed(4)}
                      </td>
                    </tr>

                    {/* Sub-Steps Breakdown (Expanded) */}
                    {isExpanded && subSteps.length > 0 && subSteps.map((sub) => (
                      <tr
                        key={`${stage.stage}-${sub.sub_step}`}
                        className="bg-surface hover:bg-paper-50/60 transition-colors text-[11px] border-b border-line/30"
                      >
                        <td className="py-2 px-3 pl-9 font-sans text-ink-700">
                          <div className="font-medium text-ink-700">{sub.display_name || sub.sub_step}</div>
                          {sub.capability && (
                            <div className="text-[10px] text-ink-400 font-mono">capability: {sub.capability}</div>
                          )}
                        </td>
                        <td className="py-2 px-3 text-ink-600 font-mono text-[10px]">
                          {(sub.models || []).join(', ') || '—'}
                        </td>
                        <td className="py-2 px-3 text-right text-ink-600">{sub.calls_count}</td>
                        <td className="py-2 px-3 text-right text-ink-600">
                          <span>{sub.input_tokens.toLocaleString()}</span>
                          <span className="text-ink-400"> / </span>
                          <span>{sub.output_tokens.toLocaleString()}</span>
                        </td>
                        <td className="py-2 px-3 text-right text-ink-600">
                          {formatMs(sub.latency_ms)}
                        </td>
                        <td className="py-2 px-3 text-right font-sans">
                          {sub.is_actual ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-good/10 text-good border border-good/30">
                              Actual Billed
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-paper-100 text-ink-700 border border-line" title={sub.formula_rate}>
                              Calculated Math
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold text-ink-700">
                          ${sub.cost_usd.toFixed(4)}
                        </td>
                      </tr>
                    ))}

                    {/* Fallback if no sub-steps instrumented yet (e.g. historical run) */}
                    {isExpanded && subSteps.length === 0 && (
                      <tr className="bg-surface/50 text-[11px] text-ink-400 italic">
                        <td colSpan={7} className="py-2 px-3 pl-9">
                          Primary stage execution ({stage.calls_count} call(s), ${(stage.cost_usd || 0).toFixed(4)} USD)
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
            {/* Grand Total Footer */}
            <tfoot>
              <tr className="border-t-2 border-line font-bold text-ink-900 bg-paper-100/90 text-xs">
                <td className="py-3 px-3 font-sans">
                  <div className="font-bold text-sm text-ink-950">Grand Total Audit Cost</div>
                  <div className="text-[10px] text-ink-500 font-mono font-normal">
                    Aggregated across all {stageEntries.length} stages & model dispatches
                  </div>
                </td>
                <td className="py-3 px-3 text-ink-600 font-mono text-[11px]">
                  {telemetry.models_used ? telemetry.models_used.join(' · ') : '—'}
                </td>
                <td className="py-3 px-3 text-right font-mono">{totalCalls}</td>
                <td className="py-3 px-3 text-right font-mono">
                  <span>{inTokens.toLocaleString()}</span>
                  <span className="text-ink-400"> / </span>
                  <span>{outTokens.toLocaleString()}</span>
                </td>
                <td className="py-3 px-3 text-right font-mono">{formatMs(totalLatency)}</td>
                <td className="py-3 px-3 text-right font-sans">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-paper-200 text-ink-700">
                    {hasActual ? 'Provider Billed Receipts' : 'Calculated List Rate'}
                  </span>
                </td>
                <td className="py-3 px-3 text-right font-mono text-ink-700 text-base font-bold">
                  ${totalCost.toFixed(4)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* 7. Verbatim Raw Call Records Inspector (Optional Drawer) */}
      <div className="p-4 rounded-xl border border-line bg-surface shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-ink-700" />
            <h3 className="text-xs font-bold uppercase tracking-[0.04em] text-ink-700">
              Verbatim Model Invocation Records
            </h3>
            <span className="text-xs text-ink-400 font-mono">({telemetry.agent_calls?.length || 0} total calls)</span>
          </div>

          <button
            type="button"
            onClick={() => setShowCallRecords(!showCallRecords)}
            className="text-xs text-ink-700 hover:underline font-semibold cursor-pointer"
          >
            {showCallRecords ? 'Hide Verbatim Logs' : 'View Verbatim Call Logs'}
          </button>
        </div>

        {showCallRecords && (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-[10px] uppercase tracking-[0.04em] text-ink-500 font-semibold bg-paper-50">
                  <th className="py-2 px-2">Call ID / Capability</th>
                  <th className="py-2 px-2">Provider & Model</th>
                  <th className="py-2 px-2 text-right">In Tokens</th>
                  <th className="py-2 px-2 text-right">Out Tokens</th>
                  <th className="py-2 px-2 text-right">Latency</th>
                  <th className="py-2 px-2 text-right">Basis</th>
                  <th className="py-2 px-2 text-right">Call Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/40 font-mono text-[11px]">
                {(telemetry.agent_calls || []).map((call: AgentCallRecord) => (
                  <tr key={call.call_id} className="hover:bg-paper-50/60">
                    <td className="py-1.5 px-2">
                      <div className="font-sans font-semibold text-ink-700">{call.capability}</div>
                      <div className="text-[10px] text-ink-400">{call.call_id}</div>
                    </td>
                    <td className="py-1.5 px-2 text-ink-700">
                      <span className="font-semibold text-ink-900">{call.provider}</span>
                      <span className="text-ink-400"> / </span>
                      <span>{call.model}</span>
                    </td>
                    <td className="py-1.5 px-2 text-right text-ink-700">{call.input_tokens.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-right text-ink-700">{call.output_tokens.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-right text-ink-600">{formatMs(call.latency_ms)}</td>
                    <td className="py-1.5 px-2 text-right">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                        call.is_actual ? 'bg-good/10 text-good' : 'bg-paper-200 text-ink-700'
                      }`}>
                        {call.cost_basis}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-right font-bold text-ink-700">
                      ${(call.cost_usd || 0).toFixed(6)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
