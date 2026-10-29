import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  CircleAlert,
  ChevronDown,
  ChevronRight,
  Copy,
  Eye,
  EyeOff,
  History,
  Layers,
  Loader2,
  MessageSquare,
  PlugZap,
  Radio,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
} from 'lucide-react';

type Provider = { id: string; provider: string; label: string; model: string; status: string; created_at: number };
type Task = { id: string; goal: string; status: string; created_at: number; execution_started?: boolean };
type AIConnection = { id: string; name: string; connection_email: string; grant_profile: string; status: string; expires_at?: number | null; last_used_at?: number | null };
type IssuedCredential = { id: string; name?: string; connection_email: string; api_key: string; grant_profile?: string; scopes?: string[]; mcp_endpoint?: string; mcp_endpoint_is_absolute?: boolean; mcp_config?: { url: string; headers: Record<string, string> }; key_display_policy?: string };
type ToolInventoryItem = { name: string; scope: string };
type OnboardingPrompts = Partial<Record<ClientTab, string>>;
type OnboardingBundle = { provider: ClientTab; prompt: string; prompts: OnboardingPrompts; tool_inventory: ToolInventoryItem[]; next_step: string; execution_policy?: string };
type OnboardingKit = OnboardingBundle & { connection: IssuedCredential };
type SavedPrompt = { connectionId: string; prompts: OnboardingPrompts; tools: ToolInventoryItem[]; nextStep: string };
type ConnectionEvent = {
  id: string;
  event: string;
  created_at: number;
  direction?: 'inbound' | 'outbound' | 'internal';
  method?: string;
  tool?: string | null;
  arguments?: Record<string, unknown>;
  summary?: string;
  status?: string;
  error?: string | null;
  metadata?: Record<string, unknown>;
};
type CapabilityItem = { name: string; status: string; description: string };

type ClientTab = 'claude' | 'chatgpt' | 'grok' | 'gemini' | 'deepseek' | 'kimi' | 'openrouter' | 'custom';

const CLIENT_TABS: ClientTab[] = ['claude', 'chatgpt', 'grok', 'gemini', 'deepseek', 'kimi', 'openrouter', 'custom'];
const CLIENT_LABELS: Record<ClientTab, string> = {
  claude: 'Claude',
  chatgpt: 'ChatGPT',
  grok: 'Grok',
  gemini: 'Gemini',
  deepseek: 'DeepSeek',
  kimi: 'Kimi',
  openrouter: 'OpenRouter',
  custom: 'Custom',
};
const DEFAULT_ONBOARDING_GOAL = 'Connect this AI to Dristik and verify authorized two-way messaging.';

const PROFILE_DETAILS: Record<string, { label: string; description: string; scopeSummary: string }> = {
  read_only: {
    label: 'Read only',
    description: 'Read-only access: discover 105 specialist agents, DAG pipeline hierarchy, audit state, evidence graph, findings, and completed reports.',
    scopeSummary: 'capabilities.list, templates.list, agents.list, pipeline.inspect, audit.read, report.read, findings.read, evidence.read, blackboard.read, connector.read',
  },
  audit_operator: {
    label: 'Audit operator',
    description: 'Launch canonical website audits, monitor progress, inspect blackboard evidence, submit external claims, track live citations, export reports, and record tasks.',
    scopeSummary: 'audit.create, audit.read, audit.cancel, blackboard.read, claim.submit, citations.track, report.read, report.export, findings.read, evidence.read, tasks.create',
  },
  workflow_admin: {
    label: 'Workflow admin',
    description: 'Full audit operator capabilities plus executing specific DAG nodes and pipeline workflow sections as the sovereign Brain.',
    scopeSummary: 'agent.execute, workflow.execute, pipeline.inspect, claim.submit, citations.track, provider.invoke, providers.list + all operator permissions',
  },
  full_access: {
    label: 'Full Dristik access',
    description: 'Complete sovereign control across 105 specialist agents, DAG execution graph, blackboard memory, live citation engine, and model providers.',
    scopeSummary: '* (Complete organization-scoped access across all audit & intelligence capabilities)',
  },
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'include', ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  return data as T;
}

const PROVIDERS = [
  { value: 'anthropic', label: 'Claude (Anthropic)', placeholder: 'claude-sonnet-4-20250514' },
  { value: 'openai', label: 'OpenAI', placeholder: 'gpt-4.1-mini' },
  { value: 'gemini', label: 'Google Gemini', placeholder: 'gemini-2.5-flash' },
  { value: 'grok', label: 'Grok (xAI)', placeholder: 'grok-3-mini' },
  { value: 'deepseek', label: 'DeepSeek', placeholder: 'deepseek-chat' },
  { value: 'kimi', label: 'Kimi (Moonshot AI)', placeholder: 'moonshot-v1-8k' },
  { value: 'openrouter', label: 'OpenRouter', placeholder: 'provider/model' },
];

