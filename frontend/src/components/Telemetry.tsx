import React, { useState } from 'react';
import { TelemetryData } from '../types';
import { costBasisCaption, formatAuditCost, formatMs } from '../lib/format';

interface TelemetryProps {
  telemetry: TelemetryData;
  onNavigateToCosting?: () => void;
}

export function Telemetry({ telemetry, onNavigateToCosting }: TelemetryProps) {
  const [showStageTable, setShowStageTable] = useState(false);
  const stageCosts = telemetry.stage_costs ? Object.values(telemetry.stage_costs) : [];
  const models = (telemetry.models_used || []).join(' · ');
  const basis = costBasisCaption(telemetry.cost_basis);
  const totalCost = telemetry.estimated_cost_usd;
  const actualCost = telemetry.actual_cost_usd ?? 0;
  const isActualBilled = (telemetry.has_actual_costs ?? false) && actualCost > 0;

  const items = [
    { label: 'Total tokens', value: telemetry.total_tokens == null ? 'Not reported' : telemetry.total_tokens.toLocaleString() },
    { label: 'Model calls', value: telemetry.model_calls_count == null ? 'Not reported' : String(telemetry.model_calls_count) },
    { label: 'Latency', value: telemetry.total_latency_ms == null ? 'Not reported' : formatMs(telemetry.total_latency_ms) },
    { label: 'Total AI Cost', value: formatAuditCost(telemetry), highlight: true },
  ];

  return (
    <div className="no-print space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-xs">
        <dl className="flex flex-wrap items-center gap-x-6 gap-y-1 text-ink-400">
          {items.map((item) => (
            <div key={item.label} className="flex items-baseline gap-1.5">
              <dt className="text-ink-500 font-medium">{item.label}:</dt>
              <dd className={`font-mono ${item.highlight ? 'font-bold text-ink-700 text-sm' : 'text-ink-700'}`}>
                {item.value}
              </dd>
            </div>
          ))}
          {isActualBilled && (
            <div className="flex items-baseline gap-1.5">
              <dt className="text-ink-500 font-medium">Provider Billed:</dt>
              <dd className="font-mono text-ink-700 font-semibold">${actualCost.toFixed(4)}</dd>
            </div>
          )}
          {(models || basis) && (
            <div className="flex items-baseline gap-1.5">
              <dt className="text-ink-500 font-medium">Models:</dt>
              <dd className="font-mono text-ink-600">
                {models || '—'}
                {basis ? ` (${basis})` : ''}
              </dd>
            </div>
          )}
        </dl>

        <div className="flex items-center gap-2">
          {stageCosts.length > 0 && (
            <button
              type="button"
              onClick={() => setShowStageTable(!showStageTable)}
              className="text-xs text-ink-700 hover:underline font-semibold flex items-center gap-1 cursor-pointer bg-paper-100 px-2.5 py-1 rounded border border-line transition-colors hover:bg-paper-100"
            >
              {showStageTable ? 'Hide Quick Summary' : 'Quick Stage Costs'}
            </button>
          )}
          {onNavigateToCosting && (
            <button
              type="button"
              onClick={onNavigateToCosting}
              className="text-xs text-ink-700 hover:bg-pine hover:text-white font-semibold flex items-center gap-1 cursor-pointer bg-paper-200 px-2.5 py-1 rounded border border-line transition-colors"
            >
              Full Cost Ledger →
            </button>
          )}
        </div>
      </div>

      {showStageTable && stageCosts.length > 0 && (
        <div className="rounded-lg border border-line bg-paper-50/70 p-3 overflow-x-auto shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-ink-700">
              Audit Pipeline Stage Cost Ledger
            </h4>
            <span className="text-[11px] text-ink-500 font-mono">
              Total: {totalCost == null ? 'Not reported' : `USD ${totalCost.toFixed(4)}`}
            </span>
          </div>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-500 font-semibold">
                <th className="py-1.5 px-2">Pipeline Stage</th>
                <th className="py-1.5 px-2 text-right">Calls</th>
                <th className="py-1.5 px-2 text-right">Tokens (In / Out)</th>
                <th className="py-1.5 px-2 text-right">Latency</th>
                <th className="py-1.5 px-2 text-right">Stage Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40 font-mono">
              {stageCosts.map((s) => (
                <tr key={s.stage} className="hover:bg-paper-100/60 transition-colors">
                  <td className="py-1.5 px-2 font-sans font-medium text-ink-700">
                    <div>{s.display_name || s.stage}</div>
                    {s.models?.length > 0 && (
                      <div className="text-[10px] text-ink-400 font-mono">{s.models.join(', ')}</div>
                    )}
                  </td>
                  <td className="py-1.5 px-2 text-right text-ink-600">{s.calls_count}</td>
                  <td className="py-1.5 px-2 text-right text-ink-600">
                    <span>{s.input_tokens.toLocaleString()}</span>
                    <span className="text-ink-400"> / </span>
                    <span>{s.output_tokens.toLocaleString()}</span>
                  </td>
                  <td className="py-1.5 px-2 text-right text-ink-600">{formatMs(s.latency_ms)}</td>
                  <td className="py-1.5 px-2 text-right font-bold text-ink-700">
                    ${s.cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-line font-bold text-ink-900 bg-paper-100/60">
                <td className="py-2 px-2 font-sans">Total Audit Cost</td>
                <td className="py-2 px-2 text-right font-mono">{telemetry.model_calls_count ?? '—'}</td>
                <td className="py-2 px-2 text-right font-mono">
                  <span>{telemetry.input_tokens == null ? '—' : telemetry.input_tokens.toLocaleString()}</span>
                  <span className="text-ink-400"> / </span>
                  <span>{telemetry.output_tokens == null ? '—' : telemetry.output_tokens.toLocaleString()}</span>
                </td>
                <td className="py-2 px-2 text-right font-mono">
                  {telemetry.total_latency_ms == null ? '—' : formatMs(telemetry.total_latency_ms)}
                </td>
                <td className="py-2 px-2 text-right font-mono text-ink-700 text-sm">
                  {totalCost == null ? 'Not reported' : `USD ${totalCost.toFixed(4)}`}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
