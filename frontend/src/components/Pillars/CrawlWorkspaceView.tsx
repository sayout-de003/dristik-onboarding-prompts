import React, { useState } from 'react';
import { ExecutiveReport } from '../../types';
import { getSectionPdfUrl, getSectionPptxUrl } from '../../services/api';
import { Globe, FileText, Download, CheckCircle, AlertTriangle, XCircle, ArrowUpRight, Search, ShieldCheck } from 'lucide-react';

interface CrawlWorkspaceViewProps {
  report: ExecutiveReport;
  analysisId?: string;
}

export function CrawlWorkspaceView({ report, analysisId }: CrawlWorkspaceViewProps) {
  const [search, setSearch] = useState('');
  const manifest = report.crawl_manifest;
  const pages: any[] = (manifest?.pages && manifest.pages.length > 0) ? manifest.pages : (report.page_reports || []);
  const pagesKnown = Array.isArray(manifest?.pages) || Array.isArray(report.page_reports);
  const health = (manifest?.crawl_health || {}) as Record<string, any>;

  const id = analysisId || report.analysis_id || report.report_id;
  const pdfUrl = id ? getSectionPdfUrl(id, 'crawl') : '#';
  const pptxUrl = id ? getSectionPptxUrl(id, 'crawl') : '#';

  const filteredPages = pages.filter((p: any) =>
    (p.url || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.title || '').toLowerCase().includes(search.toLowerCase())
  );

  const avgTtfb = typeof health.avg_ttfb_ms === 'number' ? Math.round(health.avg_ttfb_ms) : null;
  const llmsTxtFound = typeof (manifest as any)?.llms_txt_found === 'boolean' ? Boolean((manifest as any).llms_txt_found) : null;

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="bg-paper-100  border border-line rounded-xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono font-bold tracking-wider uppercase text-pine">
              <Globe className="w-4 h-4" />
              Website crawl
            </div>
            <h2 className="text-2xl font-bold text-ink  mt-1">
              Crawl coverage and technical checks
            </h2>
            <p className="text-sm text-ink-500 mt-1 max-w-2xl">
              Review which pages were fetched and what the server returned. Check response status, load timing, crawl directives, sitemap discovery and canonical URLs where the audit collected them.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-paper-50 text-pine border border-line hover:bg-paper-100 transition-colors shadow-xs"
            >
              <FileText className="w-4 h-4" />
              Export crawl report
            </a>
            <a
              href={pptxUrl}
              download
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-pine hover:bg-pine-700 text-white shadow-xs transition-colors"
            >
              <Download className="w-4 h-4" />
              Export crawl slides
            </a>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-6 pt-6 border-t border-line">
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">Pages checked</div>
            <div className="text-xl font-bold text-ink mt-0.5">{pagesKnown ? pages.length : '—'}</div>
          </div>
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">Avg TTFB</div>
            <div className="text-xl font-bold text-ink mt-0.5">
              {avgTtfb ? `${avgTtfb}ms` : '—'}
            </div>
          </div>
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">Robots.txt</div>
            <div className="text-sm font-bold text-good mt-1 flex items-center gap-1">
              {manifest?.robots_txt_found ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5 text-bad" />}
              {manifest?.robots_txt_found === true ? 'Found' : manifest?.robots_txt_found === false ? 'Missing' : 'Not checked'}
            </div>
          </div>
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">XML Sitemap</div>
            <div className="text-sm font-bold text-good mt-1 flex items-center gap-1">
              {manifest?.sitemap_found ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5 text-rose-500" />}
              {manifest?.sitemap_found === true ? 'Found' : manifest?.sitemap_found === false ? 'Missing' : 'Not checked'}
            </div>
          </div>
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">/llms.txt</div>
            <div className="text-sm font-bold text-pine mt-1 flex items-center gap-1">
              {llmsTxtFound ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5 text-warn" />}
              {llmsTxtFound === true ? 'Found' : llmsTxtFound === false ? 'Missing' : 'Not checked'}
            </div>
          </div>
          <div className="p-3 bg-paper-50 rounded-lg border border-line">
            <div className="text-[11px] font-mono text-ink-500 uppercase">Protocol</div>
            <div className="text-sm font-bold text-ink  mt-1 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              {report.website_url.startsWith('https') ? 'HTTPS / TLS' : 'HTTP'}
            </div>
          </div>
        </div>
      </div>

      {/* Pages Table */}
      <div className="bg-paper-100  border border-line rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-line flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="font-semibold text-ink  text-sm">
            Discovered Crawl Inventory ({filteredPages.length})
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-ink-500  absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search crawled URLs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-paper-50 /80 border border-line rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 text-ink "
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-paper-50  border-b border-line text-ink-500 uppercase font-mono text-[11px]">
              <tr>
                <th className="py-2.5 px-4">URL</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Depth</th>
                <th className="py-2.5 px-4">Title Tag</th>
                <th className="py-2.5 px-4">H1 Heading</th>
                <th className="py-2.5 px-3">Words</th>
                <th className="py-2.5 px-3">Canonical</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {filteredPages.map((p: any, idx: number) => {
                const statusCode = p.status_code || 200;
                const statusOk = statusCode < 400;
                const h1Val = Array.isArray(p.h1) ? p.h1[0] : (typeof p.h1 === 'string' ? p.h1 : '—');
                return (
                  <tr key={idx} className="hover:bg-paper-50  transition-colors">
                    <td className="py-2.5 px-4 font-mono font-medium text-ink  max-w-xs truncate">
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-pine inline-flex items-center gap-1"
                      >
                        {(p.url || '').replace(/^https?:\/\/[^/]+/, '') || '/'}
                        <ArrowUpRight className="w-3 h-3 opacity-60" />
                      </a>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                        statusOk ? 'bg-good/10 text-good' : 'bg-bad/10 text-bad'
                      }`}>
                        {statusCode}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-ink-500 ">
                      {p.click_depth ?? 1}
                    </td>
                    <td className="py-2.5 px-4 text-ink-500  max-w-xs truncate" title={p.title}>
                      {p.title || '—'}
                    </td>
                    <td className="py-2.5 px-4 text-ink-500  max-w-xs truncate" title={h1Val}>
                      {h1Val || '—'}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-ink ">
                      {p.word_count || '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      {p.canonical_url ? (
                        <span className="text-good font-mono text-[10px]">OK</span>
                      ) : (
                        <span className="text-amber-500 font-mono text-[10px]">None</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
