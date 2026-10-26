import React from 'react';
import { ArrowRight, CheckCircle2, Database, Gauge, ShieldCheck } from 'lucide-react';
import { Card } from '../../ui';

interface SeoScoreMethodologyProps {
  score: number | null;
  status?: string | null;
  checkedUrls: number;
  findingCount: number;
  onNavigate: (tab: string) => void;
}

const steps = [
  {
    number: '01',
    title: 'Collect observations',
    detail: 'Inspect the URLs and technical signals actually returned by this audit.',
    icon: Database,
  },
  {
    number: '02',
    title: 'Validate evidence',
    detail: 'Separate measured results from missing, unavailable, inferred, or untested data.',
    icon: ShieldCheck,
  },
  {
    number: '03',
    title: 'Calculate the SEO index',
    detail: 'Use the report’s Technical SEO category score when the scoring service supplies one.',
    icon: Gauge,
  },
  {
    number: '04',
    title: 'Explain the gaps',
    detail: 'Use affected-page findings and evidence to decide what to fix and re-check.',
    icon: CheckCircle2,
  },
];

export function SeoScoreMethodology({
  score,
  status,
  checkedUrls,
  findingCount,
  onNavigate,
}: SeoScoreMethodologyProps) {
  const unavailable = score == null || !Number.isFinite(score);
  const measurementState = unavailable
    ? 'Not measured'
    : status && ['PARTIAL', 'INCOMPLETE', 'SAMPLE_VERIFIED'].includes(status.toUpperCase())
      ? 'Partial measurement'
      : 'Score available';

  return (
    <Card className="space-y-5 border-line bg-paper-50 p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-pine-600">How the rating works</p>
          <h3 className="mt-1 text-base font-semibold text-ink">From website evidence to an explainable SEO rating</h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-ink-500">
            This is the process behind the report, not a claim that every URL or signal was measured. Unavailable data is not treated as a pass.
          </p>
        </div>
        <div className="min-w-[130px] rounded-lg border border-line bg-paper-100 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-ink-500">Technical SEO index</div>
          <div className="mt-1 font-mono text-2xl font-bold text-ink">{unavailable ? '—' : Math.round(score)}</div>
          <div className="text-[10px] text-ink-500">/100 · {measurementState}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <React.Fragment key={step.number}>
              <div className="min-w-0 rounded-lg border border-line bg-paper-100/70 p-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] font-semibold text-pine-600">{step.number}</span>
                  <Icon className="h-4 w-4 text-pine-600" aria-hidden="true" />
                </div>
                <h4 className="mt-2 text-xs font-semibold text-ink">{step.title}</h4>
                <p className="mt-1 text-[11px] leading-5 text-ink-500">{step.detail}</p>
              </div>
              {index < steps.length - 1 && (
                <ArrowRight className="hidden h-4 w-4 self-center text-ink-400 md:hidden" aria-hidden="true" />
              )}
            </React.Fragment>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-500">
          <span><strong className="text-ink">{checkedUrls}</strong> URLs in the saved crawl result</span>
          <span><strong className="text-ink">{findingCount}</strong> SEO findings in this report</span>
          <span>Sub-metric bars below are diagnostics, not invented score weights.</span>
        </div>
        <button
          type="button"
          onClick={() => onNavigate('issues')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-pine-600 hover:underline"
        >
          Review evidence and gaps <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </Card>
  );
}
