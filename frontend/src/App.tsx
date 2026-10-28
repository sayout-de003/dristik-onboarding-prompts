import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { AnalysisRun, AnalysisSummary, AppView, AuthUser, ConnectorType, Finding, TabId } from './types';
import { deleteAnalysis, getAnalysis, listAnalyses, openAnalysisStream, startAnalysis } from './services/api';
import { can, fetchMe, logout } from './services/auth';
import { AuditForm } from './components/AuditForm';
import { DeltaAnalyticsDashboard } from './components/DeltaAnalyticsDashboard';
import { Pipeline } from './components/Pipeline';
import { Telemetry } from './components/Telemetry';
import { Drawer } from './components/Drawer';
import { PricingModal } from './components/PricingModal';
import { Intro } from './components/Intro';
import { ForgotScreen, LoginScreen, ResetScreen, SignupScreen } from './components/AuthScreens';
import { AccountPanel, TeamPanel } from './components/AccountPanel';
import { ContactForm } from './components/ContactForm';
import { ConnectorsModal } from './components/ConnectorsModal';
import { ExternalAuthorityPanel } from './components/ExternalAuthorityPanel';
import { AuditDataSources } from './components/AuditDataSources';
import { UniversalConnectView } from './components/UniversalConnectView';
import { OperatingWorkflow } from './components/OperatingWorkflow';
import { PublicGrader } from './components/PublicGrader';
import { RemediationFlowModal } from './components/RemediationFlowModal';
import { AgencyWorkspaceModal } from './components/AgencyWorkspaceModal';
import { ScoringRubricModal } from './components/ScoringRubricModal';
import { ConfirmDialog, EmptyState, ErrorState, LoadingBlock, PageHeader, notify } from './components/ui';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppShell } from './layouts/AppShell';
import { parseNavigation, syncAnalysisQuery } from './routes/navigation';
import { lazyWithRetry } from './utils/lazyWithRetry';

const Overview = lazyWithRetry(() => import('./components/Overview').then((m) => ({ default: m.Overview })));
const Findings = lazyWithRetry(() => import('./components/Findings').then((m) => ({ default: m.Findings })));
const Roadmap = lazyWithRetry(() => import('./components/Roadmap').then((m) => ({ default: m.Roadmap })));
const Report = lazyWithRetry(() => import('./components/Report').then((m) => ({ default: m.Report })));
const Big4AuditReport = lazyWithRetry(() => import('./components/Big4AuditReport').then((m) => ({ default: m.Big4AuditReport })));
const AuditPdfReport = lazyWithRetry(() => import('./components/AuditPdfReport').then((m) => ({ default: m.AuditPdfReport })));
const Pricing = lazyWithRetry(() => import('./components/Pricing').then((m) => ({ default: m.Pricing })));
const SystemPanel = lazyWithRetry(() => import('./components/SystemPanel').then((m) => ({ default: m.SystemPanel })));
const ExternalAuthorityView = lazyWithRetry(() => import('./components/ExternalAuthorityView').then((m) => ({ default: m.ExternalAuthorityView })));
const CrawlWorkspaceView = lazyWithRetry(() => import('./components/Pillars/CrawlWorkspaceView').then((m) => ({ default: m.CrawlWorkspaceView })));
const SeoWorkspaceView = lazyWithRetry(() => import('./components/Pillars/SeoWorkspaceView').then((m) => ({ default: m.SeoWorkspaceView })));
const GeoWorkspaceView = lazyWithRetry(() => import('./components/Pillars/GeoWorkspaceView').then((m) => ({ default: m.GeoWorkspaceView })));
const AeoWorkspaceView = lazyWithRetry(() => import('./components/Pillars/AeoWorkspaceView').then((m) => ({ default: m.AeoWorkspaceView })));
const CroWorkspaceView = lazyWithRetry(() => import('./components/Pillars/CroWorkspaceView').then((m) => ({ default: m.CroWorkspaceView })));
const CompetitorWorkspaceView = lazyWithRetry(() => import('./components/Pillars/CompetitorWorkspaceView').then((m) => ({ default: m.CompetitorWorkspaceView })));
const DevPatchPackView = lazyWithRetry(() => import('./components/DevPatchPackView').then((m) => ({ default: m.DevPatchPackView })));
const VerificationWorkspaceView = lazyWithRetry(() => import('./components/VerificationWorkspaceView').then((m) => ({ default: m.VerificationWorkspaceView })));
const Pages = lazyWithRetry(() => import('./components/Pages').then((m) => ({ default: m.Pages })));
const CostLedgerView = lazyWithRetry(() => import('./components/CostLedgerView').then((m) => ({ default: m.CostLedgerView })));
const ContinuousIntelligenceView = lazyWithRetry(() => import('./components/ContinuousIntelligenceView').then((m) => ({ default: m.ContinuousIntelligenceView })));

