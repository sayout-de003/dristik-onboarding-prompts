import React, { useEffect, useState } from 'react';
import { PricingPlan, SubscriptionHypothesis } from '../types';
import { getPlans } from '../services/api';

interface PricingProps {
  onSelectPlan: (planId: string) => void;
}

const COMPARISON_FEATURES = [
  {
    category: 'Crawl & Evidence',
    items: [
      { name: 'Crawl depth & internal link topology', starter: 'Up to 3 pages', diagnostic: 'Up to 15 pages', bakeoff: 'Up to 30 pages', pulse: 'Up to 25 pages/mo' },
      { name: 'Zero-token AST DOM parsing (H1–H6, microdata)', starter: '✓ Basic', diagnostic: '✓ Full hierarchy', bakeoff: '✓ Full hierarchy', pulse: '✓ Monthly diff' },
      { name: 'Evidence Graph 2.0 with SHA-256 DOM locators', starter: '✕', diagnostic: '✓ Cryptographic', bakeoff: '✓ Cryptographic', pulse: '✓ Continuous' },
      { name: 'Adversarial Critic falsification against live DOM', starter: '✕', diagnostic: '✓ Included', bakeoff: '✓ Included', pulse: '✓ Included' },
    ],
  },
  {
    category: 'Generative Engine Optimization (GEO)',
    items: [
      { name: 'The 6 Commercial Buyer Questions audit', starter: '1 scenario', diagnostic: 'All 6 canonical', bakeoff: 'All 6 + Competitor', pulse: '20–40 saved prompts' },
      { name: 'ChatGPT Search, Perplexity Pro & Claude simulation', starter: 'Basic score', diagnostic: '✓ Full matrix', bakeoff: '✓ Full matrix', pulse: '✓ Weekly/Monthly' },
      { name: 'Re-Query Before → After Citation Readiness proof', starter: '✕', diagnostic: '✓ Included', bakeoff: '✓ + 14-day scan', pulse: '✓ Monthly delta' },
      { name: '1-Competitor Head-to-Head Bake-Off table', starter: '✕', diagnostic: '✕ Optional add-on', bakeoff: '✓ Included', pulse: '✕' },
      { name: 'Sales Battlecard ("Who the AI model answers for")', starter: '✕', diagnostic: '✕', bakeoff: '✓ Included', pulse: '✓ Trend alerts' },
    ],
  },
  {
    category: 'Engineering Remediation & Code Patches',
    items: [
      { name: 'Theory of Constraints single bottleneck discovery', starter: '✕', diagnostic: '✓ Core bottleneck', bakeoff: '✓ Core bottleneck', pulse: '✓ Shift detection' },
      { name: 'Pinned "What to Ignore This Month" anti-distraction list', starter: '✕', diagnostic: '✓ Pinned Page 1', bakeoff: '✓ Pinned Page 1', pulse: '✓ Updated' },
      { name: 'Developer Patch Pack (.ZIP download & Notion block)', starter: '✕', diagnostic: '✓ Full 6-file ZIP', bakeoff: '✓ Full 6-file ZIP', pulse: '✓ Delta patches' },
      { name: 'Production schema.jsonld, metadata.html, semantic faq.html', starter: '✕', diagnostic: '✓ Drop-in code', bakeoff: '✓ Drop-in code', pulse: '✓ Updated' },
      { name: 'llms.txt AI scraper guide & robots.txt directives', starter: '✕', diagnostic: '✓ Included', bakeoff: '✓ Included', pulse: '✓ Included' },
      { name: 'Character-Safe Copy Assistant (Title, Meta, Hero limits)', starter: '✕', diagnostic: '✓ Real-time counters', bakeoff: '✓ Real-time counters', pulse: '✓ Included' },
    ],
  },
  {
    category: 'Institutional Reporting & Indian Compliance',
    items: [
      { name: 'The Honest 3-Scores (Human, Google, AI Citation)', starter: 'Partial', diagnostic: '✓ 3 Verified scores', bakeoff: '✓ 3 Verified scores', pulse: '✓ Score tracking' },
      { name: 'WhatsApp C-Suite 1-Pager (Mobile shareable)', starter: '✕', diagnostic: '✓ 1-Click WhatsApp', bakeoff: '✓ 1-Click WhatsApp', pulse: '✓ Monthly summary' },
      { name: 'Big 4 Printable Institutional PDF Deck', starter: 'Standard PDF', diagnostic: '✓ Printable Deck', bakeoff: '✓ White-Label PDF', pulse: '✓ Executive deck' },
      { name: 'Commercial Purchase Receipt (Flat 0% Tax, 100% Tax Deductible)', starter: '✓ Included', diagnostic: '✓ Included', bakeoff: '✓ Included', pulse: '✓ Recurring receipt' },
      { name: '0% Surcharge Instant UPI QR & Card checkout', starter: '✓ Included', diagnostic: '✓ Included', bakeoff: '✓ Included', pulse: '✓ Included' },
      { name: 'Agency White-Label rights (No Dristik branding)', starter: '✕', diagnostic: '✕', bakeoff: '✓ Included', pulse: 'Add-on' },
    ],
  },
];

