// Queue-and-run-later: prompts you type while nothing smart is available get
// stored locally and answered automatically the moment a real engine appears
// (you reconnect, load an on-device model, or Ollama comes up).

import * as db from '../db.js';
import * as provider from './provider.js';

export async function enqueue({ conversationId, prompt }) {
  return db.put('queued_prompts', {
    conversation_id: conversationId,
    prompt,
    status: 'queued',
    created_at: Date.now(),
  });
}

export async function pending() {
  const rows = await db.all('queued_prompts');
  return rows.filter(r => r.status === 'queued');
}

export async function countPending() {
  return (await pending()).length;
}

/**
 * Try to clear the queue. Only runs when a real engine is actually chosen —
 * otherwise it would churn prompts through the offline brain.
 *
 * @param {(info:{promptId:string, conversationId:string, text:string, provider:string}) => void} onResult
 */
export async function runDue({ settings, status, serverBase = '', onResult } = {}) {
  const items = await pending();
  if (!items.length) return 0;

  const decision = provider.choose(settings, status);
  if (!['ondevice', 'ollama', 'cloud'].includes(decision.engine)) return 0;

  let ran = 0;
  for (const item of items) {
    try {
      const out = await provider.send({
        messages: [{ role: 'user', content: item.prompt }],
        settings, status, serverBase,
        force: decision.engine,
      });
      await db.put('messages', {
        conversation_id: item.conversation_id,
        role: 'assistant',
        content: out.text,
        provider: out.provider,
        model: out.model,
        queued: true,
        created_at: Date.now(),
      });
      await db.put('queued_prompts', { ...item, status: 'done', result: out.text, ran_at: Date.now() });
      ran++;
      if (onResult) onResult({
        promptId: item.id, conversationId: item.conversation_id,
        text: out.text, provider: out.provider,
      });
    } catch (err) {
      console.warn('[queue] failed', err);
      await db.put('queued_prompts', { ...item, status: 'queued', last_error: String(err.message || err) });
      break; // stop; likely still no engine
    }
  }
  return ran;
}

/** Drop completed entries so the log does not grow forever. */
export async function prune(olderThanDays = 7) {
  const cutoff = Date.now() - olderThanDays * 86400000;
  const rows = await db.all('queued_prompts');
  for (const r of rows) {
    if (r.status === 'done' && (r.ran_at || 0) < cutoff) {
      await db.purge('queued_prompts', r.id);
    }
  }
}
