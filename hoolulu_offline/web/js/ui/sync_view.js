// Sync view. Shows exactly what is local, what has gone out, and what is stuck.

import * as db from '../db.js';
import * as sync from '../sync.js';
import * as queue from '../ai/queue.js';
import { state, saveSettings, serverBase, rerender } from '../app.js';
import { el, toast, relTime, fmtTime, download } from '../util.js';
import { confirmDialog } from './modal.js';

export async function render(root) {
  const st = sync.getState();
  const s = state.settings;
  const base = serverBase();

  // ------------------------------------------------------------- status
  const card = el('div', { class: 'card' });
  card.appendChild(el('div', { class: 'spread' }, [
    el('h3', { text: 'Sync status', style: { margin: 0 } }),
    el('span', { class: 'tag ' + (st.serverOk ? 'green' : st.serverUrl || base ? 'amber' : ''),
      text: st.serverOk ? 'connected' : (s.serverUrl ? 'unreachable' : 'no server set') }),
  ]));

  const rows = [
    ['Network', navigator.onLine ? 'online' : 'offline'],
    ['Sync server', base || '(none configured — using same origin)'],
    ['Changes waiting', String(st.pending)],
    ['Last sync', st.lastSyncAt ? relTime(st.lastSyncAt) + ' at ' + fmtTime(st.lastSyncAt) : 'never'],
    ['Last push / pull', `${st.lastPush || 0} sent · ${st.lastPull || 0} received`],
    ['Cursor (server seq)', String(st.cursor || 0)],
    ['Queued AI prompts', String(await queue.countPending())],
    ['This device', (await db.deviceId())],
  ];
  if (st.lastError && !st.serverOk) rows.push(['Last error', st.lastError]);

  const table = el('div', { style: { marginTop: '12px' } });
  for (const [k, v] of rows) {
    table.appendChild(el('div', { class: 'spread', style: { padding: '7px 0', borderBottom: '1px solid var(--line-soft)' } }, [
      el('span', { class: 'small muted', text: k }),
      el('span', { class: 'small mono wrap-any', text: String(v) }),
    ]));
  }
  card.appendChild(table);

  card.appendChild(el('div', { class: 'row tight', style: { marginTop: '14px' } }, [
    el('button', {
      class: 'btn', text: st.syncing ? 'Syncing…' : 'Sync now', disabled: st.syncing,
      onclick: async () => {
        const res = await sync.syncNow();
        if (res.ok) toast(`Synced — ${res.pushed} sent, ${res.pulled} received`, 'ok');
        else toast('Sync failed: ' + (res.error || 'unknown'), 'err');
        rerender();
      },
    }),
    el('button', {
      class: 'btn ghost', text: 'Re-download from server',
      title: 'Forget the local sync position and pull every record again',
      onclick: async () => {
        await db.resetCursor();
        const res = await sync.syncNow();
        if (res.ok) toast(`Pulled ${res.pulled} records from the server`, 'ok');
        else toast('Pull failed: ' + (res.error || 'unknown'), 'err');
        rerender();
      },
    }),
    el('button', {
      class: 'btn ghost', text: 'Test connection',
      onclick: async () => {
        const health = await sync.pingServer();
        if (health) toast(`Server OK — ${health.live} records, ${health.devices.length} device(s)`, 'ok');
        else toast('No server: ' + (sync.getState().lastError || ''), 'err');
        rerender();
      },
    }),
  ]));
  root.appendChild(card);

  // ------------------------------------------------------------ settings
  root.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Server' }),
    el('p', { class: 'small muted', text: 'Leave blank to use the server this app was served from. On another device, put the full URL — e.g. http://192.168.1.20:8080 on your wifi, or https://sync.yourdomain.com once you deploy it.' }),
    el('label', { class: 'field' }, [
      el('span', { text: 'Server URL' }),
      el('input', { id: 'sync-url', value: s.serverUrl || '', placeholder: 'https://sync.yourdomain.com' }),
    ]),
    el('label', { class: 'field' }, [
      el('span', { text: 'Sync token (leave blank if the server does not require one)' }),
      el('input', { id: 'sync-token', value: s.syncToken || '', type: 'password', placeholder: 'optional' }),
    ]),
    el('label', { class: 'row tight small', style: { marginBottom: '12px' } }, [
      el('input', { type: 'checkbox', id: 'sync-auto', ...(s.autoSync ? { checked: true } : {}) }),
      el('span', { text: 'Sync automatically when online' }),
    ]),
    el('button', {
      class: 'btn', text: 'Save & test',
      onclick: async () => {
        await saveSettings({
          serverUrl: document.getElementById('sync-url').value.trim(),
          syncToken: document.getElementById('sync-token').value.trim(),
          autoSync: document.getElementById('sync-auto').checked,
        });
        const health = await sync.pingServer();
        if (health) {
          toast('Connected', 'ok');
          await sync.syncNow();
        } else {
          toast('Cannot reach server: ' + (sync.getState().lastError || ''), 'err');
        }
        rerender();
      },
    }),
  ]));

  // ------------------------------------------------------------ devices
  const health = st.serverOk ? await sync.pingServer() : null;
  if (health && health.devices && health.devices.length) {
    root.appendChild(el('div', { class: 'card' }, [
      el('h3', { text: 'Devices on the server' }),
      ...health.devices.map(d => el('div', { class: 'spread', style: { padding: '7px 0', borderBottom: '1px solid var(--line-soft)' } }, [
        el('span', { class: 'small mono', text: d.id }),
        el('span', { class: 'small dim', text: relTime(d.last_seen) }),
      ])),
    ]));
  }

  // --------------------------------------------------------------- data
  root.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Move data without a server' }),
    el('p', { class: 'small muted', text: 'Airplane mode, no VPS, no problem: export a backup, move the file, import it on the other device. Conflicts resolve newest-wins.' }),
    el('div', { class: 'row tight' }, [
      el('button', {
        class: 'btn ghost', text: 'Export backup',
        onclick: async () => {
          download(`hoolulu-backup-${new Date().toISOString().slice(0, 10)}.json`,
            JSON.stringify(await db.exportAll(), null, 2), 'application/json');
        },
      }),
      el('label', { class: 'btn ghost', style: { cursor: 'pointer' } }, [
        'Import backup',
        el('input', {
          type: 'file', accept: '.json', style: { display: 'none' },
          onchange: async (e) => {
            const f = e.target.files[0];
            if (!f) return;
            try {
              const n = await db.importAll(JSON.parse(await f.text()), 'merge');
              toast(`Imported ${n} records`, 'ok');
              rerender();
            } catch (err) { toast('Import failed: ' + err.message, 'err'); }
          },
        }),
      ]),
    ]),
  ]));

  // ------------------------------------------------------------- danger
  root.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Danger zone' }),
    el('div', { class: 'row tight' }, [
      el('button', {
        class: 'btn danger', text: 'Wipe data on the server',
        disabled: !st.serverOk,
        onclick: () => confirmDialog('Delete every record stored on the sync server? Other devices will pull the deletion.', async () => {
          try {
            const res = await fetch(`${serverBase()}/api/wipe`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(state.settings.syncToken ? { 'X-Sync-Token': state.settings.syncToken } : {}),
              },
              body: '{}',
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
            await db.metaSet('sync_cursor', 0);
            toast('Server wiped', 'ok');
            rerender();
          } catch (err) {
            toast('Wipe failed: ' + err.message, 'err');
          }
        }),
      }),
      el('button', {
        class: 'btn danger', text: 'Wipe data on this device',
        onclick: () => confirmDialog(
          'Delete everything stored locally on this device? If a sync server is connected, the next sync will pull your data back down — wipe the server first if you want it gone for good.',
          async () => {
            await db.wipeLocal();
            toast('Local data wiped', 'ok');
            rerender();
          }),
      }),
    ]),
    el('p', { class: 'small dim', style: { marginTop: '10px' },
      text: 'Wiping is not the same as deleting: records still on the server come back on the next sync. Wiping the server requires it to have been started with --token.' }),
  ]));
}
