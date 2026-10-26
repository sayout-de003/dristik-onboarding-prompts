import React, { useState } from 'react';
import { ExecutiveReport, Finding } from '../../../types';
import { UrlLevelTechnicalAppendix } from '../../UrlLevelTechnicalAppendix';
import { Card } from '../../ui';
import {
  Filter,
  Search,
  ArrowRight,
  FileSpreadsheet,
  AlertCircle,
  Code2,
  CheckCircle2,
} from 'lucide-react';

interface SeoIssuesAndAppendixProps {
  report: ExecutiveReport;
  seoFindings: Finding[];
  onSelectFinding?: (f: Finding) => void;
}

export function SeoIssuesAndAppendix({
  report,
  seoFindings,
  onSelectFinding,
}: SeoIssuesAndAppendixProps) {
  const [viewMode, setViewMode] = useState<'findings' | 'appendix'>('findings');
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');

  const crawl = report.crawl_manifest;
  const pages = crawl?.pages || [];

  // Filter findings based on severity and search term
  const filteredFindings = seoFindings.filter((f) => {
    if (severityFilter !== 'ALL' && f.severity !== severityFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = f.title.toLowerCase().includes(q);
      const matchDesc = f.description.toLowerCase().includes(q);
      const matchFix = f.recommendation?.toLowerCase().includes(q);
      return matchTitle || matchDesc || matchFix;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          TOP VIEW SWITCHER: FINDINGS LEDGER vs TECHNICAL APPENDIX
          ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between border-b border-line pb-3 gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode('findings')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              viewMode === 'findings'
                ? 'bg-paper-100 text-ink shadow-sm border border-line font-semibold'
                : 'text-ink-500 hover:text-ink hover:bg-paper-100/50'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            Flagged SEO Issues ({seoFindings.length})
          </button>
          <button
            type="button"
            onClick={() => setViewMode('appendix')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              viewMode === 'appendix'
                ? 'bg-paper-100 text-ink shadow-sm border border-line font-semibold'
                : 'text-ink-500 hover:text-ink hover:bg-paper-100/50'
            }`}
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            Technical URL Appendix ({pages.length})
          </button>
        </div>

        {viewMode === 'findings' && (
          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search issues..."
                className="text-xs font-sans pl-8 pr-3 py-1 rounded border border-line bg-paper-50 text-ink focus:outline-none focus:ring-1 focus:ring-pine-500 w-44"
              />
            </div>

            {/* Severity Filter Buttons */}
            <div className="flex items-center gap-1 text-xs">
              {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((sev) => (
                <button
                  key={sev}
                  type="button"
                  onClick={() => setSeverityFilter(sev)}
                  className={`px-2 py-0.5 rounded font-mono text-[11px] transition-colors ${
                    severityFilter === sev
                      ? 'bg-ink text-white font-semibold'
                      : 'bg-paper-100 text-ink-600 hover:bg-paper-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          1. FINDINGS LEDGER
          ───────────────────────────────────────────────────────────── */}
      {viewMode === 'findings' && (
        <div className="space-y-3">
          {filteredFindings.length === 0 ? (
            <Card className="p-8 text-center text-xs text-ink-500 bg-paper-50 border-line space-y-1">
              <CheckCircle2 className="w-6 h-6 text-good mx-auto mb-2" />
              <p className="font-semibold text-ink">No findings match the current filter</p>
              <p className="text-[11px]">Try another severity or search term. An empty filtered list does not mean the full site is issue-free.</p>
            </Card>
          ) : (
            filteredFindings.map((f) => (
              <div
                key={f.finding_id}
                onClick={() => onSelectFinding?.(f)}
                className="p-4 rounded-lg border border-line bg-paper-50 hover:bg-paper-100/80 hover:border-pine-500/30 transition-all cursor-pointer space-y-2.5 group"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                      f.severity === 'CRITICAL' ? 'bg-bad/10 text-bad' :
                      f.severity === 'HIGH' ? 'bg-warn/10 text-warn' :
                      f.severity === 'MEDIUM' ? 'bg-pine-500/10 text-pine-600 dark:text-pine-400' :
                      'bg-ink/5 text-ink-600'
                    }`}>
                      {f.severity}
                    </span>
                    <span className="text-xs font-mono text-ink-400">{f.category}</span>
                  </div>
                  <span className="text-xs text-pine-600 dark:text-pine-400 font-medium group-hover:underline flex items-center gap-1">
                    Inspect Evidence <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-ink group-hover:text-pine-600 transition-colors">
                    {f.title}
                  </h4>
                  <p className="text-xs text-ink-600 mt-1 leading-relaxed">
                    {f.description}
                  </p>
                </div>

                {f.recommendation && (
                  <div className="text-xs bg-paper-100/90 p-2.5 rounded border border-line/70 text-ink-700 flex items-start gap-2">
                    <Code2 className="w-3.5 h-3.5 text-pine-600 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-ink font-semibold">Remediation: </strong>
                      {f.recommendation}
                    </div>
                  </div>
                )}

                <details
                  className="rounded-lg border border-line bg-paper-100/50"
                  onClick={(event) => event.stopPropagation()}
                >
                  <summary className="cursor-pointer select-none px-3 py-2.5 text-xs font-semibold text-ink-700 hover:text-pine-600">
                    Analysis, evidence and verification
                  </summary>
                  <div className="space-y-3 border-t border-line p-3">
                    {(f.observed_result || f.what_was_checked || f.description) && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">What was observed</h5>
                        <p className="mt-1 text-xs leading-5 text-ink-700">{f.observed_result || f.what_was_checked || f.description}</p>
                      </section>
                    )}
                    {(f.why_it_matters || f.business_impact || f.calibrated_impact?.business_impact) && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">Why it matters</h5>
                        <p className="mt-1 text-xs leading-5 text-ink-700">{f.why_it_matters || f.business_impact || f.calibrated_impact?.business_impact}</p>
                      </section>
                    )}
                    {(f.who_affected || f.scope_status || f.scope_hit_count != null || f.scope_sample_size != null) && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">Affected scope</h5>
                        {f.who_affected && <p className="mt-1 text-xs leading-5 text-ink-700">{f.who_affected}</p>}
                        {(f.scope_hit_count != null || f.scope_sample_size != null) && (
                          <p className="mt-1 text-xs text-ink-500">
                            {f.scope_hit_count == null ? 'Affected count unavailable' : `${f.scope_hit_count} affected`}
                            {f.scope_sample_size == null ? '' : ` of ${f.scope_sample_size} checked`}
                          </p>
                        )}
                        {f.scope_status && <p className="mt-1 text-xs text-ink-500">Scope status: {f.scope_status}</p>}
                      </section>
                    )}
                    {(f.developer_instructions || f.grounded_recommendation?.how_to_change || f.recommendation) && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">Recommended fix</h5>
                        <p className="mt-1 text-xs leading-5 text-ink-700">{f.developer_instructions || f.grounded_recommendation?.how_to_change || f.recommendation}</p>
                        {f.grounded_recommendation?.why && <p className="mt-1 text-xs leading-5 text-ink-500">Reason: {f.grounded_recommendation.why}</p>}
                      </section>
                    )}
                    {f.evidence?.length > 0 && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">Evidence from the audit</h5>
                        <ul className="mt-1 space-y-2">
                          {f.evidence.slice(0, 5).map((evidence, index) => (
                            <li key={evidence.evidence_id || `${evidence.url || 'evidence'}-${index}`} className="rounded border border-line bg-paper-50 p-2">
                              {evidence.url && <p className="break-all text-[11px] font-medium text-pine-600">{evidence.url}</p>}
                              {evidence.element && <p className="mt-1 text-[11px] text-ink-500">Element: {evidence.element}</p>}
                              {(evidence.value || evidence.excerpt || evidence.snippet) && (
                                <p className="mt-1 break-words text-xs leading-5 text-ink-700">{evidence.value || evidence.excerpt || evidence.snippet}</p>
                              )}
                              {evidence.evidence_id && <p className="mt-1 font-mono text-[10px] text-ink-400">Evidence ID: {evidence.evidence_id}</p>}
                            </li>
                          ))}
                          {f.evidence.length > 5 && <li className="text-[11px] text-ink-500">Showing 5 of {f.evidence.length} evidence records.</li>}
                        </ul>
                      </section>
                    )}
                    {(f.verification_steps?.length || f.validation_criteria || f.expected_outcome || f.limitations) && (
                      <section>
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-ink-500">How to verify the fix</h5>
                        {f.verification_steps && f.verification_steps.length > 0 && (
                          <ol className="mt-1 list-decimal space-y-1 pl-4 text-xs leading-5 text-ink-700">
                            {f.verification_steps.map((step, index) => <li key={index}>{step}</li>)}
                          </ol>
                        )}
                        {f.validation_criteria && <p className="mt-1 text-xs leading-5 text-ink-700">Acceptance criteria: {f.validation_criteria}</p>}
                        {f.expected_outcome && <p className="mt-1 text-xs leading-5 text-ink-700">Expected result: {f.expected_outcome}</p>}
                        {f.limitations && <p className="mt-1 text-xs leading-5 text-ink-500">Limitations: {f.limitations}</p>}
                      </section>
                    )}
                    {f.evidence?.length === 0 && (
                      <p className="text-xs leading-5 text-ink-500">No evidence records were attached to this finding in the returned report. Treat the claim as unsubstantiated until its evidence is available.</p>
                    )}
                  </div>
                </details>
              </div>
            ))
          )}
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          2. TECHNICAL URL APPENDIX
          ───────────────────────────────────────────────────────────── */}
      {viewMode === 'appendix' && (
        <div className="space-y-4">
          <UrlLevelTechnicalAppendix
            pages={pages}
            manifest={crawl}
            domain={report.domain}
          />
        </div>
      )}
    </div>
  );
}
