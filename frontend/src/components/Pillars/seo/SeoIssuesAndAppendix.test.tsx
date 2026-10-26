import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SeoIssuesAndAppendix } from './SeoIssuesAndAppendix';
import { ExecutiveReport, Finding } from '../../../types';

const finding: Finding = {
  finding_id: 'seo-title-001',
  category: 'ON_PAGE_SEO',
  severity: 'HIGH',
  title: 'Duplicate page titles',
  description: 'Two checked pages share the same title.',
  evidence: [
    {
      evidence_id: 'ev_001',
      url: 'https://example.com/service',
      element: 'title',
      value: 'Services | Example',
    },
  ],
  evidence_refs: ['ev_001'],
  confidence: 0.94,
  confidence_label: 'HIGH',
  impact: 8,
  effort: 2,
  priority: 8,
  recommendation: 'Write a distinct title for each page.',
  verification_status: 'PAGE_VERIFIED',
  observed_result: 'The title string is identical on two checked URLs.',
  why_it_matters: 'Distinct titles help searchers understand how pages differ.',
  who_affected: 'The service and category landing pages.',
  developer_instructions: 'Update the title template to include the page-specific service name.',
  verification_steps: ['Re-crawl both URLs.', 'Confirm the title strings are unique.'],
  expected_outcome: 'Each checked URL has a unique, descriptive title.',
  scope_hit_count: 2,
  scope_sample_size: 8,
};

describe('SeoIssuesAndAppendix', () => {
  it('shows evidence-backed explanation and verification details', () => {
    render(
      <SeoIssuesAndAppendix
        report={{ domain: 'example.com', crawl_manifest: { pages: [] } } as unknown as ExecutiveReport}
        seoFindings={[finding]}
      />,
    );

    expect(screen.getByText('Duplicate page titles')).toBeInTheDocument();
    expect(screen.getByText('Analysis, evidence and verification')).toBeInTheDocument();
    expect(screen.getByText('The title string is identical on two checked URLs.')).toBeInTheDocument();
    expect(screen.getByText('Distinct titles help searchers understand how pages differ.')).toBeInTheDocument();
    expect(screen.getByText('2 affected of 8 checked')).toBeInTheDocument();
    expect(screen.getByText(/Evidence ID: ev_001/)).toBeInTheDocument();
    expect(screen.getByText('Re-crawl both URLs.')).toBeInTheDocument();
  });

  it('does not call an empty filtered list an optimal audit', () => {
    render(
      <SeoIssuesAndAppendix
        report={{ domain: 'example.com', crawl_manifest: { pages: [] } } as unknown as ExecutiveReport}
        seoFindings={[]}
      />,
    );

    expect(screen.getByText('No findings match the current filter')).toBeInTheDocument();
    expect(screen.getByText(/does not mean the full site is issue-free/i)).toBeInTheDocument();
    expect(screen.queryByText(/operating optimally/i)).not.toBeInTheDocument();
  });
});
