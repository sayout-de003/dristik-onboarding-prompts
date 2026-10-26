import React, { useState, useEffect } from 'react';
import { X, ShieldAlert, Sparkles, Building2, UserCheck, Trash2, ArrowUpRight } from 'lucide-react';

interface CompetitorProfile {
  competitor_id: string;
  domain: string;
  brand_name: string;
  market_overlap: string;
  discovered_reason: string;
  overall_score?: number | null;
  winning_queries: string[];
  vulnerabilities: string[];
  discovery_confidence?: number;
  score_basis?: string;
  product_overlap_reason?: string;
  market_size?: string | null;
  scale_score?: number | null;
  scale_tier?: string | null;
  competitor_class?: string;
  source?: string;
  similarity_score?: number | null;
  similarity_breakdown?: Record<string, number>;
  is_rejected?: boolean;
}

interface BenchmarkTableRow {
  dimension: string;
  dimension_key: string;
  target_score?: number | null;
  competitor_1?: number | null;
  competitor_2?: number | null;
  competitor_3?: number | null;
  gap_verdict: string;
}

interface CompetitorBenchmarkMatrix {
  target_domain: string;
  target_brand: string;
  market_niche: string;
  target_scale_score?: number | null;
  target_scale_tier?: string | null;
  target_motto?: string | null;
  target_buyer_persona?: string | null;
  status?: string;
  message?: string;
  competitors: CompetitorProfile[];
  aspirational_competitors?: CompetitorProfile[];
  rejected_domains?: string[];
  comparative_table: BenchmarkTableRow[];
  primary_competitive_gap: string;
  recommended_offensive_plays: string[];
  discovery_method?: string;
  market_size_status?: string;
  market_size_note?: string;
  score_basis?: string;
}

interface CompetitorDiscoveryViewProps {
  websiteUrl: string;
  analysisId?: string;
}

