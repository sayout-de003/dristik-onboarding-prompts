import React, { useMemo, useState } from 'react';
import {
  Finding,
  Severity,
  EvidenceClass,
  CodePatch,
  EvidenceLedgerItem,
  Category,
} from '../types';
import { CATEGORY_FILTERS, categoryLabel } from '../lib/format';
import { classifyFindingNature } from '../lib/findingClassifier';
import { CalibrationAxes } from './CalibrationAxes';
import { CroEvidenceDissectionCard } from './CroEvidenceDissectionCard';
import {
  Search,
  SlidersHorizontal,
  Table as TableIcon,
  LayoutGrid,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Copy,
  Check,
  Download,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  FileCode2,
  Zap,
  Sparkles,
  ArrowUpDown,
  X,
  BookOpen,
  Filter,
} from 'lucide-react';

export interface FindingsProps {
  findings: Finding[];
  onSelect: (finding: Finding) => void;
  evidenceLedger?: Record<string, EvidenceLedgerItem>;
  patches?: CodePatch[];
}

type ViewMode = 'table' | 'cards';
type SortOption = 'severity_desc' | 'impact_desc' | 'effort_asc' | 'confidence_desc' | 'id_asc';
type PresetFilter = 'ALL' | 'CRITICAL_HIGH' | 'QUICK_WINS' | 'HAS_PATCH' | 'OBSERVED_PROOF' | 'OPEN_ONLY' | 'RESOLVED_ONLY';

const SEVERITY_ORDER: Record<Severity, number> = {
  CRITICAL: 5,
  HIGH: 4,
  MEDIUM: 3,
  LOW: 2,
  INFO: 1,
};

function getSeverityBadge(severity: Severity) {
  switch (severity) {
    case 'CRITICAL':
      return {
        label: 'CRITICAL',
        badge: 'bg-bad/10 text-bad border-bad/30 dark:bg-bad/20 dark:text-bad dark:border-bad/40',
        dot: 'bg-bad',
      };
    case 'HIGH':
      return {
        label: 'HIGH',
        badge: 'bg-warn/15 text-warn border-warn/40 dark:bg-warn/25 dark:text-warn dark:border-warn/50',
        dot: 'bg-warn',
      };
    case 'MEDIUM':
      return {
        label: 'MEDIUM',
        badge: 'bg-warn/10 text-warn border-warn/30 dark:bg-warn/15 dark:text-warn dark:border-warn/30',
        dot: 'bg-warn/80',
      };
    case 'LOW':
      return {
        label: 'LOW',
        badge: 'bg-paper-200 text-ink-700 border-line dark:bg-ink-800 dark:text-ink-300 dark:border-ink-700',
        dot: 'bg-ink-400',
      };
    case 'INFO':
    default:
      return {
        label: 'INFO',
        badge: 'bg-paper-100 text-ink-600 border-line dark:bg-ink-900 dark:text-ink-400 dark:border-ink-800',
        dot: 'bg-ink-300',
      };
  }
}

function getEvidenceSourceBadge(evidenceClass: EvidenceClass, subtype?: string) {
  switch (evidenceClass) {
    case 'OBSERVED':
      return {
        label: subtype ? `DOM / ${subtype}` : 'Verified DOM Proof',
        shortLabel: subtype || 'DOM',
        style: 'bg-good/10 text-good border-good/30 dark:bg-good/15 dark:text-good dark:border-good/40',
        hint: 'Directly observed in the fetched page or response. Review the cited evidence and scope before acting.',
      };
    case 'EXTERNALLY_VERIFIED':
      return {
        label: subtype ? `External · ${subtype}` : 'Verified external source',
        shortLabel: subtype || 'External',
        style: 'bg-paper-200 text-ink-800 border-line dark:bg-ink-800 dark:text-ink-200 dark:border-ink-700',
        hint: 'Checked against a connected or external source, when available. Open the source details to confirm coverage.',
      };
    case 'MODEL_INFERRED':
      return {
        label: 'AI-assisted interpretation',
        shortLabel: 'AI Synthesis',
        style: 'bg-paper-100 text-ink-700 border-line dark:bg-ink-900 dark:text-ink-300 dark:border-ink-800',
        hint: 'An AI-assisted interpretation, not a direct observation. Validate it against the linked evidence.',
      };
    case 'HYPOTHESIS':
      return {
        label: 'Hypothesis to verify',
        shortLabel: 'Hypothesis',
        style: 'bg-warn/10 text-warn border-warn/30 dark:bg-warn/15 dark:text-warn dark:border-warn/40',
        hint: 'A possible issue that needs human confirmation or another source before it is treated as fact.',
      };
    case 'RECOMMENDATION':
    default:
      return {
        label: 'Recommended action',
        shortLabel: 'Directive',
        style: 'bg-paper-100 text-ink-700 border-line dark:bg-ink-900 dark:text-ink-300 dark:border-ink-800',
        hint: 'A suggested change. Review the affected page and verify the result after implementation.',
      };
  }
}

function impactScoreLabel(n: number | undefined): string {
  if (n == null) return '—';
  if (n >= 8) return 'High';
  if (n >= 5) return 'Medium';
  return 'Low';
}

function effortScoreLabel(n: number | undefined): string {
  if (n == null) return '—';
  if (n >= 8) return 'High';
  if (n >= 5) return 'Medium';
  return 'Low';
}

function confidenceLabel(c: number | undefined): string {
  if (c == null) return '—';
  return `${Math.round(c * 100)}%`;
}

