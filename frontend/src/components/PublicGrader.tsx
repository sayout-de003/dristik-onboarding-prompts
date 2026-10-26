import React, { useState } from 'react';
import { ApiError, api } from '../services/http';
import { Button, Input, PageHeader } from './ui';

interface GradeFinding {
  evidence_id: string;
  title: string;
  category: string;
  severity: string;
  description: string;
  suggested_fix: string;
  source_url: string;
}

interface InspectedPage {
  url: string;
  http_status?: number | null;
  error?: string | null;
}

interface PublicGrade {
  domain: string;
  assessment_kind: string;
  coverage_note: string;
  geo_score?: number | null;
  score_kind: string;
  grade?: string | null;
  grade_label: string;
  top_findings: GradeFinding[];
  locked_findings_count: number;
  pages_inspected: InspectedPage[];
  checks_run: string[];
  checks_not_run: string[];
  ai_citations: Record<string, { status?: string; limitation?: string }>;
  traffic_summary: { measurement_status?: string; monthly_visits?: number | null; attribution_note?: string };
  conversion_note: string;
  fetch_error?: string | null;
  share_path?: string | null;
}

export function PublicGrader({ onStartAudit }: { onStartAudit: () => void }) {
  const [domain, setDomain] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [grade, setGrade] = useState<PublicGrade | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api<PublicGrade>('/api/v1/public/grade', {
        method: 'POST',
        body: JSON.stringify({ domain }),
      }, 'The grader could not fetch that domain');
      setGrade(result);
    } catch (err: unknown) {
      setGrade(null);
      setError(err instanceof ApiError ? err.message : 'The grader could not fetch that domain.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-8">
      <PageHeader
        kicker="Public grader"
        title="Get a quick, evidence-based website check."
        description="Check a small, clearly defined sample of a public website. The result shows what was observed, what was not checked, and which measurements need a full audit or connected data source."
      />
      <form className="card p-5 sm:p-6 space-y-4" onSubmit={submit}>
        <Input
          label="Domain"
          name="domain"
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="example.com"
          hint="Public sites only. Private networks and metadata addresses are refused."
          error={error}
          required
        />
        <Button type="submit" loading={loading}>
          Grade this domain
        </Button>
      </form>
      {grade && (
        <div className="space-y-6">
          <article className="card p-5 space-y-2">
            <p className="label">{grade.domain}</p>
            <p className="text-ink">
              Preliminary readiness score: {grade.geo_score == null ? 'not measured' : `${grade.geo_score}`}
              {grade.grade ? ` · ${grade.grade}` : ''} · {grade.grade_label}
            </p>
            <p className="text-sm text-ink-500">{grade.coverage_note}</p>
            <p className="text-xs font-mono text-ink-400">{grade.score_kind}</p>
            {grade.fetch_error && <p className="text-sm text-bad">{grade.fetch_error}</p>}
          </article>
          <article className="card p-5 space-y-3">
            <p className="label">Pages checked in this sample</p>
            <ul className="space-y-1 text-sm text-ink-700">
              {grade.pages_inspected.map((page) => (
                <li key={page.url} className="font-mono text-xs">
                  {page.http_status ?? '—'} {page.url}{page.error ? ` · ${page.error}` : ''}
                </li>
              ))}
            </ul>
          </article>
          <article className="card p-5 space-y-3">
            <p className="label">Issues observed in the fetched pages</p>
            {grade.top_findings.length === 0 ? (
              <p className="text-sm text-ink-500">No qualifying finding was observed in this bounded check.</p>
            ) : (
              <ul className="space-y-3">
                {grade.top_findings.map((finding) => (
                  <li key={finding.evidence_id}>
                    <p className="text-ink font-medium">{finding.title}</p>
                    <p className="text-sm text-ink-600">{finding.description}</p>
                    <p className="text-xs text-ink-400">{finding.severity} · {finding.source_url}</p>
                  </li>
                ))}
              </ul>
            )}
            {grade.locked_findings_count > 0 && (
              <p className="text-sm text-ink-500">{grade.locked_findings_count} more observed findings are in a full audit.</p>
            )}
          </article>
          <article className="card p-5 space-y-2">
            <p className="label">Not checked in this quick review</p>
            <p className="text-sm text-ink-700">{grade.traffic_summary.attribution_note}</p>
            <ul className="text-sm text-ink-600 list-disc pl-5">
              {grade.checks_not_run.map((check) => <li key={check}>{check}</li>)}
            </ul>
            <p className="text-sm text-ink-500">
              AI engines in this result: {Object.values(grade.ai_citations).every((item) => item.status === 'not_measured')
                ? 'not measured'
                : 'see each engine status'}
            </p>
          </article>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={onStartAudit}>Run a full audit</Button>
            <p className="text-sm text-ink-500">{grade.conversion_note}</p>
          </div>
        </div>
      )}
    </section>
  );
}