export function App() {
  const initial = parseNavigation();
  const [url, setUrl] = useState('');
  const [maxPages, setMaxPages] = useState(5);
  const [siteType, setSiteType] = useState<string>('');
  const [declaredNotes, setDeclaredNotes] = useState<string>('');
  const [targetPillars, setTargetPillars] = useState<string[]>(['seo', 'geo', 'aeo', 'cro']);
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [tab, setTab] = useState<TabId>('overview');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plansOpen, setPlansOpen] = useState(false);
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [externalOpen, setExternalOpen] = useState(false);
  const [connectorsInitialTab, setConnectorsInitialTab] = useState<ConnectorType>('google_search_console');
  const [connectorNotice, setConnectorNotice] = useState<string | null>(null);
  const [externalNotice, setExternalNotice] = useState<string | null>(null);
  const [remediationOpen, setRemediationOpen] = useState(false);
  const [agencyOpen, setAgencyOpen] = useState(false);
  const [rubricOpen, setRubricOpen] = useState(false);
  const [planId, setPlanId] = useState('professional');
  const [voucher, setVoucher] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [view, setView] = useState<AppView>(initial.view);
  const [resetToken, setResetToken] = useState<string | undefined>(initial.token);
  const [previewDeck, setPreviewDeck] = useState(false);
  const [recentAudits, setRecentAudits] = useState<AnalysisSummary[]>([]);

  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const syncActiveAnalysisId = (id: string | null) => {
    syncAnalysisQuery(id);
  };

  const go = (next: AppView, extra?: string) => {
    if (next === 'home' && !extra) {
      history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
      setView('home');
      return;
    }
    window.location.hash = extra || next;
    const parsed = parseNavigation();
    setView(parsed.view);
    if (parsed.token) setResetToken(parsed.token);
  };

  const loadAudit = async (targetId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAnalysis(targetId);
      setRun(data);
      if (data.website_url) setUrl(data.website_url);
      syncActiveAnalysisId(data.analysis_id);

      // If still in progress, reconnect live stream
      if (data.status !== 'completed' && data.status !== 'failed') {
        const stream = openAnalysisStream(data.analysis_id);
        stream.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            setRun((prev) => {
              if (!prev) return prev;
              const liveTelemetry = payload.telemetry ?? payload.data?.telemetry ?? prev.telemetry;
              const liveGraph = payload.graph ?? payload.data?.graph ?? prev.graph;
              return {
                ...prev,
                progress_percentage: payload.progress ?? prev.progress_percentage,
                current_step: payload.message ?? prev.current_step,
                status: payload.stage ?? prev.status,
                report: payload.data?.report ?? prev.report,
                telemetry: liveTelemetry,
                graph: liveGraph,
              };
            });
            if (payload.stage === 'completed') {
              setLoading(false);
              stream.close();
            } else if (payload.stage === 'failed') {
              setLoading(false);
              setError(payload.message || 'The audit failed.');
              stream.close();
            }
          } catch {
            /* ignore */
          }
        };
        stream.onerror = () => {
          getAnalysis(data.analysis_id)
            .then((updated) => {
              setRun(updated);
              setLoading(false);
            })
            .catch(() => setLoading(false));
          stream.close();
        };
      } else {
        setLoading(false);
      }
    } catch (err: unknown) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Could not load the audit.');
      syncActiveAnalysisId(null);
    }
  };

  const clearAudit = () => {
    syncActiveAnalysisId(null);
    setRun(null);
    setUrl('');
    setError(null);
    setFinding(null);
    setTab('overview');
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connectorFlag = params.get('connector');
    const externalFlag = params.get('external');
    const provider = params.get('provider') || '';
    const reason = params.get('reason') || '';
    const labels: Record<string, string> = {
      google_search_console: 'Google Search Console',
      google_analytics_4: 'Google Analytics 4',
      google_analytics: 'Google Analytics',
      crux: 'Google CrUX',
    };
    const label = labels[provider] || provider.replace(/_/g, ' ') || 'Connector';
    let changed = false;
    if (connectorFlag === 'connected') {
      const known: ConnectorType[] = [
        'google_search_console',
        'google_analytics_4',
        'google_analytics',
        'crux',
        'dataforseo',
        'crm',
        'live_ai_search',
        'wordpress',
        'github',
        'shopify',
        'webflow',
        'generic',
      ];
      if (known.includes(provider as ConnectorType)) {
        setConnectorsInitialTab(provider as ConnectorType);
      }
      setConnectorNotice(`${label} is connected.`);
      setConnectorsOpen(true);
      notify({ title: `${label} is connected`, description: 'The account is saved on this page.', tone: 'success' });
      params.delete('connector');
      params.delete('provider');
      changed = true;
    } else if (connectorFlag === 'error') {
      const description = reason === 'cancelled'
        ? 'Google sign-in was cancelled. Nothing was connected.'
        : 'The connection was not saved. Use Connect again from this page.';
      setConnectorNotice(description);
      setConnectorsOpen(true);
      notify({ title: 'Connection was not saved', description, tone: 'warning' });
      params.delete('connector');
      params.delete('provider');
      params.delete('reason');
      changed = true;
    }
    if (externalFlag === 'connected') {
      setExternalNotice(`${label} is connected.`);
      setExternalOpen(true);
      notify({ title: `${label} is connected`, tone: 'success' });
      params.delete('external');
      params.delete('provider');
      changed = true;
    } else if (externalFlag === 'error') {
      const description = reason === 'state'
        ? 'Google returned without a saved connection. Use Connect again from this page.'
        : 'The connection was not saved.';
      setExternalNotice(description);
      setExternalOpen(true);
      notify({ title: 'Connection was not saved', description, tone: 'warning' });
      params.delete('external');
      params.delete('reason');
      changed = true;
    }
    if (changed) {
      const query = params.toString();
      const next = query
        ? `${window.location.pathname}?${query}${window.location.hash}`
        : `${window.location.pathname}${window.location.hash}`;
      window.history.replaceState(null, '', next);
    }
    fetchMe().then(setUser).catch(() => setUser(null));
    listAnalyses(6).then(setRecentAudits).catch(() => {});

    const nav = parseNavigation();
    if (nav.analysisId) {
      loadAudit(nav.analysisId);
    }

    const onHash = () => {
      const parsed = parseNavigation();
      setView(parsed.view);
      setResetToken(parsed.token);
      if (parsed.analysisId && parsed.analysisId !== run?.analysis_id) {
        loadAudit(parsed.analysisId);
      }
    };
    const onUnauthorized = () => setUser(null);
    window.addEventListener('hashchange', onHash);
    window.addEventListener('dristik:unauthorized', onUnauthorized);
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('dristik:unauthorized', onUnauthorized);
    };
  }, []);

  const statusKey = useRef<string | null>(null);
  useEffect(() => {
    if (!run?.status || !run.analysis_id) return;
    const key = `${run.analysis_id}|${run.status}`;
    const previous = statusKey.current;
    statusKey.current = key;
    if (!previous || previous === key) return;
    const [previousId, previousStatus] = previous.split('|');
    if (previousId !== run.analysis_id || previousStatus === run.status) return;
    if (run.status === 'completed') notify({ title: 'Audit ready', description: run.website_url, tone: 'success' });
    if (run.status === 'failed') notify({ title: 'Audit failed', description: run.current_step, tone: 'danger' });
  }, [run?.status, run?.analysis_id, run?.website_url, run?.current_step]);

  const start = async (overrideUrl?: string) => {
    const target = (overrideUrl ?? url).trim();
    if (!user) {
      setError('Sign in to run an audit.');
      go('login');
      return;
    }
    if (!can(user, 'mission:create')) {
      setError('Your role can view reports but cannot start audits. Ask an admin.');
      return;
    }
    if (!target) {
      setError('Enter a website URL.');
      return;
    }

    setLoading(true);
    setError(null);
    setFinding(null);
    setTab('overview');

    try {
      const created = await startAnalysis(target, maxPages, siteType, declaredNotes, targetPillars);
      setRun(created);
      syncActiveAnalysisId(created.analysis_id);

      const stream = openAnalysisStream(created.analysis_id);
      stream.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setRun((prev) => {
            if (!prev) return prev;
            const liveTelemetry = payload.telemetry ?? payload.data?.telemetry ?? prev.telemetry;
            const liveGraph = payload.graph ?? payload.data?.graph ?? prev.graph;
            return {
              ...prev,
              progress_percentage: payload.progress ?? prev.progress_percentage,
              current_step: payload.message ?? prev.current_step,
              status: payload.stage ?? prev.status,
              report: payload.data?.report ?? prev.report,
              telemetry: liveTelemetry,
              graph: liveGraph,
            };
          });

          if (payload.stage === 'completed') {
            setLoading(false);
            stream.close();
          } else if (payload.stage === 'failed') {
            setLoading(false);
            setError(payload.message || 'The audit failed.');
            stream.close();
          } else if (payload.stage === 'paused') {
            setLoading(false);
          }
        } catch {
          /* ignore malformed events */
        }
      };

      stream.onerror = () => {
        getAnalysis(created.analysis_id)
          .then((data) => {
            setRun(data);
            setLoading(false);
          })
          .catch(() => setLoading(false));
        stream.close();
      };
    } catch (err: unknown) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Could not start the audit.');
    }
  };

  const report = run?.report;
  const findingsCount = report?.findings.length ?? 0;
  const pagesCount = report?.crawl_manifest?.pages?.length ?? 0;
  const workspaceRun = view === 'home' ? run : null;

  const auditForm = (
    <AuditForm
      url={url}
      maxPages={maxPages}
      siteType={siteType}
      declaredNotes={declaredNotes}
      targetPillars={targetPillars}
      onTargetPillarsChange={setTargetPillars}
      isLoading={loading}
      error={error}
      onUrlChange={(value) => {
        setUrl(value);
        setError(null);
      }}
      onMaxPagesChange={setMaxPages}
      onSiteTypeChange={setSiteType}
      onDeclaredNotesChange={setDeclaredNotes}
      onSubmit={() => start()}
    />
  );

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteAnalysis(pendingDelete.id);
      setRecentAudits((prev) => prev.filter((item) => item.analysis_id !== pendingDelete.id));
      if (run?.analysis_id === pendingDelete.id) clearAudit();
      notify({ title: 'Audit deleted', tone: 'success' });
      window.dispatchEvent(new CustomEvent('dristik:audits-changed'));
      setPendingDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the audit.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AppShell
      user={user}
      view={view}
      tab={tab}
      run={run}
      loading={loading}
      workspace={Boolean(workspaceRun)}
      report={report || null}
      findingsCount={findingsCount}
      pagesCount={pagesCount}
      onNavigate={go}
      onSelectTab={setTab}
      onLogout={async () => {
        await logout();
        setUser(null);
        go('home');
      }}
      onNewAudit={() => {
        clearAudit();
        go('home');
      }}
      onSelectAudit={(id) => {
        go('home');
        loadAudit(id);
      }}
      onDeleteAudit={(id, label) => {
        const match = recentAudits.find((item) => item.analysis_id === id);
        setPendingDelete({
          id,
          label: label || match?.domain || run?.website_url?.replace(/^https?:\/\//, '') || 'this audit',
        });
      }}
      onOpenPlans={() => setPlansOpen(true)}
      onOpenConnectors={() => {
        setConnectorsInitialTab('wordpress');
        setConnectorsOpen(true);
      }}
      onOpenExternal={() => setExternalOpen(true)}
      onOpenRemediation={() => setRemediationOpen(true)}
      onOpenAgency={() => setAgencyOpen(true)}
      onOpenRubric={() => setRubricOpen(true)}
      onExport={() => {
        const id = run?.report?.analysis_id || run?.report?.report_id || run?.analysis_id;
        if (id) window.open(`/api/v1/reports/${id}/seo-report?format=pdf&download=true`, '_blank');
        else window.print();
      }}
    >
      {workspaceRun ? (
        <div className="no-print">
            <div className="max-w-page mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
              {!report && (
                <div className="space-y-6">
                  <PageHeader
                    kicker="Audit in progress"
                    title={workspaceRun.website_url.replace(/^https?:\/\//, '')}
                    description="Crawl, evidence, specialists, and scoring run in sequence. Stay on this page until the report is ready."
                  />
                  <Pipeline run={workspaceRun} onRefreshRun={() => loadAudit(workspaceRun.analysis_id)} />
                  {workspaceRun.telemetry && (
                    <Telemetry
                      telemetry={workspaceRun.telemetry}
                      onNavigateToCosting={() => setTab('costing')}
                    />
                  )}
                  {error && <ErrorState title="Audit problem" description={error} />}
                </div>
              )}

              {report && (
                <ErrorBoundary key={tab}>
                <Suspense fallback={<LoadingBlock label="Loading this section" />}>
                <div className="space-y-8">
                  {(tab === 'discover' || tab === 'decide' || tab === 'execute' || tab === 'prove') && (
                    <OperatingWorkflow stage={tab} report={report} onSelectTab={setTab} />
                  )}

                  {tab === 'overview' && (
                    <Overview
                      scores={report.scores}
                      honestScores={report.honest_scores}
                      profile={report.business_profile}
                      semantic={report.semantic_business}
                      contradictions={report.contradictions}
                      story={report.story_summary}
                      opportunity={report.primary_strategic_opportunity}
                      strengths={report.what_site_gets_right}
                      blockers={report.what_is_holding_it_back}
                      ignore={report.consultant_advice_what_to_ignore}
                      report={report}
                      onNavigate={(nextTab) => {
                        if ((nextTab as string) === 'connectors') {
                          setConnectorsInitialTab('google_search_console');
                          setConnectorsOpen(true);
                        } else {
                          setTab(nextTab);
                        }
                      }}
                      onOpenConnectors={(connectorTab) => {
                        setConnectorsInitialTab((connectorTab as ConnectorType) || 'google_search_console');
                        setConnectorsOpen(true);
                      }}
                    />
                  )}

                  {/* 0. WEBSITE CRAWL WORKSPACE */}
                  {tab === 'crawl' && (
                    <CrawlWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                    />
                  )}

                  {/* 1. SEO WORKSPACE */}
                  {(tab === 'seo' || tab === 'search_intelligence' || tab === 'search_console') && (
                    <SeoWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                      onSelectFinding={setFinding}
                      onOpenConnectors={(tabId) => {
                        setConnectorsInitialTab((tabId as ConnectorType) || 'google_search_console');
                        setConnectorsOpen(true);
                      }}
                    />
                  )}

                  {/* 2. GEO WORKSPACE */}
                  {(tab === 'geo' || tab === 'ai_search_intelligence' || tab === 'ai_citations' || tab === 'ai_search') && (
                    <GeoWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                      onOpenPatchPack={() => setRemediationOpen(true)}
                      onNavigateToTab={(t) => setTab(t)}
                      onEvaluationsUpdated={(newEvals) => {
                        setRun((prev) => {
                          if (!prev || !prev.report) return prev;
                          return {
                            ...prev,
                            report: {
                              ...prev.report,
                              ai_search_matrix: newEvals,
                            },
                          };
                        });
                      }}
                    />
                  )}

                  {/* 3. AEO WORKSPACE */}
                  {(tab === 'aeo' || tab === 'brand_entity_intelligence') && (
                    <AeoWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                      onOpenPatchPack={() => setRemediationOpen(true)}
                    />
                  )}

                  {/* 4. CRO WORKSPACE */}
                  {(tab === 'cro' || tab === 'conversion_intelligence' || tab === 'website_experience') && (
                    <CroWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                      onDeployRemediation={() => setRemediationOpen(true)}
                    />
                  )}

                  {/* 5. COMPETITOR INTELLIGENCE WORKSPACE */}
                  {tab === 'external_authority' && (
                    <ExternalAuthorityView report={report.external_authority} />
                  )}

                  {(tab === 'competitors' || tab === 'perspectives' || tab === 'lead_gen') && (
                    <CompetitorWorkspaceView
                      report={report}
                      analysisId={run?.analysis_id}
                      websiteUrl={run?.website_url || report.website_url}
                    />
                  )}

                  {/* 6. PAGE INSPECTOR */}
                  {tab === 'pages' && (
                    <Pages
                      manifest={report.crawl_manifest}
                      summary={report.crawl_summary}
                      pageReports={report.page_reports}
                      ga4LandingPages={
                        (report as any).analytics?.ga4?.top_landing_pages ||
                        (report as any).lifecycle_revenue?.ga4?.landing_pages ||
                        []
                      }
                    />
                  )}

                  {/* 7. EVIDENCE LEDGER / FINDINGS */}
                  {tab === 'findings' && (
                    <Findings
                      findings={report.findings}
                      patches={report.code_patches}
                      evidenceLedger={report.evidence_ledger}
                      onSelect={setFinding}
                    />
                  )}

                  {/* 8. DEV PATCH PACK */}
                  {tab === 'patches' && (
                    <DevPatchPackView report={report} analysisId={run?.analysis_id} />
                  )}

                  {/* 9. ACTION ROADMAP */}
                  {tab === 'roadmap' && (
                    <Roadmap
                      days7={report.roadmap_7_days}
                      days30={report.roadmap_30_days}
                      days90={report.roadmap_90_days}
                    />
                  )}

                  {/* 10. VERIFICATION & REGRESSION */}
                  {tab === 'verification' && (
                    <VerificationWorkspaceView report={report} analysisId={run?.analysis_id} />
                  )}

                  {/* 11. PRESENTATION REPORT */}
                  {tab === 'report' && (
                    <Report
                      report={report}
                      onPreviewDeck={() => setPreviewDeck(true)}
                      onExportPdf={() => {
                        const id = report.analysis_id || report.report_id || run?.analysis_id;
                        if (id) window.open(`/api/v1/reports/${id}/seo-report?format=pdf&download=true`, '_blank');
                        else window.print();
                      }}
                    />
                  )}

                  {/* 12. PLANS / BILLING */}
                  {tab === 'plans' && (
                    <Pricing
                      onSelectPlan={(id) => {
                        setPlanId(id);
                        setPlansOpen(true);
                      }}
                    />
                  )}

                  {/* 13. UNIT ECONOMICS & COST LEDGER */}
                  {(tab === 'costing' || tab === 'costs') && (
                    <CostLedgerView
                      report={report}
                      telemetry={run?.telemetry || report.telemetry}
                      onNavigateToTab={setTab}
                    />
                  )}

                  {report.telemetry && (
                    <div className="pt-4 border-t border-line">
                      <Telemetry
                        telemetry={report.telemetry}
                        onNavigateToCosting={() => setTab('costing')}
                      />
                    </div>
                  )}
                </div>
                </Suspense>
                </ErrorBoundary>
              )}
            </div>
        </div>
      ) : (
        <div className="no-print max-w-[1120px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
          {view === 'login' && (
            <LoginScreen
              onAuthed={async () => {
                setUser(await fetchMe());
                go('home');
              }}
              onView={go}
            />
          )}
          {view === 'signup' && (
            <SignupScreen
              onAuthed={async () => {
                setUser(await fetchMe());
                go('home');
              }}
              onView={go}
            />
          )}
          {view === 'forgot' && <ForgotScreen onView={go} />}
          {view === 'reset' && <ResetScreen token={resetToken} onView={go} />}
          {view === 'contact' && <ContactForm user={user} />}
          {view === 'account' && user && (
            <AccountPanel
              user={user}
              onDeleted={() => {
                setUser(null);
                go('home');
              }}
            />
          )}
          {(view === 'account' || view === 'team' || view === 'system') && !user && (
            <LoginScreen
              onAuthed={async () => {
                setUser(await fetchMe());
                go(view);
              }}
              onView={go}
            />
          )}
          {view === 'team' && user && <TeamPanel user={user} />}
          {view === 'system' && user?.is_system && (
            <Suspense fallback={<LoadingBlock label="Loading admin" />}>
              <SystemPanel />
            </Suspense>
          )}
          {view === 'connect' && user && <UniversalConnectView />}
          {view === 'connect' && !user && <LoginScreen onAuthed={async () => { setUser(await fetchMe()); go('connect'); }} onView={go} />}
          {view === 'analytics' && user && <DeltaAnalyticsDashboard />}
          {view === 'continuous' && user && <Suspense fallback={<LoadingBlock label="Loading continuous intelligence" />}><ContinuousIntelligenceView /></Suspense>}
          {view === 'continuous' && !user && <LoginScreen onAuthed={async () => { setUser(await fetchMe()); go('continuous'); }} onView={go} />}
          {view === 'analytics' && !user && <LoginScreen onAuthed={async () => { setUser(await fetchMe()); go('analytics'); }} onView={go} />}
          {view === 'grader' && (
            <PublicGrader onStartAudit={() => go('home')} />
          )}

          {view === 'pricing' && (
            <Suspense fallback={<LoadingBlock label="Loading pricing" />}>
              <Pricing
                onSelectPlan={(id) => {
                  setPlanId(id);
                  setPlansOpen(true);
                }}
              />
            </Suspense>
          )}

          {view === 'home' && (
            <section className="space-y-8">
              <PageHeader
                kicker="Website intelligence"
                title="Evidence-first audits for search, AI, and conversion."
                description="Paste a public URL. Dristik crawls the pages, verifies every claim against the live DOM, then returns a score, findings, patches, and a 7 / 30 / 90-day plan."
              >
                {user ? (
                  <p className="text-sm text-ink-500">
                    Signed in as {user.full_name} · {user.role_label} · {user.org_name}.{' '}
                    <button type="button" className="text-ink underline" onClick={() => go('grader')}>
                      Grade a public domain
                    </button>
                  </p>
                ) : (
                  <p className="text-sm text-ink-500">
                    Sign in with your organization to run an audit.{' '}
                    <button type="button" className="text-ink underline" onClick={() => go('signup')}>
                      Create a workspace
                    </button>
                    {' '}or{' '}
                    <button type="button" className="text-ink underline" onClick={() => go('grader')}>
                      grade a public domain
                    </button>
                    .
                  </p>
                )}
              </PageHeader>

              {voucher && (
                <p className="text-sm text-ink-500">
                  Voucher {voucher} · up to {maxPages} pages
                </p>
              )}

              <div className="card p-5 sm:p-6">
                {auditForm}
                <AuditDataSources domain={url} />
                {recentAudits.length > 0 && !run && (
                  <div className="mt-4 pt-3 border-t border-line/60 flex flex-wrap items-center gap-2 text-xs">
                    <span className="text-ink-400 font-medium">Recent audits:</span>
                    {recentAudits.slice(0, 5).map((item) => (
                      <span
                        key={item.analysis_id}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-line/40 text-ink-700 border border-line/40"
                      >
                        <button
                          type="button"
                          onClick={() => loadAudit(item.analysis_id)}
                          className="inline-flex items-center gap-1.5 hover:text-ink font-medium cursor-pointer"
                          title={`Reopen audit for ${item.website_url}`}
                        >
                          <span className="truncate max-w-[140px]">{item.domain || item.website_url.replace(/^https?:\/\//, '')}</span>
                          {item.score_overall != null && (
                            <span className="font-mono text-[10px] px-1 py-0.2 rounded bg-ink/5 text-ink-600">
                              {Math.round(item.score_overall)}
                            </span>
                          )}
                        </button>
                        <button
                          type="button"
                          className="text-[10px] text-ink-400 hover:text-bad px-1"
                          title={`Delete audit for ${item.domain}`}
                          onClick={() => setPendingDelete({ id: item.analysis_id, label: item.domain || item.website_url })}
                        >
                          Delete
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <Intro />
            </section>
          )}
        </div>
      )}

      {report && !previewDeck && (
        <Suspense fallback={null}>
          <div className="print-only">
            <AuditPdfReport report={report} />
          </div>
        </Suspense>
      )}

      {previewDeck && report && (
        <Suspense fallback={<LoadingBlock label="Loading report" />}>
        <div className="scrim fixed inset-0 z-50 overflow-y-auto p-3 sm:p-6 flex flex-col items-center print:static print:p-0 print:overflow-visible print:bg-transparent">
          <div className="w-full max-w-[1400px] my-auto print:max-w-none print:w-full print:my-0">
            <Big4AuditReport
              report={report}
              previewMode
              onPrint={() => {
                try {
                  window.print();
                } catch {
                  const id = report.analysis_id || report.report_id;
                  if (id) window.open(`/api/v1/reports/${id}/executive-deck`, '_blank');
                }
              }}
              onClosePreview={() => setPreviewDeck(false)}
            />
          </div>
        </div>
        </Suspense>
      )}

      <div className="no-print">
        <Drawer
          finding={finding}
          patches={report?.code_patches || []}
          websiteUrl={report?.website_url}
          analysisId={report?.analysis_id}
          onClose={() => setFinding(null)}
          onOpenConnectors={(connectorTab) => {
            if (connectorTab) setConnectorsInitialTab(connectorTab);
            setConnectorsOpen(true);
          }}
        />
        <PricingModal
          isOpen={plansOpen}
          onClose={() => setPlansOpen(false)}
          targetUrl={url}
          defaultPlanId={planId}
          onUnlocked={(id, code, pages) => {
            setPlanId(id);
            setVoucher(code);
            setMaxPages(pages);
            start(url);
          }}
        />
        <ConnectorsModal
          isOpen={connectorsOpen}
          onClose={() => {
            setConnectorsOpen(false);
            setConnectorNotice(null);
          }}
          targetUrl={url || run?.website_url || 'https://example.com'}
          initialTab={connectorsInitialTab}
          notice={connectorNotice}
        />
        <ExternalAuthorityPanel
          isOpen={externalOpen}
          onClose={() => {
            setExternalOpen(false);
            setExternalNotice(null);
          }}
          domain={url || run?.website_url || ''}
          notice={externalNotice}
        />
        <RemediationFlowModal
          isOpen={remediationOpen}
          onClose={() => setRemediationOpen(false)}
          analysisId={run?.analysis_id || 'latest'}
          websiteUrl={run?.website_url || url || 'https://example.com'}
        />
        <AgencyWorkspaceModal
          isOpen={agencyOpen}
          onClose={() => setAgencyOpen(false)}
          onSelectClientDomain={(clientDomain) => {
            setUrl(clientDomain);
            start(clientDomain);
          }}
        />
        <ScoringRubricModal isOpen={rubricOpen} onClose={() => setRubricOpen(false)} />
        <ConfirmDialog
          open={Boolean(pendingDelete)}
          title="Delete this audit?"
          description={pendingDelete ? `Delete the audit for ${pendingDelete.label}. This cannot be undone.` : ''}
          confirmLabel="Delete audit"
          busy={deleting}
          onConfirm={confirmDelete}
          onClose={() => setPendingDelete(null)}
        />
      </div>
    </AppShell>
  );
}

export default App;