export function UniversalConnectView() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [aiConnections, setAiConnections] = useState<AIConnection[]>([]);
  const [connectionName, setConnectionName] = useState('Claude — Full Audit Access');
  const [connectionProvider, setConnectionProvider] = useState<ClientTab>('claude');
  const [onboardingGoal, setOnboardingGoal] = useState(DEFAULT_ONBOARDING_GOAL);
  const [grantProfile, setGrantProfile] = useState('full_access');
  const [issuedCredential, setIssuedCredential] = useState<IssuedCredential | null>(null);
  const [issuedPrompts, setIssuedPrompts] = useState<OnboardingPrompts>({});
  const [issuedTools, setIssuedTools] = useState<ToolInventoryItem[]>([]);
  const [issuedNextStep, setIssuedNextStep] = useState('');
  const [savedPrompt, setSavedPrompt] = useState<SavedPrompt | null>(null);
  const [savedPromptTab, setSavedPromptTab] = useState<ClientTab>('claude');
  const [showApiKey, setShowApiKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [activeClientTab, setActiveClientTab] = useState<ClientTab>('claude');
  const [activeActivityId, setActiveActivityId] = useState<string | null>(null);
  const [activityEvents, setActivityEvents] = useState<ConnectionEvent[]>([]);
  const [trafficFilter, setTrafficFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [testingConnectionId, setTestingConnectionId] = useState<string | null>(null);
  const [probeType, setProbeType] = useState<'ping' | 'audits_list' | 'pipeline_inspect' | 'agents_list' | 'custom_message'>('audits_list');
  const [probeMessage, setProbeMessage] = useState('Inspect earlier audits for this account');
  const [probeBusy, setProbeBusy] = useState(false);
  const [probeResult, setProbeResult] = useState<Record<string, unknown> | null>(null);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([]);
  const [showCapabilities, setShowCapabilities] = useState(false);
  const [provider, setProvider] = useState('anthropic');
  const [label, setLabel] = useState('My AI provider');
  const [model, setModel] = useState('claude-sonnet-4-20250514');
  const [apiKey, setApiKey] = useState('');
  const [selected, setSelected] = useState('');
  const [prompt, setPrompt] = useState('Review this website audit and summarize evidence-backed issues.');
  const [websiteUrl, setWebsiteUrl] = useState('https://example.com');
  const [result, setResult] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const sendTestProbe = async (connectionId: string) => {
    setProbeBusy(true);
    setProbeResult(null);
    setError('');
    try {
      const res = await request<Record<string, unknown>>(`/api/v1/connect/ai-connections/${connectionId}/test-message`, {
        method: 'POST',
        body: JSON.stringify({
          message: probeMessage,
          probe_type: probeType,
          tool_arguments: probeType === 'audits_list' ? { limit: 10 } : {},
        }),
      });
      setProbeResult(res);
      const act = await request<{ events: ConnectionEvent[] }>(`/api/v1/connect/ai-connections/${connectionId}/activity`);
      setActivityEvents(act.events);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send test message');
    } finally {
      setProbeBusy(false);
    }
  };

  const refresh = useCallback(async () => {
    try {
      const [p, t, c] = await Promise.all([
        request<{ providers: Provider[] }>('/api/v1/connect/providers'),
        request<{ tasks: Task[] }>('/api/v1/connect/tasks'),
        request<{ connections: AIConnection[] }>('/api/v1/connect/ai-connections'),
      ]);
      setProviders(p.providers);
      setTasks(t.tasks);
      setAiConnections(c.connections);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load Connect data.');
    }
  }, [selected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Robust, fail-safe clipboard utility that works over HTTP and HTTPS
  const copyToClipboard = async (value: string, keyLabel?: string) => {
    let copied = false;
    // 1. Try modern async clipboard API in secure contexts
    if (typeof navigator !== 'undefined' && navigator.clipboard && typeof navigator.clipboard.writeText === 'function' && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        copied = true;
      } catch {
        copied = false;
      }
    }
    // 2. Fallback to offscreen textarea DOM execCommand copy
    if (!copied && typeof document !== 'undefined') {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.style.position = 'fixed';
        textarea.style.left = '-999999px';
        textarea.style.top = '-999999px';
        textarea.style.opacity = '0';
        textarea.setAttribute('readonly', '');
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        textarea.setSelectionRange(0, 999999);
        copied = document.execCommand('copy');
        document.body.removeChild(textarea);
      } catch {
        copied = false;
      }
    }
    if (copied) {
      if (keyLabel) {
        setCopiedKey(keyLabel);
        setTimeout(() => setCopiedKey((curr) => (curr === keyLabel ? null : curr)), 2500);
      }
      setNotice('Copied to clipboard. Treat connection credentials as secrets.');
      setError('');
    } else {
      setError('Clipboard access was blocked by the browser. Please select the text and copy manually.');
    }
  };

  const copyAllCredentials = () => {
    if (!issuedCredential) return;
    const endpoint = issuedCredential.mcp_endpoint || '/api/v1/mcp';
    const sseEndpoint = endpoint.replace(/\/$/, '') + '/sse';
    const block = [
      '# ========================================================',
      '# Dristik Universal AI Connection Credentials',
      '# ========================================================',
      `Connection Identity: ${issuedCredential.connection_email}`,
      `Dristik API Key:     ${issuedCredential.api_key}`,
      `MCP Endpoint:        ${endpoint}`,
      `MCP SSE Endpoint:    ${sseEndpoint}`,
      `Grant Profile:       ${issuedCredential.grant_profile || grantProfile}`,
      '',
      '# HTTP Authentication Headers',
      `Authorization: Bearer ${issuedCredential.api_key}`,
      `X-Dristik-Connection-Email: ${issuedCredential.connection_email}`,
      '',
      '# MCP Client Configuration (Claude Desktop / Cursor / Windsurf)',
      JSON.stringify(
        {
          mcpServers: {
            dristik: {
              url: endpoint,
              headers: {
                Authorization: `Bearer ${issuedCredential.api_key}`,
                'X-Dristik-Connection-Email': issuedCredential.connection_email,
              },
            },
          },
        },
        null,
        2,
      ),
    ].join('\n');
    void copyToClipboard(block, 'all');
  };

  const rememberIssuedPrompt = (bundle: OnboardingBundle) => {
    setIssuedPrompts(bundle.prompts || {});
    setIssuedTools(bundle.tool_inventory || []);
    setIssuedNextStep(bundle.next_step || '');
    if (bundle.provider) setActiveClientTab(bundle.provider);
  };

  const clearIssuedPrompt = () => {
    setIssuedPrompts({});
    setIssuedTools([]);
    setIssuedNextStep('');
  };

  const fetchOnboardingPrompt = (connectionId: string, provider: ClientTab) =>
    request<OnboardingBundle & { connection_id: string }>('/api/v1/connect/ai-onboarding/prompt', {
      method: 'POST',
      body: JSON.stringify({ connection_id: connectionId, provider, goal: onboardingGoal }),
    });

  const createAIConnection = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    setIssuedCredential(null);
    clearIssuedPrompt();
    try {
      const created = await request<OnboardingKit>('/api/v1/connect/ai-onboarding/kit', {
        method: 'POST',
        body: JSON.stringify({
          name: connectionName,
          provider: connectionProvider,
          grant_profile: grantProfile,
          expires_in_days: 90,
          goal: onboardingGoal,
        }),
      });
      setIssuedCredential(created.connection);
      rememberIssuedPrompt(created);
      setNotice('Dristik connection created. Copy the API key now, then copy the onboarding prompt into the selected AI. The key is shown only once and is left out of the prompt.');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create AI connection.');
    } finally {
      setBusy(false);
    }
  };

  const rotateAIConnection = async (id: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    setIssuedCredential(null);
    try {
      const rotated = await request<IssuedCredential>(`/api/v1/connect/ai-connections/${id}/rotate`, { method: 'POST' });
      setIssuedCredential(rotated);
      setNotice('Connection key rotated. The previous key is invalid; update the AI client now. The onboarding prompt does not contain the key.');
      try {
        rememberIssuedPrompt(await fetchOnboardingPrompt(id, connectionProvider));
      } catch (promptError) {
        clearIssuedPrompt();
        setError(promptError instanceof Error ? promptError.message : 'Key rotated, but the onboarding prompt could not be loaded.');
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not rotate connection key.');
    } finally {
      setBusy(false);
    }
  };

  const revokeAIConnection = async (id: string) => {
    if (!window.confirm('Revoke this AI connection? Its API key will stop working immediately.')) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await request(`/api/v1/connect/ai-connections/${id}/revoke`, { method: 'POST' });
      setNotice('AI connection revoked.');
      if (issuedCredential?.id === id) {
        setIssuedCredential(null);
        clearIssuedPrompt();
      }
      if (savedPrompt?.connectionId === id) setSavedPrompt(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not revoke connection.');
    } finally {
      setBusy(false);
    }
  };

  const validateAIConnection = async () => {
    if (!issuedCredential) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await request<{ valid: boolean }>('/api/v1/connect/ai-connections/validate', {
        method: 'POST',
        body: JSON.stringify({ connection_email: issuedCredential.connection_email, api_key: issuedCredential.api_key }),
      });
      setNotice('Dristik successfully validated this connection identity and key.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Credential validation failed.');
    } finally {
      setBusy(false);
    }
  };

  const viewActivity = async (id: string) => {
    if (activeActivityId === id) {
      setActiveActivityId(null);
      setActivityEvents([]);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await request<{ events: ConnectionEvent[] }>(`/api/v1/connect/ai-connections/${id}/activity`);
      setActiveActivityId(id);
      setActivityEvents(res.events);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load connection activity.');
    } finally {
      setBusy(false);
    }
  };

  const loadCapabilities = async () => {
    if (capabilities.length > 0) {
      setShowCapabilities(!showCapabilities);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await request<{ capabilities: CapabilityItem[] }>('/api/v1/connect/capabilities');
      setCapabilities(res.capabilities);
      setShowCapabilities(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load capabilities.');
    } finally {
      setBusy(false);
    }
  };

  const chooseProvider = (value: string) => {
    setProvider(value);
    const item = PROVIDERS.find((p) => p.value === value);
    if (item) setModel(item.placeholder);
  };

  const addProvider = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await request<Provider>('/api/v1/connect/providers', {
        method: 'POST',
        body: JSON.stringify({ provider, label, model, api_key: apiKey }),
      });
      setApiKey('');
      setSelected('');
      setNotice('Credential encrypted and saved. Select the provider, then run a test prompt before choosing it for an audit.');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save provider.');
    } finally {
      setBusy(false);
    }
  };

  const invoke = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError('');
    setNotice('');
    setResult('');
    try {
      const response = await request<{ text: string; provider: string; model: string; execution_status: string }>(
        `/api/v1/connect/providers/${selected}/invoke`,
        { method: 'POST', body: JSON.stringify({ prompt, max_tokens: 1200 }) },
      );
      setResult(response.text || '(Provider returned an empty response)');
      setNotice(`Live response received from ${response.provider} · ${response.model}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Provider invocation failed.');
    } finally {
      setBusy(false);
    }
  };

  const createTask = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const task = await request<Task>('/api/v1/connect/tasks', {
        method: 'POST',
        body: JSON.stringify({ goal: prompt, inputs: { source: 'connect-ui', url: websiteUrl } }),
      });
      setNotice(`Task ${task.id} was durably recorded. You can submit it to the canonical Dristik audit pipeline from the task actions.`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create task.');
    } finally {
      setBusy(false);
    }
  };

  const executeAudit = async (taskId: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const providerQuery = selected ? '?model_provider_id=' + encodeURIComponent(selected) : '';
      const response = await request<{ audit: { analysis_id: string; website_url: string } }>(
        '/api/v1/connect/tasks/' + taskId + '/execute-audit' + providerQuery,
        { method: 'POST' },
      );
      setNotice('Dristik audit started for ' + response.audit.website_url + '. Analysis ID: ' + response.audit.analysis_id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start audit.');
    } finally {
      setBusy(false);
    }
  };

  const renderClientGuide = () => {
    if (!issuedCredential) return null;
    const ep = issuedCredential.mcp_endpoint || '/api/v1/mcp';
    const email = issuedCredential.connection_email;
    const key = issuedCredential.api_key;

    const snippets: Record<ClientTab, { title: string; desc: string; code: string; lang: string }> = {
      claude: {
        title: 'Claude Desktop / Claude Code',
        desc: 'Add Dristik as a native MCP server in Claude Desktop or Claude Code to let Claude act as the sovereign Brain over all 105 specialist agents.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServers: {
              dristik: {
                url: ep,
                headers: {
                  Authorization: `Bearer ${key}`,
                  'X-Dristik-Connection-Email': email,
                },
              },
            },
          },
          null,
          2,
        ),
      },
      chatgpt: {
        title: 'ChatGPT (Custom GPT / Actions)',
        desc: 'In your GPT Action schema, configure the MCP POST gateway with your connection identity and Bearer API key.',
        lang: 'yaml',
        code: `openapi: 3.1.0\ninfo:\n  title: Dristik Autonomous Growth OS\n  version: 1.0.0\nservers:\n  - url: ${ep.replace(/\/mcp$/, '')}\npaths:\n  /mcp:\n    post:\n      summary: Dristik MCP Gateway\n      operationId: invokeDristik\n      parameters:\n        - name: X-Dristik-Connection-Email\n          in: header\n          required: true\n          schema:\n            type: string\n            default: "${email}"`,
      },
      grok: {
        title: 'Grok (xAI / Direct Gateway)',
        desc: 'Call Dristik directly from xAI / Grok scripts or tools to inspect DAG pipelines, trigger multi-engine citation checks, or run audits.',
        lang: 'bash',
        code: `curl -X POST "${ep}" \\\n  -H "Authorization: Bearer ${key}" \\\n  -H "X-Dristik-Connection-Email: ${email}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"jsonrpc":"2.0","id":"grok-1","method":"tools/call","params":{"name":"dristik_pipeline_inspect","arguments":{}}}'`,
      },
      gemini: {
        title: 'Google Gemini (AI Studio / CLI)',
        desc: 'Connect Gemini to Dristik via MCP or Function Calling to orchestrate the 105 specialist agents and inspect the shared blackboard.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServer: {
              name: 'dristik',
              url: ep,
              headers: {
                Authorization: `Bearer ${key}`,
                'X-Dristik-Connection-Email': email,
              },
            },
          },
          null,
          2,
        ),
      },
      deepseek: {
        title: 'DeepSeek (Cursor / Windsurf / OpenCode)',
        desc: 'Configure DeepSeek via Cursor or Windsurf MCP settings to grant sovereign control over Dristik audits, evidence graphs, and code patches.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServers: {
              dristik: {
                url: ep,
                headers: {
                  Authorization: `Bearer ${key}`,
                  'X-Dristik-Connection-Email': email,
                },
              },
            },
          },
          null,
          2,
        ),
      },
      kimi: {
        title: 'Kimi (Moonshot AI)',
        desc: 'Connect Kimi to Dristik via Moonshot function calling or MCP to analyze audits, submit reasoned claims, and verify evidence.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServers: {
              dristik: {
                url: ep,
                headers: {
                  Authorization: `Bearer ${key}`,
                  'X-Dristik-Connection-Email': email,
                },
              },
            },
          },
          null,
          2,
        ),
      },
      openrouter: {
        title: 'OpenRouter',
        desc: 'Use this when the selected client reaches Dristik through an OpenRouter-compatible tool host. Confirm that host can send the Dristik MCP headers.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServers: {
              dristik: {
                url: ep,
                headers: {
                  Authorization: `Bearer ${key}`,
                  'X-Dristik-Connection-Email': email,
                },
              },
            },
          },
          null,
          2,
        ),
      },
      custom: {
        title: 'Custom MCP client',
        desc: 'Use this for any other client that can call the Dristik MCP endpoint with the connection identity and bearer key.',
        lang: 'json',
        code: JSON.stringify(
          {
            mcpServers: {
              dristik: {
                url: ep,
                headers: {
                  Authorization: `Bearer ${key}`,
                  'X-Dristik-Connection-Email': email,
                },
              },
            },
          },
          null,
          2,
        ),
      },
    };

    const current = snippets[activeClientTab];
    const onboardingPrompt = issuedPrompts[activeClientTab] || '';

    return (
      <div className="mt-4 rounded-xl border border-line bg-surface/70 p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink">
            <Sparkles size={14} className="text-emerald-600" /> Connect Your AI Client
          </div>
          <span className="text-[11px] text-ink-400">Two-Way Integration Ready</span>
        </div>
        <p className="mb-3 text-xs text-ink-500">
          Select the AI client, copy its onboarding prompt, and paste that prompt into the AI. Put the API key only in the client's secret field. The prompt does not include the key.
        </p>

        {/* Client selector tabs */}
        <div className="flex flex-wrap gap-1.5 border-b border-line pb-2.5">
          {CLIENT_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveClientTab(tab)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                activeClientTab === tab ? 'bg-ink text-white shadow-sm' : 'border border-line bg-surface text-ink hover:bg-surface-2'
              }`}
            >
              {CLIENT_LABELS[tab]}
            </button>
          ))}
        </div>

        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-ink">Copy/paste prompt for {CLIENT_LABELS[activeClientTab]}</p>
            <button
              type="button"
              disabled={!onboardingPrompt}
              onClick={() => void copyToClipboard(onboardingPrompt, `prompt_${activeClientTab}`)}
              className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-surface-2 disabled:opacity-50"
            >
              {copiedKey === `prompt_${activeClientTab}` ? (
                <>
                  <Check size={12} className="text-emerald-600" /> Prompt copied
                </>
              ) : (
                <>
                  <Copy size={12} /> Copy prompt
                </>
              )}
            </button>
          </div>
          <textarea
            readOnly
            aria-label={`Copy/paste onboarding prompt for ${CLIENT_LABELS[activeClientTab]}`}
            value={onboardingPrompt || 'The onboarding prompt has not been loaded for this client.'}
            className="input min-h-40 w-full resize-y font-mono text-[11px] leading-relaxed"
          />
          {issuedTools.length > 0 && (
            <p className="text-[11px] text-ink-500">Authorized tools: {issuedTools.map((tool) => tool.name).join(', ')}</p>
          )}
          {issuedNextStep && <p className="text-[11px] text-ink-500">{issuedNextStep}</p>}
        </div>

        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-ink">{current.title}</p>
            <button
              type="button"
              onClick={() => void copyToClipboard(current.code, `config_${activeClientTab}`)}
              className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-surface-2"
            >
              {copiedKey === `config_${activeClientTab}` ? (
                <>
                  <Check size={12} className="text-emerald-600" /> Copied!
                </>
              ) : (
                <>
                  <Copy size={12} /> Copy config
                </>
              )}
            </button>
          </div>
          <p className="text-[11px] text-ink-500">{current.desc}</p>
          <pre className="max-h-52 overflow-x-auto rounded-lg border border-line bg-surface p-2.5 font-mono text-[11px] leading-relaxed text-ink">
            {current.code}
          </pre>
        </div>
      </div>
    );
  };

  return (
    <main className="mx-auto max-w-6xl space-y-7 p-4 sm:p-8">
      <header className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-emerald-600">
          <PlugZap size={18} /> DRISTIK CONNECT
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink">Universal AI & software connections</h1>
        <p className="max-w-3xl text-sm leading-6 text-ink-500">
          Connect external AI clients (Claude, ChatGPT, Grok, Gemini, DeepSeek, Kimi) to orchestrate Dristik as the sovereign Brain, or delegate inference to encrypted tenant model providers. Credentials are encrypted at rest with tenant isolation.
        </p>
        <div className="flex flex-wrap gap-2 text-xs text-ink-500">
          <span className="rounded-full border border-line px-3 py-1">
            <ShieldCheck className="mr-1 inline" size={13} />
            Tenant-scoped
          </span>
          <span className="rounded-full border border-line px-3 py-1">
            105 Specialist Agents · 12 Domains · DAG Pipeline
          </span>
          <span className="rounded-full border border-line px-3 py-1">
            Claude · ChatGPT · Gemini · Grok · DeepSeek · Kimi · OpenRouter
          </span>
        </div>
      </header>

      {error && (
        <div role="alert" className="flex gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          <CircleAlert size={18} />
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="flex gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
          <CheckCircle2 size={18} />
          {notice}
        </div>
      )}

      {/* External AI Connection Section */}
      <section className="card space-y-4 p-5">
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} />
          <h2 className="text-lg font-semibold text-ink">Connect an external AI to Dristik</h2>
        </div>
        <p className="max-w-3xl text-sm leading-6 text-ink-500">
          Dristik issues a connection identity, a one-time API key, and a provider-specific copy/paste prompt. Paste the prompt into Claude, ChatGPT, Grok, Gemini, DeepSeek, Kimi, OpenRouter, or a custom client. Put the API key only in that client's secret field.
        </p>

        <form onSubmit={createAIConnection} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_190px_auto] md:items-end">
          <label className="block space-y-1 text-sm">
            <span className="text-ink-600">Connection name</span>
            <input
              className="input w-full"
              value={connectionName}
              onChange={(e) => setConnectionName(e.target.value)}
              required
              maxLength={120}
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="text-ink-600">AI client</span>
            <select
              className="input w-full"
              value={connectionProvider}
              onChange={(e) => {
                const next = e.target.value as ClientTab;
                setConnectionProvider(next);
                setActiveClientTab(next);
              }}
            >
              {CLIENT_TABS.map((tab) => (
                <option key={tab} value={tab}>{CLIENT_LABELS[tab]}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1 text-sm">
            <span className="text-ink-600">Permission profile</span>
            <select className="input w-full" value={grantProfile} onChange={(e) => setGrantProfile(e.target.value)}>
              <option value="read_only">Read only</option>
              <option value="audit_operator">Audit operator</option>
              <option value="workflow_admin">Workflow admin</option>
              <option value="full_access">Full Dristik access</option>
            </select>
          </label>
          <button
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? <Loader2 className="animate-spin" size={16} /> : <PlugZap size={16} />} Generate credentials
          </button>
          <label className="col-span-full block space-y-1 text-sm">
            <span className="text-ink-600">Onboarding goal</span>
            <input
              className="input w-full"
              value={onboardingGoal}
              onChange={(e) => setOnboardingGoal(e.target.value)}
              maxLength={3000}
            />
          </label>
          <div className="col-span-full rounded-lg border border-line bg-surface/50 p-3 text-xs">
            <p className="font-semibold text-ink">
              {PROFILE_DETAILS[grantProfile]?.label}:{' '}
              <span className="font-normal text-ink-500">{PROFILE_DETAILS[grantProfile]?.description}</span>
            </p>
            <p className="mt-1 font-mono text-[11px] text-ink-400">Scopes: {PROFILE_DETAILS[grantProfile]?.scopeSummary}</p>
          </div>
        </form>

        {issuedCredential && (
          <div className="space-y-4 rounded-xl border border-emerald-300 bg-emerald-50/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-200/60 pb-3">
              <div>
                <p className="font-semibold text-ink">Copy these credentials into your AI client now</p>
                <p className="text-xs text-ink-500">The API key is only returned at creation or rotation and cannot be retrieved later.</p>
              </div>
              <button
                type="button"
                onClick={copyAllCredentials}
                className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-ink-700"
              >
                {copiedKey === 'all' ? (
                  <>
                    <Check size={14} className="text-emerald-400" /> All credentials copied!
                  </>
                ) : (
                  <>
                    <Copy size={14} /> Copy all credentials
                  </>
                )}
              </button>
            </div>

            {/* Connection email */}
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600 font-medium">Connection email / identity</span>
              <div className="flex gap-2">
                <input className="input min-w-0 flex-1 font-mono text-xs" readOnly value={issuedCredential.connection_email} />
                <button
                  type="button"
                  onClick={() => void copyToClipboard(issuedCredential.connection_email, 'email')}
                  className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-surface-2"
                >
                  {copiedKey === 'email' ? (
                    <>
                      <Check size={14} className="text-emerald-600" /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={14} /> Copy
                    </>
                  )}
                </button>
              </div>
            </label>

            {/* Dristik API key */}
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600 font-medium">Dristik API key</span>
              <div className="flex gap-2">
                <input
                  className="input min-w-0 flex-1 font-mono text-xs"
                  type={showApiKey ? 'text' : 'password'}
                  readOnly
                  value={issuedCredential.api_key}
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-2.5 text-xs font-medium text-ink hover:bg-surface-2"
                  title={showApiKey ? 'Hide secret key' : 'Show secret key'}
                >
                  {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  <span>{showApiKey ? 'Hide' : 'View'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => void copyToClipboard(issuedCredential.api_key, 'api_key')}
                  className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-surface-2"
                >
                  {copiedKey === 'api_key' ? (
                    <>
                      <Check size={14} className="text-emerald-600" /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={14} /> Copy key
                    </>
                  )}
                </button>
              </div>
            </label>

            {/* MCP Endpoint */}
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600 font-medium">MCP endpoint</span>
              <div className="flex gap-2">
                <input className="input min-w-0 flex-1 font-mono text-xs" readOnly value={issuedCredential.mcp_endpoint || '/api/v1/mcp'} />
                <button
                  type="button"
                  onClick={() => void copyToClipboard(issuedCredential.mcp_endpoint || '/api/v1/mcp', 'endpoint')}
                  className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-surface-2"
                >
                  {copiedKey === 'endpoint' ? (
                    <>
                      <Check size={14} className="text-emerald-600" /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={14} /> Copy
                    </>
                  )}
                </button>
              </div>
            </label>

            {!issuedCredential.mcp_endpoint_is_absolute && (
              <p className="text-xs text-amber-800">
                Deployment setup tip: set DRISTIK_MCP_PUBLIC_URL to the absolute HTTPS URL of this MCP endpoint for external AI clients.
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button
                type="button"
                disabled={busy}
                onClick={() => void validateAIConnection()}
                className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-2 disabled:opacity-50"
              >
                Validate credentials
              </button>
              <button
                type="button"
                onClick={() =>
                  void copyToClipboard(
                    JSON.stringify(
                      issuedCredential.mcp_config || {
                        url: issuedCredential.mcp_endpoint || '/api/v1/mcp',
                        headers: {
                          Authorization: 'Bearer ' + issuedCredential.api_key,
                          'X-Dristik-Connection-Email': issuedCredential.connection_email,
                        },
                      },
                      null,
                      2,
                    ),
                    'mcp_config',
                  )
                }
                className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-2"
              >
                {copiedKey === 'mcp_config' ? (
                  <>
                    <Check size={13} className="text-emerald-600" /> Copied!
                  </>
                ) : (
                  <>
                    <Copy size={13} /> Copy MCP config
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIssuedCredential(null);
                  clearIssuedPrompt();
                }}
                className="text-xs font-medium text-ink-500 underline ml-auto"
              >
                Hide credentials
              </button>
            </div>

            {/* Interactive multi-AI client connection guide */}
            {renderClientGuide()}
          </div>
        )}

        {/* Saved AI connections list */}
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-ink">Configured external AI connections</h3>
          {aiConnections.length === 0 ? (
            <p className="text-sm text-ink-500">No external AI credentials created yet.</p>
          ) : (
            aiConnections.map((c) => (
              <div key={c.id} className="space-y-2 rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{c.name}</p>
                    <p className="text-xs text-ink-500">
                      {c.connection_email} · {c.grant_profile.replace(/_/g, ' ')} · {c.status}
                    </p>
                    <p className="text-xs text-ink-500">
                      {c.last_used_at ? `Last used ${new Date(c.last_used_at * 1000).toLocaleString()}` : 'Not used yet'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {c.status === 'active' && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          if (savedPrompt?.connectionId === c.id) {
                            setSavedPrompt(null);
                            return;
                          }
                          setBusy(true);
                          setError('');
                          void fetchOnboardingPrompt(c.id, savedPromptTab)
                            .then((bundle) => {
                              setSavedPrompt({
                                connectionId: c.id,
                                prompts: bundle.prompts || {},
                                tools: bundle.tool_inventory || [],
                                nextStep: bundle.next_step || '',
                              });
                              if (bundle.provider) setSavedPromptTab(bundle.provider);
                            })
                            .catch((e: unknown) => {
                              setError(e instanceof Error ? e.message : 'Could not load the onboarding prompt.');
                            })
                            .finally(() => setBusy(false));
                        }}
                        className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
                      >
                        <Sparkles size={12} /> {savedPrompt?.connectionId === c.id ? 'Hide prompt' : 'Onboarding prompt'}
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void viewActivity(c.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
                    >
                      <History size={12} /> {activeActivityId === c.id ? 'Hide activity' : 'Activity'}
                    </button>
                    {c.status === 'active' && (
                      <>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void rotateAIConnection(c.id)}
                          className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
                        >
                          Rotate key
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void revokeAIConnection(c.id)}
                          className="rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 disabled:opacity-50"
                        >
                          Revoke
                        </button>
                      </>
                    )}
                  </div>
                </div>
                {savedPrompt?.connectionId === c.id && (
                  <div className="space-y-2 rounded-lg border border-line bg-surface/50 p-3">
                    <div className="flex flex-wrap gap-1.5">
                      {CLIENT_TABS.map((tab) => (
                        <button
                          key={tab}
                          type="button"
                          onClick={() => setSavedPromptTab(tab)}
                          className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                            savedPromptTab === tab ? 'bg-ink text-white shadow-sm' : 'border border-line bg-surface text-ink hover:bg-surface-2'
                          }`}
                        >
                          {CLIENT_LABELS[tab]}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold text-ink">Copy/paste prompt for {CLIENT_LABELS[savedPromptTab]}</p>
                      <button
                        type="button"
                        disabled={!savedPrompt.prompts[savedPromptTab]}
                        onClick={() => void copyToClipboard(savedPrompt.prompts[savedPromptTab] || '', `saved_prompt_${c.id}_${savedPromptTab}`)}
                        className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-surface-2 disabled:opacity-50"
                      >
                        {copiedKey === `saved_prompt_${c.id}_${savedPromptTab}` ? (
                          <>
                            <Check size={12} className="text-emerald-600" /> Prompt copied
                          </>
                        ) : (
                          <>
                            <Copy size={12} /> Copy prompt
                          </>
                        )}
                      </button>
                    </div>
                    <textarea
                      readOnly
                      aria-label={`Copy/paste onboarding prompt for ${CLIENT_LABELS[savedPromptTab]}`}
                      value={savedPrompt.prompts[savedPromptTab] || 'The onboarding prompt has not been loaded for this client.'}
                      className="input min-h-40 w-full resize-y font-mono text-[11px] leading-relaxed"
                    />
                    {savedPrompt.tools.length > 0 && (
                      <p className="text-[11px] text-ink-500">Authorized tools: {savedPrompt.tools.map((tool) => tool.name).join(', ')}</p>
                    )}
                    {savedPrompt.nextStep && <p className="text-[11px] text-ink-500">{savedPrompt.nextStep}</p>}
                  </div>
                )}
                {activeActivityId === c.id && (
                  <div className="space-y-3 rounded-lg border border-line bg-surface/50 p-3.5 text-xs">
                    {/* Header with Traffic Direction Filters and Test Action */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
                      <div>
                        <p className="font-semibold text-ink flex items-center gap-1.5">
                          <Radio size={14} className="text-emerald-500 animate-pulse" />
                          Inbound & Outbound Traffic Ledger
                        </p>
                        <p className="text-[11px] text-ink-500">
                          Real-time stream of incoming MCP tool invocations and outgoing Dristik payloads.
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setTestingConnectionId(testingConnectionId === c.id ? null : c.id);
                            setProbeResult(null);
                          }}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                            testingConnectionId === c.id
                              ? 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'border-line bg-surface text-ink hover:border-emerald-500'
                          }`}
                        >
                          <Send size={12} />
                          {testingConnectionId === c.id ? 'Close test console' : 'Test connection / Send message'}
                        </button>
                        <button
                          type="button"
                          onClick={() => void viewActivity(c.id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-2 py-1 text-xs text-ink-500 hover:text-ink"
                          title="Refresh activity"
                        >
                          <RefreshCw size={12} />
                        </button>
                      </div>
                    </div>

                    {/* Interactive Test Console */}
                    {testingConnectionId === c.id && (
                      <div className="space-y-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                            <Sparkles size={13} /> Two-Way Connection Verification Console
                          </span>
                          <span className="text-[11px] text-ink-500">Target: {c.connection_email}</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {[
                            { id: 'audits_list', label: '🔍 Past Audits (dristik_audits_list)', defaultMsg: 'Inspect earlier audits for this account' },
                            { id: 'ping', label: '⚡ Ping Heartbeat', defaultMsg: 'Ping connection heartbeat and identity' },
                            { id: 'pipeline_inspect', label: '🧠 DAG Pipeline Inspect', defaultMsg: 'Inspect pipeline execution graph' },
                            { id: 'agents_list', label: '🤖 Specialist Agent Fleet', defaultMsg: 'Query registered specialist agents' },
                            { id: 'custom_message', label: '💬 Custom Message', defaultMsg: 'Two-way test ping from Dristik UI' },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setProbeType(item.id as typeof probeType);
                                setProbeMessage(item.defaultMsg);
                              }}
                              className={`rounded-md px-2 py-1 text-[11px] font-medium transition ${
                                probeType === item.id
                                  ? 'bg-emerald-600 text-white'
                                  : 'border border-line bg-surface text-ink-600 hover:text-ink'
                              }`}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={probeMessage}
                            onChange={(e) => setProbeMessage(e.target.value)}
                            placeholder="Message or probe description..."
                            className="input flex-1 text-xs py-1.5"
                          />
                          <button
                            type="button"
                            disabled={probeBusy}
                            onClick={() => void sendTestProbe(c.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                          >
                            {probeBusy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                            Send message & check
                          </button>
                        </div>
                        {probeResult && (
                          <div className="rounded border border-emerald-500/20 bg-surface p-2.5 text-xs space-y-1.5">
                            <div className="flex items-center justify-between text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                              <span className="flex items-center gap-1">
                                <CheckCircle2 size={12} /> Round-trip verified in {String(probeResult.round_trip_ms)}ms
                              </span>
                              <span className="uppercase text-[10px] tracking-wider text-ink-400">Status 200 OK</span>
                            </div>
                            <p className="text-ink font-medium">{String(probeResult.response_summary || '')}</p>
                            <pre className="max-h-36 overflow-auto rounded bg-ink-900/5 dark:bg-black/40 p-2 font-mono text-[10px] text-ink-600 dark:text-ink-300">
                              {JSON.stringify(probeResult.response_data, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Filter Tabs */}
                    <div className="flex items-center gap-1 border-b border-line pb-1.5 text-[11px]">
                      {[
                        { id: 'all', label: `All Traffic (${activityEvents.length})` },
                        {
                          id: 'inbound',
                          label: `Inbound (${activityEvents.filter((e) => e.direction === 'inbound').length})`,
                          icon: ArrowDownLeft,
                        },
                        {
                          id: 'outbound',
                          label: `Outbound (${activityEvents.filter((e) => e.direction === 'outbound').length})`,
                          icon: ArrowUpRight,
                        },
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          type="button"
                          onClick={() => setTrafficFilter(tab.id as typeof trafficFilter)}
                          className={`inline-flex items-center gap-1 rounded px-2 py-1 font-medium transition ${
                            trafficFilter === tab.id
                              ? 'bg-ink text-surface dark:bg-ink-100 dark:text-ink-900'
                              : 'text-ink-500 hover:text-ink'
                          }`}
                        >
                          {tab.icon && <tab.icon size={11} />}
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    {/* Traffic Feed */}
                    {activityEvents.length === 0 ? (
                      <p className="text-ink-500 py-2">No events recorded for this connection yet.</p>
                    ) : (
                      <div className="divide-y divide-line max-h-80 overflow-y-auto space-y-0.5">
                        {activityEvents
                          .filter((evt) => {
                            if (trafficFilter === 'inbound') return evt.direction === 'inbound';
                            if (trafficFilter === 'outbound') return evt.direction === 'outbound';
                            return true;
                          })
                          .map((evt) => (
                            <div key={evt.id} className="py-2 space-y-1">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  {evt.direction === 'inbound' ? (
                                    <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                                      <ArrowDownLeft size={10} /> INBOUND
                                    </span>
                                  ) : evt.direction === 'outbound' ? (
                                    <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                      <ArrowUpRight size={10} /> OUTBOUND
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 rounded bg-zinc-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500">
                                      SYSTEM
                                    </span>
                                  )}
                                  <span className="font-mono font-medium text-ink">
                                    {evt.tool ? `tool: ${evt.tool}` : evt.method || evt.event}
                                  </span>
                                  {evt.status === 'error' && (
                                    <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-600">
                                      ERROR
                                    </span>
                                  )}
                                </div>
                                <span className="text-[11px] text-ink-400 font-mono">
                                  {new Date(evt.created_at * 1000).toLocaleTimeString()}
                                </span>
                              </div>
                              <p className="text-[11px] text-ink-600 dark:text-ink-300">{evt.summary}</p>
                              {(evt.arguments && Object.keys(evt.arguments).length > 0) || evt.error ? (
                                <div>
                                  <button
                                    type="button"
                                    onClick={() => setExpandedEventId(expandedEventId === evt.id ? null : evt.id)}
                                    className="text-[10px] font-medium text-ink-400 hover:text-ink underline"
                                  >
                                    {expandedEventId === evt.id ? 'Hide payload' : 'Inspect payload'}
                                  </button>
                                  {expandedEventId === evt.id && (
                                    <pre className="mt-1 overflow-auto rounded bg-ink-900/5 dark:bg-black/30 p-1.5 font-mono text-[10px] text-ink-600 dark:text-ink-300">
                                      {JSON.stringify(evt.arguments || evt.error || evt.metadata, null, 2)}
                                    </pre>
                                  )}
                                </div>
                              ) : null}
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Capabilities & 105-Agent Fleet Drawer */}
        <div className="border-t border-line pt-3">
          <button
            type="button"
            onClick={() => void loadCapabilities()}
            className="inline-flex items-center gap-2 text-xs font-semibold text-ink hover:text-emerald-600"
          >
            <Layers size={14} /> Browse 105 specialist agents & registered MCP tools{' '}
            {showCapabilities ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {showCapabilities && (
            <div className="mt-3 space-y-3">
              <p className="text-xs text-ink-500">
                Connected AI clients have full discoverability and orchestration access over the 105 specialist agents, DAG pipeline execution graph, intermediate blackboard memory, and live citation engine.
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {capabilities.map((cap) => (
                  <div key={cap.name} className="rounded-lg border border-line p-2.5 text-xs">
                    <p className="font-semibold text-ink">{cap.name}</p>
                    <p className="text-ink-500">{cap.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Model Provider Configuration & Test Grid */}
      <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="card space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Bot size={20} />
            <h2 className="text-lg font-semibold text-ink">Add a model provider</h2>
          </div>
          <form onSubmit={addProvider} className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">Provider</span>
              <select className="input w-full" value={provider} onChange={(e) => chooseProvider(e.target.value)}>
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">Connection label</span>
              <input
                className="input w-full"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                required
                maxLength={120}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">Model ID</span>
              <input
                className="input w-full"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                required
                maxLength={160}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">API key (never displayed again)</span>
              <input
                className="input w-full"
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
                minLength={8}
              />
            </label>
            <button
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? <Loader2 className="animate-spin" size={16} /> : <PlugZap size={16} />} Save encrypted connection
            </button>
          </form>

          <div className="border-t border-line pt-4">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-ink">Saved providers</h3>
              <button
                type="button"
                onClick={() => setSelected('')}
                className={`rounded-lg border px-2 py-1 text-xs ${
                  !selected ? 'border-emerald-500 text-emerald-700' : 'border-line text-ink-500'
                }`}
              >
                Use platform default
              </button>
            </div>
            <p className="mb-3 text-xs text-ink-500">
              Choose a saved provider explicitly to route compatible audit model calls through it. Test the provider successfully first; platform default is used when none is selected.
            </p>
            {providers.length === 0 ? (
              <p className="text-sm text-ink-500">No providers configured yet.</p>
            ) : (
              <div className="space-y-2">
                {providers.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelected(p.id)}
                    className={`flex w-full items-center justify-between rounded-lg border p-3 text-left ${
                      selected === p.id ? 'border-emerald-500 bg-emerald-50/40' : 'border-line'
                    }`}
                  >
                    <span>
                      <span className="block text-sm font-medium text-ink">{p.label}</span>
                      <span className="text-xs text-ink-500">
                        {p.provider} · {p.model}
                      </span>
                    </span>
                    <span className="text-xs text-ink-500">{p.status.replace(/_/g, ' ')}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Live model call tester */}
        <section className="card space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Send size={20} />
            <h2 className="text-lg font-semibold text-ink">Test a live model call</h2>
          </div>
          <form onSubmit={invoke} className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">Website to audit</span>
              <input
                className="input w-full"
                type="url"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                required
                placeholder="https://example.com"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-ink-600">Prompt</span>
              <textarea
                className="input min-h-36 w-full"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
                maxLength={30000}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                disabled={busy || !selected}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="animate-spin" size={16} /> : <Activity size={16} />} Invoke selected provider
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void createTask()}
                className="rounded-lg border border-line px-4 py-2.5 text-sm font-medium text-ink disabled:opacity-50"
              >
                Record collaboration task
              </button>
            </div>
          </form>
          {result && (
            <div className="rounded-xl border border-line bg-surface p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">Live provider response</p>
              <pre className="whitespace-pre-wrap break-words text-sm text-ink">{result}</pre>
            </div>
          )}
        </section>
      </div>

      {/* Collaboration tasks */}
      <section className="card p-5">
        <div className="mb-4 flex items-center gap-2">
          <Activity size={20} />
          <h2 className="text-lg font-semibold text-ink">Recent collaboration tasks</h2>
        </div>
        {tasks.length ? (
          <div className="divide-y divide-line">
            {tasks.map((t) => (
              <div key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium text-ink">{t.goal}</p>
                  <p className="text-xs text-ink-500">
                    {t.id} · {new Date(t.created_at * 1000).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-line px-3 py-1 text-xs text-ink-500">{t.status}</span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void executeAudit(t.id)}
                    className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-50"
                  >
                    Run website audit
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-500">No collaboration tasks yet.</p>
        )}
      </section>
    </main>
  );
}
