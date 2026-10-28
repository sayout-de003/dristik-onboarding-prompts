import { AppView, TabId } from '../types';

export const VIEWS = new Set<AppView>([
  'connect',
  'home',
  'continuous',
  'analytics',
  'grader',
  'pricing',
  'login',
  'signup',
  'forgot',
  'reset',
  'account',
  'contact',
  'team',
  'system',
]);

export const VIEW_LABELS: Record<AppView, string> = {
  connect: 'AI Connect',
  home: 'Audits',
  continuous: 'Continuous Intelligence',
  analytics: 'Delta Analytics',
  grader: 'Public grader',
  pricing: 'Pricing',
  login: 'Sign in',
  signup: 'Create workspace',
  forgot: 'Reset password',
  reset: 'New password',
  account: 'Account',
  contact: 'Contact',
  team: 'Team',
  system: 'Admin',
};

export const TAB_LABELS: Record<string, string> = {
  workflow: 'Workflow Engine',
  overview: 'Overview',
  crawl: 'Website Crawl',
  seo: 'SEO Space',
  search_intelligence: 'SEO Space',
  search_console: 'SEO Space',
  geo: 'GEO',
  ai_search_intelligence: 'GEO',
  ai_citations: 'GEO',
  ai_search: 'GEO',
  aeo: 'AEO',
  brand_entity_intelligence: 'AEO',
  cro: 'CRO',
  conversion_intelligence: 'CRO',
  website_experience: 'CRO',
  competitors: 'Competitor Analysis',
  perspectives: 'Competitor Analysis',
  lead_gen: 'Competitor Analysis',
  external_authority: 'External authority',
  pages: 'Page inspector',
  findings: 'Evidence ledger',
  costing: 'Cost ledger',
  costs: 'Cost ledger',
  patches: 'Patch pack',
  roadmap: 'Roadmap',
  verification: 'Verification',
  discover: 'Discover',
  decide: 'Decide',
  execute: 'Execute',
  prove: 'Prove',
  report: 'Report',
  plans: 'Plans',
};

const ANALYSIS_KEY = 'dristik_active_analysis_id';

export function readStoredAnalysisId(): string | null {
  try {
    return localStorage.getItem(ANALYSIS_KEY);
  } catch {
    return null;
  }
}

export function writeStoredAnalysisId(id: string | null) {
  try {
    if (id) localStorage.setItem(ANALYSIS_KEY, id);
    else localStorage.removeItem(ANALYSIS_KEY);
  } catch {
    /* storage unavailable */
  }
}

export function parseNavigation(
  loc: { hash: string; search: string } = window.location,
  storedId: string | null = readStoredAnalysisId(),
): { view: AppView; token?: string; analysisId?: string } {
  const searchParams = new URLSearchParams(loc.search);
  const searchAnalysisId = searchParams.get('analysis_id') || undefined;
  const raw = loc.hash.replace(/^#\/?/, '');
  if (!raw) {
    return { view: 'home', analysisId: searchAnalysisId || storedId || undefined };
  }
  const [path, qs] = raw.split('?');
  const view = (VIEWS.has(path as AppView) ? path : 'home') as AppView;
  const hashParams = new URLSearchParams(qs || '');
  const token = hashParams.get('token') || undefined;
  const analysisId = hashParams.get('analysis_id') || searchAnalysisId || storedId || undefined;
  return { view, token, analysisId };
}

export function tabMatches(current: TabId, id: TabId): boolean {
  if (current === id) return true;
  if (id === 'seo' && (current === 'search_intelligence' || current === 'search_console')) return true;
  if (id === 'geo' && (current === 'ai_search_intelligence' || current === 'ai_citations' || current === 'ai_search')) return true;
  if (id === 'aeo' && current === 'brand_entity_intelligence') return true;
  if (id === 'cro' && (current === 'conversion_intelligence' || current === 'website_experience')) return true;
  if (id === 'competitors' && (current === 'perspectives' || current === 'lead_gen')) return true;
  if ((id === 'costing' || id === 'costs') && (current === 'costing' || current === 'costs')) return true;
  return false;
}

export function syncAnalysisQuery(id: string | null) {
  const searchParams = new URLSearchParams(window.location.search);
  if (id) searchParams.set('analysis_id', id);
  else searchParams.delete('analysis_id');
  const query = searchParams.toString();
  const next = query
    ? `${window.location.pathname}?${query}${window.location.hash}`
    : `${window.location.pathname}${window.location.hash}`;
  window.history.replaceState(null, '', next);
  writeStoredAnalysisId(id);
}
