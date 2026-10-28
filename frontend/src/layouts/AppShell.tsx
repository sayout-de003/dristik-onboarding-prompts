import React, { useEffect, useMemo, useState } from 'react';
import {
  Bell,
  Activity,
  BarChart3,
  Contact,
  CreditCard,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeft,
  PlugZap,
  Plus,
  Search,
  Settings,
  Sun,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import { AnalysisRun, AppView, AuthUser, ExecutiveReport, TabId } from '../types';
import { can } from '../services/auth';
import { PillarNavBar } from '../components/Navigation/PillarNavBar';
import { RecentAuditsDropdown } from '../components/RecentAuditsDropdown';
import { Avatar, Button, Dropdown, MenuItem, MenuLabel } from '../components/ui';
import { useTheme } from '../theme/ThemeProvider';
import { TAB_LABELS, VIEW_LABELS } from '../routes/navigation';
import { CommandAction, CommandPalette } from './CommandPalette';

interface Notice {
  id: string;
  title: string;
  description?: string;
  tone?: string;
}

interface AppShellProps {
  user: AuthUser | null;
  view: AppView;
  tab: TabId;
  run: AnalysisRun | null;
  loading: boolean;
  workspace: boolean;
  report: ExecutiveReport | null;
  findingsCount: number;
  pagesCount: number;
  onNavigate: (view: AppView) => void;
  onSelectTab: (tab: TabId) => void;
  onLogout: () => void;
  onNewAudit: () => void;
  onSelectAudit: (id: string) => void;
  onDeleteAudit: (id: string, label?: string) => void;
  onOpenPlans: () => void;
  onOpenConnectors: () => void;
  onOpenExternal: () => void;
  onOpenRemediation: () => void;
  onOpenAgency: () => void;
  onOpenRubric: () => void;
  onExport: () => void;
  children: React.ReactNode;
}

const SIDEBAR_KEY = 'dristik_sidebar';

export function AppShell(props: AppShellProps) {
  const {
    user,
    view,
    tab,
    run,
    loading,
    workspace,
    report,
    findingsCount,
    pagesCount,
    onNavigate,
    onSelectTab,
    onLogout,
    onNewAudit,
    onSelectAudit,
    onDeleteAudit,
    onOpenPlans,
    onOpenConnectors,
    onOpenExternal,
    onOpenRemediation,
    onOpenAgency,
    onOpenRubric,
    onExport,
    children,
  } = props;
  const { dark, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === 'collapsed');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [noticesOpen, setNoticesOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? 'collapsed' : 'open');
  }, [collapsed]);

  useEffect(() => {
    const onNotify = (event: Event) => {
      const detail = (event as CustomEvent<Notice>).detail;
      if (!detail?.title) return;
      setNotices((current) => [{ ...detail, id: `${Date.now()}` }, ...current].slice(0, 12));
      setUnread((count) => count + 1);
    };
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen((open) => !open);
      } else if (event.key === '[' && !typing && !event.metaKey && !event.ctrlKey) {
        setCollapsed((value) => !value);
      }
    };
    window.addEventListener('dristik:notify', onNotify);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('dristik:notify', onNotify);
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [view, tab]);

  const actions = useMemo<CommandAction[]>(() => {
    const items: CommandAction[] = [
      { id: 'home', label: 'New audit', group: 'Workspace', onSelect: onNewAudit },
      ...(user ? [{ id: 'connect', label: 'Universal AI Connect', group: 'Workspace', onSelect: () => onNavigate('connect') }] : []),
      { id: 'analytics', label: 'Delta Analytics', group: 'Workspace', onSelect: () => onNavigate('analytics') },
      ...(user ? [{ id: 'continuous', label: 'Continuous Intelligence', group: 'Workspace', onSelect: () => onNavigate('continuous') }] : []),
      { id: 'grader', label: 'Public grader', group: 'Workspace', onSelect: () => onNavigate('grader') },
      { id: 'pricing', label: 'Pricing', group: 'Workspace', onSelect: () => onNavigate('pricing') },
      { id: 'contact', label: 'Contact', group: 'Workspace', onSelect: () => onNavigate('contact') },
      { id: 'plans', label: 'Pay for an audit', group: 'Tools', onSelect: onOpenPlans },
    ];
    if (user) {
      items.push(
        { id: 'connectors', label: 'Connectors', group: 'Tools', onSelect: onOpenConnectors },
        { id: 'external', label: 'External authority', group: 'Tools', onSelect: onOpenExternal },
        { id: 'agency', label: 'Agency workspace', group: 'Tools', onSelect: onOpenAgency },
        { id: 'rubric', label: 'Scoring rubric', group: 'Tools', onSelect: onOpenRubric },
        { id: 'account', label: 'Account', group: 'Account', onSelect: () => onNavigate('account') },
      );
      if (can(user, 'staff:invite')) items.push({ id: 'team', label: 'Team', group: 'Account', onSelect: () => onNavigate('team') });
      if (user.is_system) items.push({ id: 'system', label: 'Admin console', group: 'Account', onSelect: () => onNavigate('system') });
      items.push({ id: 'logout', label: 'Log out', group: 'Account', onSelect: onLogout });
    } else {
      items.push(
        { id: 'login', label: 'Sign in', group: 'Account', onSelect: () => onNavigate('login') },
        { id: 'signup', label: 'Create workspace', group: 'Account', onSelect: () => onNavigate('signup') },
      );
    }
    if (report) {
      items.push(
        { id: 'discover', label: 'Discover', group: 'Audit', onSelect: () => onSelectTab('discover') },
        { id: 'decide', label: 'Decide', group: 'Audit', onSelect: () => onSelectTab('decide') },
        { id: 'execute', label: 'Execute', group: 'Audit', onSelect: () => onSelectTab('execute') },
        { id: 'prove', label: 'Prove', group: 'Audit', onSelect: () => onSelectTab('prove') },
        { id: 'overview', label: 'Overview', group: 'Audit', onSelect: () => onSelectTab('overview') },
        { id: 'crawl', label: 'Website Crawl', group: 'Audit', onSelect: () => onSelectTab('crawl') },
        { id: 'seo', label: 'SEO Space', group: 'Audit', onSelect: () => onSelectTab('seo') },
        { id: 'geo', label: 'GEO', group: 'Audit', onSelect: () => onSelectTab('geo') },
        { id: 'aeo', label: 'AEO', group: 'Audit', onSelect: () => onSelectTab('aeo') },
        { id: 'cro', label: 'CRO', group: 'Audit', onSelect: () => onSelectTab('cro') },
        { id: 'competitors', label: 'Competitor Analysis', group: 'Audit', onSelect: () => onSelectTab('competitors') },
        { id: 'authority', label: 'External authority report', group: 'Audit', onSelect: () => onSelectTab('external_authority') },
        { id: 'pages', label: 'Page inspector', group: 'Audit', onSelect: () => onSelectTab('pages') },
        { id: 'findings', label: 'Evidence ledger', group: 'Audit', onSelect: () => onSelectTab('findings') },
        { id: 'patches', label: 'Dev patch pack', group: 'Audit', onSelect: () => onSelectTab('patches') },
        { id: 'roadmap', label: 'Action roadmap', group: 'Audit', onSelect: () => onSelectTab('roadmap') },
        { id: 'verification', label: 'Verification', group: 'Audit', onSelect: () => onSelectTab('verification') },
        { id: 'report', label: 'Presentation report', group: 'Audit', onSelect: () => onSelectTab('report') },
        { id: 'costing', label: 'Cost ledger', group: 'Audit', onSelect: () => onSelectTab('costing') },
        { id: 'export', label: 'Export PDF', group: 'Audit', onSelect: onExport },
      );
      if (run) items.push({ id: 'remediation', label: 'Remediation', group: 'Tools', onSelect: onOpenRemediation });
    }
    items.push({ id: 'theme', label: dark ? 'Use light mode' : 'Use dark mode', group: 'Preferences', onSelect: toggle });
    return items;
  }, [
    user,
    report,
    run,
    dark,
    onNewAudit,
    onNavigate,
    onOpenPlans,
    onOpenConnectors,
    onOpenExternal,
    onOpenAgency,
    onOpenRubric,
    onLogout,
    onSelectTab,
    onExport,
    onOpenRemediation,
    toggle,
  ]);

  const crumbs = [
    { label: 'Dristik', onClick: () => onNavigate('home') },
    workspace && run
      ? { label: run.website_url.replace(/^https?:\/\//, ''), onClick: () => onSelectTab('overview') }
      : { label: VIEW_LABELS[view] },
  ];
  if (workspace && report) crumbs.push({ label: TAB_LABELS[tab] || 'Audit' });

  const productLinks = [
    { id: 'home', label: 'Audits', icon: LayoutDashboard, active: view === 'home', onClick: () => onNavigate('home') },
    ...(user ? [{ id: 'analytics', label: 'Delta Analytics', icon: BarChart3, active: view === 'analytics', onClick: () => onNavigate('analytics') }] : []),
    ...(user ? [{ id: 'continuous', label: 'Continuous Intelligence', icon: Activity, active: view === 'continuous', onClick: () => onNavigate('continuous') }] : []),
    ...(user ? [{ id: 'connect', label: 'AI Connect', icon: PlugZap, active: view === 'connect', onClick: () => onNavigate('connect') }] : []),
    { id: 'pricing', label: 'Pricing', icon: CreditCard, active: view === 'pricing', onClick: () => onNavigate('pricing') },
    { id: 'contact', label: 'Contact', icon: Contact, active: view === 'contact', onClick: () => onNavigate('contact') },
    ...(user
      ? [{ id: 'account', label: 'Account', icon: Settings, active: view === 'account', onClick: () => onNavigate('account') }]
      : []),
    ...(user && can(user, 'staff:invite')
      ? [{ id: 'team', label: 'Team', icon: Users, active: view === 'team', onClick: () => onNavigate('team') }]
      : []),
    ...(user?.is_system
      ? [{ id: 'system', label: 'Admin', icon: Settings, active: view === 'system', onClick: () => onNavigate('system') }]
      : []),
  ];

  const compact = collapsed && !mobileOpen;
  const status = run?.status?.replace(/_/g, ' ') || '';

  return (
    <div className="min-h-screen bg-paper text-ink">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {mobileOpen && (
        <button type="button" className="scrim fixed inset-0 z-overlay lg:hidden" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />
      )}
      <div className="lg:flex min-h-screen">
        <aside
          className={`no-print fixed inset-y-0 left-0 z-modal lg:sticky lg:top-0 lg:z-sticky lg:h-screen border-r border-line bg-paper-50 flex flex-col transition-transform lg:translate-x-0 ${
            mobileOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
          style={{ width: mobileOpen || !collapsed ? 'var(--sidebar)' : 'var(--sidebar-collapsed)' }}
          aria-label="Primary"
        >
          <div className="h-14 px-3 flex items-center justify-between gap-2 border-b border-line shrink-0">
            <button type="button" onClick={() => onNavigate('home')} className="flex items-center gap-2 min-w-0" aria-label="Dristik home">
              <span className="h-7 w-7 shrink-0 rounded-md bg-ink text-[13px] font-semibold text-paper-50 inline-flex items-center justify-center">
                D
              </span>
              {!compact && <span className="text-base font-semibold leading-none text-ink tracking-tight">Dristik</span>}
            </button>
            <button type="button" className="lg:hidden p-1 text-ink-500" aria-label="Close menu" onClick={() => setMobileOpen(false)}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 py-3">
            {workspace && report ? (
              <PillarNavBar
                embedded
                collapsed={compact}
                tab={tab}
                onSelectTab={onSelectTab}
                report={report}
                findingsCount={findingsCount}
                pagesCount={pagesCount}
                onNewAudit={onNewAudit}
              />
            ) : (
              <nav className="space-y-1" aria-label="Product">\n                {!compact && <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-400">Workspace</p>}
                {productLinks.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={item.onClick}
                      aria-current={item.active ? 'page' : undefined}
                      title={item.label}
                      className={`workspace-link text-sm ${item.active ? 'is-active' : ''}`}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <Icon className="h-4 w-4 shrink-0" aria-hidden />
                        {!compact && <span className="truncate">{item.label}</span>}
                      </span>
                    </button>
                  );
                })}
              </nav>
            )}
          </div>
          <div className="border-t border-line p-2 space-y-1">
            <button
              type="button"
              className="workspace-link text-sm"
              onClick={() => setCommandOpen(true)}
              title="Open tools and quick actions (⌘K)"
            >
              <span className="flex items-center gap-2.5">
                <Wrench className="h-4 w-4" aria-hidden />
                {!compact && <span>Tools &amp; settings</span>}
              </span>
            </button>
            <button type="button" className="workspace-link text-sm" onClick={() => onNavigate('pricing')} title="Pricing">
              <span className="flex items-center gap-2.5">
                <CreditCard className="h-4 w-4" aria-hidden />
                {!compact && <span>Pricing</span>}
              </span>
            </button>
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">
          <header className="no-print sticky top-0 z-sticky topbar border-b border-line h-14 px-3 sm:px-4 flex items-center gap-2 relative">
            <button type="button" className="lg:hidden p-1.5 rounded-md hover:bg-paper-200" aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
              <Menu className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="hidden lg:inline-flex p-1.5 rounded-md text-ink-500 hover:bg-paper-200"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              onClick={() => setCollapsed((value) => !value)}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <nav aria-label="Breadcrumb" className="min-w-0 hidden sm:flex items-center gap-1.5 text-sm text-ink-500">
              {crumbs.map((crumb, index) => (
                <React.Fragment key={`${crumb.label}-${index}`}>
                  {index > 0 && <span aria-hidden>/</span>}
                  {crumb.onClick ? (
                    <button type="button" onClick={crumb.onClick} className="truncate max-w-[220px] hover:text-ink">
                      {crumb.label}
                    </button>
                  ) : (
                    <span className="truncate max-w-[220px] text-ink font-medium">{crumb.label}</span>
                  )}
                </React.Fragment>
              ))}
            </nav>
            {run && workspace && (
              <span className="hidden md:inline-flex items-center gap-1.5 ml-2 text-xs text-ink-500">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    run.status === 'completed' ? 'bg-good' : run.status === 'failed' ? 'bg-bad' : 'bg-pine animate-pulse'
                  }`}
                />
                <span className="capitalize" aria-live="polite">{status}</span>
                <span className="font-mono font-medium text-ink-700 bg-paper-200 px-1.5 py-0.5 rounded text-[11px]">
                  {run.status === 'completed' ? '100%' : Number.isFinite(run.progress_percentage) ? `${run.progress_percentage}%` : 'Progress not reported'}
                </span>
              </span>
            )}
            <div className="ml-auto flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => setCommandOpen(true)} aria-label="Search pages and actions">
                <Search className="h-4 w-4" />
                <span className="hidden md:inline">Search pages and actions</span>
                <kbd className="hidden md:inline font-mono text-[10px] text-ink-400 border border-line rounded px-1">⌘K</kbd>
              </Button>
              <RecentAuditsDropdown currentAnalysisId={run?.analysis_id} onSelectAudit={onSelectAudit} onNewAudit={onNewAudit} onAuditDeleted={onDeleteAudit} />
              
              {/* Tools Dropdown Menu */}
              <Dropdown
                align="right"
                label={
                  <span className="inline-flex items-center gap-1.5 font-medium text-xs text-ink-700 hover:text-ink">
                    <Wrench className="h-3.5 w-3.5" />
                    <span>Tools</span>
                  </span>
                }
              >
                <MenuLabel>Workspace Tools</MenuLabel>
                <MenuItem onClick={() => onNavigate('connect')}>
                  <div className="py-0.5">
                    <span className="font-semibold text-xs text-ink block">Universal AI Connect</span>
                    <span className="text-[10px] text-ink-500 block">External AI credentials &amp; MCP gateway</span>
                  </div>
                </MenuItem>
                {onOpenConnectors && (
                  <MenuItem onClick={onOpenConnectors}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Connectors</span>
                      <span className="text-[10px] text-ink-500 block">Google Search Console &amp; GA4</span>
                    </div>
                  </MenuItem>
                )}
                {onOpenExternal && (
                  <MenuItem onClick={onOpenExternal}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">External Authority</span>
                      <span className="text-[10px] text-ink-500 block">Live link graph &amp; citation verification</span>
                    </div>
                  </MenuItem>
                )}
                {onOpenRemediation && (
                  <MenuItem onClick={onOpenRemediation}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Remediation Engine</span>
                      <span className="text-[10px] text-ink-500 block">Self-contained code patches &amp; ZIP bundle</span>
                    </div>
                  </MenuItem>
                )}
                {onOpenAgency && (
                  <MenuItem onClick={onOpenAgency}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Agency Workspace</span>
                      <span className="text-[10px] text-ink-500 block">Multi-client branding &amp; white-label</span>
                    </div>
                  </MenuItem>
                )}
                {onOpenRubric && (
                  <MenuItem onClick={onOpenRubric}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Scoring Rubric</span>
                      <span className="text-[10px] text-ink-500 block">Dristik v5.0 deterministic curves</span>
                    </div>
                  </MenuItem>
                )}
                <MenuLabel>Billing &amp; Delivery</MenuLabel>
                {onOpenPlans && (
                  <MenuItem onClick={onOpenPlans}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Pay for an audit</span>
                      <span className="text-[10px] text-ink-500 block">Audit passes &amp; tiers</span>
                    </div>
                  </MenuItem>
                )}
                {report && onExport && (
                  <MenuItem onClick={onExport}>
                    <div className="py-0.5">
                      <span className="font-semibold text-xs text-ink block">Export PDF Report</span>
                      <span className="text-[10px] text-ink-500 block">Download presentation slide deck</span>
                    </div>
                  </MenuItem>
                )}
              </Dropdown>
              <button
                type="button"
                className="relative p-1.5 rounded-md text-ink-600 hover:bg-paper-200"
                aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
                aria-expanded={noticesOpen}
                onClick={() => {
                  setNoticesOpen((open) => !open);
                  setUnread(0);
                }}
              >
                <Bell className="h-4 w-4" />
                {unread > 0 && <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-bad" />}
              </button>
              {noticesOpen && (
                <div className="absolute right-3 top-14 w-80 card shadow-lg p-0 z-dropdown">
                  <div className="flex items-center justify-between px-3 py-2 border-b border-line">
                    <p className="text-sm font-semibold">Notifications</p>
                    <button type="button" className="text-xs text-ink-500 hover:text-ink" onClick={() => setNotices([])}>
                      Clear
                    </button>
                  </div>
                  {notices.length === 0 ? (
                    <p className="px-3 py-6 text-sm text-ink-500">No notifications yet. Audit updates appear here.</p>
                  ) : (
                    <ul className="max-h-80 overflow-y-auto">
                      {notices.map((notice) => (
                        <li key={notice.id} className="px-3 py-2.5 border-b border-line last:border-0">
                          <p className="text-sm text-ink">{notice.title}</p>
                          {notice.description && <p className="text-xs text-ink-500 mt-0.5">{notice.description}</p>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              <button type="button" className="p-1.5 rounded-md text-ink-600 hover:bg-paper-200" aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} onClick={toggle}>
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              {user ? (
                <button type="button" className="inline-flex items-center gap-2 pl-1" onClick={() => onNavigate('account')} aria-label="Account">
                  <Avatar name={user.full_name} src={user.avatar_url} size="sm" />
                  <span className="hidden xl:block text-sm text-ink-700 max-w-[120px] truncate">{user.full_name.split(' ')[0]}</span>
                </button>
              ) : (
                <Button size="sm" onClick={() => onNavigate('login')}>
                  Sign in
                </Button>
              )}
              <Button variant="secondary" size="sm" className="hidden sm:inline-flex" onClick={onNewAudit}>
                <Plus className="h-3.5 w-3.5" />
                New
              </Button>
            </div>
          </header>
          <main id="main" className="flex-1 min-w-0">
            {children}
          </main>
          {!workspace && (
            <footer className="no-print border-t border-line mt-auto">
              <div className="max-w-page mx-auto px-4 sm:px-6 lg:px-8 py-5 text-sm text-ink-400 flex items-center justify-between gap-4">
                <span className="font-semibold text-ink-500">Dristik</span>
                <button type="button" onClick={() => onNavigate('contact')} className="hover:text-ink">
                  Contact
                </button>
              </div>
            </footer>
          )}
        </div>
      </div>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} actions={actions} />
    </div>
  );
}
