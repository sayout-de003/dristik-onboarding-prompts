import React from 'react';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { Findings } from './Findings';
import { Finding } from '../types';

const mockFindings: Finding[] = [
  {
    finding_id: 'FIND-001',
    category: 'TECHNICAL_SEO',
    severity: 'CRITICAL',
    title: 'Missing canonical URL link tag',
    description: 'The homepage head tag lacks a valid canonical link element.',
    impact: 9,
    effort: 2,
    confidence: 0.95,
    confidence_label: 'CERTAIN',
    priority: 1,
    recommendation: 'Inject rel="canonical" pointing to domain origin.',
    verification_status: 'CONFIRMED',
    resolution_status: 'OPEN',
    evidence: [
      {
        element: 'head',
        selector: 'head > link[rel="canonical"]',
        value: 'Missing',
        url: 'https://example.com/',
      },
    ],
    evidence_refs: ['ev_001'],
  },
  {
    finding_id: 'FIND-002',
    category: 'CONTENT',
    severity: 'MEDIUM',
    title: 'Low keyword intent density in H2 tags',
    description: 'H2 headings use vague promotional slogans instead of commercial queries.',
    impact: 5,
    effort: 4,
    confidence: 0.8,
    confidence_label: 'LIKELY',
    priority: 2,
    recommendation: 'Rewrite subheadings with target query semantics.',
    verification_status: 'OBSERVED',
    resolution_status: 'RESOLVED',
    evidence: [
      {
        element: 'h2',
        selector: 'h2:nth-of-type(1)',
        value: 'Beyond Boundaries',
        url: 'https://example.com/about',
      },
    ],
    evidence_refs: ['ev_002'],
  },
];

describe('Findings (Evidence Ledger)', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders executive summary KPI counters correctly', () => {
    const handleSelect = vi.fn();
    render(<Findings findings={mockFindings} onSelect={handleSelect} />);

    expect(screen.getByText('Evidence Ledger')).toBeInTheDocument();
    expect(screen.getByText('2 Findings')).toBeInTheDocument();
    expect(screen.getByText('Total Findings')).toBeInTheDocument();
    expect(screen.getByText('High & Critical')).toBeInTheDocument();
  });

  it('filters findings by search term', () => {
    const handleSelect = vi.fn();
    render(<Findings findings={mockFindings} onSelect={handleSelect} />);

    const searchInput = screen.getByPlaceholderText(/Filter by keyword/i);
    fireEvent.change(searchInput, { target: { value: 'canonical' } });

    expect(screen.getByText('Missing canonical URL link tag')).toBeInTheDocument();
    expect(screen.queryByText('Low keyword intent density in H2 tags')).not.toBeInTheDocument();
  });

  it('toggles between Table view and Cards view', () => {
    const handleSelect = vi.fn();
    render(<Findings findings={mockFindings} onSelect={handleSelect} />);

    // Default view is table
    expect(screen.getByRole('table')).toBeInTheDocument();

    // Switch to cards view
    const cardsButton = screen.getByRole('button', { name: /Cards/i });
    fireEvent.click(cardsButton);

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText('Missing canonical URL link tag')).toBeInTheDocument();
  });

  it('triggers onSelect when inspecting a finding', () => {
    const handleSelect = vi.fn();
    render(<Findings findings={mockFindings} onSelect={handleSelect} />);

    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[0]);

    expect(handleSelect).toHaveBeenCalledWith(mockFindings[0]);
  });
});
