import React from 'react';
import { RoadmapItem } from '../types';
import { categoryLabel, display } from '../lib/format';
import { Card } from './ui';

interface RoadmapProps {
  days7: RoadmapItem[];
  days30: RoadmapItem[];
  days90: RoadmapItem[];
}

function Column({ title, items }: { title: string; items: RoadmapItem[] }) {
  return (
    <Card>
      <div className="flex items-baseline justify-between mb-4">
        <h3 className="font-sans text-2xl text-ink">{title}</h3>
        <span className="text-sm text-ink-400">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line bg-paper-100/60 px-4 py-5 text-sm text-ink-500"><p className="font-medium text-ink-700">No actions listed for this period</p><p className="mt-1">Review the findings and evidence before adding work to this time window.</p></div>
      ) : (
        <ol className="space-y-5">
          {items.map((item, index) => (
            <li key={`${item.title}-${index}`} className="pl-3 border-l border-line">
              <p className="text-xs text-ink-500">
                {categoryLabel(item.category)} · Impact {display(item.impact)} · Estimated effort {display(item.effort)}
              </p>
              <h4 className="mt-1 text-ink">{item.title}</h4>
              <p className="mt-1 text-sm text-ink-700 leading-relaxed">{display(item.description)}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export function Roadmap({ days7, days30, days90 }: RoadmapProps) {
  return (
    <div className="space-y-6">
      <div>
        <p className="label">Actions</p>
        <h2 className="font-sans text-3xl text-ink tracking-tight mt-1">Roadmap</h2>
        <p className="text-sm text-ink-500 mt-1">Prioritised actions grouped by time horizon. Start with the highest-impact items you can verify and complete; use the finding evidence to confirm each change.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Column title="7 days" items={days7} />
        <Column title="30 days" items={days30} />
        <Column title="90 days" items={days90} />
      </div>
    </div>
  );
}
