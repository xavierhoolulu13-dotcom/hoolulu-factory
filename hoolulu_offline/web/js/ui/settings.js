// Settings: which brain answers, what it costs, and who you are on invoices.

import * as db from '../db.js';
import * as webllm from '../ai/webllm.js';
import * as ollama from '../ai/ollama.js';
import * as cloud from '../ai/cloud.js';
import * as provider from '../ai/provider.js';
import { state, saveSettings, refreshProviders, serverBase, rerender } from '../app.js';
import { el, toast, money, download, uid } from '../util.js';
import { modal, confirmDialog } from './modal.js';

export async function render(root) {
  const s = state.settings;
  const p = state.providers || {};

  root.appendChild(section('You', [
    grid([
      input('Business name', 'businessName', s.businessName, 'Hoolulu Studio'),
      input('Your name', 'ownerName', s.ownerName, 'Xavier'),
      input('Currency', 'currency', s.currency, 'USD'),
      input('Default hourly rate', 'hourlyRate', s.hourlyRate, '85', 'number'),
      input('Tax rate (0.04 = 4%)', 'taxRate', s.taxRate, '0', 'number'),
      input('Payment terms', 'paymentTerms', s.paymentTerms, 'Net 14'),
    ], 2),
    el('p', { class: 'small dim', text: 'Used by the offline brain when it writes proposals and invoices.' }),
  ], saveBusiness));

  root.appendChild(await engineSection(s, p));
  root.appendChild(await onDeviceSection(s, p));
  root.appendChild(await ollamaSection(s, p));
  root.appendChild(await cloudSection(s, p));
  root.appendChild(await dataSection());
}

function section(title, children, onSave) {
  const wrap = el('div', { class: 'card' }, [el('h3', { text: title })]);
  for (const c of children) wrap.appendChild(c);
  if (onSave) {
    wrap.appendChild(el('div', { class: 'row', style: { marginTop: '12px' } }, [
      el('button', { class: 'btn', text: 'Save', onclick: onSave }),
    ]));
  }
  return wrap;
}

function grid(children, cols = 2) {
  return el('div', { class: 'grid cols-' + cols }, children);
}

function field(label, control) {
  return el('label', { class: 'field' }, [el('span', { text: label }), control]);
}

function input(label, key, value, placeholder = '', type = 'text') {
  return field(label, el('input', {
    id: 'set-' + key, value: value == null ? '' : String(value),
    placeholder, type,
  }));
}

async function saveBusiness() {
  const get = (k, num = false) => {
    const v = document.getElementById('set-' + k).value;
    return num ? Number(v) || 0 : v;
  };
  await saveSettings({
    businessName: get('businessName'),
    ownerName: get('ownerName'),
    currency: get('currency') || 'USD',
    hourlyRate: get('hourlyRate', true),
    taxRate: get('taxRate', true),
    paymentTerms: get('paymentTerms'),
  });
  toast('Saved', 'ok');
}

// ------------------------------------------------------------------ engine

async function engineSection(s, p) {
  const modeSel = el('select', { id: 'set-aiMode' }, [
    { value: 'auto', label: 'Auto — best available, on-device first if privacy is on' },
    { value: 'offline', label: 'Offline only — never call the network' },
    { value: 'ondevice', label: 'On-device model only' },
    { value: 'ollama', label: 'Local Ollama only' },
    { value: 'cloud', label: 'Cloud only' },
    { value: 'local', label: 'Offline brain only (no LLM)' },
  ].map(o => el('option', { value: o.value, selected: s.aiMode === o.value }, [o.label])));

  const privacy = el('input', { type: 'checkbox', id: 'set-privacy', ...(s.preferPrivacy ? { checked: true } : {}) });

  const decision = provider.choose(s, p);
  const status = el('div', { class: 'small', style: { marginTop: '10px' } }, [
    el('div', {}, [el('strong', { text: 'Right now: ' }), el('span', { text: `${provider.engineLabel(decision.engine)} — ${decision.reason}` })]),
    el('div', { class: 'dim', text: `WebGPU: ${p.ondevice && p.ondevice.supported ? 'yes' : 'no (' + (p.ondevice && p.ondevice.reason || 'unsupported') + ')'}` }),
    el('div', { class: 'dim', text: `Ollama: ${p.ollama && p.ollama.ok ? 'connected — ' + (p.ollama.models || []).slice(0, 4).join(', ') : 'not reachable'}` }),
    el('div', { class: 'dim', text: `Cloud: ${p.cloud && p.cloud.configured ? 'configured (' + p.cloud.model + ')' : 'not configured'}` }),
  ]);

  return section('AI engine', [
    field('How should answers be produced?', modeSel),
    el('label', { class: 'row tight small', style: { marginBottom: '10px' } }, [
      privacy, el('span', { text: 'Prefer privacy — use on-device/local before cloud' }),
    ]),
    status,
  ], async () => {
    await saveSettings({
      aiMode: document.getElementById('set-aiMode').value,
      preferPrivacy: document.getElementById('set-privacy').checked,
    });
    toast('Engine settings saved', 'ok');
  });
}

