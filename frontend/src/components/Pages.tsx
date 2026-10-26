import React, { useState } from 'react';
import { CrawlManifest, PageEvidence, PageReport, CopySection, CopyFaqItem } from '../types';
import { asNumber, asString, display, scoreTone } from '../lib/format';
import { PageGenreAnalytics, detectPageGenre, GENRE_CONFIGS, PageGenre } from './PageGenreAnalytics';

interface PagesProps {
  manifest?: CrawlManifest;
  summary: Record<string, unknown>;
  pageReports?: PageReport[];
  ga4LandingPages?: Array<{
    path: string;
    sessions: number;
    bounce_rate: number;
    engagement_rate?: number;
    avg_duration_sec?: number;
    conversions: number;
    conversion_rate?: number;
  }>;
}

function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Fallback if clipboard API is restricted
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="text-[11px] font-semibold px-2 py-0.5 rounded border border-line bg-paper-50 hover:bg-paper-200 text-ink-700 hover:text-ink transition-colors cursor-pointer shrink-0"
    >
      {copied ? '✓ Copied' : label}
    </button>
  );
}

function Pair({
  label,
  current,
  suggested,
  badge,
}: {
  label: string;
  current?: string | null;
  suggested?: string | null;
  badge?: string;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-3 border-b border-line text-xs">
      <div>
        <p className="label text-[10px] text-ink-500 mb-1">Current {label}</p>
        <p className="text-ink-700 whitespace-pre-wrap">{display(current)}</p>
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <p className="label text-[10px] text-good">Suggested {label}</p>
            {badge && (
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-paper-100 text-ink-500 border border-line">
                {badge}
              </span>
            )}
          </div>
          {suggested && <CopyButton text={suggested} />}
        </div>
        <p className="text-ink-700 whitespace-pre-wrap font-medium">{display(suggested)}</p>
      </div>
    </div>
  );
}

function HeadingList({ label, items }: { label: string; items?: string[] }) {
  if (!items?.length) {
    return (
      <p className="text-sm text-ink-700">
        <span className="text-ink-500">{label} </span>—
      </p>
    );
  }
  return (
    <div className="text-sm text-ink-700">
      <p className="text-ink-500 mb-1">{label}</p>
      <ol className="list-decimal pl-5 space-y-1 font-mono text-xs">
        {items.map((item, index) => (
          <li key={`${label}-${index}`}>{item}</li>
        ))}
      </ol>
    </div>
  );
}

