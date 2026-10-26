import React from 'react';

export const SITE_TYPES = [
  { value: '', label: 'Detect automatically' },
  { value: 'business_corporate', label: 'Business / Corporate' },
  { value: 'saas', label: 'SaaS' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'marketplace', label: 'Marketplace' },
  { value: 'agency_services', label: 'Agency / Services' },
  { value: 'portfolio', label: 'Portfolio' },
  { value: 'publisher_media', label: 'Publisher / Media' },
  { value: 'blog', label: 'Blog' },
  { value: 'community', label: 'Community' },
  { value: 'non_profit', label: 'Non-profit' },
  { value: 'educational', label: 'Educational' },
  { value: 'government', label: 'Government' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'financial', label: 'Financial' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'travel_hospitality', label: 'Travel / Hospitality' },
  { value: 'local_business', label: 'Local Business' },
  { value: 'other', label: 'Other' },
];

export interface PillarOption {
  key: string;
  name: string;
  description: string;
  tag: string;
  colorClass: string;
}

export const PILLARS_LIST: PillarOption[] = [
  {
    key: 'seo',
    name: 'SEO',
    description: 'Crawling, page content, metadata, links and technical issues',
    tag: 'Search Engine Optimization',
    colorClass: 'text-teal-800 bg-teal-50 border-teal-200 dark:text-teal-200 dark:bg-teal-950/40 dark:border-teal-800',
  },
  {
    key: 'geo',
    name: 'GEO',
    description: 'How clearly content explains entities and supports AI discovery',
    tag: 'Generative Engine Optimization',
    colorClass: 'text-teal-800 bg-teal-50 border-teal-200 dark:text-teal-200 dark:bg-teal-950/40 dark:border-teal-800',
  },
  {
    key: 'aeo',
    name: 'AEO',
    description: 'Answer quality, question coverage and structured data',
    tag: 'Answer Engine Optimization',
    colorClass: 'text-teal-800 bg-teal-50 border-teal-200 dark:text-teal-200 dark:bg-teal-950/40 dark:border-teal-800',
  },
  {
    key: 'cro',
    name: 'CRO',
    description: 'Calls to action, forms, trust signals and conversion friction',
    tag: 'Conversion Rate Optimization',
    colorClass: 'text-teal-800 bg-teal-50 border-teal-200 dark:text-teal-200 dark:bg-teal-950/40 dark:border-teal-800',
  },
];

interface AuditFormProps {
  url: string;
  maxPages: number;
  siteType: string;
  declaredNotes?: string;
  targetPillars?: string[];
  onTargetPillarsChange?: (pillars: string[]) => void;
  isLoading: boolean;
  error: string | null;
  onUrlChange: (value: string) => void;
  onMaxPagesChange: (value: number) => void;
  onSiteTypeChange: (value: string) => void;
  onDeclaredNotesChange?: (value: string) => void;
  onSubmit: () => void;
}