// --------------------------------------------------------------- on-device

async function onDeviceSection(s, p) {
  const supported = p.ondevice && p.ondevice.supported;
  const loaded = p.ondevice && p.ondevice.loaded;
  const cached = (p.ondevice && p.ondevice.cached) || [];

  const sel = el('select', { id: 'set-webllmModel' },
    webllm.MODELS.map(m => el('option', {
      value: m.id, selected: s.webllmModel === m.id,
    }, [`${m.label} · ${m.size}${cached.includes(m.id) ? ' ✓ downloaded' : ''}${m.note ? ' — ' + m.note : ''}`])));

  const progress = el('div', { class: 'bar', hidden: true, id: 'dl-bar' }, [el('i', { style: { width: '0%' } })]);
  const progressText = el('div', { class: 'small dim', id: 'dl-text' });

  const body = [
    el('p', { class: 'small muted', text: supported
      ? 'Runs a real LLM inside the browser. Download once (needs a connection), then it works with wifi off, forever. Nothing leaves your device.'
      : 'This browser has no WebGPU, so on-device models cannot run here. Try Chrome or Edge 113+, or use Ollama below.' }),
    field('Model', sel),
    progress,
    progressText,
    el('div', { class: 'row tight', style: { marginTop: '10px' } }, [
      el('button', {
        class: 'btn', text: loaded ? 'Model loaded' : 'Download & load',
        disabled: !supported || loaded,
        onclick: async () => {
          const modelId = document.getElementById('set-webllmModel').value;
          await saveSettings({ webllmModel: modelId });
          const bar = document.getElementById('dl-bar');
          const txt = document.getElementById('dl-text');
          bar.hidden = false;
          try {
            await webllm.load(modelId, {
              onProgress: (r) => {
                const pct = r.progress ? Math.round(r.progress * 100) : 0;
                bar.firstChild.style.width = pct + '%';
                txt.textContent = r.text || (`${pct}%`);
              },
            });
            await refreshProviders();
            txt.textContent = 'Loaded — this model now answers with no network.';
            toast('On-device model ready', 'ok');
            rerender();
          } catch (err) {
            txt.textContent = 'Failed: ' + err.message;
            toast('Download failed: ' + err.message, 'err');
          }
        },
      }),
      el('button', {
        class: 'btn ghost', text: 'Unload', disabled: !loaded,
        onclick: async () => { await webllm.unload(); await refreshProviders(); rerender(); },
      }),
      el('button', {
        class: 'btn ghost', text: 'Delete downloaded model', disabled: !cached.length,
        onclick: async () => {
          const modelId = document.getElementById('set-webllmModel').value;
          confirmDialog(`Delete the downloaded weights for this model? You can re-download any time.`, async () => {
            await webllm.deleteModel(modelId);
            await refreshProviders();
            toast('Model deleted', 'ok');
            rerender();
          });
        },
      }),
    ]),
  ];

  if (loaded && p.ondevice.model) {
    body.unshift(el('div', { class: 'row tight' }, [
      el('span', { class: 'tag green', text: 'loaded: ' + webllm.modelLabel(p.ondevice.model) }),
    ]));
  }
  if (cached.length) {
    body.push(el('p', { class: 'small dim', style: { marginTop: '10px' },
      text: 'Downloaded on this device: ' + cached.map(webllm.modelLabel).join(', ') }));
  }

  return section('On-device model (works offline)', body, async () => {
    await saveSettings({ webllmModel: document.getElementById('set-webllmModel').value });
    toast('Model preference saved', 'ok');
  });
}

