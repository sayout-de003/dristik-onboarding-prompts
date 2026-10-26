import React, { useState } from 'react';
import { AnalysisRun } from '../types';
import { formatMs } from '../lib/format';
import { LiveExecutionConsole } from './LiveExecutionConsole';

const STAGES = [
  { key: 'ingesting', label: 'Crawl' },
  { key: 'deterministic_analysis', label: 'Evidence' },
  { key: 'planning', label: 'Plan' },
  { key: 'specialist_execution', label: 'Specialists' },
  { key: 'adversarial_verification', label: 'Verify' },
  { key: 'executive_synthesis', label: 'Narrative' },
  { key: 'scoring', label: 'Score' },
];

interface PipelineProps {
  run: AnalysisRun;
  onRefreshRun?: () => void;
}

export function Pipeline({ run, onRefreshRun }: PipelineProps) {
  const [showStages, setShowStages] = useState(false);
  const order = STAGES.map((s) => s.key);
  const currentIndex = order.findIndex((key) => key === run.status);
  const done = run.status === 'completed';
  const failed = run.status === 'failed';

  const telemetry = run.telemetry;
  const stageCosts = telemetry?.stage_costs ? Object.values(telemetry.stage_costs) : [];
  const totalCost = telemetry?.estimated_cost_usd;
  const actualCost = telemetry?.actual_cost_usd ?? 0;
  const isActualBilled = (telemetry?.has_actual_costs ?? false) && actualCost > 0;

  return (
    <div className="space-y-4">
      {/* Live Interactive Terminal & DAG Execution Console */}
      <LiveExecutionConsole run={run} onRefreshRun={onRefreshRun} />

      {/* Pipeline Summary & Live Cost Meter */}
      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <ol className="flex flex-wrap gap-x-4 gap-y-1">
            {STAGES.map((stage, index) => {
              const passed = done || (currentIndex >= 0 && index < currentIndex);
              const current = !done && !failed && stage.key === run.status;
              return (
                <li
                  key={stage.key}
                  className={passed ? 'text-good font-medium' : current ? 'text-ink font-bold' : 'text-ink-300'}
                >
                  {stage.label}
                </li>
              );
            })}
          </ol>
          <div className="flex items-center gap-1.5 font-mono text-xs">
            <span className="text-ink-500">Progress:</span>
            <span
              className={`font-bold px-2 py-0.5 rounded border ${
                done
                  ? 'bg-good/10 text-good border-good/30'
                  : 'bg-paper-200 text-ink-700 border-line'
              }`}
            >
              {done ? '100% Complete' : run.progress_percentage == null ? 'Progress not reported' : `${run.progress_percentage}%`}
            </span>
          </div>
        </div>

      {/* Live Stage Cost Meter */}
      {telemetry && (
        <div className="pt-3 border-t border-line/60">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-semibold bg-paper-200 text-ink-700 border border-line">
                <span>Total AI Cost:</span>
                <span>{totalCost == null ? 'Not reported' : `USD ${totalCost.toFixed(4)}`}</span>
              </span>
              {isActualBilled && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono bg-paper-100 text-ink-700">
                  Actual Billed: ${actualCost.toFixed(4)}
                </span>
              )}
              <span className="text-ink-500">
                {telemetry.total_tokens == null ? 'Tokens not reported' : `${telemetry.total_tokens.toLocaleString()} tokens`} • {telemetry.model_calls_count == null ? 'Calls not reported' : `${telemetry.model_calls_count} calls`}
              </span>
            </div>

            {stageCosts.length > 0 && (
              <button
                type="button"
                onClick={() => setShowStages(!showStages)}
                className="text-ink-700 hover:underline font-medium flex items-center gap-1 cursor-pointer"
              >
                {showStages ? '▲ Hide stage costs' : '▼ Stage costs breakdown'}
              </button>
            )}
          </div>

          {/* Collapsible Stage-by-Stage Cost Breakdown */}
          {showStages && stageCosts.length > 0 && (
            <div className="mt-3 overflow-x-auto rounded border border-line bg-paper-50/50 p-2">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line text-[11px] uppercase tracking-[0.04em] text-ink-500">
                    <th className="py-1 px-2 font-medium">Pipeline Stage</th>
                    <th className="py-1 px-2 font-medium text-right">Calls</th>
                    <th className="py-1 px-2 font-medium text-right">Tokens</th>
                    <th className="py-1 px-2 font-medium text-right">Latency</th>
                    <th className="py-1 px-2 font-medium text-right">Stage Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/40 font-mono">
                  {stageCosts.map((s) => (
                    <tr key={s.stage} className="hover:bg-paper-100/60 transition-colors">
                      <td className="py-1 px-2 font-sans font-medium text-ink-700">
                        {s.display_name || s.stage}
                        {s.models?.length > 0 && (
                          <span className="block text-[10px] text-ink-500 font-mono">
                            {s.models.join(', ')}
                          </span>
                        )}
                      </td>
                      <td className="py-1 px-2 text-right text-ink-600">{s.calls_count}</td>
                      <td className="py-1 px-2 text-right text-ink-600">
                        {s.total_tokens.toLocaleString()}
                      </td>
                      <td className="py-1 px-2 text-right text-ink-600">{formatMs(s.latency_ms)}</td>
                      <td className="py-1 px-2 text-right font-bold text-ink-700">
                        ${s.cost_usd.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-line font-bold text-ink-900 bg-paper-100/40">
                    <td className="py-1.5 px-2 font-sans">Total Pipeline Cost</td>
                    <td className="py-1.5 px-2 text-right font-mono">{telemetry.model_calls_count ?? '—'}</td>
                    <td className="py-1.5 px-2 text-right font-mono">
                      {telemetry.total_tokens == null ? '—' : telemetry.total_tokens.toLocaleString()}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono">
                      {telemetry.total_latency_ms == null ? '—' : formatMs(telemetry.total_latency_ms)}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono text-ink-700">
                      {totalCost == null ? 'Not reported' : `USD ${totalCost.toFixed(4)}`}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}
      </section>
    </div>
  );
}
