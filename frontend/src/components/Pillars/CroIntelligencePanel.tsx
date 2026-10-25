import React, { useMemo, useState } from 'react';
import { CroIntelligenceReport, ExecutiveReport } from '../../types';
import { Card } from '../ui';

interface CroIntelligencePanelProps {
  report: ExecutiveReport;
  analysisId?: string;
}

function statusClass(status: string): string {
  const value = status.toUpperCase();
  if (value === 'GAP' || value === 'HIGH') return 'text-bad';
  if (value === 'PARTIAL' || value === 'MEDIUM' || value === 'NEEDS VALIDATION') return 'text-warn';
  if (value === 'MEASURED' || value === 'REVIEWED' || value === 'LOW') return 'text-good';
  return 'text-ink-500';
}

function scoreText(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return 'Unmeasured';
  return score.toFixed(1);
}

export function CroIntelligencePanel({ report, analysisId }: CroIntelligencePanelProps) {
  const intel = report.cro_audit?.intelligence as CroIntelligenceReport | null | undefined;
  const [openPart, setOpenPart] = useState<string | null>(null);
  const reportId = analysisId || report.analysis_id || report.report_id;
  const reportHref = reportId ? `/api/v1/reports/${reportId}/cro-report` : '';

  const sectionsByPart = useMemo(() => {
    const groups = new Map<string, NonNullable<CroIntelligenceReport['sections']>>();
    for (const section of intel?.sections || []) {
      const current = groups.get(section.part) || [];
      current.push(section);
      groups.set(section.part, current);
    }
    return groups;
  }, [intel]);

  if (!intel || !intel.sections?.length) {
    return (
      <Card className="p-6 space-y-3">
        <h3 className="font-sans text-base font-semibold text-ink">Full CRO audit</h3>
        <p className="text-sm text-ink-700 leading-relaxed">
          This saved audit has no CRO intelligence block. The report endpoint rebuilds the 55-section audit from the stored crawl.
        </p>
        {reportHref ? (
          <a className="inline-block text-sm font-medium text-ink underline underline-offset-2" href={reportHref}>
            Open the CRO report
          </a>
        ) : (
          <p className="text-xs text-ink-500">Save the analysis to open the CRO report.</p>
        )}
      </Card>
    );
  }

  const dimensions = intel.dimensions || [];
  const metrics = intel.metrics || [];
  const findings = intel.findings || [];

  return (
    <div className="space-y-6">
      <Card className="p-5 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h3 className="font-sans text-base font-semibold text-ink">Full CRO audit</h3>
          {reportHref && (
            <a className="text-xs font-mono text-ink-700 underline underline-offset-2" href={reportHref}>
              HTML report
            </a>
          )}
        </div>
        <p className="text-sm text-ink-700 leading-relaxed">{intel.scope_note}</p>
        {intel.principle && <p className="text-sm text-ink-600 leading-relaxed">{intel.principle}</p>}
        <p className="text-xs font-mono text-ink-500">
          Model {intel.business_model || 'unclassified'}
          {intel.sample_size != null ? ` · ${intel.sample_size} inspected page(s)` : ''}
          {intel.discovered_urls != null ? ` · ${intel.discovered_urls} discovered` : ''}
        </p>
        {intel.model_basis && <p className="text-xs text-ink-500">{intel.model_basis}</p>}
        {intel.coverage && (
          <div className="rounded border border-line bg-paper-50 p-3 space-y-1">
            <p className="text-xs font-mono uppercase tracking-wide text-ink-600">Coverage and execution limits</p>
            <p className="text-xs text-ink-700">
              {intel.coverage.inspected_pages ?? intel.sample_size ?? 'Not measured'} inspected · {intel.coverage.discovered_urls ?? intel.discovered_urls ?? 'Discovery total unavailable'} discovered · {intel.coverage.sample_coverage_pct == null ? 'Sample percentage unavailable' : `${intel.coverage.sample_coverage_pct.toFixed(1)}% sample coverage`}
            </p>
            <p className="text-xs text-ink-600">
              Rendered DOM: {intel.coverage.rendered_dom_status || 'NOT_VERIFIED'} · User journeys: {intel.coverage.journey_execution_status || 'NOT_EXECUTED'}
            </p>
            {intel.coverage.note && <p className="text-xs text-ink-500">{intel.coverage.note}</p>}
          </div>
        )}
        {intel.scoring_calibration && (
          <div className="rounded border border-line bg-paper-50 p-3 space-y-1">
            <p className="text-xs font-mono uppercase tracking-wide text-ink-600">Scoring calibration</p>
            <p className="text-xs text-ink-700">{intel.scoring_calibration.status || 'NOT_RECORDED'} · {intel.scoring_calibration.priority_calibration || 'NOT_RECORDED'}</p>
            {intel.scoring_calibration.basis && <p className="text-xs text-ink-600">{intel.scoring_calibration.basis}</p>}
            {intel.scoring_calibration.note && <p className="text-xs text-ink-500">{intel.scoring_calibration.note}</p>}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {dimensions.map((dimension) => (
          <Card key={dimension.id} className="p-4 space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-[0.04em] text-ink-500 font-semibold block">
              {dimension.name}
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-2xl font-semibold text-ink">{scoreText(dimension.score)}</span>
              <span className={`font-mono text-xs ${statusClass(dimension.status)}`}>{dimension.status}</span>
            </div>
            <p className="text-xs text-ink-600 leading-relaxed">{dimension.note}</p>
          </Card>
        ))}
      </div>

      <Card className="p-4 space-y-3 overflow-x-auto">
        <h3 className="font-sans text-sm font-semibold text-ink">Metrics</h3>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-line text-ink-500 font-mono">
              <th className="py-2 pr-3 font-medium">Metric</th>
              <th className="py-2 pr-3 font-medium">Formula</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 font-medium">Value</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.metric} className="border-b border-line align-top">
                <td className="py-2 pr-3 text-ink">{metric.metric}</td>
                <td className="py-2 pr-3 text-ink-600">{metric.formula}</td>
                <td className={`py-2 pr-3 font-mono ${statusClass(metric.status)}`}>{metric.status}</td>
                <td className="py-2 font-mono text-ink">
                  {metric.display}
                  {metric.denominator ? <span className="block text-ink-500">Denominator: {metric.denominator}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="space-y-3">
        <h3 className="font-sans text-sm font-semibold text-ink">Findings ({findings.length})</h3>
        {findings.length === 0 ? (
          <Card className="p-4">
            <p className="text-sm text-ink-600">No experience defect met the evidence bar for a finding.</p>
          </Card>
        ) : findings.map((finding) => (
          <Card key={finding.finding_id} className="p-4 space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h4 className="font-mono text-xs text-ink">{finding.finding_id}</h4>
              <span className={`font-mono text-[10px] uppercase ${statusClass(finding.priority)}`}>{finding.priority}</span>
            </div>
            <p className="text-sm text-ink">{finding.finding}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Evidence. </span>{finding.evidence}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Scope. </span>{finding.observed_scope}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Hypothesis. </span>{finding.hypothesis}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Action. </span>{finding.recommended_action}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Metric. </span>{finding.primary_metric}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Guardrails. </span>{(finding.guardrail_metrics || []).join(', ')}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Validation. </span>{finding.validation}</p>
            <p className="text-xs text-ink-600"><span className="font-semibold text-ink-700">Impact. </span>{finding.impact_estimate}</p>
            <p className="text-xs font-mono text-ink-500">{finding.status} · {finding.owner} · {finding.evidence_state}</p>
          </Card>
        ))}
      </div>

      <div className="space-y-3">
        <h3 className="font-sans text-sm font-semibold text-ink">Taxonomy</h3>
        {(intel.parts || []).map((part) => {
          const sections = sectionsByPart.get(part.id) || [];
          const open = openPart === part.id;
          return (
            <Card key={part.id} className="p-4 space-y-2">
              <button
                type="button"
                className="w-full text-left"
                onClick={() => setOpenPart(open ? null : part.id)}
              >
                <span className="font-mono text-[10px] uppercase tracking-[0.04em] text-ink-500">Part {part.id}</span>
                <span className="block font-sans text-sm font-semibold text-ink">{part.title}</span>
                <span className="text-xs text-ink-500">{sections.length} section(s)</span>
              </button>
              {open && sections.map((section) => (
                <div key={section.number} className="border-t border-line pt-2 space-y-1">
                  <p className="text-sm text-ink">
                    <span className="font-mono text-xs text-ink-500">{section.number}. </span>
                    {section.title}
                  </p>
                  <p className={`text-[10px] font-mono uppercase ${statusClass(section.status)}`}>{section.status}</p>
                  <ul className="space-y-1">
                    {section.checks.map((check) => (
                      <li key={check.check_id} className="text-xs text-ink-600">
                        <span className="font-mono text-ink-500">{check.evidence_state}</span> {check.label}. {check.summary}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