export function AuditForm({
  url,
  maxPages,
  siteType,
  declaredNotes = '',
  targetPillars = ['seo', 'geo', 'aeo', 'cro'],
  onTargetPillarsChange,
  isLoading,
  error,
  onUrlChange,
  onMaxPagesChange,
  onSiteTypeChange,
  onDeclaredNotesChange,
  onSubmit,
}: AuditFormProps) {
  const allPillarsKeys = ['seo', 'geo', 'aeo', 'cro'];
  const isAllSelected = targetPillars.length === allPillarsKeys.length;

  const handleTogglePillar = (key: string) => {
    if (!onTargetPillarsChange) return;
    if (targetPillars.includes(key)) {
      if (targetPillars.length === 1) return; // Keep at least one pillar active
      onTargetPillarsChange(targetPillars.filter((p) => p !== key));
    } else {
      onTargetPillarsChange([...targetPillars, key]);
    }
  };

  const handleSelectAll = () => {
    if (!onTargetPillarsChange) return;
    onTargetPillarsChange(allPillarsKeys);
  };
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex flex-col lg:flex-row lg:items-end gap-3">
        <label className="flex-1 min-w-0">
          <span className="label block mb-1.5">Website URL</span>
          <input
            type="text"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            placeholder="https://example.com"
            disabled={isLoading}
            autoComplete="url"
            spellCheck={false}
            className="field"
          />
        </label>

        <label className="lg:w-52">
          <span className="label block mb-1.5">Site type</span>
          <select
            value={siteType}
            onChange={(e) => onSiteTypeChange(e.target.value)}
            disabled={isLoading}
            className="field"
          >
            {SITE_TYPES.map((st) => (
              <option key={st.value} value={st.value}>
                {st.label}
              </option>
            ))}
          </select>
        </label>

        <label className="lg:w-24">
          <span className="label block mb-1.5">Pages to inspect</span>
          <select
            value={maxPages}
            onChange={(e) => onMaxPagesChange(Number(e.target.value))}
            disabled={isLoading}
            className="field"
          >
            <option value={3}>3</option>
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={25}>25</option>
          </select>
        </label>

        <button
          type="submit"
          disabled={isLoading}
          className="btn-primary px-5 py-2.5 disabled:opacity-50 lg:mb-px"
        >
          {isLoading ? 'Running…' : 'Run audit'}
        </button>
      </div>

      {siteType === 'other' && onDeclaredNotesChange && (
        <label className="block">
          <span className="label block mb-1.5">Describe the business</span>
          <input
            type="text"
            value={declaredNotes}
            onChange={(e) => onDeclaredNotesChange(e.target.value)}
            placeholder="e.g. B2B wholesale marketplace"
            disabled={isLoading}
            className="field"
          />
        </label>
      )}

      {/* 4 Core Intelligence Pillars Selection */}
      <div className="pt-2 border-t border-line/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="label text-xs font-semibold uppercase tracking-wider text-ink-700">Choose what to review</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
              isAllSelected
                ? 'bg-good/10 text-good border border-good/30'
                : 'bg-paper-200 text-ink-700 border border-line'
            }`}>
              {isAllSelected ? 'Full 4-Pillar Audit' : `Selective Run: ${targetPillars.length} / 4 Active`}
            </span>
          </div>
          {!isAllSelected && onTargetPillarsChange && (
            <button
              type="button"
              onClick={handleSelectAll}
              disabled={isLoading}
              className="text-xs text-ink-500 hover:text-ink underline cursor-pointer disabled:opacity-50"
            >
              Select All Pillars
            </button>
          )}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {PILLARS_LIST.map((pillar) => {
            const isSelected = targetPillars.includes(pillar.key);
            return (
              <button
                key={pillar.key}
                type="button"
                onClick={() => handleTogglePillar(pillar.key)}
                disabled={isLoading}
                className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer select-none flex flex-col justify-between ${
                  isSelected
                    ? 'bg-card border-ink/40 shadow-xs ring-1 ring-ink/20'
                    : 'bg-paper-100/50 border-line/60 opacity-60 hover:opacity-90'
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="font-sans font-bold text-xs text-ink flex items-center gap-1.5">
                    <span className={`w-3.5 h-3.5 rounded flex items-center justify-center text-[10px] ${
                      isSelected ? 'bg-pine text-white' : 'border border-line bg-paper-200 text-transparent'
                    }`}>
                      ✓
                    </span>
                    {pillar.name}
                  </span>
                  <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded border ${pillar.colorClass}`}>
                    {pillar.key.toUpperCase()}
                  </span>
                </div>
                <p className="text-[10px] text-ink-500 line-clamp-1 leading-tight">{pillar.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      <p className="text-xs text-ink-400">
        Site type is treated as context, not truth. Dristik verifies the live pages independently.
      </p>

      {error && (
        <p className="text-sm text-bad" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