// ----------------------------------------------------------------- ollama

async function ollamaSection(s, p) {
  const ok = p.ollama && p.ollama.ok;
  const models = (p.ollama && p.ollama.models) || [];

  const modelInput = el('input', { id: 'set-ollamaModel', value: s.ollamaModel || '', placeholder: 'qwen2.5-coder:1.5b' });
  if (models.length) {
    const dl = el('datalist', { id: 'ollama-models' }, models.map(m => el('option', { value: m })));
    modelInput.setAttribute('list', 'ollama-models');
    modelInput.setAttribute('list', 'ollama-models');
    // datalist must be in the DOM
    setTimeout(() => { if (!document.getElementById('ollama-models')) document.body.appendChild(dl); }, 0);
  }

  return section('Local Ollama', [
    el('p', { class: 'small muted', text: 'Bigger models than fit in a browser tab, still entirely on your machine. Requests go through your sync server proxy by default.' }),
    grid([
      field('Model', modelInput),
      field('Ollama host (blank = proxy through this server)', el('input', {
        id: 'set-ollamaHost', value: s.ollamaHost || '', placeholder: 'http://127.0.0.1:11434',
      })),
    ]),
    el('div', { class: 'row tight' }, [
      el('span', { class: 'tag ' + (ok ? 'green' : ''), text: ok ? 'connected' : 'not reachable' }),
      el('button', {
        class: 'btn ghost sm', text: 'Test',
        onclick: async () => {
          const r = await ollama.ping(state.settings);
          await refreshProviders();
          if (r.ok) toast('Ollama connected — ' + (r.models || []).length + ' models', 'ok');
          else toast('Ollama not reachable: ' + r.error, 'err');
          rerender();
        },
      }),
    ]),
    el('p', { class: 'small dim', text: ollama.INSTALL_HINT }),
  ], async () => {
    await saveSettings({
      ollamaModel: document.getElementById('set-ollamaModel').value,
      ollamaHost: document.getElementById('set-ollamaHost').value.trim(),
    });
    await refreshProviders();
    toast('Ollama settings saved', 'ok');
  });
}

// ------------------------------------------------------------------ cloud

async function cloudSection(s, p) {
  const providerSel = el('select', { id: 'set-cloudProvider' },
    cloud.PROVIDERS.map(pr => el('option', { value: pr.id, selected: s.cloudProvider === pr.id }, [pr.label])));

  providerSel.addEventListener('change', () => {
    const chosen = cloud.PROVIDERS.find(x => x.id === providerSel.value);
    const model = document.getElementById('set-cloudModel');
    const base = document.getElementById('set-cloudBaseUrl');
    if (chosen && model && !model.value) model.value = chosen.defaultModel;
    if (chosen && base && chosen.defaultBase) base.value = chosen.defaultBase;
  });

  return section('Cloud (only when online)', [
    el('p', { class: 'small muted', text: 'Optional. Used when nothing local is available, or when you want the best quality. Your key stays in this browser unless you use the proxy, in which case it goes to your own server.' }),
    grid([
      field('Provider', providerSel),
      field('Model', el('input', { id: 'set-cloudModel', value: s.cloudModel || '', placeholder: 'gpt-4o-mini' })),
      field('Base URL (OpenAI-compatible)', el('input', { id: 'set-cloudBaseUrl', value: s.cloudBaseUrl || '', placeholder: 'https://api.openai.com/v1' })),
      field('API key', el('input', { id: 'set-cloudKey', value: s.cloudKey || '', type: 'password', placeholder: 'sk-…' })),
    ]),
    el('label', { class: 'row tight small' }, [
      el('input', { type: 'checkbox', id: 'set-cloudViaProxy', ...(s.cloudViaProxy ? { checked: true } : {}) }),
      el('span', { text: 'Route through my sync server (avoids CORS issues)' }),
    ]),
    el('div', { class: 'row tight', style: { marginTop: '10px' } }, [
      el('button', {
        class: 'btn ghost', text: 'Test',
        onclick: async () => {
          const payload = {
            cloudProvider: document.getElementById('set-cloudProvider').value,
            cloudModel: document.getElementById('set-cloudModel').value,
            cloudBaseUrl: document.getElementById('set-cloudBaseUrl').value,
            cloudKey: document.getElementById('set-cloudKey').value,
            cloudViaProxy: document.getElementById('set-cloudViaProxy').checked,
          };
          try {
            const out = await cloud.chat([{ role: 'user', content: 'Reply with the single word: ok' }], {
              settings: payload, serverBase: serverBase(),
            });
            toast('Cloud works: ' + out.text.slice(0, 40), 'ok');
          } catch (err) {
            toast('Cloud failed: ' + err.message, 'err');
          }
        },
      }),
    ]),
  ], async () => {
    await saveSettings({
      cloudProvider: document.getElementById('set-cloudProvider').value,
      cloudModel: document.getElementById('set-cloudModel').value,
      cloudBaseUrl: document.getElementById('set-cloudBaseUrl').value,
      cloudKey: document.getElementById('set-cloudKey').value,
      cloudViaProxy: document.getElementById('set-cloudViaProxy').checked,
    });
    await refreshProviders();
    toast('Cloud settings saved', 'ok');
  });
}

