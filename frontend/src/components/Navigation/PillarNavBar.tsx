import React from 'react';
import { TabId, ExecutiveReport } from '../../types';
import { synthesizePillars } from '../../lib/pillarSynthesis';
import { buildDisplayedScore } from '../../lib/displayedAuditScore';
import { cn, ScorePill } from '../ui';
import { tabMatches } from '../../routes/navigation';
import {
  LayoutDashboard,
  Search,
  Sparkles,
  Bot,
  Zap,
  Swords,
  Landmark,
  FileSpreadsheet,
  FileCheck2,
  FileCode2,
  CalendarClock,
  ShieldCheck,
  FileText,
  PlusCircle,
  Coins,
  Compass,
  ListOrdered,
  Wrench,
  BadgeCheck,
} from 'lucide-react';

interface PillarNavBarProps {
  tab: TabId;
  onSelectTab: (tab: TabId) => void;
  report?: ExecutiveReport;
  findingsCount?: number;
  pagesCount?: number;
  onNewAudit?: () => void;
  embedded?: boolean;
  collapsed?: boolean;
}

export function PillarNavBar({
  tab,
  onSelectTab,
  report,
  findingsCount = 0,
  pagesCount = 0,
  onNewAudit,
  embedded = false,
  collapsed = false,
}: PillarNavBarProps) {
  const rollup = synthesizePillars(report);
  const displayedOverall = report ? buildDisplayedScore(report).composite : null;
  const patchesCount = (report?.code_patches?.length || 0) + (report?.remediation_patches?.length || 0);

  const workflowItems = [
    { id: 'discover' as TabId, label: 'Discover', icon: Compass },
    { id: 'decide' as TabId, label: 'Decide', icon: ListOrdered },
    { id: 'execute' as TabId, label: 'Execute', icon: Wrench },
    { id: 'prove' as TabId, label: 'Prove', icon: BadgeCheck },
  ];

  // Group 1: Executive
  const executiveItems = [
    {
      id: 'overview' as TabId,
      label: 'Executive Overview',
      icon: LayoutDashboard,
      score: displayedOverall != null ? Math.round(displayedOverall) : undefined,
    },
    {
      id: 'report' as TabId,
      label: 'Presentation Report',
      icon: FileText,
    },
  ];

  // Group 2: Core Disciplines (Separated & Industry Standard)
  const disciplineItems = [
    {
      id: 'seo' as TabId,
      label: 'SEO (Technical & On-Page)',
      icon: Search,
      score: report ? rollup.seo.score : undefined,
      badge: rollup.seo.findingsCount || undefined,
    },
    {
      id: 'geo' as TabId,
      label: 'GEO (Generative Engines)',
      icon: Sparkles,
      score: report ? rollup.geo.score : undefined,
      badge: rollup.geo.findingsCount || undefined,
    },
    {
      id: 'aeo' as TabId,
      label: 'AEO (Answer Engine & Agents)',
      icon: Bot,
      score: report ? rollup.aeo.score : undefined,
      badge: rollup.aeo.findingsCount || undefined,
    },
    {
      id: 'cro' as TabId,
      label: 'CRO & UX Optimization',
      icon: Zap,
      score: report ? rollup.cro.score : undefined,
      badge: rollup.cro.findingsCount || undefined,
    },
    {
      id: 'competitors' as TabId,
      label: 'Competitor Intelligence',
      icon: Swords,
      score: report ? rollup.competitors.score : undefined,
      badge: rollup.competitors.findingsCount || undefined,
    },
    {
      id: 'external_authority' as TabId,
      label: 'External Authority',
      icon: Landmark,
      score: undefined,
      badge: undefined,
    },
  ];

  // Group 3: Diagnostics
  const diagnosticItems = [
    {
      id: 'pages' as TabId,
      label: 'Page Inspector',
      icon: FileSpreadsheet,
      badge: pagesCount || report?.crawl_manifest?.pages?.length || undefined,
    },
    {
      id: 'findings' as TabId,
      label: 'Evidence Ledger',
      icon: FileCheck2,
      badge: findingsCount || report?.findings?.length || undefined,
    },
    {
      id: 'costing' as TabId,
      label: 'Unit Economics & Cost Ledger',
      icon: Coins,
      badge: report?.telemetry?.estimated_cost_usd ? `$${report.telemetry.estimated_cost_usd.toFixed(2)}` : undefined,
    },
  ];

  // Group 4: Engineering & Remediation
  const engineeringItems = [
    {
      id: 'patches' as TabId,
      label: 'Dev Patch Pack',
      icon: FileCode2,
      badge: patchesCount || undefined,
    },
    {
      id: 'roadmap' as TabId,
      label: 'Action Roadmap',
      icon: CalendarClock,
    },
    {
      id: 'verification' as TabId,
      label: 'Verification & Regression',
      icon: ShieldCheck,
    },
  ];

  // Helper to determine if a tab is active (supporting aliases)
  const isTabActive = (id: TabId) => tabMatches(tab, id);

  const renderItem = (item: {
    id: TabId;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    score?: number | null;
    badge?: string | number;
  }) => {
    const Icon = item.icon;
    const active = isTabActive(item.id);
    return (
      <button
        key={item.id}
        type="button"
        onClick={() => onSelectTab(item.id)}
        aria-current={active ? 'page' : undefined}
        title={item.label}
        className={cn('workspace-link text-xs font-medium', active && 'is-active')}
      >
        <div className="flex items-center gap-2.5 truncate">
          <Icon className={cn('w-4 h-4 shrink-0', active ? 'text-ink' : 'text-ink-500')} />
          {!collapsed && <span className="truncate">{item.label}</span>}
        </div>
        {!collapsed && (
          <div className="flex items-center gap-1.5 shrink-0">
            {item.badge != null && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-ink/5 text-ink-600">{item.badge}</span>
            )}
            {item.score != null && <ScorePill score={item.score} />}
          </div>
        )}
      </button>
    );
  };

  const groupLabel = (label: string) =>
    !collapsed && <p className="text-[10px] font-sans font-semibold uppercase tracking-[0.09em] text-ink-400 px-2.5 mb-1.5">{label}</p>;

  const nav = (
    <nav className={cn('flex flex-col gap-4', !embedded && 'px-3 py-3 lg:px-4 lg:py-5')} aria-label="Audit sections">
      <div className="space-y-1">
        {groupLabel('Workflow')}
        {workflowItems.map(renderItem)}
      </div>
      <div className="space-y-1">
        {groupLabel('Executive')}
        {executiveItems.map(renderItem)}
      </div>
      <div className="space-y-1">
        {groupLabel('Disciplines')}
        {disciplineItems.map(renderItem)}
      </div>
      <div className="space-y-1">
        {groupLabel('Diagnostics')}
        {diagnosticItems.map(renderItem)}
      </div>
      <div className="space-y-1">
        {groupLabel('Engineering')}
        {engineeringItems.map(renderItem)}
      </div>
      {onNewAudit && (
        <div className="pt-3 border-t border-line">
          <button type="button" onClick={onNewAudit} className="workspace-link text-xs font-semibold" title="New audit">
            <span className="flex items-center gap-2">
              <PlusCircle className="w-4 h-4 text-ink-500" />
              {!collapsed && <span>New audit</span>}
            </span>
          </button>
        </div>
      )}
    </nav>
  );

  if (embedded) return nav;

  return (
    <aside className="no-print lg:w-64 xl:w-72 shrink-0 border-b lg:border-b-0 lg:border-r border-line bg-paper-50">
      {nav}
    </aside>
  );
}