const INDIA_MARKET_FAQS = [
  {
    q: 'How are invoices and commercial receipts handled?',
    a: 'Every purchase generates an itemized Commercial Purchase Receipt detailing your organization name, GSTIN (if provided), target URL, and transaction reference ID. Receipts are provided in standard format suitable for corporate business expense accounting.',
  },
  {
    q: 'Can we pay via Corporate UPI or NetBanking?',
    a: 'Yes. In addition to corporate credit and debit cards, we natively support 0% transaction fee UPI payments via QR code (Google Pay, PhonePe, BHIM, Paytm, ICICI/HDFC Corporate UPI) and direct NetBanking across all major Indian banks.',
  },
  {
    q: 'Why a ₹4,999 Diagnostic Sprint instead of an agency retainer?',
    a: 'Traditional digital agencies in India charge ₹50,000 to ₹1,50,000 per month on 3-to-6 month contracts, assigning junior analysts to run free tools and deliver a 60-page PDF slide deck that takes weeks to produce. Dristik runs empirical multi-page crawling, tests the 6 commercial buyer questions on ChatGPT and Perplexity, isolates the single TOC bottleneck, and delivers drop-in code patches in a ZIP file in under 3 minutes for a flat ₹4,999.',
  },
  {
    q: 'What is the Developer Patch Pack and can our engineer deploy it immediately?',
    a: 'Yes. The Developer Patch Pack is an instant downloadable .ZIP file and copy-paste Notion block containing 6 production-ready files: schema.jsonld, metadata.html, semantic faq.html, llms.txt, robots.txt, and a clean README_DEV_INSTALL.md guide. Any front-end engineer or webmaster can review and merge the files into React, Next.js, WordPress, or plain HTML in under 15 minutes.',
  },
  {
    q: 'What is the 1-Competitor Bake-Off (₹11,999)?',
    a: 'On sales calls, Indian and US SaaS buyers constantly ask: "How does our product compare to our primary rival in AI search engines?" The Bake-Off runs the same 6 commercial inquiries on both your domain and your chosen rival, rendering a side-by-side sales battlecard table showing who the AI model answers for, which brand earns the citation, and where your competitor is capturing market demand.',
  },
  {
    q: 'Can agencies white-label the audit deliverables?',
    a: 'Yes. On the Diagnostic + Competitor Bake-Off tier (₹11,999) or agency custom plans, you receive complete white-label rights. The printable institutional PDF and WhatsApp 1-pager can be exported with zero Dristik branding so you can present them directly to your clients under your own agency brand.',
  },
];

