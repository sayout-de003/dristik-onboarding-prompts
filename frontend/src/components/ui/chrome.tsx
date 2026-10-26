import React, { useEffect, useId, useRef, useState } from 'react';
import { cn } from '../../lib/cn';

export function PageHeader({
  kicker,
  title,
  description,
  actions,
  children,
}: {
  kicker?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header data-page-header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
      <div className="min-w-0 max-w-2xl space-y-2">
        {kicker && <p className="label">{kicker}</p>}
        <h1 className="text-2xl sm:text-[1.75rem] font-semibold leading-tight text-ink tracking-tight">{title}</h1>
        {description && <p className="text-body text-ink-500 leading-relaxed">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section data-section className={cn('space-y-4', className)}>
      {(title || actions || description) && (
        <div className="flex items-end justify-between gap-4">
          <div className="min-w-0">
            {title && <h2 className="section-title">{title}</h2>}
            {description && <p className="mt-1 text-sm text-ink-500 leading-relaxed">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Card({
  children,
  className,
  padding = true,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
}) {
  return (
    <div
      onClick={onClick}
      className={cn('card', padding && 'p-4', className)}
    >
      {children}
    </div>
  );
}

export function SubNav<T extends string>({
  items,
  value,
  onChange,
  label = 'Section',
}: {
  items: Array<{ id: T; label: string }>;
  value: T;
  onChange: (id: T) => void;
  label?: string;
}) {
  return (
    <div className="subnav" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={value === item.id}
          onClick={() => onChange(item.id)}
          className={cn('subnav-item', value === item.id && 'is-active')}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function Dropdown({
  label,
  align = 'right',
  children,
  menuLabel,
}: {
  label: React.ReactNode;
  align?: 'left' | 'right';
  children: React.ReactNode;
  menuLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="nav-link inline-flex items-center px-2 py-1"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        {label}
        <span className="ml-1 text-[10px] text-ink-400" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={menuLabel}
          className={cn(
            'absolute top-full mt-2 min-w-[220px] card py-1.5 z-dropdown shadow-lg',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  onClick,
  children,
  danger,
}: {
  onClick?: () => void;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cn(
        'w-full text-left px-3.5 py-2 text-sm hover:bg-paper-100 transition-colors',
        danger ? 'text-bad' : 'text-ink-700',
      )}
    >
      {children}
    </button>
  );
}

export function MenuLabel({ children }: { children: React.ReactNode }) {
  return <p className="px-3.5 pt-2 pb-1 text-xs font-medium text-ink-500">{children}</p>;
}

export function PillarShell({
  kicker,
  title,
  description,
  score,
  scoreLabel,
  meta,
  metaLabel,
  tabs,
  activeTab,
  onTab,
  actions,
  children,
}: {
  kicker: string;
  title: string;
  description: string;
  score: React.ReactNode;
  scoreLabel: string;
  meta?: React.ReactNode;
  metaLabel?: string;
  tabs: Array<{ id: string; label: string }>;
  activeTab: string;
  onTab: (id: string) => void;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div data-pillar-shell className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
        <div className="max-w-2xl space-y-1.5">
          <p className="label">{kicker}</p>
          <h2 className="text-2xl font-semibold text-ink tracking-tight">{title}</h2>
          <p className="text-sm text-ink-500 leading-relaxed">{description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-4 self-start">
          {actions && <div className="flex items-center gap-2">{actions}</div>}
          <div className="flex items-stretch card overflow-hidden shrink-0">
            <div className="px-4 py-3 min-w-[112px]">
              <p className="label">{scoreLabel}</p>
              <p className="font-mono text-2xl font-semibold text-ink leading-none mt-1">{score}</p>
            </div>
            {metaLabel && (
              <div className="px-4 py-3 border-l border-line min-w-[128px]">
                <p className="label">{metaLabel}</p>
                <p className="text-sm font-medium text-ink mt-1.5">{meta}</p>
              </div>
            )}
          </div>
        </div>
      </div>
      <SubNav items={tabs} value={activeTab} onChange={(id) => onTab(id)} label={title} />
      {children}
    </div>
  );
}
