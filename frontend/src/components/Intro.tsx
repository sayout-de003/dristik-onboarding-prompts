import React from 'react';
import { Card, Section } from './ui';

const STEPS = [
  {
    n: '01',
    title: 'Scan the live site',
    body: 'Paste a public URL. Dristik reads headlines, pricing, proof, and structure the way a buyer and a search engine would.',
  },
  {
    n: '02',
    title: 'Test buyer questions',
    body: 'We check how clearly the site answers what you sell, who it is for, pricing, alternatives, trust, and results.',
  },
  {
    n: '03',
    title: 'Ship the fixes',
    body: 'You get a score, ranked findings, a 7 / 30 / 90-day plan, and drop-in code your developer can install.',
  },
];

const SCORES = [
  { title: 'Human', body: 'Can a visitor tell what you sell, at what price, and what to do next in five seconds?' },
  { title: 'Search', body: 'Can search engines discover and understand the pages we checked?' },
  { title: 'AI readiness', body: 'Can an answer engine extract what you offer from the pages we checked? Live citations are a separate measurement and remain unmeasured until the relevant engines are actually queried.' },
];

const FITS = [
  { title: 'SaaS & software', body: 'Pricing, ICP, and competitor comparisons that AI can quote.' },
  { title: 'Agencies & services', body: 'Proof, credentials, and a clear reason to enquire.' },
  { title: 'Commerce & local', body: 'Products, reviews, and trust signals that engines can extract.' },
];

export function Intro() {
  return (
    <div className="space-y-14 pt-6">
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STEPS.map((step) => (
          <Card key={step.n}>
            <p className="label mb-2">Step {step.n}</p>
            <h3 className="font-sans text-2xl text-ink">{step.title}</h3>
            <p className="mt-2 text-sm text-ink-700 leading-relaxed">{step.body}</p>
          </Card>
        ))}
      </section>

      <Section title="Three ways to assess readiness" description="Scores are based on the audit evidence and pages checked. Traffic, revenue impact and live AI citations are separate measurements—not assumptions.">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {SCORES.map((score) => (
            <Card key={score.title}>
              <h3 className="font-sans text-xl text-ink">{score.title}</h3>
              <p className="mt-2 text-sm text-ink-700 leading-relaxed">{score.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title="Who it is for">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {FITS.map((item) => (
            <Card key={item.title}>
              <h3 className="font-sans text-xl text-ink">{item.title}</h3>
              <p className="mt-2 text-sm text-ink-700 leading-relaxed">{item.body}</p>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}
