// Chat view. Works identically online and offline — only the brain answering
// changes, and the UI always tells you which one it was.

import * as db from '../db.js';
import * as provider from '../ai/provider.js';
import * as queue from '../ai/queue.js';
import { state, serverBase, rerender, navigate } from '../app.js';
import { el, clear, renderMarkdown, toast, uid, now, escapeHtml } from '../util.js';

let currentId = null;
let busy = false;

const SUGGESTIONS = [
  'What can you do offline?',
  'Show me my money report',
  'Build a landing page for a surf school',
  'Plan a client onboarding system',
  'Price 30 hours of work',
  'Write a cold email',
  'Explain my sync status',
];

export async function render(root) {
  const wrap = el('div', { class: 'chat-wrap' });

  const select = el('select', { id: 'conv-select' });
  select.addEventListener('change', () => { currentId = select.value; db.metaSet('last_conversation', currentId); rerender(); });

  const delBtn = el('button', { class: 'btn ghost sm', title: 'Delete this conversation', text: 'Delete' });
  delBtn.addEventListener('click', async () => {
    if (!currentId) return;
    if (!confirm('Delete this conversation?')) return;
    for (const m of await db.all('messages')) {
      if (m.conversation_id === currentId) await db.remove('messages', m.id);
    }
    await db.remove('conversations', currentId);
    currentId = null;
    await db.metaSet('last_conversation', '');
    rerender();
  });

  const newBtn = el('button', { class: 'btn sm', text: 'New chat' });
  newBtn.addEventListener('click', async () => { currentId = null; rerender(); });

  const bar = el('div', { class: 'chat-bar' }, [
    select, el('div', { class: 'grow' }), delBtn, newBtn,
  ]);

  const messagesEl = el('div', { class: 'messages', id: 'messages' });

  // ------------------------------------------------------------ composer
  const ta = el('textarea', {
    rows: '2', placeholder: 'Ask anything — works with no network…', id: 'composer-input',
  });
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(180, ta.scrollHeight) + 'px';
  });

  const sendBtn = el('button', { class: 'btn send', text: 'Send' });
  sendBtn.addEventListener('click', () => send());

  const composer = el('div', { class: 'composer' }, [ta, sendBtn]);

  const engineNote = el('div', { class: 'small dim', style: { marginTop: '8px' } });

  wrap.append(bar, messagesEl, composer, engineNote);
  root.appendChild(wrap);

  await refreshConversations(select);
  await paintMessages(messagesEl);
  paintEngineNote(engineNote, messagesEl);
  if (!busy) ta.focus();
}

function paintEngineNote(node, messagesEl) {
  const p = state.providers;
  if (!p || !state.settings) { node.textContent = ''; return; }
  const d = provider.choose(state.settings, p);
  const bits = [];
  bits.push(`Answering with: ${provider.engineLabel(d.engine)} — ${d.reason}`);
  if (!p.online) bits.push('You are offline. Everything still works.');
  node.textContent = bits.join(' ');

  if ((messagesEl.childElementCount === 0)) {
    const chips = el('div', { class: 'chips' });
    for (const s of SUGGESTIONS) {
      chips.appendChild(el('button', {
        class: 'chip', text: s,
        onclick: () => { const ta = document.getElementById('composer-input'); ta.value = s; ta.focus(); },
      }));
    }
    messagesEl.appendChild(el('div', { class: 'empty' }, [
      el('h3', { text: 'Offline workspace ready' }),
      el('p', { text: 'Talk to AI with no network, build projects, and run the money side of your business.' }),
      chips,
    ]));
  }
}

async function refreshConversations(select) {
  const convs = (await db.all('conversations'))
    .sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
  clear(select);
  select.appendChild(el('option', { value: '' }, ['+ start typing to begin']));
  for (const c of convs) {
    select.appendChild(el('option', { value: c.id, selected: c.id === currentId },
      [c.title || 'Untitled']));
  }
  if (!currentId) currentId = (await db.metaGet('last_conversation')) || null;
  if (currentId && !convs.find(c => c.id === currentId)) currentId = null;
  select.value = currentId || '';
}

async function ensureConversation(firstMessage) {
  if (currentId) {
    const c = await db.get('conversations', currentId);
    if (c) return c;
  }
  const conv = await db.put('conversations', {
    title: String(firstMessage).slice(0, 48),
    created_at: now(),
  });
  currentId = conv.id;
  await db.metaSet('last_conversation', conv.id);
  return conv;
}

async function paintMessages(container) {
  clear(container);
  if (!currentId) return;
  const msgs = (await db.all('messages'))
    .filter(m => m.conversation_id === currentId)
    .sort((a, b) => (a.created_at || 0) - (b.created_at || 0));

  for (const m of msgs) container.appendChild(renderMessage(m));
  container.scrollTop = container.scrollHeight;
}

