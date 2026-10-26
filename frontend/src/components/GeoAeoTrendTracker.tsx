import React, { useState, useEffect } from 'react';

interface GeoSnapshotSummary {
  snapshot_id: string;
  domain: string;
  brand_name: string;
  industry: string;
  timestamp: string;
  overall_score: number;
  delta_score?: number | null;
  total_queries: number;
  engines_measured_count: number;
  engine_scores: Record<string, number>;
  critical_blindspots: string[];
}

interface GeoQueryRecord {
  query_id: string;
  buyer_query: string;
  commercial_intent: string;
  engine_id: string;
  engine_name: string;
  raw_response_text: string;
  was_mentioned: boolean;
  mention_position?: number | null;
  was_cited: boolean;
  cited_urls: string[];
  competitor_cited_instead?: string | null;
  extractability_health: string;
  delta_vs_previous?: string | null;
}

interface GeoSnapshotDetail extends GeoSnapshotSummary {
  query_results: GeoQueryRecord[];
}

interface GeoTrendData {
  domain: string;
  current_score?: number | null;
  latest_delta?: number | null;
  total_snapshots: number;
  history: GeoSnapshotSummary[];
  engine_trends: Record<string, Array<{ timestamp: string; score: number }>>;
  first_tracked?: string | null;
  last_tracked?: string | null;
  canonical_prompts: Array<{ query_id: string; intent: string; template: string }>;
}

interface GeoAeoTrendTrackerProps {
  domain: string;
  brandName?: string;
  industry?: string;
}

