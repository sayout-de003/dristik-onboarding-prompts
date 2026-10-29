import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { UniversalConnectView } from './UniversalConnectView';

const prompts = {
  claude: 'CLAUDE ONBOARDING PROMPT unique',
  chatgpt: 'CHATGPT ONBOARDING PROMPT unique',
  grok: 'GROK ONBOARDING PROMPT unique',
  gemini: 'GEMINI ONBOARDING PROMPT unique',
  deepseek: 'DEEPSEEK ONBOARDING PROMPT unique',
  kimi: 'KIMI ONBOARDING PROMPT unique',
  openrouter: 'OPENROUTER ONBOARDING PROMPT unique',
  custom: 'CUSTOM ONBOARDING PROMPT unique',
};

const kit = {
  connection: {
    id: 'dai_new',
    name: 'Claude — Full Audit Access',
    connection_email: 'ai-new@connect.example.test',
    api_key: 'drk_live_secret_value',
    grant_profile: 'full_access',
    scopes: ['*'],
    mcp_endpoint: 'https://octaos.org/api/v1/mcp',
    mcp_endpoint_is_absolute: true,
    mcp_config: { url: 'https://octaos.org/api/v1/mcp', headers: { Authorization: 'Bearer drk_live_secret_value' } },
    key_display_policy: 'shown_once',
  },
  provider: 'claude',
  prompt: prompts.claude,
  prompts,
  tool_inventory: [{ name: 'dristik_ping', scope: 'capabilities.list' }],
  next_step: 'Copy the prompt to the selected AI.',
  execution_policy: 'AI-generated code is staged for review and is never executed by this endpoint.',
};

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response);
}

function installFetch(connections: Array<Record<string, unknown>> = []) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method || 'GET';
    if (url.endsWith('/api/v1/connect/providers')) return jsonResponse({ providers: [] });
    if (url.endsWith('/api/v1/connect/tasks')) return jsonResponse({ tasks: [] });
    if (url.endsWith('/api/v1/connect/ai-connections') && method === 'GET') return jsonResponse({ connections });
    if (url.endsWith('/api/v1/connect/ai-onboarding/kit') && method === 'POST') return jsonResponse(kit, 201);
    if (url.endsWith('/api/v1/connect/ai-onboarding/prompt') && method === 'POST') {
      return jsonResponse({ connection_id: 'dai_existing', provider: 'claude', prompt: prompts.claude, prompts, tool_inventory: kit.tool_inventory, next_step: kit.next_step });
    }
    return jsonResponse({ detail: `unexpected ${method} ${url}` }, 500);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('UniversalConnectView onboarding prompts', () => {
  it('creates a kit and shows the provider prompt without putting the key in the prompt', async () => {
    const fetchMock = installFetch();
    render(<UniversalConnectView />);
    await screen.findByRole('button', { name: 'Generate credentials' });

    fireEvent.click(screen.getByRole('button', { name: 'Generate credentials' }));

    const prompt = await screen.findByLabelText('Copy/paste onboarding prompt for Claude');
    expect(prompt).toHaveValue(prompts.claude);
    expect(prompt).not.toHaveValue(expect.stringContaining('drk_live_secret_value'));
    expect(screen.getByText(/Authorized tools: dristik_ping/)).toBeInTheDocument();

    const kitCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith('/api/v1/connect/ai-onboarding/kit'));
    expect(kitCall).toBeTruthy();
    expect(JSON.parse(String(kitCall?.[1]?.body))).toMatchObject({
      name: 'Claude — Full Audit Access',
      provider: 'claude',
      grant_profile: 'full_access',
    });
    expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith('/api/v1/connect/ai-connections') && (call[1]?.method || 'GET') === 'POST')).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'ChatGPT' }));
    expect(screen.getByLabelText('Copy/paste onboarding prompt for ChatGPT')).toHaveValue(prompts.chatgpt);
  });

  it('loads a copy/paste prompt for an existing connection without issuing a key', async () => {
    const fetchMock = installFetch([
      { id: 'dai_existing', name: 'Existing client', connection_email: 'ai-existing@connect.example.test', grant_profile: 'audit_operator', status: 'active' },
    ]);
    render(<UniversalConnectView />);
    const open = await screen.findByRole('button', { name: 'Onboarding prompt' });
    fireEvent.click(open);

    const prompt = await screen.findByLabelText('Copy/paste onboarding prompt for Claude');
    expect(prompt).toHaveValue(prompts.claude);
    expect(screen.queryByText('Copy these credentials into your AI client now')).not.toBeInTheDocument();

    await waitFor(() => {
      const promptCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith('/api/v1/connect/ai-onboarding/prompt'));
      expect(JSON.parse(String(promptCall?.[1]?.body)).connection_id).toBe('dai_existing');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Grok' }));
    expect(screen.getByLabelText('Copy/paste onboarding prompt for Grok')).toHaveValue(prompts.grok);
  });
});