function renderMessage(m) {
  const isUser = m.role === 'user';
  const body = el('div', { class: 'body' });
  const meta = el('div', { class: 'meta' });
  meta.appendChild(el('span', { text: isUser ? 'You' : (m.provider ? provider.engineLabel(m.provider) : 'Assistant') }));
  if (m.model) meta.appendChild(el('span', { class: 'dim', text: m.model }));
  if (m.queued) meta.appendChild(el('span', { class: 'tag amber', text: 'ran from queue' }));
  meta.appendChild(el('span', { class: 'dim', text: new Date(m.created_at || Date.now()).toLocaleTimeString() }));

  const bubble = el('div', { class: 'bubble md' });
  bubble.innerHTML = isUser
    ? `<p>${escapeHtml(m.content).replace(/\n/g, '<br>')}</p>`
    : renderMarkdown(m.content);
  body.append(meta, bubble);
  return el('div', { class: 'msg ' + (isUser ? 'user' : 'ai') }, [
    el('div', { class: 'avatar', text: isUser ? 'You' : 'AI' }),
    body,
  ]);
}

// ------------------------------------------------------------------- sending

async function send() {
  if (busy) return;
  const ta = document.getElementById('composer-input');
  const text = (ta.value || '').trim();
  if (!text) return;

  busy = true;
  ta.value = '';
  ta.style.height = 'auto';
  const sendBtn = document.querySelector('.composer .send');
  if (sendBtn) sendBtn.disabled = true;

  const messagesEl = document.getElementById('messages');
  const conv = await ensureConversation(text);
  currentId = conv.id;

  await db.put('messages', {
    conversation_id: conv.id, role: 'user', content: text, created_at: now(),
  });
  const sel = document.getElementById('conv-select');
  if (sel) await refreshConversations(sel);
  messagesEl.appendChild(renderMessage({
    role: 'user', content: text, created_at: Date.now(),
  }));
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // Thinking placeholder
  const thinking = el('div', { class: 'msg ai' }, [
    el('div', { class: 'avatar', text: 'AI' }),
    el('div', { class: 'body' }, [
      el('div', { class: 'meta' }, [el('span', { text: 'thinking' })]),
      el('div', { class: 'bubble' }, [
        el('span', { class: 'typing' }, [el('i'), el('i'), el('i')]),
        el('span', { class: 'small dim', id: 'progress-text', style: { marginLeft: '10px' } }),
      ]),
    ]),
  ]);
  messagesEl.appendChild(thinking);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const setProgress = (txt) => {
    const n = thinking.querySelector('#progress-text');
    if (n && txt) n.textContent = txt;
  };

  const history = (await db.all('messages'))
    .filter(m => m.conversation_id === conv.id)
    .sort((a, b) => (a.created_at || 0) - (b.created_at || 0))
    .slice(-14)
    .map(m => ({ role: m.role, content: m.content }));

  try {
    const out = await provider.send({
      messages: history,
      settings: state.settings,
      status: state.providers,
      serverBase: serverBase(),
      context: { conversationId: conv.id },
      onProgress: (p) => setProgress(p.text || ''),
    });

    thinking.remove();

    await db.put('messages', {
      conversation_id: conv.id, role: 'assistant', content: out.text,
      provider: out.provider, model: out.model, skill: out.skill || null,
      created_at: now(),
    });

    const node = renderMessage({
      role: 'assistant', content: out.text, provider: out.provider,
      model: out.model, created_at: Date.now(),
    });

    // Show anything the local brain wrote to your database.
    if (out.created && out.created.length) {
      const note = el('div', { class: 'created-note' });
      note.appendChild(el('span', { text: '✓ Saved: ' + out.created.map(c => c.label).join(', ') }));
      if (out.created[0].type === 'project') {
        note.appendChild(el('button', {
          class: 'chip', text: 'Open', style: { marginLeft: '8px' },
          onclick: () => navigate('projects'),
        }));
      }
      node.querySelector('.body').appendChild(note);
    }

    // Offer to queue for a smarter brain when the offline brain was a stretch.
    const lowConfidence = out.provider === 'local' &&
      (out.skill === 'fallback' || (out.confidence != null && out.confidence < 0.5));
    if (lowConfidence) {
      const chips = el('div', { class: 'chips' });
      chips.appendChild(el('button', {
        class: 'chip', text: 'Queue for a real model when online',
        onclick: async () => {
          await queue.enqueue({ conversationId: conv.id, prompt: text });
          chips.remove();
          toast('Queued — it will run the moment a real model is available', 'ok');
        },
      }));
      node.querySelector('.body').appendChild(chips);
    }

    if (out.followups && out.followups.length) {
      const chips = el('div', { class: 'chips' });
      for (const f of out.followups.slice(0, 3)) {
        chips.appendChild(el('button', {
          class: 'chip', text: f,
          onclick: () => { const t = document.getElementById('composer-input'); t.value = f; t.focus(); },
        }));
      }
      node.querySelector('.body').appendChild(chips);
    }

    messagesEl.appendChild(node);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } catch (err) {
    thinking.remove();
    console.error(err);
    messagesEl.appendChild(el('div', { class: 'msg ai' }, [
      el('div', { class: 'avatar', text: '!' }),
      el('div', { class: 'body' }, [
        el('div', { class: 'bubble' }, [
          el('strong', { text: 'That failed: ' }),
          el('span', { class: 'mono', text: String(err.message || err) }),
        ]),
      ]),
    ]));
    toast('Request failed: ' + (err.message || err), 'err');
  } finally {
    busy = false;
    if (sendBtn) sendBtn.disabled = false;
    const t = document.getElementById('composer-input');
    if (t) t.focus();
    const s = document.getElementById('conv-select');
    if (s) refreshConversations(s);
  }
}
