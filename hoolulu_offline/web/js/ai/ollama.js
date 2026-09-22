// Talk to a local Ollama daemon. Requests go through the sync server's
// /api/ollama proxy by default, which sidesteps CORS and mixed-content blocks
// (so it works even when the app is served over https from another host).

export function baseUrl(settings) {
  const host = (settings && settings.ollamaHost || '').trim().replace(/\/+$/, '');
  return host || '';   // blank = same-origin proxy
}

export async function ping(settings, timeoutMs = 5000) {
  const base = baseUrl(settings);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}/api/ollama/tags`, { signal: ctrl.signal, cache: 'no-store' });
    clearTimeout(timer);
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    const json = await res.json();
    return { ok: true, models: (json.models || []).map(m => m.name || m.model) };
  } catch (err) {
    clearTimeout(timer);
    return { ok: false, error: err.name === 'AbortError' ? 'timeout' : err.message };
  }
}

export async function listModels(settings) {
  const r = await ping(settings);
  return r.ok ? r.models : [];
}

export async function chat(messages, { settings, model, onToken, temperature = 0.7 } = {}) {
  const base = baseUrl(settings);
  const res = await fetch(`${base}/api/ollama/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: model || settings.ollamaModel || 'qwen2.5-coder:1.5b',
      messages,
      stream: false,
      options: { temperature },
    }),
  });

  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `Ollama HTTP ${res.status}`);

  const text = (json.message && json.message.content) || json.response || '';
  if (onToken) onToken(text, text);
  return { text: text.trim(), model: json.model || model };
}

export const INSTALL_HINT =
  'Install Ollama from ollama.com, run `ollama serve`, then `ollama pull qwen2.5-coder:1.5b`.';