export function GeoAeoTrendTracker({ domain, brandName, industry }: GeoAeoTrendTrackerProps) {
  const [data, setData] = useState<GeoTrendData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<GeoSnapshotDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [inspectingQuery, setInspectingQuery] = useState<GeoQueryRecord | null>(null);

  const cleanDomain = domain.replace('https://', '').replace('http://', '').split('/')[0];

  const fetchTrends = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/geo-pipeline/trends?domain=${encodeURIComponent(cleanDomain)}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to load GEO/AEO trends.`);
      }
      const trendData: GeoTrendData = await res.json();
      setData(trendData);
      if (trendData.history && trendData.history.length > 0) {
        const latest = trendData.history[trendData.history.length - 1];
        setSelectedSnapshotId(latest.snapshot_id);
      }
    } catch (err: any) {
      console.error('Failed to fetch GEO trends:', err);
      setError(err?.message || 'Could not load pipeline trends.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrends();
  }, [cleanDomain]);

  useEffect(() => {
    if (!selectedSnapshotId) {
      setSelectedDetail(null);
      return;
    }
    setLoadingDetail(true);
    fetch(`/api/v1/geo-pipeline/snapshots/${selectedSnapshotId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load snapshot details');
        return res.json();
      })
      .then((detail: GeoSnapshotDetail) => {
        setSelectedDetail(detail);
      })
      .catch((err) => {
        console.error('Detail fetch error:', err);
      })
      .finally(() => {
        setLoadingDetail(false);
      });
  }, [selectedSnapshotId]);

  const handleRunLivePipeline = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/geo-pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: cleanDomain,
          brand_name: brandName,
          industry: industry,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Pipeline execution failed: HTTP ${res.status}`);
      }
      await fetchTrends();
    } catch (err: any) {
      setError(err?.message || 'Failed to trigger live GEO pipeline.');
    } finally {
      setRunning(false);
    }
  };

  const formatDate = (isoStr?: string | null) => {
    if (!isoStr) return 'N/A';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  if (loading) {
    return (
      <div className="sheet border border-line rounded-xl p-8 text-center space-y-3">
        <div className="inline-block animate-spin text-2xl">⏳</div>
        <p className="text-xs font-mono text-ink-500">Loading GEO/AEO longitudinal citation history...</p>
      </div>
    );
  }

  const hasHistory = data && data.history && data.history.length > 0;
  const latestSnapshot = hasHistory ? data.history[data.history.length - 1] : null;

  return (
    <div className="space-y-6">
      {/* Header & Live Action Banner */}
      <div className="sheet border border-line rounded-xl p-6 sm:p-8 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">📈</span>
              <span className="label text-ink-700 text-xs">Longitudinal AI Answer Engine Pipeline</span>
            </div>
            <h3 className="font-sans text-2xl sm:text-3xl text-ink mt-1 font-normal">
              GEO / AEO Citation Trend & Historical Trajectory
            </h3>
            <p className="text-xs text-ink-500 mt-1 max-w-2xl">
              Fires the fixed 6-prompt commercial query set across OpenAI, Anthropic, Perplexity, and Gemini. Tracks raw model outputs, citation graphs, and longitudinal visibility trends over time.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRunLivePipeline}
              disabled={running}
              className="px-4 py-2 bg-ink text-paper rounded-md text-xs font-medium hover:bg-ink/90 transition-colors flex items-center gap-2 shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {running ? (
                <>
                  <span className="animate-spin">⏳</span>
                  <span>Executing Live LLM Queries...</span>
                </>
              ) : (
                <>
                  <span></span>
                  <span>Run Live Pipeline Snapshot Now</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-bad/10 dark:bg-bad/10 border border-bad/30 text-xs text-bad rounded">
            <strong>Pipeline Error:</strong> {error}
          </div>
        )}

        {/* High-Level KPI Summary Cards */}
        {hasHistory && latestSnapshot && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
            <div className="bg-paper-50 dark:bg-ink-900/40 border border-line p-3.5 rounded-lg space-y-1">
              <span className="label text-[10px] block">Current AI Citation Score</span>
              <div className="flex items-baseline gap-2">
                <span className="font-sans text-3xl font-bold text-good">
                  {latestSnapshot.overall_score}
                </span>
                <span className="text-xs font-mono text-ink-500">/ 100</span>
                {latestSnapshot.delta_score !== null && latestSnapshot.delta_score !== undefined && (
                  <span
                    className={`text-[11px] font-mono font-bold px-1.5 py-0.5 rounded ${
                      latestSnapshot.delta_score > 0
                        ? 'bg-good/15 text-good'
                        : latestSnapshot.delta_score < 0
                        ? 'bg-bad/15 text-bad'
                        : 'bg-paper-100 text-ink-600'
                    }`}
                  >
                    {latestSnapshot.delta_score > 0 ? `+${latestSnapshot.delta_score}` : latestSnapshot.delta_score} pts
                  </span>
                )}
              </div>
            </div>

            <div className="bg-paper-50 dark:bg-ink-900/40 border border-line p-3.5 rounded-lg space-y-1">
              <span className="label text-[10px] block">Snapshots Logged</span>
              <span className="font-sans text-3xl font-bold text-ink">
                {data.total_snapshots}
              </span>
              <span className="text-[10px] text-ink-500 block">Time-series checkpoints</span>
            </div>

            <div className="bg-paper-50 dark:bg-ink-900/40 border border-line p-3.5 rounded-lg space-y-1">
              <span className="label text-[10px] block">First Tracked</span>
              <span className="font-mono text-sm font-semibold text-ink block pt-1">
                {formatDate(data.first_tracked)}
              </span>
              <span className="text-[10px] text-ink-500 block">Baseline established</span>
            </div>

            <div className="bg-paper-50 dark:bg-ink-900/40 border border-line p-3.5 rounded-lg space-y-1">
              <span className="label text-[10px] block">Last Pipeline Run</span>
              <span className="font-mono text-sm font-semibold text-ink-700 block pt-1">
                {formatDate(data.last_tracked)}
              </span>
              <span className="text-[10px] text-ink-500 block">Live model verified</span>
            </div>
          </div>
        )}
      </div>

      {/* Empty State when no history exists */}
      {!hasHistory && (
        <div className="sheet border border-dashed border-line rounded-xl p-10 text-center space-y-4">
          <div className="text-4xl">📡</div>
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="font-sans text-xl text-ink font-semibold">No Historical Snapshots Logged Yet</h4>
            <p className="text-xs text-ink-500">
              The autonomous GEO/AEO pipeline fires fixed commercial inquiries at OpenAI, Anthropic, and Perplexity, recording raw text and calculating score deltas across recurring runs.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRunLivePipeline}
            disabled={running}
            className="px-4 py-2.5 bg-pine text-white text-xs font-semibold rounded-md hover:bg-pine/90 transition-colors shadow-sm cursor-pointer disabled:opacity-50 inline-flex items-center gap-2"
          >
            {running ? (
              <>
                <span className="animate-spin">⏳</span>
                <span>Firing Live Answer Engines...</span>
              </>
            ) : (
              <>
                <span>🚀</span>
                <span>Run Initial Baseline Snapshot for {cleanDomain}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Historical visibility score chart: only persisted snapshots are plotted. */}
      {hasHistory && (
        <div className="sheet border border-line rounded-xl p-5 space-y-4">
          <div>
            <h4 className="font-sans text-lg text-ink font-semibold">Historical visibility score</h4>
            <p className="text-xs text-ink-500">Each bar is a persisted live pipeline snapshot. This is not the content-readiness or technical AEO score.</p>
          </div>
          <div className="space-y-3" role="img" aria-label="Historical live answer-engine visibility score by snapshot">
            {data.history.map((snap, idx) => {
              const value = Number.isFinite(snap.overall_score) ? Math.max(0, Math.min(100, snap.overall_score)) : null;
              return (
                <div key={snap.snapshot_id} className="grid grid-cols-[88px_minmax(0,1fr)_44px] gap-3 items-center">
                  <span className="text-[10px] font-mono text-ink-500">{formatDate(snap.timestamp)}</span>
                  <div className="h-3 rounded bg-paper-200 dark:bg-ink-800 overflow-hidden">
                    {value !== null && <div className="h-full rounded bg-pine" style={{ width: `${value}%` }} />}
                  </div>
                  <span className="text-xs font-mono font-semibold text-ink text-right">{value === null ? '—' : value}</span>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[10px] text-ink-500 font-mono"><span>0</span><span>50</span><span>100</span></div>
        </div>
      )}

      {/* TIMELINE & HISTORICAL TRAJECTORY */}
      {hasHistory && (
        <div className="sheet border border-line rounded-xl p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div>
              <h4 className="font-sans text-lg text-ink font-semibold">Longitudinal Citation Trajectory</h4>
              <p className="text-xs text-ink-500">Click any checkpoint to inspect its full raw response ledger and query citations.</p>
            </div>
            <span className="text-xs font-mono text-ink-500">
              {data.history.length} snapshot{data.history.length === 1 ? '' : 's'}
            </span>
          </div>

          {/* Chronological Step Track */}
          <div className="flex items-center gap-3 overflow-x-auto pb-3 pt-1">
            {data.history.map((snap, idx) => {
              const isSelected = selectedSnapshotId === snap.snapshot_id;
              return (
                <button
                  key={snap.snapshot_id}
                  type="button"
                  onClick={() => setSelectedSnapshotId(snap.snapshot_id)}
                  className={`shrink-0 p-3 rounded-lg border text-left transition-all cursor-pointer min-w-[150px] ${
                    isSelected
                      ? 'border-ink bg-paper-100 dark:bg-ink-800 shadow-xs'
                      : 'border-line bg-paper-50 dark:bg-ink-900/30 hover:border-ink-400'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="text-[10px] font-mono text-ink-500">Run #{idx + 1}</span>
                    {snap.delta_score !== null && snap.delta_score !== undefined && (
                      <span
                        className={`text-[9px] font-mono font-bold px-1 rounded ${
                          snap.delta_score > 0
                            ? 'bg-good/15 text-good'
                            : snap.delta_score < 0
                            ? 'bg-bad/15 text-bad'
                            : 'bg-paper-200 text-ink-600'
                        }`}
                      >
                        {snap.delta_score > 0 ? `+${snap.delta_score}` : snap.delta_score}
                      </span>
                    )}
                  </div>
                  <div className="font-sans text-2xl font-bold text-ink">{snap.overall_score}%</div>
                  <div className="text-[10px] font-mono text-ink-500 truncate mt-0.5">
                    {formatDate(snap.timestamp)}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Engine Breakdown for Selected Snapshot */}
          {selectedDetail && (
            <div className="space-y-4 pt-4 border-t border-line">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs font-mono font-bold text-ink uppercase tracking-[0.04em]">
                  Active Engine Scores · Snapshot {selectedDetail.snapshot_id} ({formatDate(selectedDetail.timestamp)})
                </span>
                <span className="text-xs text-ink-500">
                  {selectedDetail.engines_measured_count} engines measured live
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(selectedDetail.engine_scores).map(([engName, score]) => (
                  <div key={engName} className="bg-paper-50 dark:bg-ink-950 p-3 rounded-lg border border-line space-y-1">
                    <span className="text-xs font-semibold text-ink block truncate">{engName}</span>
                    <div className="flex items-baseline justify-between">
                      <span className="font-sans text-2xl font-bold text-ink">{Math.round(score)}%</span>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${
                          score >= 70 ? 'bg-good/15 text-good' : score >= 40 ? 'bg-warn/10 text-warn' : 'bg-bad/15 text-bad'
                        }`}
                      >
                        {score >= 70 ? 'STRONG' : score >= 40 ? 'MODERATE' : 'AT RISK'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Query Results Matrix */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <h5 className="font-sans text-base text-ink font-semibold">Fixed Commercial Inquiry Ledger</h5>
                  <span className="text-[11px] font-mono text-ink-500">
                    {selectedDetail.query_results.length} query records
                  </span>
                </div>

                <div className="border border-line rounded-lg divide-y divide-line overflow-hidden">
                  {selectedDetail.query_results.map((qr, idx) => (
                    <div
                      key={idx}
                      className="p-4 bg-paper-50/50 dark:bg-ink-900/20 hover:bg-paper-100/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 bg-paper-200 dark:bg-ink-800 rounded">
                            {qr.query_id}
                          </span>
                          <span className="text-xs font-semibold text-ink-700">{qr.commercial_intent}</span>
                          <span className="text-xs text-ink-500">· {qr.engine_name}</span>
                          {qr.delta_vs_previous && (
                            <span
                              className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded ${
                                qr.delta_vs_previous.includes('+')
                                  ? 'bg-good/20 text-good'
                                  : qr.delta_vs_previous.includes('-')
                                  ? 'bg-bad/20 text-bad'
                                  : 'bg-paper-200 text-ink-600'
                              }`}
                            >
                              {qr.delta_vs_previous}
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-medium text-ink truncate max-w-xl">"{qr.buyer_query}"</p>
                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-500 pt-0.5 font-mono">
                          <span>
                            Mentioned:{' '}
                            <strong className={qr.was_mentioned ? 'text-good' : 'text-bad'}>
                              {qr.was_mentioned ? 'YES' : 'NO'}
                            </strong>
                            {qr.mention_position ? ` (Rank #${qr.mention_position})` : ''}
                          </span>
                          <span>
                            Cited:{' '}
                            <strong className={qr.was_cited ? 'text-good' : 'text-bad'}>
                              {qr.was_cited ? 'YES' : 'NO'}
                            </strong>
                          </span>
                          {qr.competitor_cited_instead && (
                            <span className="text-warn dark:text-warn">
                              Competitor: <strong>{qr.competitor_cited_instead}</strong>
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="shrink-0">
                        <button
                          type="button"
                          onClick={() => setInspectingQuery(qr)}
                          className="px-3 py-1.5 bg-paper-50 dark:bg-ink-800 border border-line rounded text-xs font-medium text-ink hover:bg-paper-100 transition-colors shadow-2xs cursor-pointer flex items-center gap-1.5"
                        >
                          <span>🔍</span>
                          <span>Inspect Raw LLM Output</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* RAW LLM RESPONSE INSPECTOR MODAL */}
      {inspectingQuery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/60 backdrop-blur-xs">
          <div className="sheet border border-line rounded-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="p-4 sm:p-5 border-b border-line flex items-center justify-between">
              <div>
                <span className="label text-[10px] text-ink-700">{inspectingQuery.engine_name} · RAW LLM RESPONSE</span>
                <h4 className="font-sans text-lg text-ink font-semibold mt-0.5">{inspectingQuery.commercial_intent}</h4>
              </div>
              <button
                type="button"
                onClick={() => setInspectingQuery(null)}
                className="p-1.5 hover:bg-paper-100 rounded text-ink-500 hover:text-ink cursor-pointer text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-4 sm:p-5 overflow-y-auto space-y-4 text-xs">
              <div className="space-y-1">
                <span className="label text-[10px] block">Prompt Dispatched</span>
                <div className="p-2.5 bg-paper-100 dark:bg-ink-950 font-mono text-ink-700 rounded border border-line">
                  {inspectingQuery.buyer_query}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 font-mono text-[11px]">
                <div className="p-2.5 bg-paper-50 dark:bg-ink-900/40 rounded border border-line">
                  <span className="text-ink-500 block text-[9px] uppercase">Brand Mention</span>
                  <span className={`font-bold ${inspectingQuery.was_mentioned ? 'text-good' : 'text-bad'}`}>
                    {inspectingQuery.was_mentioned ? 'DETECTED' : 'MISSING'}
                  </span>
                  {inspectingQuery.mention_position && (
                    <span className="text-ink-600 block mt-0.5">Rank #{inspectingQuery.mention_position}</span>
                  )}
                </div>

                <div className="p-2.5 bg-paper-50 dark:bg-ink-900/40 rounded border border-line">
                  <span className="text-ink-500 block text-[9px] uppercase">Direct Citation Link</span>
                  <span className={`font-bold ${inspectingQuery.was_cited ? 'text-good' : 'text-bad'}`}>
                    {inspectingQuery.was_cited ? 'VERIFIED LINK' : 'NO CITATION'}
                  </span>
                  {inspectingQuery.cited_urls.length > 0 && (
                    <span className="text-ink-600 block mt-0.5">{inspectingQuery.cited_urls.length} link(s) matched</span>
                  )}
                </div>
              </div>

              {inspectingQuery.cited_urls.length > 0 && (
                <div className="space-y-1">
                  <span className="label text-[10px] block">Extracted Citation URLs</span>
                  <ul className="space-y-1 font-mono text-[11px] text-ink-700 break-all">
                    {inspectingQuery.cited_urls.map((url, i) => (
                      <li key={i} className="p-1.5 bg-paper-50 dark:bg-ink-950 rounded border border-line">
                        🔗 {url}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-1">
                <span className="label text-[10px] block">Verbatim Model Response</span>
                <div className="p-3 bg-paper-100 dark:bg-ink-950 text-ink leading-relaxed rounded border border-line whitespace-pre-wrap font-sans text-xs">
                  {inspectingQuery.raw_response_text}
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-line flex justify-end">
              <button
                type="button"
                onClick={() => setInspectingQuery(null)}
                className="px-4 py-2 bg-ink text-paper rounded text-xs font-medium hover:bg-ink/90 transition-colors cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
