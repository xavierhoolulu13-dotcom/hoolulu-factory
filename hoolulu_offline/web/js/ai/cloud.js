// Cloud LLM access. Used only when you are online and have it configured.
// Two paths: direct from the browser, or proxied through your own sync server
// (recommended — it avoids CORS rules and keeps the key in one place).

export function isConfigured(settings) {
  if (settings.cloudViaProxy) return !!(settings.cloudKey || true) && !!settings.cloudModel;
  return !!settings.cloudKey && !!settings.cloudModel;
}

function endpointFor(settings) {
  const provider = settings.cloudProvider || 'openai';
  return provider === 'anthropic' ? '/api/ai/anthropic' : '/api/ai/openai';
}

function messagesFor(provider, messages, system) {
  // Anthropic takes `system` as a top-level field, not a message.
  if (provider === 'anthropic') {
    return {
      system: system || (messages.find(m => m.role === 'system') || {}).content || '',
      messages: messages.filter(m => m.role !== 'system'),
    };
  }
  return { messages };
}

function extractText(provider, json) {
  if (provider === 'anthropic') {
    const blocks = json.content || [];
    return blocks.map(b => b.text || '').join('').trim();
  }
  const choice = (json.choices || [])[0];
  return (((choice && choice.message) || {}).content || json.text || '').trim();
}

/**
 * @param {Array<{role:string,content:string}>} messages
 * @returns {Promise<{text:string,model:string}>}
 */
export async function chat(messages, { settings, serverBase = '', onToken, maxTokens = 2048, temperature = 0.7 } = {}) {
  const provider = settings.cloudProvider || 'openai';
  const model = settings.cloudModel || 'gpt-4o-mini';
  const key = settings.cloudKey || '';

  const { system, messages: msgs } = messagesFor(provider, messages,
    (messages.find(m => m.role === 'system') || {}).content);

  let json;
  if (settings.cloudViaProxy) {
    const res = await fetch(`${serverBase}${endpointFor(settings)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: key,
        base_url: settings.cloudBaseUrl || 'https://api.openai.com/v1',
        model, messages: msgs, system,
        max_tokens: maxTokens, temperature,
      }),
    });
    json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `proxy HTTP ${res.status}`);
  } else if (provider === 'anthropic') {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({ model, system, messages: msgs, max_tokens: maxTokens, temperature }),
    });
    json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error?.message || `Anthropic HTTP ${res.status}`);
  } else {
    const base = (settings.cloudBaseUrl || 'https://api.openai.com/v1').replace(/\/+$/, '');
    const res = await fetch(`${base}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
      body: JSON.stringify({ model, messages: msgs, max_tokens: maxTokens, temperature }),
    });
    json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((json.error && json.error.message) || `HTTP ${res.status}`);
  }

  const text = extractText(provider, json);
  if (onToken) onToken(text, text);
  return { text, model: json.model || model };
}

export const PROVIDERS = [
  { id: 'openai', label: 'OpenAI', defaultModel: 'gpt-4o-mini', defaultBase: 'https://api.openai.com/v1' },
  { id: 'anthropic', label: 'Anthropic', defaultModel: 'claude-sonnet-4-5', defaultBase: '' },
  { id: 'custom', label: 'OpenAI-compatible (Groq, OpenRouter, local)', defaultModel: 'llama-3.3-70b-versatile', defaultBase: 'https://api.groq.com/openai/v1' },
];
