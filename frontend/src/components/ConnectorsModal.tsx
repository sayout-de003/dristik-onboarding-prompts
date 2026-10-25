import React, { useState, useEffect } from 'react';
import { Integration, ConnectorType } from '../types';

interface ConnectorsModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetUrl?: string;
  initialTab?: ConnectorType;
  onIntegrationAdded?: () => void;
  notice?: string | null;
}

export type ConnectorCategory = 'ALL' | 'ANALYTICS' | 'CRM' | 'GEO' | 'CMS' | 'SOCIAL' | 'MESSAGING' | 'DEVELOPER';

export interface ConnectorDefinition {
  id: ConnectorType;
  label: string;
  icon: string;
  category: 'ANALYTICS' | 'CRM' | 'GEO' | 'CMS' | 'SOCIAL' | 'MESSAGING' | 'DEVELOPER';
  desc: string;
  tag: string;
}

export const ALL_CONNECTORS: ConnectorDefinition[] = [
  { id: 'google_search_console', label: 'Search Console', icon: 'GSC', category: 'ANALYTICS', desc: 'Queries, CTR, Pos', tag: 'Google Search Console' },
  { id: 'google_analytics_4', label: 'Google Analytics', icon: 'GA4', category: 'ANALYTICS', desc: 'Funnels, Visitors', tag: 'Google Analytics 4' },
  { id: 'dataforseo', label: 'DataForSEO Index', icon: 'SEO', category: 'ANALYTICS', desc: 'SERP & Backlinks', tag: 'DataForSEO v3' },
  { id: 'crux', label: 'Google CrUX', icon: 'CWV', category: 'ANALYTICS', desc: 'Real User Vitals', tag: 'Chrome UX Report' },
  { id: 'crm', label: 'CRM & Revenue', icon: 'CRM', category: 'CRM', desc: 'HubSpot, SF, Stripe', tag: 'Pipeline Attribution' },
  { id: 'live_ai_search', label: 'Live AI Citations', icon: 'GEO', category: 'GEO', desc: 'Perplexity, ChatGPT', tag: 'Answer Engine Test' },
  { id: 'wordpress', label: 'WordPress', icon: 'W', category: 'CMS', desc: 'Auto Deploy', tag: 'REST & Plugin' },
  { id: 'github', label: 'GitHub', icon: 'GH', category: 'CMS', desc: 'Pull Requests', tag: 'GitHub API' },
  { id: 'shopify', label: 'Shopify', icon: 'S', category: 'CMS', desc: 'Liquid Theme', tag: 'Admin GraphQL' },
  { id: 'webflow', label: 'Webflow', icon: 'WF', category: 'CMS', desc: 'Embed Head', tag: 'Webflow Sites' },
  { id: 'generic', label: 'Generic Web', icon: 'URL', category: 'CMS', desc: 'Crawl & Patch Pack', tag: 'Direct Crawl' },
  { id: 'framer', label: 'Framer', icon: 'FR', category: 'CMS', desc: 'API readiness required', tag: 'Capability gated' },
  { id: 'wix', label: 'Wix', icon: 'WX', category: 'CMS', desc: 'API readiness required', tag: 'Capability gated' },
  { id: 'sanity', label: 'Sanity', icon: 'SN', category: 'CMS', desc: 'Project, dataset & documents', tag: 'Sanity HTTP API' },
  { id: 'openai_search', label: 'OpenAI APIs', icon: 'OA', category: 'GEO', desc: 'Model API, not search visibility', tag: 'OpenAI API' },
  { id: 'perplexity', label: 'Perplexity', icon: 'PX', category: 'GEO', desc: 'Live answer API handshake', tag: 'Perplexity API' },
  { id: 'claude', label: 'Claude', icon: 'CL', category: 'GEO', desc: 'Model API, search tool gated', tag: 'Anthropic API' },
  { id: 'gemini', label: 'Gemini', icon: 'GM', category: 'GEO', desc: 'Model API, grounding gated', tag: 'Gemini API' },
  { id: 'linkedin', label: 'LinkedIn', icon: 'IN', category: 'SOCIAL', desc: 'OAuth scopes govern publishing', tag: 'LinkedIn API' },
  { id: 'x', label: 'X', icon: 'X', category: 'SOCIAL', desc: 'OAuth scopes govern publishing', tag: 'X API' },
  { id: 'tiktok', label: 'TikTok', icon: 'TT', category: 'SOCIAL', desc: 'Approval and scopes required', tag: 'TikTok API' },
  { id: 'instagram', label: 'Instagram', icon: 'IG', category: 'SOCIAL', desc: 'Professional account required', tag: 'Instagram Graph API' },
  { id: 'whatsapp_business', label: 'WhatsApp Business', icon: 'WA', category: 'MESSAGING', desc: 'Phone Number ID + Meta token', tag: 'WhatsApp Cloud API' },
  { id: 'telegram', label: 'Telegram', icon: 'TG', category: 'MESSAGING', desc: 'Bot token handshake', tag: 'Telegram Bot API' },
  { id: 'slack', label: 'Slack', icon: 'SL', category: 'MESSAGING', desc: 'Bot token + granted scopes', tag: 'Slack API' },
  { id: 'hubspot', label: 'HubSpot', icon: 'HS', category: 'CRM', desc: 'Contacts API handshake', tag: 'HubSpot CRM API' },
  { id: 'salesforce', label: 'Salesforce', icon: 'SF', category: 'CRM', desc: 'Instance URL + access token', tag: 'Salesforce REST API' },
  { id: 'stripe', label: 'Stripe', icon: 'ST', category: 'CRM', desc: 'Account and revenue APIs', tag: 'Stripe API' },
];

const GoogleIcon = () => (
  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
    />
  </svg>
);