// ------------------------------------------------------------------- data

async function dataSection() {
  const size = await db.estimateSize();
  const lines = [];
  const counts = {};
  for (const c of db.COLLECTIONS) counts[c] = (await db.all(c)).length;
  const pending = await db.outboxCount();

  const wrap = el('div', { class: 'card' }, [el('h3', { text: 'Data' })]);
  wrap.appendChild(el('p', { class: 'small muted', text: size
    ? `Using about ${(size.usage / 1048576).toFixed(1)} MB of local storage. ${pending} change(s) waiting to sync.`
    : 'Storage estimate unavailable. ' + pending + ' change(s) waiting to sync.' }));

  wrap.appendChild(el('div', { class: 'row tight small dim', style: { marginBottom: '12px' } },
    Object.entries(counts).filter(([, n]) => n > 0)
      .map(([k, n]) => el('span', { class: 'tag', text: `${k}: ${n}` }))));

  wrap.appendChild(el('div', { class: 'row tight' }, [
    el('button', {
      class: 'btn ghost', text: 'Export backup (.json)',
      onclick: async () => {
        const data = await db.exportAll();
        download(`hoolulu-backup-${new Date().toISOString().slice(0, 10)}.json`,
          JSON.stringify(data, null, 2), 'application/json');
        toast('Backup exported', 'ok');
      },
    }),
    el('label', { class: 'btn ghost', style: { cursor: 'pointer' } }, [
      'Import backup',
      el('input', {
        type: 'file', accept: '.json,application/json', style: { display: 'none' },
        onchange: async (e) => {
          const file = e.target.files[0];
          if (!file) return;
          try {
            const parsed = JSON.parse(await file.text());
            modal({
              title: 'Import backup',
              body: el('div', {}, [
                el('p', { class: 'small muted', text: `${(parsed.records || []).length} records from ${parsed.exported_at || 'unknown date'}.` }),
              ]),
              actions: [
                { label: 'Merge (newest wins)', kind: '', run: async (close) => {
                  close();
                  const n = await db.importAll(parsed, 'merge');
                  toast(`Imported ${n} records`, 'ok');
                  rerender();
                } },
                { label: 'Replace everything', kind: 'danger', run: async (close) => {
                  close();
                  const n = await db.importAll(parsed, 'replace');
                  toast(`Replaced local data with ${n} records`, 'ok');
                  rerender();
                } },
              ],
            });
          } catch (err) {
            toast('Import failed: ' + err.message, 'err');
          }
        },
      }),
    ]),
    el('button', {
      class: 'btn danger', text: 'Wipe local data',
      onclick: () => confirmDialog('Delete every conversation, project, client and invoice on this device? If a sync server is connected, the next sync will pull them back — use Sync → "Wipe data on the server" to remove them everywhere.', async () => {
        await db.wipeLocal();
        toast('Local data wiped', 'ok');
        rerender();
      }),
    }),
  ]));

  wrap.appendChild(el('p', { class: 'small dim', style: { marginTop: '12px' },
    text: 'Device ID: ' + (await db.deviceId()) }));
  return wrap;
}
