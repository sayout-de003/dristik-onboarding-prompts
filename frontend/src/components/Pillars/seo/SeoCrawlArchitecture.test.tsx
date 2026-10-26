import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SeoCrawlArchitecture } from './SeoCrawlArchitecture';
import { ExecutiveReport } from '../../../types';

describe('SeoCrawlArchitecture data availability', () => {
  it('does not present missing crawl measurements as healthy defaults', () => {
    render(<SeoCrawlArchitecture report={{} as ExecutiveReport} />);

    expect(screen.getByText('HTTP status data unavailable')).toBeInTheDocument();
    expect(screen.getAllByText(/Not measured/).length).toBeGreaterThan(0);
    expect(screen.queryByText('HTTPS & TLS Enforced')).not.toBeInTheDocument();
    expect(screen.queryByText('100/100')).not.toBeInTheDocument();
    expect(screen.queryByText('2 Hops')).not.toBeInTheDocument();
    expect(screen.getByText(/Orphan-page analysis was not available/)).toBeInTheDocument();
  });
});
