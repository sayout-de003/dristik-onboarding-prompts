import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SeoScoreMethodology } from './SeoScoreMethodology';

describe('SeoScoreMethodology', () => {
  it('explains the rating flow and preserves a measured score', () => {
    render(
      <SeoScoreMethodology
        score={72.4}
        status="MEASURED"
        checkedUrls={8}
        findingCount={11}
        onNavigate={vi.fn()}
      />,
    );

    expect(screen.getByText('From website evidence to an explainable SEO rating')).toBeInTheDocument();
    expect(screen.getByText('72')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('11')).toBeInTheDocument();
    expect(screen.getByText('Validate evidence')).toBeInTheDocument();
    expect(screen.getByText(/not invented score weights/i)).toBeInTheDocument();
  });

  it('does not replace an unavailable score with zero or a passing score', () => {
    render(
      <SeoScoreMethodology
        score={null}
        status="NOT_MEASURED"
        checkedUrls={0}
        findingCount={0}
        onNavigate={vi.fn()}
      />,
    );

    expect(screen.getByText(/Not measured/)).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('100')).not.toBeInTheDocument();
  });
});