export const ConnectorsModal: React.FC<ConnectorsModalProps> = ({
  isOpen,
  onClose,
  targetUrl = '',
  initialTab,
  onIntegrationAdded,
  notice,
}) => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [activeTab, setActiveTab] = useState<ConnectorType>(initialTab || 'google_search_console');
  const [categoryFilter, setCategoryFilter] = useState<ConnectorCategory>('ALL');
  const [rightPanelTab, setRightPanelTab] = useState<'directory' | 'active'>('directory');
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Form states
  const [siteUrl, setSiteUrl] = useState(targetUrl || '');
  const [gscSiteUrl, setGscSiteUrl] = useState(targetUrl || '');
  const [gscCredentials, setGscCredentials] = useState('');
  const [gscAuthMode, setGscAuthMode] = useState<'oauth' | 'service_account'>('oauth');
  const [oauthProviders, setOauthProviders] = useState<Record<string, { configured: boolean; label: string; client_id_env: string; client_secret_env: string }>>({});
  const [wpUsername, setWpUsername] = useState('');
  const [wpAppPassword, setWpAppPassword] = useState('');
  const [wpPluginKey, setWpPluginKey] = useState('');

  const [ghRepo, setGhRepo] = useState('');
  const [ghToken, setGhToken] = useState('');
  const [ghBranch, setGhBranch] = useState('main');

  const [shopifyUrl, setShopifyUrl] = useState('');
  const [shopifyToken, setShopifyToken] = useState('');

  const [webflowSiteId, setWebflowSiteId] = useState('');
  const [webflowToken, setWebflowToken] = useState('');
  const [wpAuthMode, setWpAuthMode] = useState<'app_password' | 'plugin'>('app_password');

  // GA4 states
  const [ga4AuthMode, setGa4AuthMode] = useState<'oauth' | 'manual'>('oauth');
  const [ga4PropertyId, setGa4PropertyId] = useState('');
  const [ga4MeasurementId, setGa4MeasurementId] = useState('');
  const [ga4ApiKey, setGa4ApiKey] = useState('');

  // DataForSEO states
  const [dfsLogin, setDfsLogin] = useState('');
  const [dfsPassword, setDfsPassword] = useState('');

  // CrUX states
  const [cruxApiKey, setCruxApiKey] = useState('');

  // CRM states
  const [crmPlatform, setCrmPlatform] = useState<'hubspot' | 'salesforce' | 'stripe' | 'postgresql'>('hubspot');
  const [crmApiKey, setCrmApiKey] = useState('');

  // Live AI Search states
  const [aiEngine, setAiEngine] = useState<'perplexity' | 'openai' | 'claude' | 'gemini'>('perplexity');
  const [aiApiKey, setAiApiKey] = useState('');
  const [providerToken, setProviderToken] = useState('');
  const [providerResource, setProviderResource] = useState('');
  const [providerDataset, setProviderDataset] = useState('');
  const [providerApiUrl, setProviderApiUrl] = useState('');
  const [providerWebhookSecret, setProviderWebhookSecret] = useState('');
  const [resourcePreview, setResourcePreview] = useState<{ integrationId: string; resource: string; result: any } | null>(null);
  const [actionDrafts, setActionDrafts] = useState<Record<string, Record<string, string>>>({});
  const [providerRegistry, setProviderRegistry] = useState<Record<string, { implementation_status?: string; connection_status?: string; notes?: string | null }>>({});

  const fetchIntegrations = async () => {
    try {
      const res = await fetch('/api/v1/connectors');
      if (res.ok) {
        const data = await res.json();
        setIntegrations(data);
      }
    } catch (e) {
      console.error('Failed to load integrations', e);
    }
  };

  const fetchProviderRegistry = async () => {
    try {
      const res = await fetch('/api/v1/connectors/registry');
      if (!res.ok) return;
      const data = await res.json();
      const next: Record<string, { implementation_status?: string; connection_status?: string; notes?: string | null }> = {};
      for (const item of data.providers || []) next[item.id] = item;
      setProviderRegistry(next);
    } catch {
      // Keep the directory visible, but do not infer that a provider is configured.
    }
  };

  useEffect(() => {
    setProviderToken('');
    setProviderResource('');
    setProviderDataset('');
    setProviderApiUrl('');
    setProviderWebhookSecret('');
  }, [activeTab]);

  useEffect(() => {
    if (isOpen) {
      fetchIntegrations();
      fetchProviderRegistry();
      if (targetUrl) {
        setSiteUrl(targetUrl);
        setGscSiteUrl(targetUrl);
      }
      if (initialTab) {
        setActiveTab(initialTab);
      }
      if (notice) {
        const saved = /connected/i.test(notice);
        setStatusMessage(saved ? `✓ ${notice}` : notice);
        setRightPanelTab('active');
      }
    }
  }, [isOpen, targetUrl, initialTab, notice]);

  // Listen for Google / Connector OAuth callback from popup window / broadcast
  useEffect(() => {
    const onAuthSuccess = async (provider?: string) => {
      setLoading(false);
      setStatusMessage(`Signed in${provider ? ` with ${provider}` : ''}. Connected successfully.`);
      await fetchIntegrations();
      onIntegrationAdded?.();
    };

    const handleMessage = async (e: MessageEvent) => {
      if (e.data && (e.data.type === 'GSC_OAUTH_SUCCESS' || e.data.type === 'OAUTH_SUCCESS')) {
        await onAuthSuccess(e.data.provider);
      }
    };

    let bcGsc: BroadcastChannel | null = null;
    let bcConn: BroadcastChannel | null = null;
    try {
      bcGsc = new BroadcastChannel('dristik_gsc_auth');
      bcGsc.onmessage = async () => {
        await onAuthSuccess('Google Search Console');
      };
      bcConn = new BroadcastChannel('dristik_connector_oauth');
      bcConn.onmessage = async (e) => {
        await onAuthSuccess(e.data?.provider);
      };
    } catch (_) {}

    const handleStorage = async (e: StorageEvent) => {
      if ((e.key === 'dristik_gsc_auth_sync' || e.key === 'dristik_connector_oauth_sync') && e.newValue) {
        try {
          const payload = JSON.parse(e.newValue);
          localStorage.removeItem(e.key);
          await onAuthSuccess(payload?.provider);
        } catch (_) {}
      }
    };

    window.addEventListener('message', handleMessage);
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('message', handleMessage);
      window.removeEventListener('storage', handleStorage);
      if (bcGsc) try { bcGsc.close(); } catch (_) {}
      if (bcConn) try { bcConn.close(); } catch (_) {}
    };
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/v1/connectors/oauth/providers')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setOauthProviders(data.providers || data);
      })
      .catch(() => {});
  }, [isOpen]);

  const startOauth = (provider: string, params: Record<string, string>) => {
    const ready = oauthProviders[provider];
    if (ready && !ready.configured) {
      setStatusMessage(`Add ${ready.client_id_env} and ${ready.client_secret_env} to backend/.env, then restart the API.`);
      return;
    }
    setLoading(true);
    setStatusMessage('Taking you to Google in this tab. You will come back here when the connection is saved.');
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value));
    window.location.assign(`/api/v1/connectors/oauth/${provider}/authorize?${query.toString()}`);
  };

  const handleGoogleOAuth = () => {
    setLoading(true);
    setStatusMessage(null);
    const cleanDomain = (gscSiteUrl || siteUrl).replace('https://', '').replace('http://', '').split('/')[0];
    if (!cleanDomain) {
      setStatusMessage('Enter the site URL before signing in with Google.');
      setLoading(false);
      return;
    }
    const gscReady = oauthProviders['google_search_console'] || oauthProviders['google_analytics_4'];
    if (gscReady && !gscReady.configured) {
      setStatusMessage('Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, then restart the API.');
      setLoading(false);
      return;
    }
    setStatusMessage('Taking you to Google in this tab. Search Console will show as connected when you return.');
    window.location.assign(
      `/api/v1/connectors/oauth/google_search_console/authorize?domain=${encodeURIComponent(cleanDomain)}`,
    );
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    let payload: any = {
      provider: activeTab,
      name: `${activeTab.toUpperCase()} Integration (${siteUrl || ghRepo || 'Site'})`,
      target_url: siteUrl,
    };

    if (activeTab === 'google_search_console') {
      payload.provider = 'google_search_console';
      payload.target_url = gscSiteUrl || siteUrl;
      payload.name = `Google Search Console (${gscSiteUrl || siteUrl})`;
      payload.api_key = gscCredentials;
    } else if (activeTab === 'wordpress') {
      payload.target_url = siteUrl;
      payload.username = wpUsername;
      payload.app_password = wpAppPassword;
      payload.api_key = wpPluginKey;
    } else if (activeTab === 'github') {
      payload.repository = ghRepo;
      payload.github_token = ghToken;
      payload.branch = ghBranch;
      payload.target_url = siteUrl || `https://github.com/${ghRepo}`;
      payload.name = `GitHub: ${ghRepo}`;
    } else if (activeTab === 'shopify') {
      payload.target_url = shopifyUrl;
      payload.api_key = shopifyToken;
    } else if (activeTab === 'webflow') {
      payload.target_url = webflowSiteId;
      payload.api_key = webflowToken;
    } else if (activeTab === 'google_analytics_4') {
      payload.provider = 'google_analytics_4';
      payload.target_url = siteUrl;
      payload.name = `Google Analytics (${ga4PropertyId || ga4MeasurementId || siteUrl})`;
      let apiKeyPayload = ga4ApiKey;
      if (apiKeyPayload && apiKeyPayload.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(apiKeyPayload);
          if (ga4PropertyId && !parsed.property_id) {
            parsed.property_id = ga4PropertyId.trim();
          }
          if (ga4MeasurementId && !parsed.measurement_id) {
            parsed.measurement_id = ga4MeasurementId.trim();
          }
          apiKeyPayload = JSON.stringify(parsed);
        } catch {
          // keep original
        }
      } else if (!apiKeyPayload && (ga4PropertyId || ga4MeasurementId)) {
        apiKeyPayload = JSON.stringify({
          property_id: ga4PropertyId.trim(),
          measurement_id: ga4MeasurementId.trim(),
        });
      }
      payload.api_key = apiKeyPayload;
    } else if (activeTab === 'crm') {
      payload.provider = 'crm';
      payload.target_url = siteUrl;
      payload.name = `CRM: ${crmPlatform.toUpperCase()}`;
      payload.api_key = crmApiKey;
    } else if (activeTab === 'dataforseo') {
      payload.provider = 'dataforseo';
      payload.target_url = siteUrl;
      payload.name = `DataForSEO (${dfsLogin || siteUrl})`;
      payload.username = dfsLogin;
      payload.api_key = dfsPassword;
    } else if (activeTab === 'live_ai_search') {
      payload.provider = 'live_ai_search';
      payload.target_url = siteUrl;
      payload.name = `Live AI Search (${aiEngine.toUpperCase()})`;
      payload.api_key = aiApiKey;
    } else if (activeTab === 'crux') {
      payload.provider = 'crux';
      payload.target_url = siteUrl;
      payload.name = `Google CrUX (${siteUrl})`;
      payload.api_key = cruxApiKey;
    } else if (['framer', 'wix'].includes(activeTab)) {
      setStatusMessage('This provider is listed for visibility, but its approved API capability is not configured yet. No connection was saved.');
      setLoading(false);
      return;
    } else if (['sanity', 'openai_search', 'perplexity', 'claude', 'gemini', 'linkedin', 'x', 'tiktok', 'instagram', 'whatsapp_business', 'telegram', 'slack', 'hubspot', 'salesforce', 'stripe'].includes(activeTab)) {
      payload.api_key = providerToken;
      payload.access_token = providerToken;
      payload.webhook_secret = providerWebhookSecret || undefined;
      payload.api_url = providerApiUrl || undefined;
      payload.repository = providerResource || undefined;
      payload.branch = providerDataset || undefined;
      if (activeTab === 'slack' || activeTab === 'instagram') payload.account_id = providerResource || undefined;
      payload.target_url = providerApiUrl || siteUrl || ({
        sanity: 'https://api.sanity.io',
        openai_search: 'https://api.openai.com',
        perplexity: 'https://api.perplexity.ai',
        claude: 'https://api.anthropic.com',
        gemini: 'https://generativelanguage.googleapis.com',
        linkedin: 'https://api.linkedin.com',
        x: 'https://api.x.com',
        tiktok: 'https://open.tiktokapis.com',
        instagram: 'https://graph.facebook.com',
        whatsapp_business: 'https://graph.facebook.com',
        telegram: 'https://api.telegram.org',
        slack: 'https://slack.com',
        hubspot: 'https://api.hubapi.com',
        salesforce: providerApiUrl || '',
        stripe: 'https://api.stripe.com',
      } as Record<string, string>)[activeTab] || '';
      payload.name = `${activeTab.toUpperCase()} Integration`;
      if (activeTab === 'salesforce') payload.api_url = providerApiUrl;
    } else {
      payload.target_url = siteUrl;
    }

    try {
      const existing = integrations.find((integration) =>
        integration.provider === payload.provider &&
        (integration.target_url === payload.target_url ||
          (payload.repository && integration.repository === payload.repository))
      );
      const endpoint = existing
        ? `/api/v1/connectors/${existing.integration_id}/credentials`
        : '/api/v1/connectors/connect';
      const res = await fetch(endpoint, {
        method: existing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setStatusMessage(`✓ ${data.message || 'Connected successfully'}`);
        setRightPanelTab('active');
        await fetchIntegrations();
        onIntegrationAdded?.();
      } else {
        const detail = data.health?.message || data.detail || data.message || 'The connector was not saved.';
        setStatusMessage(detail);
        await fetchIntegrations();
      }
    } catch (err: any) {
      setStatusMessage(`Connection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async (integrationId: string) => {
    try {
      const res = await fetch(`/api/v1/connectors/${integrationId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setStatusMessage(data.detail || 'Disconnect failed.');
        return;
      }
      setStatusMessage('Disconnected and removed local connection.');
      await fetchIntegrations();
      await fetchProviderRegistry();
    } catch (e) {
      setStatusMessage('Disconnect failed: network error.');
    }
  };

  const handleConnectorAction = async (integrationId: string, action: 'test' | 'reconnect' | 'refresh' | 'revoke') => {
    setLoading(true);
    try {
      const route = action === 'test'
        ? `/api/v1/connectors/${integrationId}/health`
        : `/api/v1/connectors/${integrationId}/${action}`;
      const res = await fetch(route, { method: action === 'test' ? 'GET' : 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStatusMessage(data.detail || `${action} failed.`);
      } else if (action === 'test') {
        setStatusMessage(data.authenticated ? `✓ Live provider handshake passed: ${data.message || 'authenticated'}` : `Connection check failed: ${data.message || data.status || 'not authenticated'}`);
      } else {
        setStatusMessage(data.message || (data.success ? `${action} completed.` : `${action} did not complete.`));
      }
      await fetchIntegrations();
      await fetchProviderRegistry();
    } catch {
      setStatusMessage(`${action} failed: network error.`);
    } finally {
      setLoading(false);
    }
  };

  const handleReadResource = async (integrationId: string, resource: string) => {
    setLoading(true);
    setResourcePreview(null);
    try {
      const res = await fetch(`/api/v1/connectors/${integrationId}/resources/${encodeURIComponent(resource)}?limit=5`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStatusMessage(data.detail || `Could not read ${resource}.`);
        return;
      }
      setResourcePreview({ integrationId, resource, result: data });
      setStatusMessage(data.status === 'LIVE_DATA' ? `✓ Read ${data.resource_count ?? 0} live ${resource} records.` : (data.message || `Resource status: ${data.status || 'unavailable'}`));
    } catch {
      setStatusMessage(`Could not read ${resource}: network error.`);
    } finally {
      setLoading(false);
    }
  };

  const setActionDraftField = (integrationId: string, field: string, value: string) => {
    setActionDrafts((current) => ({
      ...current,
      [integrationId]: { ...(current[integrationId] || {}), [field]: value },
    }));
  };

  const handleProviderAction = async (integrationId: string, action: string, payload: Record<string, string>) => {
    const approved = window.confirm(`Dristik will send the "${action}" action to the connected provider. Continue?`);
    if (!approved) return;
    setLoading(true);
    try {
      const key = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const res = await fetch(`/api/v1/connectors/${integrationId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, idempotency_key: key, approval_confirmed: true, payload }),
      });
      const data = await res.json().catch(() => ({}));
      const result = data.result || data.detail || data;
      if (!res.ok) {
        setStatusMessage(typeof result === 'string' ? result : JSON.stringify(result));
      } else {
        setResourcePreview({ integrationId, resource: `action: ${action}`, result });
        setStatusMessage(result.status === 'SUCCEEDED' ? `✓ Provider accepted ${action}.` : (result.message || `${action}: ${result.status || 'unverified'}`));
      }
      await fetchIntegrations();
      await fetchProviderRegistry();
    } catch {
      setStatusMessage(`Action "${action}" failed at the network layer. Check the provider before retrying.`);
    } finally {
      setLoading(false);
    }
  };

  const filteredConnectors =
    categoryFilter === 'ALL'
      ? ALL_CONNECTORS
      : ALL_CONNECTORS.filter((c) => c.category === categoryFilter);

  const isConnectorConnected = (connId: ConnectorType) => {
    return integrations.some((integration) => {
      const status = String(integration.status || '').toLowerCase();
      const match =
        integration.provider === connId ||
        (connId === 'google_analytics_4' && (integration.provider as string) === 'google_analytics') ||
        (connId === 'google_analytics' && (integration.provider as string) === 'google_analytics_4');
      return match && status === 'connected';
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 scrim">
      <div className="relative w-full max-w-5xl sheet border border-line rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-line bg-paper-50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-paper-200 border border-line flex items-center justify-center text-ink shadow-xs">
              <svg className="w-5 h-5 text-ink-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-sans text-ink tracking-tight flex items-center gap-2">
                Connectors & Integrations Hub
                <span className="text-[11px] uppercase px-2 py-0.5 rounded bg-paper-200 text-ink-700 border border-line font-mono font-bold">
                  {ALL_CONNECTORS.length} Providers Listed
                </span>
              </h2>
              <p className="text-xs text-ink-500">
                Unify search metrics (GSC), visitor telemetry (GA4), sales revenue (CRM), AI citation testing, and CMS/Git remediation.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-ink-500 hover:text-ink p-1.5 rounded-lg border border-line bg-paper-50 hover:bg-paper-100 transition"
          >
            ✕
          </button>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Column: Platform Tabs & Configuration */}
          <div className="md:col-span-7 space-y-4">
            <div>
              {/* Category Filter Pills */}
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-ink-500 uppercase tracking-wider block">
                  Select Connector to Configure
                </label>
                <div className="flex items-center gap-1">
                  {(
                    [
                      { id: 'ALL', label: `All (${ALL_CONNECTORS.length})` },
                      { id: 'ANALYTICS', label: 'Search & Data' },
                      { id: 'CRM', label: 'Revenue' },
                      { id: 'GEO', label: 'AI Search' },
                      { id: 'CMS', label: 'CMS & Code' },
                      { id: 'SOCIAL', label: 'Social' },
                      { id: 'MESSAGING', label: 'Messaging' },
                      { id: 'DEVELOPER', label: 'Developer' },
                    ] as const
                  ).map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setCategoryFilter(cat.id)}
                      className={`text-[11px] px-2 py-0.5 rounded font-mono transition ${
                        categoryFilter === cat.id
                          ? 'bg-ink text-paper-50 font-semibold'
                          : 'bg-paper-100 text-ink-600 hover:bg-paper-200'
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Grid of all connectors */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {filteredConnectors.map((item) => {
                  const connected = isConnectorConnected(item.id);
                  const isSelected = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveTab(item.id)}
                      className={`relative flex flex-col items-start p-2.5 rounded-lg border text-xs font-medium transition text-left ${
                        isSelected
                          ? 'bg-paper-100 border-ink text-ink font-semibold shadow-xs ring-1 ring-ink/20'
                          : 'bg-paper-50 border-line text-ink-700 hover:border-ink-500'
                      }`}
                    >
                      <div className="flex items-center justify-between w-full mb-1">
                        <span className="font-mono text-[11px] font-bold px-1.5 py-0.5 rounded bg-paper-200 border border-line text-ink">
                          {item.icon}
                        </span>
                        {connected ? (
                          <span className="text-[10px] font-mono text-good font-bold flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-good"></span>
                            ACTIVE
                          </span>
                        ) : (
                          <span className="text-[9px] font-mono text-ink-400">
                            {providerRegistry[item.id]?.implementation_status === 'adapter_required' ? 'ADAPTER REQUIRED' : 'NOT CONNECTED'}
                          </span>
                        )}
                      </div>
                      <span className="font-bold leading-tight truncate w-full text-xs text-ink">{item.label}</span>
                      <span className="text-[10px] text-ink-400 font-mono mt-0.5 truncate w-full">{item.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Configuration Form for activeTab */}
            <form onSubmit={handleConnect} className="space-y-4 bg-paper-50 p-5 rounded-lg border border-line shadow-xs">
              {/* Google Search Console Form */}
              {activeTab === 'google_search_console' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Google Search Console:</span> Authorizes Dristik to pull verified search queries, real impressions, average rank positions, and click-through rates (CTR).
                  </div>

                  {/* Auth mode selector */}
                  <div className="flex items-center gap-2 p-1 bg-paper-100 rounded-lg border border-line w-fit">
                    <button
                      type="button"
                      onClick={() => setGscAuthMode('oauth')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        gscAuthMode === 'oauth'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      1-Click Google OAuth
                    </button>
                    <button
                      type="button"
                      onClick={() => setGscAuthMode('service_account')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        gscAuthMode === 'service_account'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      Service Account JSON
                    </button>
                  </div>

                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">
                      Website / GSC Property URL
                    </label>
                    <input
                      type="url"
                      value={gscSiteUrl}
                      onChange={(e) => setGscSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>

                  {gscAuthMode === 'oauth' ? (
                    <div className="space-y-3 pt-2">
                      <button
                        type="button"
                        onClick={handleGoogleOAuth}
                        disabled={loading}
                        className="w-full py-2.5 px-4 bg-paper-50 hover:bg-paper-50 text-ink font-semibold rounded border border-line text-sm transition flex items-center justify-center gap-2 shadow-xs cursor-pointer"
                      >
                        <GoogleIcon />
                        Sign in with Google Search Console
                      </button>
                      <p className="text-[11px] text-ink-500 text-center">
                        Requires read-only access to verify site search queries and impressions.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">
                        Service Account JSON Credentials
                      </label>
                      <textarea
                        value={gscCredentials}
                        onChange={(e) => setGscCredentials(e.target.value)}
                        placeholder='{"type": "service_account", "project_id": "...", "private_key": "..."}'
                        rows={4}
                        className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-xs text-ink font-mono placeholder:text-ink-500 focus:outline-none focus:border-pine"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Google Analytics Form */}
              {activeTab === 'google_analytics_4' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Google Analytics (GA4) Connector:</span> Measures landing pages, visitor engagement, bounce rates, custom event tags, and conversion funnels. Directly grounds CRO hypotheses into empirical percentages.
                  </div>

                  {/* Auth mode selector */}
                  <div className="flex items-center gap-2 p-1 bg-paper-100 rounded-lg border border-line w-fit">
                    <button
                      type="button"
                      onClick={() => setGa4AuthMode('oauth')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        ga4AuthMode === 'oauth'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      1-Click Google OAuth
                    </button>
                    <button
                      type="button"
                      onClick={() => setGa4AuthMode('manual')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        ga4AuthMode === 'manual'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      Property ID / Service Account
                    </button>
                  </div>

                  {ga4AuthMode === 'oauth' ? (
                    <div className="space-y-3 pt-2">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-ink-700 font-medium block mb-1">Target Website URL</label>
                          <input
                            type="url"
                            value={siteUrl}
                            onChange={(e) => setSiteUrl(e.target.value)}
                            placeholder="https://example.com"
                            className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-ink-700 font-medium block mb-1">GA4 Property ID (Optional)</label>
                          <input
                            type="text"
                            value={ga4PropertyId}
                            onChange={(e) => setGa4PropertyId(e.target.value)}
                            placeholder="properties/123456789"
                            className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => startOauth('google_analytics_4', { domain: siteUrl || targetUrl, property_id: ga4PropertyId })}
                        disabled={loading}
                        className="w-full py-2.5 px-4 bg-paper-50 hover:bg-paper-100 text-ink font-semibold rounded border border-line text-sm transition flex items-center justify-center gap-2 shadow-xs cursor-pointer"
                      >
                        <GoogleIcon />
                        Sign in with Google Analytics
                      </button>
                      <p className="text-[11px] text-ink-500 text-center">
                        Requires read-only access to verify visitor telemetry, sessions, and conversions.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Target Website URL</label>
                        <input
                          type="url"
                          value={siteUrl}
                          onChange={(e) => setSiteUrl(e.target.value)}
                          placeholder="https://example.com"
                          className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                          required
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-ink-700 font-medium block mb-1">GA4 Property ID</label>
                          <input
                            type="text"
                            value={ga4PropertyId}
                            onChange={(e) => setGa4PropertyId(e.target.value)}
                            placeholder="properties/123456789"
                            className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                            required
                          />
                        </div>
                        <div>
                          <label className="text-xs text-ink-700 font-medium block mb-1">Measurement ID (Optional)</label>
                          <input
                            type="text"
                            value={ga4MeasurementId}
                            onChange={(e) => setGa4MeasurementId(e.target.value)}
                            placeholder="G-XXXXXXXXXX"
                            className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Service Account JSON / API Key</label>
                        <textarea
                          value={ga4ApiKey}
                          onChange={(e) => setGa4ApiKey(e.target.value)}
                          placeholder='{"type": "service_account", "property_id": "123456789", ...}'
                          rows={3}
                          className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-xs text-ink font-mono placeholder:text-ink-500 focus:outline-none focus:border-pine"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* DataForSEO Form */}
              {activeTab === 'dataforseo' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">DataForSEO SERP & Backlink Graph:</span> Pulls live monthly search volume, keyword difficulty, competitor SERP rankings, and verified referring domains.
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Target Website URL</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">DataForSEO API Login</label>
                      <input
                        type="text"
                        value={dfsLogin}
                        onChange={(e) => setDfsLogin(e.target.value)}
                        placeholder="login@company.com"
                        className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">API Password / Key</label>
                      <input
                        type="password"
                        value={dfsPassword}
                        onChange={(e) => setDfsPassword(e.target.value)}
                        placeholder="••••••••••••••••"
                        className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                        required
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Google CrUX Form */}
              {activeTab === 'crux' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Google CrUX (Chrome User Experience Report):</span> Pulls actual 75th-percentile field user metrics (LCP, INP, CLS). This is not the Google sign-in used by Search Console. It needs a Chrome UX Report API key (CRUX_API_KEY on the server, or paste one here).
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Target Website URL</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Google Cloud / PageSpeed API Key (Optional)</label>
                    <input
                      type="password"
                      value={cruxApiKey}
                      onChange={(e) => setCruxApiKey(e.target.value)}
                      placeholder="AIzaSy... (Leave blank for public quota)"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                    />
                  </div>
                </div>
              )}

              {/* CRM & Revenue Intelligence Form */}
              {activeTab === 'crm' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">CRM & Revenue Connector:</span> Unifies website visitor journeys with sales pipeline, deal velocity, MQL/SQL quality scores, and closed revenue attribution.
                  </div>
                  {crmPlatform !== 'postgresql' && (
                    <button
                      type="button"
                      onClick={() => startOauth(crmPlatform, { domain: siteUrl })}
                      className="w-full py-2.5 px-4 rounded border border-line bg-paper-50 text-sm font-semibold capitalize"
                    >
                      Sign in with {crmPlatform}
                    </button>
                  )}
                  {crmPlatform === 'postgresql' && (
                    <p className="text-xs text-ink-500">PostgreSQL has no OAuth sign-in. Use a connection string.</p>
                  )}
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Select CRM Platform</label>
                    <div className="grid grid-cols-4 gap-2">
                      {(['hubspot', 'salesforce', 'stripe', 'postgresql'] as const).map((plat) => (
                        <button
                          key={plat}
                          type="button"
                          onClick={() => setCrmPlatform(plat)}
                          className={`p-2 rounded border text-xs font-mono font-bold capitalize transition ${
                            crmPlatform === plat
                              ? 'bg-paper-100 border-ink text-ink font-semibold shadow-xs'
                              : 'bg-paper-50 border-line text-ink-500 hover:text-ink'
                          }`}
                        >
                          {plat}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Target Website / App Domain</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">
                      {crmPlatform === 'hubspot'
                        ? 'HubSpot Private App Access Token (pat-na1-...)'
                        : crmPlatform === 'salesforce'
                        ? 'Salesforce Connected App Client Secret / Token'
                        : crmPlatform === 'stripe'
                        ? 'Stripe Restricted API Key (rk_live_...)'
                        : 'PostgreSQL Connection URI (postgresql://...)'}
                    </label>
                    <input
                      type="password"
                      value={crmApiKey}
                      onChange={(e) => setCrmApiKey(e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                </div>
              )}

              {/* Live AI Citations Form */}
              {activeTab === 'live_ai_search' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Live AI Search & Citations (GEO):</span> Dispatches live queries to Perplexity, ChatGPT Search, Gemini, and Claude to verify exact citation rank and grounded quotes.
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Primary Answer Engine</label>
                    <div className="grid grid-cols-4 gap-2">
                      {(['perplexity', 'openai', 'claude', 'gemini'] as const).map((eng) => (
                        <button
                          key={eng}
                          type="button"
                          onClick={() => setAiEngine(eng)}
                          className={`p-2 rounded border text-xs font-mono font-bold capitalize transition ${
                            aiEngine === eng
                              ? 'bg-paper-100 border-ink text-ink font-semibold shadow-xs'
                              : 'bg-paper-50 border-line text-ink-500 hover:text-ink'
                          }`}
                        >
                          {eng}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Target Website Domain</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">
                      {aiEngine === 'perplexity'
                        ? 'Perplexity API Key (pplx-...)'
                        : aiEngine === 'openai'
                        ? 'OpenAI API Key (sk-...)'
                        : aiEngine === 'claude'
                        ? 'Anthropic API Key (sk-ant-...)'
                        : 'Google Gemini API Key (AIzaSy...)'}
                    </label>
                    <input
                      type="password"
                      value={aiApiKey}
                      onChange={(e) => setAiApiKey(e.target.value)}
                      placeholder="••••••••••••••••••••••••••••••••"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                </div>
              )}

              {/* WordPress Form */}
              {activeTab === 'wordpress' && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 p-1 bg-paper-100 rounded-lg border border-line w-fit">
                    <button
                      type="button"
                      onClick={() => setWpAuthMode('app_password')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        wpAuthMode === 'app_password'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      Application Passwords (Native)
                    </button>
                    <button
                      type="button"
                      onClick={() => setWpAuthMode('plugin')}
                      className={`px-3 py-1 text-xs rounded font-medium transition ${
                        wpAuthMode === 'plugin'
                          ? 'bg-paper-50 text-ink shadow-xs border border-line font-semibold'
                          : 'text-ink-500 hover:text-ink'
                      }`}
                    >
                      Dristik Plugin
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => startOauth('wordpress', { domain: siteUrl })}
                    className="w-full py-2.5 px-4 rounded border border-line bg-paper-50 text-sm font-semibold"
                  >
                    Sign in with WordPress.com
                  </button>

                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">WordPress Site URL</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://mysite.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>

                  {wpAuthMode === 'app_password' ? (
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Admin Username</label>
                        <input
                          type="text"
                          value={wpUsername}
                          onChange={(e) => setWpUsername(e.target.value)}
                          placeholder="admin"
                          className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine"
                          required
                        />
                      </div>
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Application Password</label>
                        <input
                          type="password"
                          value={wpAppPassword}
                          onChange={(e) => setWpAppPassword(e.target.value)}
                          placeholder="abcd efgh ijkl mnop"
                          className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                          required
                        />
                      </div>
                    </div>
                  ) : (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">Dristik Plugin Secret Key</label>
                      <input
                        type="password"
                        value={wpPluginKey}
                        onChange={(e) => setWpPluginKey(e.target.value)}
                        placeholder="dristik_sec_••••••••••••"
                        className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                        required
                      />
                    </div>
                  )}
                </div>
              )}

              {/* GitHub Form */}
              {activeTab === 'github' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">GitHub Automation:</span> Automatically opens clean, tested Pull Requests against your repo with exact code patches for Schema, metadata, robots.txt, and canonical tags.
                  </div>
                  <button
                    type="button"
                    onClick={() => startOauth('github', { domain: siteUrl, repository: ghRepo })}
                    className="w-full py-2.5 px-4 rounded border border-line bg-paper-50 text-sm font-semibold"
                  >
                    Sign in with GitHub
                  </button>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Repository (owner/repo)</label>
                    <input
                      type="text"
                      value={ghRepo}
                      onChange={(e) => setGhRepo(e.target.value)}
                      placeholder="acme-corp/marketing-website"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Personal Access Token (classic / fine-grained)</label>
                    <input
                      type="password"
                      value={ghToken}
                      onChange={(e) => setGhToken(e.target.value)}
                      placeholder="ghp_••••••••••••••••••••••••••••••••"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Target Production Branch</label>
                    <input
                      type="text"
                      value={ghBranch}
                      onChange={(e) => setGhBranch(e.target.value)}
                      placeholder="main"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                    />
                  </div>
                </div>
              )}

              {/* Shopify Form */}
              {activeTab === 'shopify' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Shopify Liquid Theme:</span> Injects structured JSON-LD and canonical product tags via the Shopify Admin GraphQL API into <code>theme.liquid</code>.
                  </div>
                  <button
                    type="button"
                    onClick={() => startOauth('shopify', { shop: shopifyUrl, domain: shopifyUrl })}
                    className="w-full py-2.5 px-4 rounded border border-line bg-paper-50 text-sm font-semibold"
                  >
                    Sign in with Shopify
                  </button>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Store URL</label>
                    <input
                      type="text"
                      value={shopifyUrl}
                      onChange={(e) => setShopifyUrl(e.target.value)}
                      placeholder="mystore.myshopify.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Admin API Access Token</label>
                    <input
                      type="password"
                      value={shopifyToken}
                      onChange={(e) => setShopifyToken(e.target.value)}
                      placeholder="shpat_••••••••••••••••••••••••••••••••"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                </div>
              )}

              {/* Webflow Form */}
              {activeTab === 'webflow' && (
                <div className="space-y-4">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Webflow Custom Code:</span> Injects automated head code and entity schemas via the Webflow REST API v2.
                  </div>
                  <button
                    type="button"
                    onClick={() => startOauth('webflow', { domain: siteUrl })}
                    className="w-full py-2.5 px-4 rounded border border-line bg-paper-50 text-sm font-semibold"
                  >
                    Sign in with Webflow
                  </button>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Webflow Site ID</label>
                    <input
                      type="text"
                      value={webflowSiteId}
                      onChange={(e) => setWebflowSiteId(e.target.value)}
                      placeholder="6482f... (Found in Site Settings)"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Webflow API Token</label>
                    <input
                      type="password"
                      value={webflowToken}
                      onChange={(e) => setWebflowToken(e.target.value)}
                      placeholder="wfl_••••••••••••"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                </div>
              )}

              {/* Generic Website Form */}
              {activeTab === 'generic' && (
                <div className="space-y-3">
                  <div className="text-xs text-ink-700 leading-relaxed bg-paper-100 p-3 rounded border border-line">
                    <span className="text-ink font-semibold">Generic Website (Crawl-Only):</span> Zero credentials required. Dristik audits public HTML and exports ready-to-deploy Developer Patch Packs (ZIP) with 15-minute install guides.
                  </div>
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">Public Website URL</label>
                    <input
                      type="url"
                      value={siteUrl}
                      onChange={(e) => setSiteUrl(e.target.value)}
                      placeholder="https://example.com"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine"
                      required
                    />
                  </div>
                </div>
              )}

              {['sanity', 'openai_search', 'perplexity', 'claude', 'gemini', 'linkedin', 'x', 'tiktok', 'instagram', 'whatsapp_business', 'telegram', 'slack', 'hubspot', 'salesforce', 'stripe'].includes(activeTab) && (
                <div className="space-y-3 rounded-lg border border-line bg-paper-50 p-4">
                  <div>
                    <div className="text-sm font-semibold text-ink">Provider API credentials</div>
                    <p className="mt-1 text-xs text-ink-500">
                      Credentials are sent to the Dristik API and stored encrypted. The first check is a live authentication handshake; it does not imply publishing, analytics, or search-citation capabilities are enabled.
                    </p>
                  </div>
                  {['linkedin', 'slack', 'instagram', 'whatsapp_business', 'hubspot', 'salesforce', 'stripe'].includes(activeTab) && oauthProviders[activeTab]?.configured && (
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => startOauth(activeTab, { domain: providerApiUrl || siteUrl, shop: providerApiUrl || siteUrl, repository: providerResource })}
                      className="w-full py-2.5 px-4 border border-line rounded text-sm font-semibold text-ink hover:bg-paper-100 disabled:opacity-50"
                    >
                      Connect with {activeTab === 'whatsapp_business' ? 'Meta' : activeTab[0].toUpperCase() + activeTab.slice(1)} OAuth
                    </button>
                  )}
                  <div>
                    <label className="text-xs text-ink-700 font-medium block mb-1">API key / authorized access token</label>
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={providerToken}
                      onChange={(e) => setProviderToken(e.target.value)}
                      placeholder="Paste provider-issued credential"
                      className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink placeholder:text-ink-500 focus:outline-none focus:border-pine font-mono"
                      required
                    />
                  </div>
                  {activeTab === 'sanity' && (
                    <>
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Sanity project ID</label>
                        <input value={providerResource} onChange={(e) => setProviderResource(e.target.value)} placeholder="Project ID" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" required />
                      </div>
                      <div>
                        <label className="text-xs text-ink-700 font-medium block mb-1">Dataset</label>
                        <input value={providerDataset} onChange={(e) => setProviderDataset(e.target.value)} placeholder="production" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" required />
                      </div>
                    </>
                  )}
                  {activeTab === 'whatsapp_business' && (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">WhatsApp Phone Number ID</label>
                      <input value={providerResource} onChange={(e) => setProviderResource(e.target.value)} placeholder="Phone Number ID from Meta" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" required />
                    </div>
                  )}
                  {activeTab === 'salesforce' && (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">Salesforce instance URL</label>
                      <input type="url" value={providerApiUrl} onChange={(e) => setProviderApiUrl(e.target.value)} placeholder="https://your-domain.my.salesforce.com" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" required />
                    </div>
                  )}
                  {activeTab !== 'salesforce' && (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">Optional API / account URL</label>
                      <input type="url" value={providerApiUrl} onChange={(e) => setProviderApiUrl(e.target.value)} placeholder="Only if your provider requires a custom endpoint" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" />
                    </div>
                  )}
                  {activeTab === 'telegram' && (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">Telegram webhook secret token (optional)</label>
                      <input type="password" autoComplete="new-password" value={providerWebhookSecret} onChange={(e) => setProviderWebhookSecret(e.target.value)} placeholder="Must match the secret configured in setWebhook" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" />
                      <p className="mt-1 text-[10px] text-ink-500">Dristik validates this token on incoming webhook requests. Register the public webhook URL and the same secret with Telegram.</p>
                    </div>
                  )}
                  {activeTab !== 'sanity' && activeTab !== 'whatsapp_business' && (
                    <div>
                      <label className="text-xs text-ink-700 font-medium block mb-1">Optional account or resource ID</label>
                      <input value={providerResource} onChange={(e) => setProviderResource(e.target.value)} placeholder="Required only by some provider APIs" className="w-full bg-paper-50 border border-line rounded px-3 py-2 text-sm text-ink" />
                    </div>
                  )}
                </div>
              )}

              {statusMessage && (
                <div
                  className={`p-3 rounded text-xs font-mono border ${
                    statusMessage.startsWith('✓')
                      ? 'bg-good/10 border-good/30 text-good'
                      : 'bg-paper-200 border-line text-ink-700'
                  }`}
                >
                  {statusMessage}
                </div>
              )}

              {!(activeTab === 'google_search_console' && gscAuthMode === 'oauth') && !(activeTab === 'google_analytics_4' && ga4AuthMode === 'oauth') && (
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 btn-primary text-white font-semibold rounded text-sm transition disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer"
                >
                  {loading ? 'Authenticating & Verifying...' : `Connect ${activeTab.toUpperCase()}`}
                </button>
              )}
            </form>
          </div>

          {/* Right Column: All Connectors Directory + Active Connections */}
          <div className="md:col-span-5 space-y-4">
            {/* Tab switch between Directory and Active */}
            <div className="flex items-center justify-between border-b border-line pb-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRightPanelTab('directory')}
                  className={`text-xs font-semibold uppercase tracking-wider transition pb-0.5 ${
                    rightPanelTab === 'directory'
                      ? 'text-ink border-b-2 border-ink'
                      : 'text-ink-400 hover:text-ink-700'
                  }`}
                >
                  Directory ({ALL_CONNECTORS.length})
                </button>
                <span className="text-ink-300">|</span>
                <button
                  type="button"
                  onClick={() => setRightPanelTab('active')}
                  className={`text-xs font-semibold uppercase tracking-wider transition pb-0.5 ${
                    rightPanelTab === 'active'
                      ? 'text-ink border-b-2 border-ink'
                      : 'text-ink-400 hover:text-ink-700'
                  }`}
                >
                  Active ({integrations.length})
                </button>
              </div>
              <button
                onClick={fetchIntegrations}
                className="text-xs text-ink-700 font-medium hover:underline"
              >
                Refresh
              </button>
            </div>

            {/* View A: Full Directory of ALL Connectors */}
            {rightPanelTab === 'directory' && (
              <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
                {ALL_CONNECTORS.map((conn) => {
                  const isConnected = isConnectorConnected(conn.id);
                  const isCurrent = activeTab === conn.id;
                  return (
                    <div
                      key={conn.id}
                      className={`p-3 rounded-lg border text-xs transition flex items-center justify-between gap-3 ${
                        isCurrent
                          ? 'sheet border-ink shadow-xs ring-1 ring-ink/20'
                          : 'bg-paper-50 border-line hover:border-ink-300'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-8 h-8 rounded bg-paper-200 border border-line flex items-center justify-center font-mono font-bold text-ink shrink-0">
                          {conn.icon}
                        </span>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-ink truncate">{conn.label}</span>
                            <span className="text-[9px] uppercase font-mono px-1.5 py-0.2 rounded bg-paper-200 text-ink-500">
                              {conn.category}
                            </span>
                          </div>
                          <p className="text-[10px] text-ink-500 truncate">{conn.desc}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {isConnected ? (
                          <span className="text-[10px] font-mono text-good font-bold flex items-center gap-1 bg-good/10 px-2 py-0.5 rounded border border-good/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-good"></span>
                            LINKED
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setActiveTab(conn.id)}
                            className="text-[11px] font-mono font-medium text-ink-700 hover:underline px-2 py-0.5 rounded border border-line bg-paper-100"
                          >
                            Configure →
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* View B: Active Configured Connections */}
            {rightPanelTab === 'active' && (
              <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
                {integrations.length === 0 ? (
                  <div className="p-8 text-center bg-paper-50 rounded-lg border border-line text-ink-500 text-xs">
                    No platforms connected yet. Select a connector from the directory to begin.
                  </div>
                ) : (
                  integrations.map((integ) => (
                    <div
                      key={integ.integration_id}
                      className="p-4 rounded-lg sheet border border-line hover:border-ink-500 transition space-y-2 shadow-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${String(integ.status).toLowerCase() === 'connected' ? 'bg-good' : 'bg-paper-300 border border-line'}`}></span>
                          <span className="text-sm font-semibold text-ink truncate max-w-[180px]">
                            {integ.name}
                          </span>
                        </div>
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-paper-100 text-ink-700 border border-line">
                          {integ.provider}
                        </span>
                      </div>

                      <div className="text-xs text-ink-500 truncate font-mono">
                        {integ.target_url || integ.repository}
                      </div>

                      {(({
                        hubspot: ['contacts', 'companies', 'deals'],
                        salesforce: ['accounts', 'leads', 'opportunities', 'campaigns'],
                        stripe: ['customers', 'subscriptions', 'payment_intents'],
                        sanity: ['documents'],
                      } as Record<string, string[]>)[integ.provider] || []).length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {(({
                            hubspot: ['contacts', 'companies', 'deals'],
                            salesforce: ['accounts', 'leads', 'opportunities', 'campaigns'],
                            stripe: ['customers', 'subscriptions', 'payment_intents'],
                            sanity: ['documents'],
                          } as Record<string, string[]>)[integ.provider] || []).map((resource) => (
                            <button key={resource} type="button" disabled={loading || String(integ.status).toLowerCase() !== 'connected'} onClick={() => handleReadResource(integ.integration_id, resource)} className="rounded border border-line px-2 py-1 text-[10px] text-ink-700 hover:bg-paper-100 disabled:opacity-40">
                              Read {resource.replace('_', ' ')}
                            </button>
                          ))}
                        </div>
                      )}

                      {String(integ.status).toLowerCase() === 'connected' && ['telegram', 'slack', 'x', 'whatsapp_business', 'instagram'].includes(integ.provider) && (
                        <div className="rounded border border-line bg-paper-50 p-3 space-y-2">
                          <div className="text-[10px] uppercase tracking-wide font-semibold text-ink-500">Explicitly confirmed provider action</div>
                          {integ.provider === 'telegram' && (
                            <>
                              <input value={actionDrafts[integ.integration_id]?.chat_id || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'chat_id', e.target.value)} placeholder="Telegram chat ID" className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <textarea value={actionDrafts[integ.integration_id]?.text || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'text', e.target.value)} placeholder="Message text" rows={2} className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <button type="button" disabled={loading || !actionDrafts[integ.integration_id]?.chat_id || !actionDrafts[integ.integration_id]?.text} onClick={() => handleProviderAction(integ.integration_id, 'send_message', { chat_id: actionDrafts[integ.integration_id]?.chat_id || '', text: actionDrafts[integ.integration_id]?.text || '' })} className="rounded border border-line px-2 py-1 text-[11px] text-ink-700 disabled:opacity-40">Send Telegram message…</button>
                            </>
                          )}
                          {integ.provider === 'slack' && (
                            <>
                              <input value={actionDrafts[integ.integration_id]?.channel || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'channel', e.target.value)} placeholder="Slack channel ID" className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <textarea value={actionDrafts[integ.integration_id]?.text || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'text', e.target.value)} placeholder="Message text" rows={2} className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <button type="button" disabled={loading || !actionDrafts[integ.integration_id]?.channel || !actionDrafts[integ.integration_id]?.text} onClick={() => handleProviderAction(integ.integration_id, 'post_message', { channel: actionDrafts[integ.integration_id]?.channel || '', text: actionDrafts[integ.integration_id]?.text || '' })} className="rounded border border-line px-2 py-1 text-[11px] text-ink-700 disabled:opacity-40">Post Slack message…</button>
                            </>
                          )}
                          {integ.provider === 'x' && (
                            <>
                              <textarea value={actionDrafts[integ.integration_id]?.text || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'text', e.target.value)} placeholder="Post text" rows={3} className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <button type="button" disabled={loading || !actionDrafts[integ.integration_id]?.text} onClick={() => handleProviderAction(integ.integration_id, 'publish_post', { text: actionDrafts[integ.integration_id]?.text || '' })} className="rounded border border-line px-2 py-1 text-[11px] text-ink-700 disabled:opacity-40">Publish on X…</button>
                            </>
                          )}
                          {integ.provider === 'whatsapp_business' && (
                            <>
                              <input value={actionDrafts[integ.integration_id]?.to || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'to', e.target.value)} placeholder="Recipient phone number (international format)" className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <input value={actionDrafts[integ.integration_id]?.template_name || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'template_name', e.target.value)} placeholder="Approved WhatsApp template name" className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <button type="button" disabled={loading || !actionDrafts[integ.integration_id]?.to || !actionDrafts[integ.integration_id]?.template_name} onClick={() => handleProviderAction(integ.integration_id, 'send_template', { to: actionDrafts[integ.integration_id]?.to || '', template_name: actionDrafts[integ.integration_id]?.template_name || '' })} className="rounded border border-line px-2 py-1 text-[11px] text-ink-700 disabled:opacity-40">Send approved template…</button>
                            </>
                          )}
                          {integ.provider === 'instagram' && (
                            <>
                              <input value={actionDrafts[integ.integration_id]?.media_url || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'media_url', e.target.value)} placeholder="Public HTTPS image URL" className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <textarea value={actionDrafts[integ.integration_id]?.caption || ''} onChange={(e) => setActionDraftField(integ.integration_id, 'caption', e.target.value)} placeholder="Caption (optional)" rows={2} className="w-full rounded border border-line bg-paper-50 px-2 py-1.5 text-xs text-ink" />
                              <button type="button" disabled={loading || !actionDrafts[integ.integration_id]?.media_url?.startsWith('https://')} onClick={() => handleProviderAction(integ.integration_id, 'publish_image', { media_url: actionDrafts[integ.integration_id]?.media_url || '', caption: actionDrafts[integ.integration_id]?.caption || '' })} className="rounded border border-line px-2 py-1 text-[11px] text-ink-700 disabled:opacity-40">Publish image…</button>
                            </>
                          )}
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-2 border-t border-line text-[11px]">
                        <span className={`font-mono uppercase ${String(integ.status).toLowerCase() === 'connected' ? 'text-good' : 'text-ink-500'}`}>{integ.status}</span>
                        <div className="flex flex-wrap justify-end gap-2">
                          <button type="button" disabled={loading} onClick={() => handleConnectorAction(integ.integration_id, 'test')} className="text-ink-700 hover:underline disabled:opacity-50">Test</button>
                          <button type="button" disabled={loading} onClick={() => handleConnectorAction(integ.integration_id, 'reconnect')} className="text-ink-700 hover:underline disabled:opacity-50">Reconnect</button>
                          {integ.settings?.auth_mode === 'oauth2' && (
                            <button type="button" disabled={loading} onClick={() => handleConnectorAction(integ.integration_id, 'refresh')} className="text-ink-700 hover:underline disabled:opacity-50">Refresh token</button>
                          )}
                          <button type="button" disabled={loading} onClick={() => handleConnectorAction(integ.integration_id, 'revoke')} className="text-ink-700 hover:underline disabled:opacity-50">Forget credentials</button>
                          <button type="button" disabled={loading} onClick={() => handleDisconnect(integ.integration_id)} className="text-bad hover:underline disabled:opacity-50">Delete</button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
                {resourcePreview && (
                  <div className="rounded-lg border border-line bg-paper-50 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-ink">Live resource preview: {resourcePreview.resource}</div>
                      <button type="button" onClick={() => setResourcePreview(null)} className="text-xs text-ink-500 hover:text-ink">Close</button>
                    </div>
                    <div className="text-[10px] font-mono text-ink-500">
                      {resourcePreview.result.status || 'UNKNOWN'} · {resourcePreview.result.resource_count ?? 'count not reported'} records
                    </div>
                    <pre className="max-h-56 overflow-auto rounded bg-paper-100 p-2 text-[10px] leading-relaxed text-ink-700 whitespace-pre-wrap break-words">{JSON.stringify(resourcePreview.result.records || resourcePreview.result, null, 2)}</pre>
                    {resourcePreview.result.evidence?.response_sha256 && (
                      <div className="text-[9px] font-mono text-ink-400 break-all">SHA-256: {resourcePreview.result.evidence.response_sha256}</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Security Guarantee Note */}
            <div className="p-4 rounded-lg bg-paper-100 border border-line text-xs text-ink-700 space-y-1.5 shadow-xs">
              <div className="font-semibold text-ink flex items-center gap-1.5">
                <span> Least-Privilege Isolation</span>
              </div>
              <p className="text-[11px] text-ink-500 leading-relaxed">
                Connectors run within isolated environments. Search queries and CRM revenue metrics are encrypted with AES/HMAC keys and never transmitted to public search engines.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