export function Findings({ findings, onSelect, patches = [] }: FindingsProps) {
  // ── State ──────────────────────────────────────────────────────────────────
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState<Severity | 'ALL'>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<(typeof CATEGORY_FILTERS)[number]>('ALL');
  const [evidenceClassFilter, setEvidenceClassFilter] = useState<EvidenceClass | 'ALL'>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'RESOLVED'>('ALL');
  const [presetFilter, setPresetFilter] = useState<PresetFilter>('ALL');
  const [sortBy, setSortBy] = useState<SortOption>('severity_desc');
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [showMethodology, setShowMethodology] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Helper toast notification
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2200);
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast(`✓ Copied ${label}`);
    } catch {
      // fallback
    }
  };

  // ── Metrics & Aggregations ────────────────────────────────────────────────
  const metrics = useMemo(() => {
    let criticalCount = 0;
    let highCount = 0;
    let mediumCount = 0;
    let lowCount = 0;
    let resolvedCount = 0;
    let openCount = 0;
    let observedCount = 0;
    let externalCount = 0;
    let hypothesisCount = 0;
    let patchCount = 0;

    findings.forEach((f) => {
      if (f.severity === 'CRITICAL') criticalCount++;
      else if (f.severity === 'HIGH') highCount++;
      else if (f.severity === 'MEDIUM') mediumCount++;
      else lowCount++;

      if (f.resolution_status === 'RESOLVED') resolvedCount++;
      else openCount++;

      const cl = classifyFindingNature(f);
      if (cl.evidenceClass === 'OBSERVED') observedCount++;
      else if (cl.evidenceClass === 'EXTERNALLY_VERIFIED') externalCount++;
      else if (cl.evidenceClass === 'HYPOTHESIS') hypothesisCount++;

      const hasPatch = Boolean(
        f.code_patch ||
        patches.some((p) => p.patch_id === f.finding_id || p.category === f.category)
      );
      if (hasPatch) patchCount++;
    });

    const total = findings.length;
    const empiricalFacts = observedCount + externalCount;
    const integrityPercent = total > 0 ? Math.round((empiricalFacts / total) * 100) : null;

    return {
      total,
      criticalCount,
      highCount,
      mediumCount,
      lowCount,
      criticalAndHigh: criticalCount + highCount,
      resolvedCount,
      openCount,
      observedCount,
      externalCount,
      hypothesisCount,
      patchCount,
      integrityPercent,
    };
  }, [findings, patches]);

  // ── Filtering and Sorting ─────────────────────────────────────────────────
  const filteredAndSorted = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();

    const filtered = findings.filter((f) => {
      // 1. Text Search
      if (term) {
        const matchesTitle = (f.title || f.finding || '').toLowerCase().includes(term);
        const matchesDesc = (f.description || '').toLowerCase().includes(term);
        const matchesId = (f.finding_id || '').toLowerCase().includes(term);
        const matchesRec = (f.recommendation || '').toLowerCase().includes(term);
        const matchesCategory = (f.category || '').toLowerCase().includes(term);
        const matchesEvidence = f.evidence?.some(
          (ev) =>
            (ev.selector || '').toLowerCase().includes(term) ||
            (ev.snippet || '').toLowerCase().includes(term) ||
            (ev.value || '').toLowerCase().includes(term) ||
            (ev.url || '').toLowerCase().includes(term)
        );
        if (
          !matchesTitle &&
          !matchesDesc &&
          !matchesId &&
          !matchesRec &&
          !matchesCategory &&
          !matchesEvidence
        ) {
          return false;
        }
      }

      // 2. Severity filter
      if (severityFilter !== 'ALL' && f.severity !== severityFilter) {
        return false;
      }

      // 3. Category filter
      if (categoryFilter !== 'ALL' && f.category !== categoryFilter) {
        return false;
      }

      // 4. Evidence Class filter
      const cl = classifyFindingNature(f);
      if (evidenceClassFilter !== 'ALL' && cl.evidenceClass !== evidenceClassFilter) {
        return false;
      }

      // 5. Status filter
      if (statusFilter === 'RESOLVED' && f.resolution_status !== 'RESOLVED') {
        return false;
      }
      if (statusFilter === 'OPEN' && f.resolution_status === 'RESOLVED') {
        return false;
      }

      // 6. Quick Preset Filter
      if (presetFilter === 'CRITICAL_HIGH') {
        if (f.severity !== 'CRITICAL' && f.severity !== 'HIGH') return false;
      } else if (presetFilter === 'QUICK_WINS') {
        const imp = f.impact ?? 5;
        const eff = f.effort ?? 5;
        if (imp < 6 || eff > 5) return false;
      } else if (presetFilter === 'HAS_PATCH') {
        const hasPatch = Boolean(
          f.code_patch ||
          patches.some((p) => p.patch_id === f.finding_id || p.category === f.category)
        );
        if (!hasPatch) return false;
      } else if (presetFilter === 'OBSERVED_PROOF') {
        if (cl.evidenceClass !== 'OBSERVED') return false;
      } else if (presetFilter === 'OPEN_ONLY') {
        if (f.resolution_status === 'RESOLVED') return false;
      } else if (presetFilter === 'RESOLVED_ONLY') {
        if (f.resolution_status !== 'RESOLVED') return false;
      }

      return true;
    });

    // Sorting
    return filtered.sort((a, b) => {
      switch (sortBy) {
        case 'severity_desc': {
          const diff = (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0);
          if (diff !== 0) return diff;
          return (b.impact ?? 0) - (a.impact ?? 0);
        }
        case 'impact_desc':
          return (b.impact ?? 0) - (a.impact ?? 0);
        case 'effort_asc':
          return (a.effort ?? 5) - (b.effort ?? 5);
        case 'confidence_desc':
          return (b.confidence ?? 0) - (a.confidence ?? 0);
        case 'id_asc':
          return (a.finding_id || '').localeCompare(b.finding_id || '');
        default:
          return 0;
      }
    });
  }, [
    findings,
    searchTerm,
    severityFilter,
    categoryFilter,
    evidenceClassFilter,
    statusFilter,
    presetFilter,
    sortBy,
    patches,
  ]);

  // Toggle row expansion in table view
  const toggleRow = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  // Clear all filters
  const resetFilters = () => {
    setSearchTerm('');
    setSeverityFilter('ALL');
    setCategoryFilter('ALL');
    setEvidenceClassFilter('ALL');
    setStatusFilter('ALL');
    setPresetFilter('ALL');
    setSortBy('severity_desc');
  };

  const hasActiveFilters =
    searchTerm !== '' ||
    severityFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    evidenceClassFilter !== 'ALL' ||
    statusFilter !== 'ALL' ||
    presetFilter !== 'ALL';

  // ── Export Functions ───────────────────────────────────────────────────────
  const exportCsv = () => {
    const headers = [
      'Finding ID',
      'Severity',
      'Title',
      'Category',
      'Evidence Class',
      'Target URL',
      'DOM Selector',
      'Impact (1-10)',
      'Effort (1-10)',
      'Status',
      'Recommendation',
    ];

    const rows = filteredAndSorted.map((f) => {
      const cl = classifyFindingNature(f);
      const primaryEv = f.evidence?.find((e) => e.selector || e.element) || f.evidence?.[0];
      const escape = (val: any) => `"${String(val ?? '').replace(/"/g, '""')}"`;

      return [
        escape(f.finding_id),
        escape(f.severity),
        escape(f.title || f.finding),
        escape(categoryLabel(f.category)),
        escape(cl.evidenceClass),
        escape(primaryEv?.url || ''),
        escape(primaryEv?.selector || primaryEv?.element || ''),
        escape(f.impact ?? ''),
        escape(f.effort ?? ''),
        escape(f.resolution_status || 'OPEN'),
        escape(f.recommendation || ''),
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `dristik-evidence-ledger-${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('✓ Exported CSV Ledger');
  };

  const exportJson = () => {
    const dataStr = JSON.stringify(filteredAndSorted, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `dristik-evidence-ledger-${Date.now()}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('✓ Exported JSON Ledger');
  };

  const copyMarkdownSummary = () => {
    const lines = [
      `# Institutional Evidence Ledger (${filteredAndSorted.length} items)`,
      `Generated by Dristik Grounded Verification Engine`,
      '',
      `**Summary:**`,
      `- Total Findings: ${findings.length}`,
      `- Critical & High Priority: ${metrics.criticalAndHigh}`,
      `- Findings with observed or external evidence: ${metrics.integrityPercent == null ? 'Not available' : `${metrics.integrityPercent}%`}`,
      `- Resolved: ${metrics.resolvedCount} | Open: ${metrics.openCount}`,
      '',
      `## Key Findings:`,
    ];

    filteredAndSorted.slice(0, 15).forEach((f) => {
      lines.push(
        `- **[${f.severity}]** [${f.finding_id}] ${f.title || f.finding}` +
        (f.recommendation ? ` — *Fix:* ${f.recommendation}` : '')
      );
    });

    if (filteredAndSorted.length > 15) {
      lines.push(`- ...and ${filteredAndSorted.length - 15} additional findings recorded in the ledger.`);
    }

    copyToClipboard(lines.join('\n'), 'Markdown Summary');
  };

  return (
    <div className="space-y-6">
      {/* ── Toast Notification ────────────────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-ink text-paper-50 px-4 py-2.5 rounded-lg shadow-lg text-xs font-mono font-medium flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <CheckCircle2 className="w-4 h-4 text-good" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* ── Executive Header & Top Bar ───────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="font-sans text-2xl font-bold tracking-tight text-ink">
              Evidence Ledger
            </h2>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-paper-200 text-ink-700 border border-line">
              {findings.length} Findings
            </span>
          </div>
          <p className="text-xs text-ink-600 mt-1 max-w-2xl leading-relaxed">
            Review each finding's evidence type, scope and recommended fix. Direct observations, external signals, AI-assisted interpretations and hypotheses are labelled separately.
          </p>
        </div>

        {/* Action Controls: Methodology Toggle & Export */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowMethodology(!showMethodology)}
            className={`px-3 py-2 rounded-lg text-xs font-semibold border transition-all flex items-center gap-1.5 cursor-pointer ${
              showMethodology
                ? 'bg-paper-200 text-ink border-ink-400 dark:bg-ink-800 dark:border-ink-600'
                : 'bg-paper-50 text-ink-700 border-line hover:bg-paper-100 hover:text-ink'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Verification Methodology</span>
            {showMethodology ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          <button
            type="button"
            onClick={exportCsv}
            title="Download CSV"
            className="px-3 py-2 rounded-lg text-xs font-semibold border border-line bg-paper-50 text-ink-700 hover:bg-paper-100 hover:text-ink transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          <button
            type="button"
            onClick={copyMarkdownSummary}
            title="Copy Markdown Summary"
            className="px-3 py-2 rounded-lg text-xs font-semibold border border-line bg-paper-50 text-ink-700 hover:bg-paper-100 hover:text-ink transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5" />
            <span>Copy Summary</span>
          </button>
        </div>
      </div>

      {/* ── Sleek Methodology Accordion ──────────────────────────────── */}
      {showMethodology && (
        <div className="rounded-xl border border-line bg-paper-100/60 dark:bg-ink-900/40 p-5 space-y-4 shadow-xs animate-in fade-in duration-150">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-good" />
                <h4 className="font-sans text-sm font-bold text-ink">
                  Epistemic Grounding &amp; Anti-Hallucination Hierarchy
                </h4>
              </div>
              <p className="text-xs text-ink-600 max-w-3xl leading-relaxed">
                Dristik strictly separates empirical physical measurements from neural model deductions.
                Every finding in this ledger is labeled with its exact evidentiary level.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowMethodology(false)}
              className="text-ink-400 hover:text-ink text-xs p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg border border-line bg-paper-50 dark:bg-ink-950/50 space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-good" />
                <span className="font-mono font-bold text-ink">1. Measured DOM Facts</span>
              </div>
              <p className="text-[11px] text-ink-600 leading-snug">
                Extracted directly from live browser runtime, CSS selectors, response headers, or HTML AST.
                100% reproducible via curl or browser DevTools.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-line bg-paper-50 dark:bg-ink-950/50 space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-ink-600" />
                <span className="font-mono font-bold text-ink">2. External Authority</span>
              </div>
              <p className="text-[11px] text-ink-600 leading-snug">
                Corroborated by third-party APIs: Google Search Console, certificate registries, WHOIS, or live search engine results.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-line bg-paper-50 dark:bg-ink-950/50 space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-ink-400" />
                <span className="font-mono font-bold text-ink">3. AI Synthesis</span>
              </div>
              <p className="text-[11px] text-ink-600 leading-snug">
                Cognitive semantic analysis (e.g. value proposition clarity, search intent matching) derived by LLMs from the measured facts.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-line bg-paper-50 dark:bg-ink-950/50 space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-warn" />
                <span className="font-mono font-bold text-ink">4. Provisional Hypotheses</span>
              </div>
              <p className="text-[11px] text-ink-600 leading-snug">
                Single-source observations or edge-case anomalies flagged as working hypotheses requiring manual verification prior to production rollout.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Executive KPI Ticker Cards ───────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Metric 1: Total Defects */}
        <div
          onClick={() => {
            resetFilters();
          }}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
            presetFilter === 'ALL' && !hasActiveFilters
              ? 'bg-paper-100 border-ink-400 dark:bg-ink-900 shadow-xs ring-1 ring-ink/10'
              : 'bg-paper-50 border-line hover:border-ink-300'
          }`}
        >
          <div className="flex items-center justify-between text-ink-500 mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Total Findings</span>
            <AlertCircle className="w-3.5 h-3.5 text-ink-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-ink">{metrics.total}</div>
          <div className="text-[10px] text-ink-500 font-mono mt-0.5">
            Full audit register
          </div>
        </div>

        {/* Metric 2: Critical & High Priority */}
        <div
          onClick={() => {
            setPresetFilter(presetFilter === 'CRITICAL_HIGH' ? 'ALL' : 'CRITICAL_HIGH');
          }}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
            presetFilter === 'CRITICAL_HIGH'
              ? 'bg-bad/10 border-bad/50 shadow-xs ring-1 ring-bad/20'
              : 'bg-paper-50 border-line hover:border-bad/40'
          }`}
        >
          <div className="flex items-center justify-between text-bad mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">High &amp; Critical</span>
            <AlertTriangle className="w-3.5 h-3.5 text-bad" />
          </div>
          <div className="text-2xl font-bold font-mono text-bad">{metrics.criticalAndHigh}</div>
          <div className="text-[10px] text-ink-500 font-mono mt-0.5">
            {metrics.criticalCount} critical · {metrics.highCount} high
          </div>
        </div>

        {/* Metric 3: Observed / external evidence */}
        <div
          onClick={() => {
            setPresetFilter(presetFilter === 'OBSERVED_PROOF' ? 'ALL' : 'OBSERVED_PROOF');
          }}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
            presetFilter === 'OBSERVED_PROOF'
              ? 'bg-good/10 border-good/50 shadow-xs ring-1 ring-good/20'
              : 'bg-paper-50 border-line hover:border-good/40'
          }`}
        >
          <div className="flex items-center justify-between text-good mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Observed / external</span>
            <ShieldCheck className="w-3.5 h-3.5 text-good" />
          </div>
          <div className="text-2xl font-bold font-mono text-good">{metrics.integrityPercent == null ? '—' : `${metrics.integrityPercent}%`}</div>
          <div className="text-[10px] text-ink-500 font-mono mt-0.5">
            {metrics.observedCount + metrics.externalCount} findings with observed or external evidence
          </div>
        </div>

        {/* Metric 4: Code Patches */}
        <div
          onClick={() => {
            setPresetFilter(presetFilter === 'HAS_PATCH' ? 'ALL' : 'HAS_PATCH');
          }}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
            presetFilter === 'HAS_PATCH'
              ? 'bg-paper-100 border-ink-400 dark:bg-ink-900 shadow-xs ring-1 ring-ink/10'
              : 'bg-paper-50 border-line hover:border-ink-300'
          }`}
        >
          <div className="flex items-center justify-between text-ink-500 mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Code Patches</span>
            <FileCode2 className="w-3.5 h-3.5 text-ink-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-ink">{metrics.patchCount}</div>
          <div className="text-[10px] text-ink-500 font-mono mt-0.5">
            Git-ready remedies
          </div>
        </div>

        {/* Metric 5: Open vs Resolved */}
        <div
          onClick={() => {
            setStatusFilter(statusFilter === 'OPEN' ? 'ALL' : 'OPEN');
          }}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
            statusFilter === 'OPEN'
              ? 'bg-paper-100 border-ink-400 dark:bg-ink-900 shadow-xs ring-1 ring-ink/10'
              : 'bg-paper-50 border-line hover:border-ink-300'
          }`}
        >
          <div className="flex items-center justify-between text-ink-500 mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider">Pending Action</span>
            <Zap className="w-3.5 h-3.5 text-warn" />
          </div>
          <div className="text-2xl font-bold font-mono text-ink">{metrics.openCount}</div>
          <div className="text-[10px] text-ink-500 font-mono mt-0.5">
            {metrics.resolvedCount} marked resolved
          </div>
        </div>
      </div>

      {/* ── Command & Filter Toolbar ─────────────────────────────────── */}
      <div className="rounded-xl border border-line bg-paper-50 dark:bg-ink-950 p-4 space-y-3 shadow-xs">
        {/* Row 1: Search + View Mode Switch + Sort */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Omni Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-400 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter by keyword, selector (e.g. h1, canonical, schema), URL, or issue title..."
              className="w-full pl-9 pr-8 py-2 text-xs rounded-lg border border-line bg-paper-100/50 dark:bg-ink-900 text-ink placeholder:text-ink-400 focus:outline-none focus:ring-1 focus:ring-ink focus:border-ink"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Right Toolbar Controls: Sort & View Toggle */}
          <div className="flex items-center gap-2 self-end md:self-auto shrink-0">
            {/* Sort Select */}
            <div className="flex items-center gap-1.5 text-xs text-ink-600 bg-paper-100 dark:bg-ink-900 border border-line rounded-lg px-2.5 py-1.5">
              <ArrowUpDown className="w-3.5 h-3.5 text-ink-400" />
              <span className="text-[11px] font-mono text-ink-400 hidden sm:inline">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                aria-label="Sort findings"
                className="bg-transparent text-xs font-semibold text-ink focus:outline-none cursor-pointer"
              >
                <option value="severity_desc">Severity (High → Low)</option>
                <option value="impact_desc">Impact (High → Low)</option>
                <option value="effort_asc">Effort (Quickest First)</option>
                <option value="confidence_desc">Confidence (Highest First)</option>
                <option value="id_asc">Finding ID</option>
              </select>
            </div>

            {/* View Mode Toggle: Table vs Cards */}
            <div className="flex p-0.5 rounded-lg border border-line bg-paper-100 dark:bg-ink-900 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('table')}
                title="Ledger Table View"
                className={`px-2.5 py-1.5 rounded-md font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  viewMode === 'table'
                    ? 'bg-paper-50 text-ink shadow-xs dark:bg-ink-800'
                    : 'text-ink-500 hover:text-ink'
                }`}
              >
                <TableIcon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Table</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                title="Dossier Cards View"
                className={`px-2.5 py-1.5 rounded-md font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                  viewMode === 'cards'
                    ? 'bg-paper-50 text-ink shadow-xs dark:bg-ink-800'
                    : 'text-ink-500 hover:text-ink'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Cards</span>
              </button>
            </div>
          </div>
        </div>

        {/* Row 2: Secondary Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line/60 text-xs">
          {/* Severity Dropdown */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono uppercase text-ink-400">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as any)}
              aria-label="Filter by severity"
              className="px-2 py-1 rounded-md border border-line bg-paper-100 dark:bg-ink-900 text-ink font-mono text-xs focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical ({metrics.criticalCount})</option>
              <option value="HIGH">High ({metrics.highCount})</option>
              <option value="MEDIUM">Medium ({metrics.mediumCount})</option>
              <option value="LOW">Low ({metrics.lowCount})</option>
            </select>
          </div>

          {/* Category Dropdown */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono uppercase text-ink-400">Category:</span>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value as any)}
              aria-label="Filter by category"
              className="px-2 py-1 rounded-md border border-line bg-paper-100 dark:bg-ink-900 text-ink font-mono text-xs focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Categories</option>
              {CATEGORY_FILTERS.filter((c) => c !== 'ALL').map((cat) => (
                <option key={cat} value={cat}>
                  {categoryLabel(cat)}
                </option>
              ))}
            </select>
          </div>

          {/* Evidence Grounding Class */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono uppercase text-ink-400">Source:</span>
            <select
              value={evidenceClassFilter}
              onChange={(e) => setEvidenceClassFilter(e.target.value as any)}
              aria-label="Filter by source type"
              className="px-2 py-1 rounded-md border border-line bg-paper-100 dark:bg-ink-900 text-ink font-mono text-xs focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Grounding Types</option>
              <option value="OBSERVED">DOM Measured Proof ({metrics.observedCount})</option>
              <option value="EXTERNALLY_VERIFIED">External Source ({metrics.externalCount})</option>
              <option value="MODEL_INFERRED">AI Synthesized</option>
              <option value="HYPOTHESIS">Hypothesis ({metrics.hypothesisCount})</option>
            </select>
          </div>

          {/* Status Dropdown */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono uppercase text-ink-400">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              aria-label="Filter by resolution status"
              className="px-2 py-1 rounded-md border border-line bg-paper-100 dark:bg-ink-900 text-ink font-mono text-xs focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open Only ({metrics.openCount})</option>
              <option value="RESOLVED">Certified Resolved ({metrics.resolvedCount})</option>
            </select>
          </div>

          {/* Quick Clear All Filters button */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="ml-auto text-xs text-bad hover:underline font-semibold flex items-center gap-1 cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Reset all filters</span>
            </button>
          )}
        </div>

        {/* Row 3: Quick Filter Presets Chips */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[10px] font-mono uppercase text-ink-400 mr-1">Quick Presets:</span>
          
          <button
            type="button"
            onClick={() => setPresetFilter(presetFilter === 'CRITICAL_HIGH' ? 'ALL' : 'CRITICAL_HIGH')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold transition-all border cursor-pointer ${
              presetFilter === 'CRITICAL_HIGH'
                ? 'bg-bad text-paper-50 border-bad'
                : 'bg-paper-100 text-ink-700 border-line hover:border-bad/40'
            }`}
          >
            🚨 Critical &amp; High
          </button>

          <button
            type="button"
            onClick={() => setPresetFilter(presetFilter === 'QUICK_WINS' ? 'ALL' : 'QUICK_WINS')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold transition-all border cursor-pointer ${
              presetFilter === 'QUICK_WINS'
                ? 'bg-good text-paper-50 border-good'
                : 'bg-paper-100 text-ink-700 border-line hover:border-good/40'
            }`}
          >
            ⚡ Quick Wins (High Impact, Low Effort)
          </button>

          <button
            type="button"
            onClick={() => setPresetFilter(presetFilter === 'HAS_PATCH' ? 'ALL' : 'HAS_PATCH')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold transition-all border cursor-pointer ${
              presetFilter === 'HAS_PATCH'
                ? 'bg-ink text-paper-50 border-ink'
                : 'bg-paper-100 text-ink-700 border-line hover:border-ink-400'
            }`}
          >
            🛠 Has Code Patch
          </button>

          <button
            type="button"
            onClick={() => setPresetFilter(presetFilter === 'OBSERVED_PROOF' ? 'ALL' : 'OBSERVED_PROOF')}
            className={`px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold transition-all border cursor-pointer ${
              presetFilter === 'OBSERVED_PROOF'
                ? 'bg-good/20 text-good border-good font-bold'
                : 'bg-paper-100 text-ink-700 border-line hover:border-good/40'
            }`}
          >
            🛡 DOM Proof Only
          </button>
        </div>
      </div>

      {/* ── Results Count Indicator ─────────────────────────────────── */}
      <div className="flex items-center justify-between text-xs text-ink-500 font-mono px-1">
        <div>
          Showing <span className="font-bold text-ink">{filteredAndSorted.length}</span> of{' '}
          <span className="font-bold text-ink">{findings.length}</span> recorded findings
          {hasActiveFilters && ' (filtered)'}
        </div>
        <div className="text-[11px] text-ink-400 hidden sm:block">
          Click any row to open the full technical dossier and code remediation
        </div>
      </div>

      {/* ── Main View (Table or Cards) ───────────────────────────────── */}
      {filteredAndSorted.length === 0 ? (
        <div className="rounded-xl border border-line bg-paper-50 dark:bg-ink-950 p-12 text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-paper-200 dark:bg-ink-900 flex items-center justify-center mx-auto text-ink-400">
            <Filter className="w-5 h-5" />
          </div>
          <h4 className="font-sans text-base font-bold text-ink">No findings match the active criteria</h4>
          <p className="text-xs text-ink-500 max-w-sm mx-auto">
            Try adjusting your search terms, changing severity or category filters, or reset the filters.
          </p>
          <button
            type="button"
            onClick={resetFilters}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-ink text-paper-50 hover:bg-ink-800 transition-colors inline-flex items-center gap-1.5 cursor-pointer mt-2"
          >
            <X className="w-3.5 h-3.5" />
            <span>Reset All Filters</span>
          </button>
        </div>
      ) : viewMode === 'table' ? (
        /* ═══════════════════════════════════════════════════════════════ */
        /* LEDGER TABLE VIEW (ENTERPRISE GRID)                             */
        /* ═══════════════════════════════════════════════════════════════ */
        <div className="rounded-xl border border-line bg-paper-50 dark:bg-ink-950 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-line bg-paper-100/70 dark:bg-ink-900/60 text-[10px] font-mono uppercase text-ink-500 tracking-wider">
                  <th className="py-3 px-3 w-10 text-center"></th>
                  <th className="py-3 px-3 w-24">Severity</th>
                  <th className="py-3 px-3 min-w-[280px]">Finding &amp; Issue</th>
                  <th className="py-3 px-3 w-32">Category</th>
                  <th className="py-3 px-3 min-w-[200px]">Evidence details</th>
                  <th className="py-3 px-3 w-28 text-center">Impact / Effort</th>
                  <th className="py-3 px-3 w-24 text-center">Status</th>
                  <th className="py-3 px-3 w-28 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {filteredAndSorted.map((finding) => {
                  const cl = classifyFindingNature(finding);
                  const sevSpec = getSeverityBadge(finding.severity);
                  const srcSpec = getEvidenceSourceBadge(cl.evidenceClass, cl.evidenceSubtype);
                  const primaryEv = finding.evidence?.find((e) => e.selector || e.element) || finding.evidence?.[0];
                  const hasSelector = primaryEv?.selector || primaryEv?.element;
                  const isExpanded = Boolean(expandedRows[finding.finding_id]);
                  const hasCodePatch = Boolean(
                    finding.code_patch ||
                    patches.some((p) => p.patch_id === finding.finding_id || p.category === finding.category)
                  );

                  return (
                    <React.Fragment key={finding.finding_id}>
                      <tr
                        onClick={() => onSelect(finding)}
                        className={`group hover:bg-paper-100/70 dark:hover:bg-ink-900/50 transition-colors cursor-pointer ${
                          isExpanded ? 'bg-paper-100/40 dark:bg-ink-900/30' : ''
                        }`}
                      >
                        {/* Expand accordion chevron */}
                        <td
                          className="py-3 px-2 text-center"
                          onClick={(e) => toggleRow(finding.finding_id, e)}
                        >
                          <button
                            type="button"
                            aria-label="Toggle details"
                            className="text-ink-400 hover:text-ink p-1 rounded hover:bg-paper-200/60 dark:hover:bg-ink-800 transition-colors cursor-pointer"
                          >
                            {isExpanded ? (
                              <ChevronUp className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </td>

                        {/* Severity */}
                        <td className="py-3 px-3">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wide border ${sevSpec.badge}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${sevSpec.dot}`} />
                            {sevSpec.label}
                          </span>
                        </td>

                        {/* Finding Title & ID */}
                        <td className="py-3 px-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span
                                onClick={(e) => {
                                  e.stopPropagation();
                                  copyToClipboard(finding.finding_id, 'Finding ID');
                                }}
                                title="Click to copy ID"
                                className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-paper-200 dark:bg-ink-900 text-ink-600 border border-line hover:border-ink-400 cursor-copy shrink-0"
                              >
                                {finding.finding_id}
                              </span>
                              <h4 className="font-sans text-xs font-bold text-ink leading-snug group-hover:text-ink-900">
                                {finding.title || finding.finding}
                              </h4>
                              {hasCodePatch && (
                                <span className="inline-flex items-center gap-0.5 text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-paper-200 dark:bg-ink-900 text-ink-700 border border-line shrink-0">
                                  <FileCode2 className="w-2.5 h-2.5" />
                                  Patch
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-ink-600 dark:text-ink-400 line-clamp-1">
                              {finding.description || finding.why_it_matters || finding.recommendation}
                            </p>
                          </div>
                        </td>

                        {/* Category */}
                        <td className="py-3 px-3">
                          <span className="text-[11px] font-mono text-ink-700 dark:text-ink-300">
                            {categoryLabel(finding.category)}
                          </span>
                        </td>

                        {/* Ground Truth Proof */}
                        <td className="py-3 px-3">
                          <div className="space-y-1 max-w-[280px]">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`text-[9px] font-mono font-semibold px-1.5 py-0.2 rounded border ${srcSpec.style}`}
                                title={srcSpec.hint}
                              >
                                {srcSpec.shortLabel}
                              </span>
                              {hasSelector && (
                                <code
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    copyToClipboard(hasSelector, 'Selector');
                                  }}
                                  title="Click to copy selector"
                                  className="text-[10px] font-mono text-good dark:text-good font-medium truncate max-w-[170px] hover:underline cursor-copy block"
                                >
                                  {hasSelector}
                                </code>
                              )}
                            </div>
                            {primaryEv?.url && (
                              <div className="text-[10px] font-mono text-ink-500 truncate" title={primaryEv.url}>
                                {primaryEv.url.replace(/^https?:\/\//, '')}
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Impact / Effort */}
                        <td className="py-3 px-3 text-center">
                          <div className="font-mono text-[10px] space-y-0.5">
                            <div>
                              <span className="text-ink-400">Impact: </span>
                              <span className="font-bold text-ink">
                                {impactScoreLabel(finding.impact)} ({finding.impact ?? '—'}/10)
                              </span>
                            </div>
                            <div>
                              <span className="text-ink-400">Effort: </span>
                              <span className="text-ink-600 font-medium">
                                {effortScoreLabel(finding.effort)}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="py-3 px-3 text-center">
                          {finding.resolution_status === 'RESOLVED' ? (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-good/10 text-good border border-good/30">
                              <Check className="w-2.5 h-2.5" />
                              Resolved
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-warn/10 text-warn border border-warn/30">
                              Open
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-3 px-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelect(finding);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-paper-100 hover:bg-paper-200 dark:bg-ink-900 dark:hover:bg-ink-800 text-ink border border-line transition-colors cursor-pointer"
                          >
                            <span>Inspect</span>
                            <ExternalLink className="w-3 h-3 text-ink-400" />
                          </button>
                        </td>
                      </tr>

                      {/* ── Expandable Inline Details Drawer ────────────────── */}
                      {isExpanded && (
                        <tr className="bg-paper-100/50 dark:bg-ink-950/80 border-b border-line">
                          <td colSpan={8} className="p-4 sm:p-5">
                            <div className="rounded-lg border border-line bg-paper-50 dark:bg-ink-900 p-4 space-y-4 shadow-inner">
                              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line/60 pb-3">
                                <div>
                                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-ink-400">
                                    Technical Dossier &amp; Evidence Audit
                                  </span>
                                  <h4 className="font-sans text-sm font-bold text-ink mt-0.5">
                                    {finding.title || finding.finding}
                                  </h4>
                                </div>
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => copyToClipboard(JSON.stringify(finding, null, 2), 'Finding JSON')}
                                    className="px-2.5 py-1 text-xs font-mono font-semibold rounded border border-line bg-paper-100 hover:bg-paper-200 text-ink-700 flex items-center gap-1 cursor-pointer"
                                  >
                                    <Copy className="w-3 h-3" />
                                    <span>Copy JSON</span>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => onSelect(finding)}
                                    className="px-3 py-1 text-xs font-semibold rounded bg-ink text-paper-50 hover:bg-ink-800 flex items-center gap-1.5 cursor-pointer"
                                  >
                                    <span>Open Full Inspector &amp; Code Patch</span>
                                    <span>→</span>
                                  </button>
                                </div>
                              </div>

                              {/* 2-Column High Readability Layout */}
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                                {/* Left: Detailed Evidence & Observed Snippet */}
                                <div className="space-y-3">
                                  <div>
                                    <span className="text-[10px] font-mono font-bold uppercase tracking-wide text-ink-500 block mb-1">
                                      What was observed (Empirical Fact)
                                    </span>
                                    <p className="text-ink-700 dark:text-ink-300 leading-relaxed font-sans">
                                      {finding.description || finding.finding}
                                    </p>
                                  </div>

                                  {/* Evidence tokens */}
                                  {(hasSelector || primaryEv?.value || primaryEv?.snippet) && (
                                    <div className="p-3 rounded-md bg-paper-100 dark:bg-ink-950 font-mono text-[11px] border border-line space-y-1.5">
                                      {hasSelector && (
                                        <div className="flex items-center justify-between gap-2">
                                          <div className="truncate">
                                            <span className="text-ink-400 uppercase text-[9px] font-bold">Selector: </span>
                                            <code className="text-good dark:text-good font-semibold">{hasSelector}</code>
                                          </div>
                                          <button
                                            type="button"
                                            onClick={() => copyToClipboard(hasSelector, 'Selector')}
                                            className="text-[10px] text-ink-500 hover:text-ink shrink-0 underline cursor-pointer"
                                          >
                                            Copy
                                          </button>
                                        </div>
                                      )}
                                      {(primaryEv?.value || primaryEv?.snippet) && (
                                        <div>
                                          <span className="text-ink-400 uppercase text-[9px] font-bold block">Measured Content: </span>
                                          <div className="text-ink-700 dark:text-ink-300 italic bg-paper-200/50 dark:bg-ink-900 p-2 rounded mt-0.5 border border-line/40 max-h-24 overflow-y-auto">
                                            "{primaryEv?.value || primaryEv?.snippet}"
                                          </div>
                                        </div>
                                      )}
                                      {primaryEv?.url && (
                                        <div className="text-[10px] text-ink-500 truncate pt-1 border-t border-line/40">
                                          URL: <span className="text-ink-700 dark:text-ink-300">{primaryEv.url}</span>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {/* Sub-observations if clustered */}
                                  {finding.detailed_observations && finding.detailed_observations.length > 0 && (
                                    <div className="space-y-1 pt-1">
                                      <span className="text-[10px] font-mono font-bold uppercase tracking-wide text-ink-500 block">
                                        Synthesizes {finding.detailed_observations.length} underlying observations:
                                      </span>
                                      <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                                        {finding.detailed_observations.map((obs, idx) => (
                                          <div key={obs.observation_id || idx} className="p-1.5 rounded bg-paper-100 dark:bg-ink-950 border border-line text-[10px]">
                                            <div className="font-semibold text-ink-700 dark:text-ink-200">• {obs.title}</div>
                                            {obs.snippet && <div className="text-ink-500 italic truncate pl-2">"{obs.snippet}"</div>}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>

                                {/* Right: Problem Impact & Actionable Solution */}
                                <div className="space-y-3">
                                  {/* Why it matters */}
                                  <div className="p-3 rounded-md bg-warn/10 border border-warn/30 space-y-1">
                                    <div className="flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wide text-warn">
                                      <AlertTriangle className="w-3.5 h-3.5" />
                                      <span>Why it matters &amp; Business Impact</span>
                                    </div>
                                    <p className="text-ink-700 dark:text-ink-300 text-xs leading-relaxed font-sans">
                                      {finding.why_it_matters || finding.business_impact || 'Directly degrades compliance, visibility or conversion velocity.'}
                                    </p>
                                  </div>

                                  {/* Recommendation & Code Patch */}
                                  <div className="p-3 rounded-md bg-paper-100 dark:bg-ink-950 border border-line space-y-1.5">
                                    <div className="flex items-center justify-between font-mono text-[10px] font-bold uppercase tracking-wide text-ink-600">
                                      <span>Recommended Engineering Remediation</span>
                                      {finding.code_patch && (
                                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-ink text-paper-50 font-bold">
                                          Code Patch Ready
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-ink-700 dark:text-ink-300 text-xs leading-relaxed font-sans">
                                      {finding.recommendation || 'Implement suggested architectural fixes to restore compliance.'}
                                    </p>
                                    {finding.validation_criteria && (
                                      <div className="text-[10px] font-mono text-ink-500 pt-1 border-t border-line/40">
                                        Target Criteria: <span className="font-semibold text-ink">{finding.validation_criteria}</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* ═══════════════════════════════════════════════════════════════ */
        /* DOSSIER CARDS VIEW (CLEAN, READABLE, ENTERPRISE POLISH)         */
        /* ═══════════════════════════════════════════════════════════════ */
        <div className="space-y-4">
          {filteredAndSorted.map((finding) => {
            const cl = classifyFindingNature(finding);
            const sevSpec = getSeverityBadge(finding.severity);
            const srcSpec = getEvidenceSourceBadge(cl.evidenceClass, cl.evidenceSubtype);
            const primaryEv = finding.evidence?.find((e) => e.selector || e.element) || finding.evidence?.[0];
            const hasSelector = primaryEv?.selector || primaryEv?.element;
            const hasObserved = primaryEv?.value || primaryEv?.snippet;
            const hasCodePatch = Boolean(
              finding.code_patch ||
              patches.some((p) => p.patch_id === finding.finding_id || p.category === finding.category)
            );

            return (
              <div
                key={finding.finding_id}
                onClick={() => onSelect(finding)}
                className="rounded-xl border border-line bg-paper-50 dark:bg-ink-950 shadow-xs hover:shadow-md hover:border-ink-400 transition-all cursor-pointer overflow-hidden group"
              >
                {/* ── Card Header ────────────────────────────────────── */}
                <div className="px-5 py-3.5 border-b border-line/70 bg-paper-100/50 dark:bg-ink-900/40 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Severity chip */}
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono font-bold tracking-wide border ${sevSpec.badge}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${sevSpec.dot}`} />
                      {sevSpec.label}
                    </span>

                    {/* Category */}
                    <span className="text-[11px] font-mono font-semibold text-ink-700 dark:text-ink-300 uppercase px-2 py-0.5 rounded bg-paper-200 dark:bg-ink-800 border border-line">
                      {categoryLabel(finding.category)}
                    </span>

                    {/* Evidence Source Badge */}
                    <span
                      className={`text-[10px] font-mono font-medium px-2 py-0.5 rounded border ${srcSpec.style}`}
                      title={srcSpec.hint}
                    >
                      {srcSpec.label}
                    </span>

                    {/* Scope hit count */}
                    {finding.evidence_scope && (
                      <span className="text-[10px] font-mono text-ink-500">
                        {finding.evidence_scope.replace(/_/g, ' ')}
                        {finding.scope_hit_count && finding.scope_sample_size
                          ? ` (${finding.scope_hit_count}/${finding.scope_sample_size})`
                          : ''}
                      </span>
                    )}
                  </div>

                  {/* Right: ID + Resolution Status */}
                  <div className="flex items-center gap-2">
                    {finding.resolution_status === 'RESOLVED' ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-good/10 text-good border border-good/30 font-bold">
                        <Check className="w-3 h-3" />
                        CERTIFIED RESOLVED
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-warn/10 text-warn border border-warn/30 font-bold">
                        OPEN
                      </span>
                    )}
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard(finding.finding_id, 'Finding ID');
                      }}
                      title="Click to copy ID"
                      className="text-[10px] font-mono text-ink-500 bg-paper-100 dark:bg-ink-900 px-2 py-0.5 rounded border border-line hover:border-ink-400 cursor-copy"
                    >
                      {finding.finding_id}
                    </span>
                  </div>
                </div>

                {/* ── Card Body ──────────────────────────────────────── */}
                <div className="p-5 space-y-4">
                  {/* Root cause badge if multiple observations */}
                  {finding.sub_observations && finding.sub_observations.length > 1 && (
                    <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-paper-100 dark:bg-ink-900 border border-line text-xs font-mono">
                      <div className="flex items-center gap-2 text-ink-700">
                        <span className="font-bold text-[10px] bg-ink text-paper-50 px-1.5 py-0.5 rounded">
                          ROOT CAUSE
                        </span>
                        <span>Synthesizes {finding.sub_observations.length} underlying observations</span>
                      </div>
                      <span className="text-[10px] text-ink-500">Unified Remediation Plan</span>
                    </div>
                  )}

                  {/* Title & Description */}
                  <div className="space-y-1.5">
                    <h3 className="font-sans text-base font-bold text-ink group-hover:text-ink-900 transition-colors">
                      {finding.title || finding.finding}
                    </h3>
                    <p className="text-xs text-ink-700 dark:text-ink-300 leading-relaxed font-sans">
                      {finding.description || finding.finding}
                    </p>
                  </div>

                  {/* Calibration Axes if present */}
                  <CalibrationAxes finding={finding} compact />

                  {/* Ground Truth Proof Container */}
                  {(hasSelector || hasObserved || primaryEv?.url) && (
                    <div className="p-3.5 rounded-lg bg-paper-100/70 dark:bg-ink-900/60 border border-line space-y-2">
                      <div className="flex items-center justify-between text-[10px] font-mono font-bold uppercase tracking-wide text-ink-500">
                        <span className="flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-good" />
                          <span>Empirical Proof &amp; Extraction</span>
                        </span>
                        {hasSelector && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              copyToClipboard(hasSelector, 'Selector');
                            }}
                            className="text-[10px] font-mono text-ink-600 hover:text-ink underline cursor-pointer"
                          >
                            Copy Selector
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] font-mono">
                        {hasSelector && (
                          <div className="space-y-0.5">
                            <span className="text-[9px] uppercase font-bold text-ink-400 block">DOM Selector:</span>
                            <code className="text-good dark:text-good font-semibold block truncate bg-paper-50 dark:bg-ink-950 p-1.5 rounded border border-line/60">
                              {hasSelector}
                            </code>
                          </div>
                        )}
                        {hasObserved && (
                          <div className="space-y-0.5">
                            <span className="text-[9px] uppercase font-bold text-ink-400 block">Measured Snippet:</span>
                            <div className="text-ink-700 dark:text-ink-300 italic truncate bg-paper-50 dark:bg-ink-950 p-1.5 rounded border border-line/60">
                              "{hasObserved}"
                            </div>
                          </div>
                        )}
                      </div>

                      {primaryEv?.url && (
                        <div className="text-[10px] font-mono text-ink-400 truncate pt-1 border-t border-line/40">
                          Target URL: <span className="text-ink-700 dark:text-ink-300 font-medium">{primaryEv.url}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 2-Section Grid: Impact vs Fix */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                    {/* Column 1: Why it matters */}
                    <div className="p-3.5 rounded-lg border border-warn/30 bg-warn/10 flex flex-col justify-between space-y-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase tracking-wider text-warn">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>Problem &amp; Business Impact</span>
                        </div>
                        <p className="text-xs text-ink-800 dark:text-ink-200 leading-relaxed font-sans">
                          {finding.why_it_matters || finding.business_impact || (
                            `Defect impairs compliance and discoverability for ${finding.severity.toLowerCase()} severity standard.`
                          )}
                        </p>
                      </div>
                      <div className="pt-2 border-t border-warn/30 flex items-center justify-between text-[10px] font-mono text-warn">
                        <span>Impact: <strong className="font-bold">{impactScoreLabel(finding.impact)} ({finding.impact ?? '—'}/10)</strong></span>
                        <span>Effort: <strong className="font-bold">{effortScoreLabel(finding.effort)}</strong></span>
                      </div>
                    </div>

                    {/* Column 2: How to fix it */}
                    <div className="p-3.5 rounded-lg border border-line bg-paper-100/60 dark:bg-ink-900/40 flex flex-col justify-between space-y-2">
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[10px] font-mono font-bold uppercase tracking-wider text-ink-600">
                          <span>Actionable Engineering Fix</span>
                          {hasCodePatch && (
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-ink text-paper-50 font-bold">
                              Code Patch Available
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-ink-700 dark:text-ink-300 leading-relaxed font-sans">
                          {finding.recommendation || 'Apply suggested architectural or tag fixes to align with verified standards.'}
                        </p>
                      </div>
                      <div className="pt-2 border-t border-line text-[10px] font-mono text-ink-500">
                        {finding.validation_criteria ? (
                          <span className="truncate block">Target Criteria: <span className="font-semibold text-ink">{finding.validation_criteria}</span></span>
                        ) : (
                          <span>Verify via continuous assurance loop</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* CRO Evidence Dissection Card if present */}
                  {finding.cro_dissection && (
                    <CroEvidenceDissectionCard dissection={finding.cro_dissection} finding={finding} />
                  )}
                </div>

                {/* ── Card Footer ────────────────────────────────────── */}
                <div className="px-5 py-3 border-t border-line/60 bg-paper-100/40 dark:bg-ink-900/30 flex items-center justify-between text-xs text-ink-500">
                  <div className="flex items-center gap-2 font-mono text-[10px]">
                    <span>{cl.checkMethod}</span>
                    <span>·</span>
                    <span>Confidence: {confidenceLabel(finding.confidence)}</span>
                  </div>
                  <span className="text-xs font-semibold text-ink flex items-center gap-1 group-hover:underline">
                    <span>Inspect Full Dossier, Code Patch &amp; Verification</span>
                    <span>→</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