function ScrapedContent({ page }: { page: PageEvidence }) {
  const scraped = (page.body_text || '').trim();
  const chars = scraped.length;
  const words = page.word_count || (scraped ? scraped.split(/\s+/).filter(Boolean).length : 0);

  return (
    <section className="space-y-5">
      <div>
        <p className="label mb-1">Raw Extracted Page Payload</p>
        <p className="text-xs text-ink-500">
          Complete textual DOM elements extracted from this URL ({words} words, {chars} characters)
          {page.render_mode && page.render_mode !== 'static' ? ` · source ${page.render_mode}` : ''}
        </p>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 text-xs text-ink-700">
        <div>
          <dt className="text-ink-500">Raw Title Tag</dt>
          <dd className="whitespace-pre-wrap font-mono mt-0.5">{display(page.title)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Raw Meta Description</dt>
          <dd className="whitespace-pre-wrap font-mono mt-0.5">{display(page.meta_description)}</dd>
        </div>
      </dl>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <HeadingList label="H1 Headings" items={page.h1} />
        <HeadingList label="H2 Headings" items={page.h2} />
        <HeadingList label="H3 Headings" items={page.h3} />
      </div>

      {page.ctas && page.ctas.length > 0 && (
        <div className="text-xs text-ink-700">
          <p className="text-ink-500 mb-1">Extracted CTA Button Microcopy</p>
          <p className="font-mono">{page.ctas.join(' · ')}</p>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="label">Full Body Copy Text</p>
          {scraped && <CopyButton text={scraped} label="Copy Raw Text" />}
        </div>
        {scraped ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-ink-700 border border-line bg-paper-50 p-4 max-h-96 overflow-y-auto rounded">
            {scraped}
          </pre>
        ) : (
          <p className="text-ink-400 text-xs">No body copy was extracted from this page.</p>
        )}
      </div>
    </section>
  );
}

function SectionHighlights({
  sections,
  fullRewrite,
}: {
  sections?: CopySection[];
  fullRewrite?: string;
}) {
  if (!sections || sections.length === 0) return null;

  const statusBadge = (status: string) => {
    switch (status) {
      case 'NEEDS_REWRITE':
        return 'bg-bad/10 text-bad border-bad/30';
      case 'UPDATE_RECOMMENDED':
        return 'bg-warn/10 text-warn border-warn/30';
      case 'OPTIMIZED':
        return 'bg-good/10 text-good border-good/30';
      default:
        return 'bg-paper-200 text-ink-700 border-line';
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'NEEDS_REWRITE':
        return 'Needs Rewrite';
      case 'UPDATE_RECOMMENDED':
        return 'Update Recommended';
      case 'OPTIMIZED':
        return 'Optimized';
      default:
        return status;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-2">
        <div>
          <p className="label text-ink-700">Page Sections — Needs to be Updated</p>
          <p className="text-xs text-ink-500 mt-0.5">
            Production-grade, high-converting copy rewrites optimized for SEO search intent and GEO answer engine citation.
          </p>
        </div>
        {fullRewrite && (
          <CopyButton text={fullRewrite} label="Copy Complete Page Rewrite" />
        )}
      </div>

      <div className="grid grid-cols-1 gap-4">
        {sections.map((sec) => (
          <div
            key={sec.section_id}
            className="sheet border border-line rounded-lg p-4 space-y-3 hover:border-ink-400 transition-colors"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
              <div className="flex items-center gap-2">
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-[0.04em] ${statusBadge(
                    sec.status
                  )}`}
                >
                  {statusLabel(sec.status)}
                </span>
                <h4 className="font-semibold text-sm text-ink">{sec.section_name}</h4>
              </div>
              <CopyButton text={sec.suggested_copy} label="Copy Section" />
            </div>

            {sec.purpose && (
              <p className="text-xs text-ink-500 italic">
                <span className="font-medium text-ink-700">Strategic Purpose: </span>
                {sec.purpose}
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {sec.current_preview && (
                <div className="p-3 bg-paper-50 rounded border border-line space-y-1">
                  <p className="label text-[10px] text-ink-500">Current Observed Copy</p>
                  <p className="text-ink-700 whitespace-pre-wrap leading-relaxed">{sec.current_preview}</p>
                </div>
              )}
              <div className="p-3 bg-good/10 rounded border border-good/30 space-y-1">
                <p className="label text-[10px] text-good">Suggested Production Copy</p>
                <p className="text-ink-700 whitespace-pre-wrap leading-relaxed font-sans font-medium">
                  {sec.suggested_copy}
                </p>
              </div>
            </div>

            {sec.seo_geo_notes && (
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-ink-500">
                <span> {sec.seo_geo_notes}</span>
                {sec.keywords && sec.keywords.length > 0 && (
                  <span className="font-mono text-[10px]">
                    Keywords: {sec.keywords.join(', ')}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SpecialistInsightsBar({ insights }: { insights?: Record<string, string> }) {
  if (!insights || Object.keys(insights).length === 0) return null;
  return (
    <div className="bg-paper-50 border border-line rounded-lg p-4 space-y-2 text-xs">
      <p className="label text-xs">Page content review</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {insights.seo && (
          <div className="p-2.5 bg-paper-50 rounded border border-line space-y-1">
            <span className="label text-[10px] text-ink-700 block">Search relevance</span>
            <p className="text-ink-700 text-[11px] leading-snug">{insights.seo}</p>
          </div>
        )}
        {insights.geo && (
          <div className="p-2.5 bg-paper-50 rounded border border-line space-y-1">
            <span className="label text-[10px] text-ink-700 block">AI search clarity</span>
            <p className="text-ink-700 text-[11px] leading-snug">{insights.geo}</p>
          </div>
        )}
        {insights.cro && (
          <div className="p-2.5 bg-paper-50 rounded border border-line space-y-1">
            <span className="label text-[10px] text-ink-700 block">Conversion clarity</span>
            <p className="text-ink-700 text-[11px] leading-snug">{insights.cro}</p>
          </div>
        )}
        {insights.clarity && (
          <div className="p-2.5 bg-paper-50 rounded border border-line space-y-1">
            <span className="label text-[10px] text-ink-700 block">Brand and messaging</span>
            <p className="text-ink-700 text-[11px] leading-snug">{insights.clarity}</p>
          </div>
        )}
        {insights.sections && (
          <div className="p-2.5 bg-paper-50 rounded border border-line space-y-1">
            <span className="label text-[10px] text-ink-700 block">Content structure</span>
            <p className="text-ink-700 text-[11px] leading-snug">{insights.sections}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function FaqBlock({ faqs }: { faqs?: CopyFaqItem[] }) {
  if (!faqs || faqs.length === 0) return null;
  return (
    <div className="sheet border border-line rounded-lg p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div>
          <p className="label text-ink-700">Generative Engine Optimization (GEO) FAQs</p>
          <p className="text-xs text-ink-500">
            Suggested question-and-answer content. This format may help answer discovery, but does not guarantee citations by any search or AI platform.
          </p>
        </div>
        <CopyButton
          text={faqs.map((f) => `Q: ${f.question}\nA: ${f.answer}`).join('\n\n')}
          label="Copy All FAQs"
        />
      </div>
      <div className="space-y-3">
        {faqs.map((faq, i) => (
          <div key={i} className="p-3 bg-paper-50 rounded border border-line text-xs space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <p className="font-bold text-ink">Q: {faq.question}</p>
              <CopyButton text={`Q: ${faq.question}\nA: ${faq.answer}`} label="Copy" />
            </div>
            <p className="text-ink-700 leading-relaxed">A: {faq.answer}</p>
            {faq.target_engine && (
              <p className="text-[10px] text-ink-700 font-mono pt-0.5">Engine Target: {faq.target_engine}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PageDetail({
  page,
  report,
  ga4LandingPages,
}: {
  page: PageEvidence;
  report?: PageReport;
  ga4LandingPages?: Array<{
    path: string;
    sessions: number;
    bounce_rate: number;
    engagement_rate?: number;
    avg_duration_sec?: number;
    conversions: number;
    conversion_rate?: number;
  }>;
}) {
  const [showTechnical, setShowTechnical] = useState(false);
  const seo = report?.seo;
  const copy = report?.copywriting;
  const suggested = copy?.suggested;

  return (
    <div className="space-y-8">
      {/* 1. Score Overview */}
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-5">
        <div>
          <dt className="label">Overall Score</dt>
          <dd className={`font-sans text-3xl ${scoreTone(report?.overall_score ?? 0)}`}>
            {report ? Math.round(report.overall_score) : '—'}
          </dd>
        </div>
        <div>
          <dt className="label">SEO Score</dt>
          <dd className="font-sans text-3xl">{seo ? Math.round(seo.score) : '—'}</dd>
        </div>
        <div>
          <dt className="label">Copywriting Score</dt>
          <dd className="font-sans text-3xl">
            {copy && copy.llm_status === 'ok' && copy.score != null ? Math.round(copy.score) : 'null'}
          </dd>
        </div>
        <div>
          <dt className="label">Page Type</dt>
          <dd className="mt-1 capitalize text-ink font-medium">{display(page.page_type)}</dd>
        </div>
      </dl>

      {/* 2. Genre-Specific Analytics & Vector Visualizations */}
      <PageGenreAnalytics page={page} report={report} ga4LandingPages={ga4LandingPages} />

      {copy?.llm_status === 'failed' && (
        <div className="p-4 rounded-lg border border-bad/40 bg-bad/10 space-y-2">
          <span className="label text-bad block">Copy rewrite FAILED</span>
          <p className="text-sm text-ink-700 leading-relaxed">
            {copy.llm_failure_reason || copy.analysis || 'The model did not return a rewrite.'}
          </p>
          {copy.llm_failure_code && (
            <p className="text-[11px] font-mono text-ink-600">Code: {copy.llm_failure_code}</p>
          )}
          <p className="text-xs text-ink-600">
            Suggested production copy is hidden because it would be a crawl echo, not an agent rewrite.
            SEO scores below are from the crawl. Groq HTTP 404 means that engine's model id was retired
            (llama-3.1-8b-instant / llama-3.3-70b-versatile shut down for free/dev tiers on 2026-08-16).
            Use openai/gpt-oss-20b or openai/gpt-oss-120b. This does not affect the Claude audit path.
          </p>
          {copy.issues?.length > 0 && (
            <ul className="text-xs text-ink-700 space-y-1 pt-1">
              {copy.issues.map((item) => (
                <li key={item.issue}>Crawl copy issue ({item.area}): {item.issue}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* 2. 5-Specialist Insights — only when the model actually ran */}
      {copy?.llm_status === 'ok' && copy?.specialist_insights && Object.keys(copy.specialist_insights).length > 0 && (
        <SpecialistInsightsBar insights={copy.specialist_insights} />
      )}

      {/* 3. 3-Second Hook & GEO Citation Callouts */}
      {copy?.llm_status === 'ok' && (suggested?.hook_3sec || suggested?.geo_snippet) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {suggested.hook_3sec && (
            <div className="sheet border border-line rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="label text-ink-700">3-Second First Impression Hook</span>
                <CopyButton text={suggested.hook_3sec} />
              </div>
              <p className="text-sm font-sans font-bold text-ink leading-snug">
                "{suggested.hook_3sec}"
              </p>
              <p className="text-[11px] text-ink-500">
                Immediately communicates core audience and value mechanism before visitor scroll.
              </p>
            </div>
          )}
          {suggested.geo_snippet && (
            <div className="sheet border border-line rounded-lg p-4 space-y-2 bg-good/10">
              <div className="flex items-center justify-between">
                <span className="label text-good">Direct AI Citation Snippet (GEO)</span>
                <CopyButton text={suggested.geo_snippet} />
              </div>
              <p className="text-xs font-mono text-ink-700 leading-relaxed bg-paper-50/80 p-2.5 rounded border border-good/30">
                {suggested.geo_snippet}
              </p>
              <p className="text-[11px] text-ink-500">
                40–60 word extractable definition crafted for direct quotation by ChatGPT and Perplexity.
              </p>
            </div>
          )}
        </div>
      )}

      {/* 4. Section-Wise Highlights: What Needs To Be Updated */}
      {copy?.llm_status === 'ok' && suggested?.sections && suggested.sections.length > 0 && (
        <SectionHighlights
          sections={suggested.sections}
          fullRewrite={suggested.body_rewrite}
        />
      )}

      {/* 5. SERP-Safe Title, Meta & Header Optimization */}
      {copy?.llm_status === 'ok' && suggested && (
        <section className="sheet border border-line rounded-lg p-5 space-y-4">
          <div className="border-b border-line pb-2">
            <p className="label text-ink-700">SERP Metadata & Header Optimization</p>
            <p className="text-xs text-ink-500">
              Strict length compliance enforced: Title (50–60 chars) and Meta Description (140–160 chars) to prevent search engine truncation.
            </p>
          </div>

          <Pair
            label="Title Tag"
            current={page.title}
            suggested={suggested.title}
            badge={suggested.title ? `${suggested.title.length} chars (Target 50-60)` : undefined}
          />
          <Pair
            label="Meta Description"
            current={page.meta_description}
            suggested={suggested.meta_description}
            badge={suggested.meta_description ? `${suggested.meta_description.length} chars (Target 140-160)` : undefined}
          />
          <Pair
            label="Primary H1 Headline"
            current={page.h1?.[0]}
            suggested={suggested.h1}
          />
          <Pair
            label="Hero Subheadline"
            current={
              page.body_text
                ? page.body_text
                    .split('\n')
                    .map((l) => l.trim())
                    .filter((l) => l.length >= 40)[0]
                : undefined
            }
            suggested={suggested.hero}
          />
          <Pair
            label="Primary Call to Action"
            current={page.ctas && page.ctas[0]}
            suggested={suggested.primary_cta}
          />
          {suggested.secondary_cta && (
            <Pair
              label="Secondary Call to Action"
              current={page.ctas && page.ctas[1]}
              suggested={suggested.secondary_cta}
            />
          )}

          {suggested.supporting_points?.length > 0 && (
            <div className="py-3 border-b border-line">
              <div className="flex items-center justify-between mb-1.5">
                <p className="label text-[10px]">Key Supporting Pillars</p>
                <CopyButton text={suggested.supporting_points.map((p) => `• ${p}`).join('\n')} />
              </div>
              <ul className="space-y-1.5 text-xs text-ink-700">
                {suggested.supporting_points.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-ink-700 font-bold">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {suggested.notes && (
            <p className="text-xs text-ink-500 italic pt-1">{suggested.notes}</p>
          )}
        </section>
      )}

      {/* 6. AI Answer Engine FAQ Block */}
      {copy?.llm_status === 'ok' && suggested?.faq_items && suggested.faq_items.length > 0 && (
        <FaqBlock faqs={suggested.faq_items} />
      )}

      {/* 7. SEO Issues & Recommendations */}
      {seo && (
        <section className="sheet border border-line rounded-lg p-5 space-y-4">
          <p className="label text-ink-700">Search Engine Optimization Audit</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 text-xs">
            <div>
              <p className="text-ink font-semibold mb-2">Identified SEO Issues</p>
              {seo.issues.length ? (
                <ul className="space-y-1.5 text-ink-700">
                  {seo.issues.map((item) => (
                    <li key={item} className="flex items-start gap-1.5">
                      <span className="text-bad">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-ink-400">No major SEO issues detected.</p>
              )}
            </div>
            <div>
              <p className="text-ink font-semibold mb-2">Recommended Fixes</p>
              {seo.recommendations.length ? (
                <ul className="space-y-1.5 text-ink-700">
                  {seo.recommendations.map((item) => (
                    <li key={item} className="flex items-start gap-1.5">
                      <span className="text-good">✓</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-ink-400">—</p>
              )}
            </div>
          </div>
          <p className="text-xs text-ink-500 pt-2 border-t border-line">
            Title {seo.title_status} ({seo.title_length}) · Meta {seo.meta_status} ({seo.meta_length}) · H1 {seo.h1_status} · Canonical {seo.canonical_status} · Schema {seo.schema_status}
          </p>
        </section>
      )}

      {/* 8. Technical On-Page Signals (Collapsible) */}
      <div className="pt-2">
        <button
          type="button"
          onClick={() => setShowTechnical(!showTechnical)}
          className="text-xs text-ink-500 hover:text-ink font-semibold flex items-center gap-1 cursor-pointer"
        >
          <span>{showTechnical ? '▲ Hide On-Page Technical Signals' : '▼ View On-Page Technical Signals (TTFB, Schema, Links)'}</span>
        </button>

        {showTechnical && (
          <div className="mt-3 p-4 bg-paper-50 border border-line rounded-lg text-xs text-ink-700 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2">
            <p><span className="text-ink-500">Status </span>{page.status_code}</p>
            <p><span className="text-ink-500">Words </span>{page.word_count}</p>
            <p><span className="text-ink-500">Readability </span>{page.readability_score ? page.readability_score.toFixed(0) : '—'}</p>
            <p><span className="text-ink-500">TTFB </span>{page.ttfb_ms ? `${Math.round(page.ttfb_ms)}ms` : '—'}</p>
            <p><span className="text-ink-500">Canonical </span>{display(page.canonical_url)}</p>
            <p><span className="text-ink-500">Schema </span>{page.schema_types?.length ? page.schema_types.join(', ') : '—'}</p>
            <p><span className="text-ink-500">Open Graph </span>{page.og_tags && Object.keys(page.og_tags).length ? 'Yes' : 'No'}</p>
            <p><span className="text-ink-500">Viewport </span>{display(page.viewport)}</p>
            <p><span className="text-ink-500">Images missing alt </span>{page.images_without_alt}/{page.total_images}</p>
            <p><span className="text-ink-500">Internal links </span>{page.internal_links?.length ?? 0}</p>
            <p><span className="text-ink-500">Indexability </span>{display(seo?.indexability)}</p>
            <p><span className="text-ink-500">Content source </span>{
              page.render_mode === 'js_rendered'
                ? 'JavaScript / CMS render'
                : page.render_mode === 'embedded_cms'
                ? 'Admin/CMS payload'
                : display(page.render_mode, 'HTML')
            }</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function Pages({ manifest, summary, pageReports = [], ga4LandingPages }: PagesProps) {
  const [openScrapedUrls, setOpenScrapedUrls] = useState<Set<string>>(new Set());
  const [selectedGenre, setSelectedGenre] = useState<string>('all');
  const pages = manifest?.pages || [];
  const reportsByUrl = new Map(pageReports.map((item) => [item.url, item]));
  const recordedDiscovered = [manifest?.total_pages_discovered, summary.total_pages_discovered]
    .find((value) => typeof value === 'number' && value > 0);
  const sitemap = manifest?.sitemap_found ?? Boolean(summary.sitemap_found);
  const robots = manifest?.robots_txt_found ?? Boolean(summary.robots_txt_found);
  const health = manifest?.crawl_health || summary || {};

  const resolvedGa4Pages =
    ga4LandingPages ||
    (summary?.ga4 as any)?.landing_pages ||
    (summary?.top_landing_pages as any) ||
    [];

  const genreCounts = pages.reduce((acc, p) => {
    const g = detectPageGenre(p.page_type, p.url, p.title);
    acc[g] = (acc[g] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const filteredPages =
    selectedGenre === 'all'
      ? pages
      : pages.filter((p) => detectPageGenre(p.page_type, p.url, p.title) === selectedGenre);

  const toggleScraped = (url: string) => {
    setOpenScrapedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else {
        next.add(url);
      }
      return next;
    });
  };

  const stats = [
    { label: 'Crawled', value: String(pages.length) },
    { label: 'Reports', value: String(pageReports.length || pages.length) },
    { label: 'Discovered', value: recordedDiscovered != null ? String(recordedDiscovered) : '—' },
    { label: 'Sitemap', value: sitemap ? 'Yes' : 'No' },
    { label: 'robots.txt', value: robots ? 'Yes' : 'No' },
    { label: 'Words', value: String(asNumber(health.total_words_across_site ?? summary.total_words, 0)) },
  ];

  return (
    <div className="space-y-8">
      <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6">
        {stats.map((item) => (
          <div key={item.label}>
            <dt className="label">{item.label}</dt>
            <dd className="mt-1 font-sans text-2xl text-ink">{item.value}</dd>
          </div>
        ))}
      </dl>

      {pages.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line">
          <span className="text-xs font-semibold text-ink-500 mr-1">Filter by Genre:</span>
          <button
            type="button"
            onClick={() => setSelectedGenre('all')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer ${
              selectedGenre === 'all'
                ? 'bg-paper-50 text-ink border-line font-bold shadow-xs'
                : 'bg-paper-100 text-ink-500 border-transparent hover:text-ink'
            }`}
          >
            All Genres ({pages.length})
          </button>
          {Object.entries(GENRE_CONFIGS).map(([gKey, gConfig]) => {
            const count = genreCounts[gKey] || 0;
            if (count === 0) return null;
            return (
              <button
                key={gKey}
                type="button"
                onClick={() => setSelectedGenre(gKey)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer flex items-center gap-1.5 ${
                  selectedGenre === gKey
                    ? 'bg-paper-50 text-ink border-line font-bold shadow-xs'
                    : 'bg-paper-100 text-ink-500 border-transparent hover:text-ink'
                }`}
              >
                <span>{gConfig.name.split('/')[0].trim()}</span>
                <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-paper-200 text-ink-700">
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {pages.length === 0 ? (
        <p className="text-ink-400">No pages in this crawl.</p>
      ) : filteredPages.length === 0 ? (
        <p className="text-ink-400 py-6">No crawled pages match the selected "{selectedGenre}" genre.</p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {filteredPages.map((page) => {
            const report = reportsByUrl.get(page.url);
            const isScrapedOpen = openScrapedUrls.has(page.url);

            return (
              <li key={page.url} className="py-8 space-y-6">
                {/* Page Bar Header */}
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-4">
                  <div className="min-w-0 max-w-3xl">
                    <p className="text-lg font-sans text-ink">{display(page.title, page.url)}</p>
                    <p className="text-xs text-ink-500 font-mono truncate mt-0.5">{page.url}</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-ink-500 shrink-0">
                    {report && (
                      <span className={`font-sans text-lg font-bold px-2 py-0.5 rounded border border-line ${scoreTone(report.overall_score)}`}>
                        {Math.round(report.overall_score)}
                      </span>
                    )}
                    <span className="px-2 py-1 rounded bg-paper-50 border border-line font-mono">{page.status_code}</span>
                    <span>{page.word_count} words</span>
                    <span className="capitalize px-2 py-1 rounded bg-paper-100 text-ink-700 font-medium">
                      {display(page.page_type)}
                    </span>
                  </div>
                </div>

                {/* Main Content: Copywriting Intelligence & Section-Wise Highlights (Shown by Default) */}
                <PageDetail page={page} report={report} ga4LandingPages={resolvedGa4Pages} />

                {/* Raw Extracted Scraped Content: Hidden Behind Toggle Button */}
                <div className="pt-2 border-t border-line">
                  <button
                    type="button"
                    onClick={() => toggleScraped(page.url)}
                    className="inline-flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded border border-line bg-paper-50 hover:bg-paper-200 text-ink-700 hover:text-ink transition-colors cursor-pointer"
                  >
                    <span>
                      {isScrapedOpen
                        ? '▲ Hide Raw Extracted Page Payload'
                        : `▼ View Raw Extracted Page Payload (${page.word_count} words, ${page.total_images || 0} images)`}
                    </span>
                  </button>

                  {isScrapedOpen && (
                    <div className="mt-4 p-5 rounded-lg border border-line bg-paper-50/70">
                      <ScrapedContent page={page} />
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {manifest?.sitemap_url && (
        <p className="text-sm text-ink-500">Sitemap {asString(manifest.sitemap_url)}</p>
      )}
    </div>
  );
}
