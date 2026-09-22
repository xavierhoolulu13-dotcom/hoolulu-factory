// Provider chain. Picks the best brain available right now and always degrades
// gracefully: on-device → Ollama → cloud → offline brain → queue for later.

import * as local from './local_brain.js';
import * as webllm from './webllm.js';
import * as ollama from './ollama.js';
import * as cloud from './cloud.js';

export const LABELS = {
  ondevice: 'On-device',
  ollama: 'Ollama (local)',
  cloud: 'Cloud',
  local: 'Offline brain',
  queue: 'Queued',
};

export function engineLabel(id) {
  return LABELS[id] || id;
}

/** Probe everything once so the UI and the router can make decisions. */
export async function detect({ settings, online, serverBase = '' }) {
  const status = {
    online,
    ondevice: {
      supported: webllm.isSupported(),
      reason: webllm.unsupportedReason(),
      loaded: webllm.isLoaded(),
      model: webllm.currentModel(),
      cached: [],
    },
    ollama: { ok: false, models: [], error: null },
    cloud: {
      configured: cloud.isConfigured(settings),
      provider: settings.cloudProvider,
      model: settings.cloudModel,
      viaProxy: settings.cloudViaProxy,
    },
    local: { available: true },
  };

  if (status.ondevice.supported) {
    try { status.ondevice.cached = await webllm.cachedModels(); }
    catch { status.ondevice.cached = []; }
  }

  // Only probe Ollama when it is plausibly there; a failed fetch to a missing
  // daemon is cheap locally but pointless on a phone.
  try {
    const r = await ollama.ping(settings, 3500);
    status.ollama.ok = r.ok;
    status.ollama.models = r.models || [];
    status.ollama.error = r.error || null;
  } catch (err) {
    status.ollama.error = err.message;
  }

  return status;
}

/**
 * Decide which engine answers the next message.
 * @returns {{engine:string, reason:string}}
 */
export function choose(settings, status, { force = null } = {}) {
  const mode = force || settings.aiMode || 'auto';
  const ondeviceReady = status.ondevice.loaded ||
    (status.ondevice.supported && status.ondevice.cached.includes(settings.webllmModel));
  const ollamaReady = !!status.ollama.ok;
  const cloudReady = !!status.online && !!status.cloud.configured;

  if (mode === 'ondevice') {
    return ondeviceReady
      ? { engine: 'ondevice', reason: 'on-device model' }
      : { engine: 'local', reason: 'on-device model not downloaded yet' };
  }
  if (mode === 'ollama') {
    return ollamaReady
      ? { engine: 'ollama', reason: 'local Ollama' }
      : { engine: 'local', reason: 'Ollama not reachable' };
  }
  if (mode === 'cloud') {
    if (!status.online) return { engine: 'local', reason: 'offline, cloud unavailable' };
    return cloudReady
      ? { engine: 'cloud', reason: 'cloud model' }
      : { engine: 'local', reason: 'cloud not configured' };
  }
  if (mode === 'local') return { engine: 'local', reason: 'offline brain forced' };
  if (mode === 'offline') {
    if (ondeviceReady) return { engine: 'ondevice', reason: 'on-device model' };
    if (ollamaReady) return { engine: 'ollama', reason: 'local Ollama' };
    return { engine: 'local', reason: 'offline brain' };
  }

  // auto
  if (settings.preferPrivacy) {
    if (ondeviceReady) return { engine: 'ondevice', reason: 'on-device model (private)' };
    if (ollamaReady) return { engine: 'ollama', reason: 'local Ollama (private)' };
    if (cloudReady) return { engine: 'cloud', reason: 'cloud (nothing local available)' };
    return { engine: 'local', reason: 'offline brain' };
  }
  if (cloudReady) return { engine: 'cloud', reason: 'cloud (best quality)' };
  if (ondeviceReady) return { engine: 'ondevice', reason: 'on-device model' };
  if (ollamaReady) return { engine: 'ollama', reason: 'local Ollama' };
  return { engine: 'local', reason: 'offline brain' };
}

/**
 * Send a message through the chain. Never throws for a missing provider — it
 * falls back until something answers.
 */
export async function send({
  messages, settings, status, online = null,
  onToken, onProgress, force = null, context = {}, serverBase = '',
} = {}) {
  const effStatus = status || await detect({ settings, online: online ?? navigator.onLine, serverBase });
  const decision = choose(settings, effStatus, { force });
  const started = performance.now();

  if (decision.engine === 'ondevice') {
    try {
      if (!webllm.isLoaded()) {
        if (onProgress) onProgress({ stage: 'load', text: 'Loading on-device model…' });
        await webllm.load(settings.webllmModel, {
          onProgress: (p) => onProgress && onProgress({ stage: 'download', text: p.text, progress: p.progress }),
        });
      }
      if (onProgress) onProgress({ stage: 'ready', text: 'On-device model ready' });
      const out = await webllm.chat(messages, { onToken });
      return {
        text: out.text, provider: 'ondevice', model: out.model || settings.webllmModel,
        label: LABELS.ondevice, reason: decision.reason,
        ms: Math.round(performance.now() - started),
      };
    } catch (err) {
      console.warn('[provider] on-device failed:', err);
      // fall through to the next best thing
      const next = effStatus.ollama.ok ? 'ollama'
        : (effStatus.online && effStatus.cloud.configured) ? 'cloud' : 'local';
      return send({ messages, settings, status: effStatus, online, onToken, onProgress,
        force: next, context, serverBase });
    }
  }

  if (decision.engine === 'ollama') {
    try {
      const out = await ollama.chat(messages, { settings, onToken });
      return {
        text: out.text, provider: 'ollama', model: out.model || settings.ollamaModel,
        label: LABELS.ollama, reason: decision.reason,
        ms: Math.round(performance.now() - started),
      };
    } catch (err) {
      console.warn('[provider] ollama failed:', err);
      const next = (effStatus.online && effStatus.cloud.configured) ? 'cloud' : 'local';
      return send({ messages, settings, status: effStatus, online, onToken, onProgress,
        force: next, context, serverBase });
    }
  }

  if (decision.engine === 'cloud') {
    try {
      const out = await cloud.chat(messages, { settings, serverBase, onToken });
      return {
        text: out.text, provider: 'cloud', model: out.model || settings.cloudModel,
        label: LABELS.cloud, reason: decision.reason,
        ms: Math.round(performance.now() - started),
      };
    } catch (err) {
      console.warn('[provider] cloud failed:', err);
      const fb = await local.run({ prompt: lastUser(messages), settings, runtime: effStatus, context });
      return {
        text: fb.text,
        provider: 'local',
        model: fb.model,
        label: LABELS.local,
        reason: `cloud failed (${err.message}) — used offline brain`,
        skill: fb.skill,
        created: fb.created,
        followups: fb.followups,
        ms: Math.round(performance.now() - started),
      };
    }
  }

  const out = await local.run({
    prompt: lastUser(messages), settings, runtime: effStatus, context,
  });
  return {
    text: out.text,
    provider: 'local',
    model: out.model,
    label: LABELS.local,
    reason: decision.reason,
    skill: out.skill,
    created: out.created || [],
    followups: out.followups || [],
    confidence: out.confidence,
    projectId: out.projectId,
    ms: Math.round(performance.now() - started),
  };
}

function lastUser(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user') return messages[i].content;
  }
  return '';
}

export { local, webllm, ollama, cloud };