export function Pricing({ onSelectPlan }: PricingProps) {
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  const [planType, setPlanType] = useState<'sprints' | 'monitoring'>('sprints');
  const [audits, setAudits] = useState<PricingPlan[]>([]);
  const [monitoring, setMonitoring] = useState<PricingPlan[]>([]);
  const [hypotheses, setHypotheses] = useState<SubscriptionHypothesis[]>([]);
  const [hypothesisNote, setHypothesisNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    getPlans()
      .then((catalog) => {
        setAudits(catalog.one_time_audits || []);
        setMonitoring(catalog.continuous_monitoring || []);
        setHypotheses(catalog.subscription_hypotheses || []);
        setHypothesisNote(catalog.subscription_hypotheses_note || null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Could not load plans.');
      });
  }, []);

  // Primary featured plans
  const diagnosticPlan = audits.find((p) => p.id === 'diagnostic');
  const bakeoffPlan = audits.find((p) => p.id === 'diagnostic_bakeoff');
  const starterPlan = audits.find((p) => p.id === 'starter');
  const pulsePlan = monitoring.find((p) => p.id === 'monthly_pulse');

  return (
    <div className="space-y-16 max-w-[1400px] mx-auto pb-16">
      {/* Header & Market Value Anchor */}
      <section data-page-header className="max-w-2xl space-y-3 pt-2">
        <p className="label">Pricing</p>
        <h1 className="font-sans text-4xl sm:text-5xl text-ink tracking-tight">
          Choose an audit sprint or ongoing monitoring.
        </h1>
        <p className="text-ink-500 leading-relaxed">
          Compare each package by scope and deliverables. Live citation checks, analytics and external data depend on the providers and measurements available to your workspace.
        </p>

        {/* Currency & Scope Toggles */}
        <div className="flex flex-col sm:flex-row items-start gap-3 pt-4">
          <div className="inline-flex p-1 bg-paper-100 rounded border border-line text-sm">
            <button
              type="button"
              onClick={() => setPlanType('sprints')}
              className={`px-4 py-1.5 rounded transition-colors font-medium ${
                planType === 'sprints' ? 'bg-ink text-paper-50' : 'text-ink-700 hover:text-ink'
              }`}
            >
              Sprints
            </button>
            <button
              type="button"
              onClick={() => setPlanType('monitoring')}
              className={`px-4 py-1.5 rounded transition-colors font-medium ${
                planType === 'monitoring' ? 'bg-ink text-paper-50' : 'text-ink-700 hover:text-ink'
              }`}
            >
              Monitoring
            </button>
          </div>

          <div className="inline-flex p-1 bg-paper-100 rounded border border-line text-sm">
            <button
              type="button"
              onClick={() => setCurrency('INR')}
              className={`px-3 py-1.5 rounded transition-colors ${
                currency === 'INR' ? 'bg-pine text-paper-50 font-bold' : 'text-ink-700'
              }`}
            >
              ₹ INR
            </button>
            <button
              type="button"
              onClick={() => setCurrency('USD')}
              className={`px-3 py-1.5 rounded transition-colors ${
                currency === 'USD' ? 'bg-pine text-paper-50 font-bold' : 'text-ink-700'
              }`}
            >
              $ USD
            </button>
          </div>
        </div>

        {/* India Advantage Banner */}
        <p className="mt-4 text-xs text-ink-500">
          Instant receipt · UPI and cards · WhatsApp one-pager included
        </p>
      </section>

      {error && <p className="text-bad text-center text-sm">{error}</p>}

      {/* Plan Cards Grid: Sprints View */}
      {planType === 'sprints' && (
        <div className="space-y-12">
          {/* Segment 1: SMB & Flagship Sprint */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <span className="label">One-time sprints</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
              {/* Card 0: Free Scan */}
              <article className="p-6 bg-paper-50 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-700 font-mono">100% Free · 1-Page Teaser</span>
                  <h2 className="font-sans text-2xl text-ink">Free Diagnostic</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    Instant single-page audit showing your Honest 3-Scores and top bottlenecks.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">₹0</p>
                    <p className="text-[11px] text-ink-400 font-mono">Zero commitment</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5">✓ 1-Page Instant Crawl</li>
                    <li className="flex items-center gap-1.5">✓ Honest 3-Scores (Human, Google, AI)</li>
                    <li className="flex items-center gap-1.5">✓ Top 3 Critical Bottlenecks</li>
                    <li className="flex items-center gap-1.5">✓ 1 Competitor Insight</li>
                    <li className="flex items-center gap-1.5 text-ink-400">✕ No Code Patches</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('free_scan')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Start Free Scan (₹0)
                </button>
              </article>

              {/* Card 1: Starter Baseline */}
              <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-500 font-mono">Early-Stage Sites</span>
                  <h2 className="font-sans text-2xl text-ink">Dristik Starter</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    Essential crawl & technical DOM hygiene check for landing pages.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">
                      {currency === 'INR' ? '₹1,499' : '$19'}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono">Flat one-time · 0% tax</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5">✓ Up to 3 key pages crawled</li>
                    <li className="flex items-center gap-1.5">✓ Core Technical SEO & DOM hygiene</li>
                    <li className="flex items-center gap-1.5">✓ Basic Schema.org AST check</li>
                    <li className="flex items-center gap-1.5">✓ Initial GEO Extractability score</li>
                    <li className="flex items-center gap-1.5 text-ink-400">✕ No Code Patches</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('starter')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Select Starter (₹1,499)
                </button>
              </article>

              {/* Card 2: Professional */}
              <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-500 font-mono">Growing Startups</span>
                  <h2 className="font-sans text-2xl text-ink">Professional</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    10-page crawl with verified DOM evidence and 7/30/90-day roadmap.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">
                      {currency === 'INR' ? '₹3,499' : '$49'}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono">Flat one-time · 0% tax</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5">✓ Up to 10 strategic pages</li>
                    <li className="flex items-center gap-1.5">✓ Deep Technical SEO + Schema verification</li>
                    <li className="flex items-center gap-1.5">✓ AI-Search Discoverability matrix</li>
                    <li className="flex items-center gap-1.5">✓ 7/30/90-Day Remediation Roadmap</li>
                    <li className="flex items-center gap-1.5">✓ Printable Executive Story PDF</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('professional')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Select Professional (₹3,499)
                </button>
              </article>

              {/* Card 3: Diagnostic Sprint (Flagship Highlight) */}
              <article className="p-6 bg-paper-50 rounded-xl border-2 border-line shadow-md flex flex-col justify-between space-y-5 relative">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-pine text-paper-50 text-[10px] px-3 py-0.5 rounded-md font-bold uppercase tracking-[0.04em]">
                  Recommended Flagship
                </div>
                <div className="space-y-3 pt-1">
                  <span className="label text-ink-700 font-mono">Flagship Sprint</span>
                  <h2 className="font-sans text-2xl text-ink">Diagnostic Sprint</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    The complete proof-and-patch engagement: full diagnosis, developer ZIP pack, and re-query citation proof.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink-700">
                      {currency === 'INR' ? '₹4,999' : '$69'}
                    </p>
                    <p className="text-[11px] text-ink-500 font-mono">Flat price · 0% Added Tax</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5 font-medium text-ink">✓ Up to 15 primary strategic pages</li>
                    <li className="flex items-center gap-1.5 font-medium text-ink">✓ The 6 Commercial Buyer Inquiries</li>
                    <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Developer Patch Pack (.ZIP download)</li>
                    <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Re-Query Citation Proof Matrix</li>
                    <li className="flex items-center gap-1.5">✓ WhatsApp C-Suite 1-Pager & PDF</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('diagnostic')}
                  className="w-full py-2.5 px-3 rounded bg-pine text-paper-50 font-bold text-xs hover:bg-pine-700 transition-colors shadow"
                >
                  Start Diagnostic (₹4,999)
                </button>
              </article>
            </div>
          </div>

          {/* Segment 2: Growth & Mid-Market Intelligence */}
          <div className="pt-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="label">Growth & competitive</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
              {/* Business Intelligence */}
              <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-500 font-mono">Scaleups & B2B</span>
                  <h2 className="font-sans text-2xl text-ink">Business Intelligence</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    35-page deep crawl, 3-way competitor positioning, and cross-page contradiction detection.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">
                      {currency === 'INR' ? '₹9,999' : '$129'}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono">Flat one-time · 0% tax</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5 font-medium text-ink">✓ Up to 35 strategic pages</li>
                    <li className="flex items-center gap-1.5">✓ 3-Way Competitor Positioning Matrix</li>
                    <li className="flex items-center gap-1.5">✓ Cross-Page Claim & Pricing Contradictions</li>
                    <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Universal Patches (WordPress + GitHub PR ready)</li>
                    <li className="flex items-center gap-1.5">✓ Consultant-Grade Presentation Deck</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('business')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Select Business (₹9,999)
                </button>
              </article>

              {/* Competitor Bake-Off */}
              <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-700 font-mono">Sales Battlecard</span>
                  <h2 className="font-sans text-2xl text-ink">Competitor Bake-Off</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    Everything in Diagnostic Sprint + Head-to-Head 3-Competitor Bake-Off on commercial queries.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">
                      {currency === 'INR' ? '₹14,999' : '$189'}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono">Sprint + 3-Competitor Battlecard</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5 font-medium text-ink">✓ Up to 50 strategic pages</li>
                    <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Head-to-Head 3-Competitor Bake-Off</li>
                    <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Side-by-side sales battlecard table</li>
                    <li className="flex items-center gap-1.5">✓ Agency White-Label licensing rights</li>
                    <li className="flex items-center gap-1.5">✓ 14-Day Post-Patch Re-Query verification</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('diagnostic_bakeoff')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Select Bake-Off (₹14,999)
                </button>
              </article>

              {/* Growth Intelligence */}
              <article className="p-6 bg-paper-50 rounded-xl border border-line flex flex-col justify-between space-y-5 hover:border-ink-300 transition">
                <div className="space-y-3">
                  <span className="label text-ink-700 font-mono">Mid-Market Platform</span>
                  <h2 className="font-sans text-2xl text-ink">Growth Intelligence</h2>
                  <p className="text-xs text-ink-700 leading-relaxed">
                    100-page deep crawl, automated competitor discovery, developer remediation PR pack, and historical delta.
                  </p>
                  <div>
                    <p className="font-sans text-3xl text-ink">
                      {currency === 'INR' ? '₹24,999' : '$319'}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono">Comprehensive mid-market audit</p>
                  </div>
                  <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                    <li className="flex items-center gap-1.5 font-medium text-ink">✓ Up to 100 deep pages crawled</li>
                    <li className="flex items-center gap-1.5">✓ Real competitor auto-discovery (Top 5)</li>
                    <li className="flex items-center gap-1.5">✓ Complete GitHub PR & WordPress sync</li>
                    <li className="flex items-center gap-1.5">✓ Executive presentation & Business ROI attribution</li>
                    <li className="flex items-center gap-1.5">✓ Direct senior remediation review session</li>
                  </ul>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectPlan('growth')}
                  className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition-colors"
                >
                  Select Growth (₹24,999)
                </button>
              </article>
            </div>
          </div>

          {/* Segment 3: Enterprise Custom Tier */}
          <div className="p-6 rounded-2xl bg-paper-100 border border-line flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <span className="text-xs font-mono uppercase tracking-[0.04em] px-2 py-0.5 rounded bg-paper-100 text-ink-700 font-bold border border-line">
                Tier 3: Enterprise Custom Engagement
              </span>
              <h3 className="font-sans text-2xl text-ink">Enterprise Custom Platforms & Portfolios</h3>
              <p className="text-xs text-ink-700 leading-relaxed">
                200+ pages across multi-domains, automated webhook feeds, custom AI buyer query benchmarking, dedicated Slack channels, and enterprise SLAs. Starting at ₹49,999 to ₹1,50,000+ depending on scope.
              </p>
            </div>
            <button
              type="button"
              onClick={() => onSelectPlan('enterprise')}
              className="px-6 py-3 rounded-lg bg-ink text-paper-50 font-bold text-sm hover:bg-ink-900 transition whitespace-nowrap"
            >
              Contact Enterprise Sales (₹49,999+)
            </button>
          </div>
        </div>
      )}

      {/* Plan Cards Grid: Monitoring View */}
      {planType === 'monitoring' && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Sentinel Radar */}
          <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5">
            <div className="space-y-3">
              <span className="label text-ink-500 font-mono">Bi-Weekly Radar</span>
              <h2 className="font-sans text-2xl text-ink">Sentinel Radar</h2>
              <p className="text-xs text-ink-700 leading-relaxed">
                Continuous bi-weekly audits, SEO/GEO regression alerts, and email digests.
              </p>
              <div>
                <p className="font-sans text-3xl text-ink">
                  {currency === 'INR' ? '₹1,499' : '$19'}
                  <span className="text-xs font-normal text-ink-500"> / mo</span>
                </p>
              </div>
              <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                <li className="flex items-center gap-1.5">✓ Bi-weekly autonomous audits</li>
                <li className="flex items-center gap-1.5">✓ Technical & GEO regression alerts</li>
                <li className="flex items-center gap-1.5">✓ AI discoverability score tracking</li>
                <li className="flex items-center gap-1.5">✓ Email executive summary digests</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={() => onSelectPlan('monitoring-starter')}
              className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition"
            >
              Subscribe (₹1,499/mo)
            </button>
          </article>

          {/* Card 2: AI Citation Monitoring */}
          <article className="p-6 bg-paper-50 rounded-xl border-2 border-line shadow-md flex flex-col justify-between space-y-5 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-pine text-paper-50 text-[10px] px-3 py-0.5 rounded-md font-bold uppercase tracking-[0.04em]">
              Hero Retainer
            </div>
            <div className="space-y-3 pt-1">
              <span className="label text-ink-700 font-mono">Citation Defense</span>
              <h2 className="font-sans text-2xl text-ink">AI Citation Pulse</h2>
              <p className="text-xs text-ink-700 leading-relaxed">
                20–40 saved commercial buyer prompts tracked continuously on ChatGPT Search & Perplexity.
              </p>
              <div>
                <p className="font-sans text-3xl text-ink-700">
                  {currency === 'INR' ? '₹3,999' : '$49'}
                  <span className="text-xs font-normal text-ink-500"> / mo</span>
                </p>
              </div>
              <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                <li className="flex items-center gap-1.5 font-medium text-ink">✓ 20–40 saved buyer prompts tracked</li>
                <li className="flex items-center gap-1.5 font-medium text-ink">✓ ChatGPT & Perplexity citation monitoring</li>
                <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ Monthly crawl change-log diff</li>
                <li className="flex items-center gap-1.5">✓ WhatsApp executive regression alerts</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={() => onSelectPlan('monthly_pulse')}
              className="w-full py-2.5 px-3 rounded bg-pine text-paper-50 font-bold text-xs hover:bg-pine-700 transition shadow"
            >
              Subscribe (₹3,999/mo)
            </button>
          </article>

          {/* Card 3: Agency Multi-Guard */}
          <article className="p-6 bg-paper-100 rounded-xl border border-line flex flex-col justify-between space-y-5">
            <div className="space-y-3">
              <span className="label text-ink-700 font-mono">Agencies & Portfolios</span>
              <h2 className="font-sans text-2xl text-ink">Agency Multi-Guard</h2>
              <p className="text-xs text-ink-700 leading-relaxed">
                Up to 5 client domains monitored with white-label client PDF exports.
              </p>
              <div>
                <p className="font-sans text-3xl text-ink">
                  {currency === 'INR' ? '₹14,999' : '$189'}
                  <span className="text-xs font-normal text-ink-500"> / mo</span>
                </p>
              </div>
              <ul className="space-y-1.5 text-xs text-ink-700 border-t border-line pt-3">
                <li className="flex items-center gap-1.5 font-medium text-ink">✓ Up to 5 client domains monitored</li>
                <li className="flex items-center gap-1.5">✓ Automated PR-ready remediation patches</li>
                <li className="flex items-center gap-1.5 font-semibold text-ink-700">✓ 100% White-Label client PDF decks</li>
                <li className="flex items-center gap-1.5">✓ Dedicated Slack channel with specialists</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={() => onSelectPlan('monitoring-agency')}
              className="w-full py-2.5 px-3 rounded border border-ink text-ink font-semibold text-xs hover:bg-ink hover:text-paper-50 transition"
            >
              Select Agency Guard (₹14,999/mo)
            </button>
          </article>
        </section>
      )}

      {/* Interactive Business Impact & ROI Calculator */}
      <section className="p-8 rounded-2xl bg-paper-50 border-2 border-line shadow-sm space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="label text-ink-700">Revenue & Commercial Upside Modeling</span>
          <h2 className="font-sans text-3xl text-ink">Explore potential value from Dristik</h2>
          <p className="text-xs text-ink-700 leading-relaxed">
            See how fixing AI search extractability and conversion bottlenecks connects directly to business revenue.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center pt-2">
          {/* Inputs */}
          <div className="md:col-span-6 space-y-4 bg-paper-100 p-5 rounded-xl border border-line">
            <div>
              <div className="flex justify-between text-xs text-ink-700 font-medium mb-1">
                <span>Monthly Website Visitors</span>
                <span className="font-mono font-bold text-ink">25,000</span>
              </div>
              <input type="range" min="1000" max="250000" step="5000" defaultValue="25000" className="w-full accent-pine" />
            </div>

            <div>
              <div className="flex justify-between text-xs text-ink-700 font-medium mb-1">
                <span>Average Deal Size / Customer LTV</span>
                <span className="font-mono font-bold text-ink-700">₹1,50,000</span>
              </div>
              <input type="range" min="10000" max="1000000" step="25000" defaultValue="150000" className="w-full accent-pine" />
            </div>

            <div>
              <div className="flex justify-between text-xs text-ink-700 font-medium mb-1">
                <span>Current Demo/Lead Conversion Rate</span>
                <span className="font-mono font-bold text-ink">1.5%</span>
              </div>
              <input type="range" min="0.5" max="5.0" step="0.1" defaultValue="1.5" className="w-full accent-pine" />
            </div>

            <p className="text-[11px] text-ink-500 italic">
              *Assumes conservative +25% organic & AI-search citation lift and +15% conversion lift from character-safe value proposition clarity.
            </p>
          </div>

          {/* Output Metric Cards */}
          <div className="md:col-span-6 space-y-4">
            <div className="p-4 rounded-md bg-paper-50 border border-line text-ink space-y-2">
              <span className="text-xs font-medium text-ink-500">Projected annual pipeline upside</span>
              <p className="font-mono text-3xl font-semibold tracking-tight">₹39,37,500</p>
              <p className="text-xs text-ink-500">Estimated net new revenue unlocked across Google Search and ChatGPT/Perplexity citations.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-paper-100 border border-line text-center">
                <span className="text-[11px] text-ink-500 font-mono block">Estimated ROI Multiple</span>
                <span className="text-2xl font-sans font-bold text-ink-700">78.8x</span>
                <span className="text-[10px] text-ink-400 block mt-0.5">vs ₹4,999 Diagnostic</span>
              </div>
              <div className="p-4 rounded-xl bg-paper-100 border border-line text-center">
                <span className="text-[11px] text-ink-500 font-mono block">New Qualified Leads / Mo</span>
                <span className="text-2xl font-sans font-bold text-ink">+16 Leads</span>
                <span className="text-[10px] text-ink-400 block mt-0.5">From captured buyer queries</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Comprehensive Feature Comparison Matrix */}
      <section className="border-t border-line pt-12">
        <div className="mb-8">
          <span className="label text-ink-700">Exhaustive Deliverables Matrix</span>
          <h2 className="font-sans text-3xl text-ink mt-1">
            Compare all features across tiers
          </h2>
          <p className="text-ink-700 text-sm mt-1">
            Every deliverable is grounded in verified DOM facts, code artifacts, and answer engine tests.
          </p>
        </div>

        <div className="overflow-x-auto border border-line rounded">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-paper-100 border-b border-line text-xs uppercase tracking-[0.04em] text-ink-500 font-semibold">
              <tr>
                <th className="py-3.5 px-4 w-1/3">Feature / Deliverable</th>
                <th className="py-3.5 px-3">Starter (₹1,499)</th>
                <th className="py-3.5 px-3 bg-paper-300/40 text-ink-700 font-bold">Diagnostic (₹4,999)</th>
                <th className="py-3.5 px-3">Bake-Off (₹11,999)</th>
                <th className="py-3.5 px-3">Pulse (₹1,999/mo)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line text-ink-700">
              {COMPARISON_FEATURES.map((section) => (
                <React.Fragment key={section.category}>
                  <tr className="bg-paper-100/70">
                    <td colSpan={5} className="py-2.5 px-4 font-bold text-xs uppercase tracking-[0.04em] text-ink font-mono">
                      {section.category}
                    </td>
                  </tr>
                  {section.items.map((item) => (
                    <tr key={item.name} className="hover:bg-paper-100/40 transition-colors">
                      <td className="py-3 px-4 font-medium text-ink">{item.name}</td>
                      <td className="py-3 px-3 text-ink-600">{item.starter}</td>
                      <td className="py-3 px-3 bg-paper-300/20 font-semibold text-ink-700">{item.diagnostic}</td>
                      <td className="py-3 px-3 font-medium text-ink">{item.bakeoff}</td>
                      <td className="py-3 px-3 text-ink-600">{item.pulse}</td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {hypotheses.length > 0 && (
        <section className="border-t border-line pt-12 space-y-4">
          <div>
            <span className="label">Planning ranges</span>
            <h2 className="font-sans text-3xl text-ink mt-1">Subscription assumptions</h2>
          </div>
          {hypothesisNote && <p className="text-sm text-ink-500 max-w-3xl">{hypothesisNote}</p>}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {hypotheses.map((plan) => {
              const range = plan.price_inr_monthly_range || plan.price_inr_annual_range;
              const suffix = plan.price_inr_annual_range ? '/yr' : '/mo';
              const label = range
                ? `₹${range[0].toLocaleString('en-IN')}–₹${range[1].toLocaleString('en-IN')}${suffix}`
                : 'Not priced';
              return (
                <article key={plan.id} className="card p-5 space-y-2">
                  <p className="label">{plan.buyer}</p>
                  <h3 className="text-xl text-ink">{plan.name}</h3>
                  <p className="font-mono text-sm text-ink">{label}</p>
                  <p className="text-xs text-ink-400">Not a checkout price</p>
                  <ul className="text-sm text-ink-600 space-y-1">
                    {plan.includes.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Indian Market Context & FAQ */}
      <section className="border-t border-line pt-12 space-y-8">
        <div>
          <span className="label text-ink-700">India Commercial FAQ</span>
          <h2 className="font-sans text-3xl text-ink mt-1">
            Frequently asked questions for Indian businesses & agencies
          </h2>
        </div>

        <div className="divide-y divide-line border-y border-line">
          {INDIA_MARKET_FAQS.map((faq, index) => (
            <article key={faq.q} className="py-5">
              <button
                type="button"
                onClick={() => setOpenFaq(openFaq === index ? null : index)}
                className="w-full text-left flex items-center justify-between gap-4 font-sans text-xl text-ink focus:outline-none"
              >
                <span>{faq.q}</span>
                <span className="font-mono text-sm text-ink-700 shrink-0">
                  {openFaq === index ? '−' : '+'}
                </span>
              </button>
              {openFaq === index && (
                <p className="mt-3 text-sm text-ink-700 leading-relaxed max-w-4xl animate-fadeIn">
                  {faq.a}
                </p>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* Direct Contact & Custom Scoping */}
      <section className="p-8 bg-paper-100 rounded border border-line text-center space-y-4">
        <h3 className="font-sans text-2xl text-ink">
          Need a multi-domain enterprise audit or custom RAG ingestion pipeline?
        </h3>
        <p className="text-sm text-ink-700 max-w-2xl mx-auto leading-relaxed">
          For agencies auditing 10+ client sites per month or enterprises requiring dedicated VPC inference, we provide custom enterprise scopes with volume billing and direct engineering SLA.
        </p>
        <div className="pt-2">
          <button
            type="button"
            onClick={() => onSelectPlan('enterprise')}
            className="btn-primary py-2.5 px-6 text-sm font-semibold rounded"
          >
            Inquire About Enterprise Custom
          </button>
        </div>
      </section>
    </div>
  );
}
