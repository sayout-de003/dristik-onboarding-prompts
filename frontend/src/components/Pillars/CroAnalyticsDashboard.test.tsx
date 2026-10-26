import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { api } from '../../services/http';
import { ExecutiveReport } from '../../types';
import { CroAnalyticsDashboard } from './CroAnalyticsDashboard';

vi.mock('../../services/http', () => ({ api: vi.fn() }));

const emptyReport = {
  report_id: 'audit-current',
  analysis_id: 'audit-current',
  website_url: 'https://example.com',
  domain: 'example.com',
} as unknown as ExecutiveReport;

describe('CroAnalyticsDashboard', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows unavailable and empty states instead of fabricated analytics', async () => {
    vi.mocked(api).mockResolvedValue([] as never);
    render(<CroAnalyticsDashboard report={emptyReport} analysisId="audit-current" />);

    expect(screen.getByText('Current CRO rating')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No saved CRO-scored audits for this domain/)).toBeInTheDocument();
    });
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
    expect(screen.queryByText(/100 sessions/)).not.toBeInTheDocument();
  });

  it('explains the actual observed-check formula and score precedence', async () => {
    vi.mocked(api).mockResolvedValue([] as never);
    render(<CroAnalyticsDashboard report={emptyReport} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Score methodology' }));
    await waitFor(() => expect(screen.getByText('Experience-quality formula')).toBeInTheDocument());
    expect(screen.getByText('100 × passed ÷ (passed + failed)')).toBeInTheDocument();
    expect(screen.getByText('Explicit CRO score → UX_CONVERSION category score → Unavailable')).toBeInTheDocument();
  });

  it('shows a visible history error instead of silently presenting an empty chart', async () => {
    vi.mocked(api).mockRejectedValue(new Error('network unavailable'));
    render(<CroAnalyticsDashboard report={emptyReport} />);

    await waitFor(() => expect(screen.getByText(/History could not be loaded: network unavailable/)).toBeInTheDocument());
  });
});
