// On-device inference via WebLLM (WebGPU). The JS runtime is vendored in
// vendor/webllm/ so it needs no CDN. Model weights are fetched once from
// HuggingFace, then cached by the browser — after that it works with wifi off.

let mod = null;
let engine = null;
let currentModelId = null;
let loadingPromise = null;

export const MODELS = [
  { id: 'Qwen2.5-Coder-1.5B-Instruct-q4f16_1-MLC', label: 'Qwen2.5 Coder 1.5B', size: '~1.1 GB', note: 'Best small coder. Recommended.' },
  { id: 'Qwen3-1.7B-q4f16_1-MLC', label: 'Qwen3 1.7B', size: '~1.3 GB', note: 'Strong all-rounder' },
  { id: 'Llama-3.2-1B-Instruct-q4f16_1-MLC', label: 'Llama 3.2 1B', size: '~0.9 GB', note: 'Fastest, lowest RAM' },
  { id: 'SmolLM2-1.7B-Instruct-q4f16_1-MLC', label: 'SmolLM2 1.7B', size: '~1.3 GB', note: 'Good on weak GPUs' },
  { id: 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC', label: 'Qwen2.5 0.5B (tiny)', size: '~0.35 GB', note: 'Phones and low RAM' },
  { id: 'Qwen2.5-Coder-3B-Instruct-q4f16_1-MLC', label: 'Qwen2.5 Coder 3B', size: '~2.1 GB', note: 'Best code under 4B' },
  { id: 'Hermes-3-Llama-3.2-3B-q4f16_1-MLC', label: 'Hermes 3 3B', size: '~2.0 GB', note: 'Less censored, chatty' },
  { id: 'Qwen2.5-3B-Instruct-q4f16_1-MLC', label: 'Qwen2.5 3B', size: '~2.0 GB', note: 'Balanced quality' },
  { id: 'gemma-2-2b-it-q4f16_1-MLC', label: 'Gemma 2 2B', size: '~1.8 GB', note: 'Google, solid writing' },
  { id: 'Phi-3.5-mini-instruct-q4f16_1-MLC', label: 'Phi-3.5 mini 3.8B', size: '~2.3 GB', note: 'Best reasoning here' },
];

export function modelLabel(id) {
  const m = MODELS.find(x => x.id === id);
  return m ? m.label : id;
}

/** WebGPU is required. Chrome/Edge 113+, Safari 18+, Firefox 141+. */
export function isSupported() {
  try {
    return typeof navigator !== 'undefined' && !!navigator.gpu &&
      typeof WebAssembly === 'object';
  } catch { return false; }
}

export function unsupportedReason() {
  if (isSupported()) return null;
  if (typeof navigator === 'undefined' || !navigator.gpu) {
    return 'This browser has no WebGPU. Try Chrome or Edge 113+, or Safari 18+.';
  }
  return 'WebGPU is unavailable in this browser.';
}

export const isLoaded = () => !!engine;
export const currentModel = () => currentModelId;

async function importRuntime() {
  if (mod) return mod;
  mod = await import('../../vendor/webllm/index.js');
  return mod;
}

/** Which of the offered models are already cached in this browser? */
export async function cachedModels() {
  if (!isSupported()) return [];
  try {
    const m = await importRuntime();
    const out = [];
    for (const model of MODELS) {
      // hasModelInCache resolves false quickly when nothing is downloaded.
      // eslint-disable-next-line no-await-in-loop
      if (await m.hasModelInCache(model.id)) out.push(model.id);
    }
    return out;
  } catch { return []; }
}

export async function load(modelId, { onProgress } = {}) {
  if (engine && currentModelId === modelId) return engine;
  if (loadingPromise) return loadingPromise;

  loadingPromise = (async () => {
    if (engine) { try { await engine.unload(); } catch { /* ignore */ } engine = null; }
    const m = await importRuntime();
    engine = await m.CreateMLCEngine(modelId, {
      initProgressCallback: (report) => {
        if (onProgress) onProgress(report);
      },
    });
    currentModelId = modelId;
    return engine;
  })();

  try {
    return await loadingPromise;
  } finally {
    loadingPromise = null;
  }
}

export async function chat(messages, { onToken, temperature = 0.7, maxTokens = 1024 } = {}) {
  if (!engine) throw new Error('no on-device model loaded');
  const stream = await engine.chat.completions.create({
    messages,
    stream: true,
    temperature,
    max_tokens: maxTokens,
  });

  let full = '';
  for await (const chunk of stream) {
    const delta = chunk.choices && chunk.choices[0] && chunk.choices[0].delta;
    if (delta && delta.content) {
      full += delta.content;
      if (onToken) onToken(delta.content, full);
    }
  }
  return { text: full.trim(), model: currentModelId };
}

export async function unload() {
  if (!engine) return;
  try { await engine.unload(); } catch { /* ignore */ }
  engine = null;
  currentModelId = null;
}

export async function deleteModel(modelId) {
  const m = await importRuntime();
  await m.deleteModelAllInfoInCache(modelId);
  if (currentModelId === modelId) await unload();
}