export function CompetitorDiscoveryView({ websiteUrl, analysisId }: CompetitorDiscoveryViewProps) {
  const [matrix, setMatrix] = useState<CompetitorBenchmarkMatrix | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customCompetitorUrl, setCustomCompetitorUrl] = useState('');
  const [activeCompetitorUrls, setActiveCompetitorUrls] = useState<string[]>([]);
  const [rejectingDomain, setRejectingDomain] = useState<string | null>(null);

  const loadCompetitors = async (overrideUrls?: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();
      if (websiteUrl) queryParams.set('website_url', websiteUrl);
      if (analysisId) queryParams.set('analysis_id', analysisId);

      const urlsToUse = overrideUrls !== undefined ? overrideUrls : activeCompetitorUrls;
      urlsToUse.forEach((u) => {
        queryParams.append('competitor_urls', u);
      });

      const res = await fetch(`/api/v1/intelligence/competitors?${queryParams.toString()}`);
      const raw = await res.text();
      if (!res.ok) {
        setMatrix(null);
        setError(`Competitor API returned HTTP ${res.status}. ${raw.slice(0, 240) || 'Empty body.'}`);
        return;
      }
      const data = raw ? JSON.parse(raw) : null;
      if (!data) {
        setMatrix(null);
        setError('Competitor API returned an empty body. Restart the backend and retry.');
        return;
      }
      setMatrix(data);
    } catch (err) {
      setMatrix(null);
      setError(`Could not load competitors: ${err instanceof Error ? err.message : String(err)}.`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompetitors();
  }, [websiteUrl, analysisId]);

  const handleAddCustomCompetitor = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customCompetitorUrl.trim();
    if (!trimmed) return;
    const cleanDomain = trimmed.replace(/^https?:\/\//i, '').split('/')[0].toLowerCase();
    if (activeCompetitorUrls.includes(cleanDomain)) return;
    const updated = [...activeCompetitorUrls, cleanDomain].slice(0, 3);
    setActiveCompetitorUrls(updated);
    setCustomCompetitorUrl('');
    loadCompetitors(updated);
  };

  const handleRemoveCustomCompetitor = (domainToRemove: string) => {
    const updated = activeCompetitorUrls.filter((d) => d !== domainToRemove);
    setActiveCompetitorUrls(updated);
    loadCompetitors(updated);
  };

  const handleResetToAutomated = () => {
    setActiveCompetitorUrls([]);
    loadCompetitors([]);
  };

  const handleRejectCompetitor = async (rejectedDomain: string) => {
    setRejectingDomain(rejectedDomain);
    try {
      await fetch('/api/v1/intelligence/competitors/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_domain: matrix?.target_domain || websiteUrl,
          rejected_domain: rejectedDomain,
        }),
      });
      // Filter out of current state immediately, then reload
      if (matrix) {
        setMatrix({
          ...matrix,
          competitors: matrix.competitors.filter((c) => c.domain !== rejectedDomain),
          aspirational_competitors: (matrix.aspirational_competitors || []).filter((c) => c.domain !== rejectedDomain),
        });
      }
      await loadCompetitors();
    } catch (e) {
      console.error('Failed to record competitor rejection:', e);
    } finally {
      setRejectingDomain(null);
    }
  };

  if (loading && !matrix) {
    return (
      <div className="p-8 sheet border border-line rounded-lg flex items-center justify-center gap-3 text-ink-500">
        <div className="w-5 h-5 border-2 border-line border-t-transparent rounded-full animate-spin"></div>
        <span>Evaluating scale parity, business specialization & peer competitors...</span>
      </div>
    );
  }

  if (error && !matrix) {
    return (
      <div className="p-6 sheet border border-bad/40 rounded-lg space-y-3">
        <span className="label text-bad">Competitor discovery failed</span>
        <p className="text-sm text-ink-700">{error}</p>
        <p className="text-xs text-ink-600">
          Enter a rival domain manually in the box below or retry automated discovery.
        </p>
        <button
          type="button"
          onClick={() => loadCompetitors()}
          className="px-3 py-1.5 text-xs bg-pine text-white rounded-md"
        >
          Retry discovery
        </button>
      </div>
    );
  }

  if (!matrix) return null;

  const targetScaleTier = matrix.target_scale_tier || 'Not assessed';
  const targetScaleScore = matrix.target_scale_score ?? null;

  return (
    <div className="space-y-6">
      {/* Target Business Profile & Scale Understanding */}
      <div className="sheet border border-line rounded-lg p-5 bg-paper-50/50">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="label text-ink-700 flex items-center gap-1 font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                Audited Business Identity & Scale Parity
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-paper-200 text-ink-700 border border-line font-bold uppercase">
                {targetScaleTier}{targetScaleScore == null ? '' : ` · ${targetScaleScore}/1.0`}
              </span>
            </div>
            <h3 className="font-sans text-xl md:text-2xl text-ink font-normal">
              {matrix.target_brand} · <span className="text-ink-600 font-sans text-base">{matrix.market_niche}</span>
            </h3>
            {matrix.target_motto && (
              <p className="text-xs text-ink-600 italic">
                "{matrix.target_motto}"
              </p>
            )}
            {matrix.target_buyer_persona && (
              <div className="flex items-center gap-1.5 text-[11px] text-ink-500 pt-0.5">
                <UserCheck className="w-3 h-3 text-ink-700" />
                <span>Target Buyer: <strong>{matrix.target_buyer_persona}</strong></span>
              </div>
            )}
          </div>

          <div className="bg-paper-50 border border-line rounded-md p-3.5 text-xs text-ink-700 max-w-md shadow-2xs">
            <span className="label text-[10px] block mb-0.5 text-warn font-semibold">Market Scale Gap & Finding:</span>
            <p className="text-xs text-ink leading-relaxed font-medium">{matrix.primary_competitive_gap}</p>
          </div>
        </div>

        {/* Inline Custom Competitor Input (Preserved & Prominent) */}
        <div className="mt-5 pt-4 border-t border-line flex flex-col sm:flex-row items-center justify-between gap-3">
          <form onSubmit={handleAddCustomCompetitor} className="flex items-center gap-2 w-full sm:w-auto flex-1 max-w-lg">
            <input
              type="text"
              placeholder="Add competitor domain (e.g. thoughtbot.com, rivalstudio.com)..."
              value={customCompetitorUrl}
              onChange={(e) => setCustomCompetitorUrl(e.target.value)}
              className="px-3 py-1.5 text-xs bg-paper-50 border border-line rounded-md text-ink w-full focus:outline-none focus:border-pine font-mono"
            />
            <button
              type="submit"
              disabled={!customCompetitorUrl.trim()}
              className="px-3 py-1.5 text-xs bg-pine text-white rounded-md hover:bg-pine/90 disabled:opacity-50 transition-colors whitespace-nowrap font-medium flex items-center gap-1"
            >
              <span>+ Add Competitor</span>
            </button>
          </form>

          {activeCompetitorUrls.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-ink-500">
                {activeCompetitorUrls.length} custom {activeCompetitorUrls.length === 1 ? 'rival' : 'rivals'} active
              </span>
              <button
                onClick={handleResetToAutomated}
                className="text-xs text-bad hover:underline font-medium"
              >
                Clear Custom Links
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Discovered Direct Competitor Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-ink flex items-center gap-1.5">
              <Building2 className="w-4 h-4 text-ink-700" />
              Direct Competitors & Scale-Matched Peers
            </h4>
            <span className="text-xs text-ink-500">
              (Identified against same offering, buyer persona, and commercial scale)
            </span>
          </div>
        </div>

        {matrix.competitors.length === 0 ? (
          <div className="sheet border border-line rounded-lg p-6 text-center text-sm text-ink-600">
            No direct competitors identified for this tier yet. Add rival domains above to compare.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {matrix.competitors.map((comp, idx) => {
              const isUserSpecified = comp.source === 'user_specified';
              return (
                <div
                  key={comp.competitor_id || idx}
                  className="sheet border border-line rounded-lg p-4 space-y-3 relative group hover:border-ink transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-mono font-bold text-ink-500">#{idx + 1}</span>
                        <span className="text-sm font-bold text-ink block">{comp.brand_name}</span>
                      </div>
                      <a
                        href={`https://${comp.domain}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] font-mono text-ink-700 hover:underline flex items-center gap-0.5"
                      >
                        <span>{comp.domain}</span>
                        <ArrowUpRight className="w-2.5 h-2.5 inline" />
                      </a>
                    </div>

                    <div className="flex flex-col items-end gap-1">
                      {isUserSpecified ? (
                        <div className="flex items-center gap-1">
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-paper-200 text-ink-700 border border-line font-bold">
                            USER SPECIFIED
                          </span>
                          <button
                            onClick={() => handleRemoveCustomCompetitor(comp.domain)}
                            title="Remove custom competitor"
                            className="p-1 text-ink-400 hover:text-bad rounded transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-good/10 text-good border border-good/20 font-bold">
                            SCALE MATCH
                          </span>
                          <button
                            onClick={() => handleRejectCompetitor(comp.domain)}
                            disabled={rejectingDomain === comp.domain}
                            title="Reject this competitor (never suggest again)"
                            className="p-1 text-ink-400 hover:text-bad rounded transition-colors"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      )}

                      {comp.scale_score != null && (
                        <span className="text-[10px] font-mono text-ink-500">
                          Scale: {comp.scale_score}/1.0
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-xs text-ink-700 bg-paper-50 p-2.5 rounded border border-line/60">
                    <span className="label text-[10px] block text-ink-500 font-semibold mb-0.5">Match Explanation</span>
                    <p className="text-xs leading-relaxed">{comp.discovered_reason}</p>
                  </div>

                  {(comp.winning_queries?.length > 0 || comp.vulnerabilities?.length > 0) && (
                    <div className="text-xs pt-2 border-t border-line space-y-2">
                      {comp.winning_queries?.length > 0 && (
                        <div>
                          <span className="label text-[10px] text-good block font-semibold">Winning Queries:</span>
                          <ul className="mt-1 space-y-0.5">
                            {comp.winning_queries.map((q, qIdx) => (
                              <li key={qIdx} className="text-[11px] text-ink-700 truncate font-mono">
                                • "{q}"
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Aspirational Market Leaders (Segregated to avoid polluting direct comparisons) */}
      {matrix.aspirational_competitors && matrix.aspirational_competitors.length > 0 && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-warn" />
            <h4 className="text-sm font-semibold text-ink">
              Aspirational Market Leaders & Enterprise Conglomerates
            </h4>
            <span className="text-xs text-ink-500">
              (Same digital sector, but operate 1–2 scale tiers above. Segregated from direct bidding comparisons.)
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {matrix.aspirational_competitors.map((asp, idx) => (
              <div key={idx} className="sheet border border-line rounded-lg p-3.5 space-y-2 bg-paper-50/40">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-ink block">{asp.brand_name}</span>
                    <span className="text-[11px] font-mono text-ink-500">{asp.domain}</span>
                  </div>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-warn/10 text-warn border border-warn/20 font-semibold">
                    ENTERPRISE LEADER
                  </span>
                </div>
                <p className="text-[11px] text-ink-600 leading-relaxed">
                  {asp.discovered_reason}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 7-Vector Comparative Benchmark Table */}
      <div className="sheet border border-line rounded-lg overflow-hidden">
        <div className="p-4 border-b border-line flex items-center justify-between bg-paper-50/50">
          <div>
            <span className="label text-ink font-semibold block">
              7-Vector Commercial Benchmark Matrix
            </span>
            <span className="text-xs text-ink-500">Your column is from this audit when measured. Rival columns are null unless that site was crawled. No copied fallback numbers.</span>
          </div>
          <span className="text-xs font-mono bg-paper-100 dark:bg-ink-900 px-2.5 py-1 rounded border border-line text-ink-700">
            Unmeasured = null
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-paper-50 text-ink-500 border-b border-line label text-[10px]">
                <th className="p-3.5">Dimension</th>
                <th className="p-3.5 text-ink-700 font-bold bg-paper-100">
                  You ({matrix.target_brand})
                </th>
                {matrix.competitors.map((c, i) => (
                  <th key={c.competitor_id || i} className="p-3.5 font-semibold text-ink-700">
                    Comp {i + 1}: {c.brand_name}
                  </th>
                ))}
                <th className="p-3.5">Gap Analysis & Strategic Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line font-mono">
              {matrix.comparative_table.map((row, idx) => {
                const peerScores = [row.competitor_1, row.competitor_2, row.competitor_3];
                return (
                  <tr key={idx} className="hover:bg-paper-200/40 transition-colors">
                    <td className="p-3.5 font-sans font-medium text-ink">{row.dimension}</td>
                    <td className="p-3.5 font-bold text-ink-700 text-sm bg-paper-100">
                      <span className="inline-block min-w-[28px]">{row.target_score != null ? row.target_score : 'null'}</span>
                    </td>
                    {matrix.competitors.map((c, i) => (
                      <td key={c.competitor_id || i} className="p-3.5 text-ink-500 font-semibold">
                        {peerScores[i] != null ? peerScores[i] : 'null'}
                      </td>
                    ))}
                    <td className="p-3.5 font-sans text-ink-600 text-[11px] leading-relaxed max-w-sm">
                      {row.gap_verdict}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recommended Offensive Plays */}
      {matrix.recommended_offensive_plays?.length > 0 && (
        <div className="sheet border border-line rounded-lg p-5 space-y-3 bg-paper-50/30">
          <div className="flex items-center gap-2 label text-ink-700 font-semibold">
            <span>⚔</span>
            <span>Recommended Offensive Plays to Displace Competitors</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {matrix.recommended_offensive_plays.map((play, i) => (
              <div key={i} className="bg-paper-50 border border-line p-3.5 rounded-md text-xs text-ink-700 space-y-1 shadow-2xs">
                <span className="label text-ink-700 block font-mono text-[10px]">Strategic Play #{i + 1}</span>
                <p className="leading-relaxed">{play}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
