// Projects: scaffolded by the offline brain, edited here, previewed here,
// exported here. Files live in IndexedDB, so all of it works on a plane.

import * as db from '../db.js';
import { state, rerender, navigate } from '../app.js';
import { el, clear, toast, uid, now, makeZip, download, slug, renderMarkdown, hours } from '../util.js';

let selectedId = null;
let selectedFile = null;
const timer = { running: false, startedAt: 0, taskId: null, label: '' };

export async function render(root) {
  if (selectedId) {
    const proj = await db.get('projects', selectedId);
    if (!proj) { selectedId = null; return render(root); }
    return renderProject(root, proj);
  }
  return renderList(root);
}

// ------------------------------------------------------------- project list

async function renderList(root) {
  const projects = (await db.all('projects'))
    .sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));

  const head = el('div', { class: 'spread' }, [
    el('div', {}, [
      el('h3', { text: `${projects.length} project${projects.length === 1 ? '' : 's'}` }),
      el('p', { class: 'small muted', text: 'Stored on this device. Synced when you reconnect.' }),
    ]),
    el('div', { class: 'row tight' }, [
      el('button', { class: 'btn', text: 'New project', onclick: newProject }),
    ]),
  ]);

  const askRow = el('div', { class: 'card', style: { marginTop: '14px' } }, [
    el('h3', { text: 'Or have the offline brain build one' }),
    el('p', { class: 'small muted', text: 'No network needed. Landing pages, dashboards, Flask/FastAPI/Express APIs, Chrome extensions, Python CLIs, bots.' }),
    el('div', { class: 'row', style: { marginTop: '10px' } }, [
      el('input', {
        id: 'ask-build', placeholder: 'build a dashboard for tracking surf conditions',
        style: { flex: '1' },
      }),
      el('button', { class: 'btn', text: 'Build it', onclick: () => goBuild() }),
    ]),
  ]);

  root.append(head, askRow);

  if (!projects.length) {
    root.appendChild(el('div', { class: 'empty', style: { marginTop: '18px' } }, [
      el('h3', { text: 'No projects yet' }),
      el('p', { text: 'Say "build a landing page for a surf school" in Chat, or type it above.' }),
    ]));
    return;
  }

  const grid = el('div', { class: 'grid cols-2', style: { marginTop: '14px' } });
  for (const p of projects) {
    const files = (await db.all('files')).filter(f => f.project_id === p.id);
    const tasks = (await db.all('tasks')).filter(t => t.project_id === p.id);
    const done = tasks.filter(t => t.status === 'done').length;

    grid.appendChild(el('div', { class: 'card' }, [
      el('div', { class: 'spread' }, [
        el('strong', { text: p.name }),
        el('span', { class: 'tag', text: p.stack || 'project' }),
      ]),
      el('p', { class: 'small muted', text: p.description || 'No description', style: { margin: '8px 0 10px' } }),
      el('div', { class: 'row small dim' }, [
        el('span', { text: `${files.length} files` }),
        el('span', { text: '·' }),
        el('span', { text: `${done}/${tasks.length} tasks done` }),
      ]),
      el('div', { class: 'row tight', style: { marginTop: '12px' } }, [
        el('button', { class: 'btn sm', text: 'Open', onclick: () => { selectedId = p.id; selectedFile = null; rerender(); } }),
        el('button', { class: 'btn ghost sm', text: 'Delete', onclick: () => removeProject(p) }),
      ]),
    ]));
  }
  root.appendChild(grid);
}

async function newProject() {
  const name = prompt('Project name?');
  if (!name) return;
  const p = await db.put('projects', {
    name, stack: 'blank', status: 'planning', description: '', created_at: now(),
  });
  await db.put('files', {
    project_id: p.id, path: 'index.html',
    content: `<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>${name}</title>\n</head>\n<body>\n  <h1>${name}</h1>\n</body>\n</html>\n`,
    created_at: now(),
  });
  selectedId = p.id;
  selectedFile = 'index.html';
  rerender();
}

async function removeProject(p) {
  if (!confirm(`Delete "${p.name}" and all its files?`)) return;
  for (const f of await db.all('files')) if (f.project_id === p.id) await db.remove('files', f.id);
  for (const t of await db.all('tasks')) if (t.project_id === p.id) await db.remove('tasks', t.id);
  await db.remove('projects', p.id);
  toast('Project deleted', 'ok');
  rerender();
}

function goBuild() {
  const input = document.getElementById('ask-build');
  const v = (input && input.value || '').trim();
  if (!v) return;
  // Hand the prompt to Chat, which owns the AI pipeline.
  navigate('chat');
  let tries = 0;
  const tick = () => {
    const ta = document.getElementById('composer-input');
    if (ta) {
      ta.value = v;
      ta.focus();
      ta.dispatchEvent(new Event('input'));
      return;
    }
    if (tries++ < 25) setTimeout(tick, 60);
  };
  setTimeout(tick, 40);
}

// ----------------------------------------------------------- single project

async function renderProject(root, proj) {
  const files = (await db.all('files'))
    .filter(f => f.project_id === proj.id)
    .sort((a, b) => a.path.localeCompare(b.path));
  const tasks = (await db.all('tasks')).filter(t => t.project_id === proj.id);

  if (!selectedFile && files.length) selectedFile = files[0].path;
  const file = files.find(f => f.path === selectedFile) || files[0] || null;

  // header
  root.appendChild(el('div', { class: 'spread', style: { marginBottom: '14px' } }, [
    el('div', {}, [
      el('div', { class: 'row tight' }, [
        el('button', { class: 'btn ghost sm', text: '← Projects', onclick: () => { selectedId = null; rerender(); } }),
        el('h3', { text: proj.name, style: { margin: '0' } }),
        el('span', { class: 'tag', text: proj.stack || 'project' }),
      ]),
    ]),
    el('div', { class: 'row tight' }, [
      el('button', { class: 'btn sm', text: 'Preview', onclick: () => preview(files, proj) }),
      el('button', { class: 'btn ghost sm', text: 'Export .zip', onclick: () => exportZip(files, proj) }),
      el('button', { class: 'btn ghost sm', text: 'Rename', onclick: async () => {
        const n = prompt('New name?', proj.name);
        if (n) { await db.put('projects', { ...proj, name: n }); rerender(); }
      } }),
    ]),
  ]));

  const layout = el('div', { class: 'proj-layout' });

  // ---- file list
  const fileList = el('div', { class: 'card' }, [
    el('div', { class: 'spread', style: { marginBottom: '8px' } }, [
      el('strong', { class: 'small', text: 'Files' }),
      el('button', { class: 'btn tiny ghost', text: '+ New', onclick: async () => {
        const p = prompt('File path (e.g. src/util.js)?');
        if (!p) return;
        await db.put('files', { project_id: proj.id, path: p, content: '', created_at: now() });
        selectedFile = p; rerender();
      } }),
    ]),
    el('div', { class: 'file-list' }),
  ]);

  const fl = fileList.querySelector('.file-list');
  if (!files.length) {
    fl.appendChild(el('p', { class: 'small dim', text: 'No files yet.' }));
  }
  for (const f of files) {
    fl.appendChild(el('div', {
      class: 'file-item' + (file && f.path === selectedFile ? ' active' : ''),
      onclick: () => { selectedFile = f.path; rerender(); },
    }, [
      el('span', { class: 'wrap-any', text: f.path }),
      el('button', {
        class: 'del x', text: '×', title: 'Delete file',
        onclick: async (e) => {
          e.stopPropagation();
          if (!confirm(`Delete ${f.path}?`)) return;
          await db.remove('files', f.id);
          if (selectedFile === f.path) selectedFile = null;
          rerender();
        },
      }),
    ]));
  }
  layout.appendChild(fileList);

  // ---- editor
  const editorCard = el('div', { class: 'card' });
  if (file) {
    const ta = el('textarea', { class: 'code-area', id: 'code-area', spellcheck: 'false' });
    ta.value = file.content || '';
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const s = ta.selectionStart;
        ta.value = ta.value.slice(0, s) + '  ' + ta.value.slice(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = s + 2;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveFile(); }
    });

    editorCard.append(
      el('div', { class: 'editor-head' }, [
        el('strong', { class: 'mono small', text: file.path }),
        el('div', { class: 'row tight' }, [
          el('span', { class: 'small dim', id: 'save-state', text: 'Ctrl+S to save' }),
          el('button', { class: 'btn sm', text: 'Save', onclick: saveFile }),
        ]),
      ]),
      ta,
    );

    async function saveFile() {
      const content = document.getElementById('code-area').value;
      await db.put('files', { ...file, content });
      const s = document.getElementById('save-state');
      if (s) { s.textContent = 'Saved ' + new Date().toLocaleTimeString(); setTimeout(() => { s.textContent = 'Ctrl+S to save'; }, 2200); }
      toast('Saved ' + file.path, 'ok', 1400);
    }
  } else {
    editorCard.appendChild(el('div', { class: 'empty' }, [
      el('h3', { text: 'No file open' }),
      el('p', { text: 'Create a file, or ask the offline brain to build something.' }),
    ]));
  }
  layout.appendChild(editorCard);
  root.appendChild(layout);

  // ---- tasks + timer
  root.appendChild(await renderTasks(proj, tasks));
}

async function renderTasks(proj, tasks) {
  const wrap = el('div', { style: { marginTop: '18px' } });
  wrap.appendChild(el('div', { class: 'spread' }, [
    el('h3', { text: 'Tasks & time', style: { margin: '0' } }),
    el('div', { class: 'row tight' }, [
      el('span', { class: 'small mono', id: 'timer-label', text: timer.running ? 'running…' : '' }),
      el('button', {
        class: 'btn sm ' + (timer.running ? 'danger' : 'ghost'),
        text: timer.running ? 'Stop timer' : 'Start timer',
        onclick: () => toggleTimer(proj),
      }),
    ]),
  ]));

  const input = el('input', { placeholder: 'Add a task, press Enter', style: { marginTop: '10px' } });
  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter' && input.value.trim()) {
      await db.put('tasks', { project_id: proj.id, title: input.value.trim(), status: 'todo', created_at: now() });
      input.value = '';
      rerender();
    }
  });
  wrap.appendChild(input);

  const cols = el('div', { class: 'kanban', style: { marginTop: '12px' } });
  for (const status of ['todo', 'doing', 'done']) {
    const col = el('div', { class: 'kanban-col' }, [
      el('h4', { text: status === 'todo' ? 'To do' : status === 'doing' ? 'Doing' : 'Done' }),
    ]);
    for (const t of tasks.filter(x => (x.status || 'todo') === status)) {
      col.appendChild(el('div', { class: 'task' }, [
        el('button', {
          class: 'x', text: '→', title: 'Move to next column',
          onclick: async () => {
            const next = status === 'todo' ? 'doing' : status === 'doing' ? 'done' : 'todo';
            await db.put('tasks', { ...t, status: next });
            rerender();
          },
        }),
        el('span', { class: 'grow wrap-any', text: t.title }),
        el('button', {
          class: 'x', text: '×', title: 'Delete',
          onclick: async () => { await db.remove('tasks', t.id); rerender(); },
        }),
      ]));
    }
    cols.appendChild(col);
  }
  wrap.appendChild(cols);

  const entries = (await db.all('time_entries')).filter(e => e.project_id === proj.id);
  if (entries.length) {
    const total = entries.reduce((s, e) => s + (Number(e.seconds) || 0), 0);
    wrap.appendChild(el('p', { class: 'small dim', style: { marginTop: '10px' },
      text: `${hours(total)}h tracked across ${entries.length} session${entries.length === 1 ? '' : 's'}` }));
  }
  return wrap;
}

async function toggleTimer(proj) {
  if (timer.running) {
    const seconds = Math.round((Date.now() - timer.startedAt) / 1000);
    await db.put('time_entries', {
      project_id: proj.id, task_id: timer.taskId, seconds,
      started_at: timer.startedAt, ended_at: Date.now(),
      billable: true, created_at: now(),
    });
    timer.running = false;
    toast(`Logged ${hours(seconds)}h`, 'ok');
  } else {
    timer.running = true;
    timer.startedAt = Date.now();
    toast('Timer running', 'info', 1600);
  }
  rerender();
}

// -------------------------------------------------------------- preview/zip

function buildSrcDoc(files, entry = 'index.html') {
  let html = (files.find(f => f.path === entry) || files[0]);
  if (!html) return '<p>No files</p>';
  let out = html.content || '';

  out = out.replace(/<link[^>]+href=["']([^"']+)["'][^>]*>/gi, (m, href) => {
    const f = files.find(x => x.path === href || x.path.endsWith('/' + href));
    return f ? `<style>\n${f.content}\n</style>` : m;
  });
  out = out.replace(/<script([^>]*)\ssrc=["']([^"']+)["'][^>]*>\s*<\/script>/gi, (m, attrs, src) => {
    const f = files.find(x => x.path === src || x.path.endsWith('/' + src));
    return f ? `<script${attrs}>\n${f.content}\n<\/script>` : m;
  });
  return out;
}

function preview(files, proj) {
  const entry = proj.entry || 'index.html';
  const back = el('div', { class: 'modal-back' });
  const close = () => back.remove();
  back.addEventListener('click', (e) => { if (e.target === back) close(); });

  const frame = el('iframe', {
    class: 'preview-frame', sandbox: 'allow-scripts allow-modals',
    srcdoc: buildSrcDoc(files, entry),
  });

  back.appendChild(el('div', { class: 'modal' }, [
    el('div', { class: 'spread' }, [
      el('h3', { text: 'Preview — ' + proj.name }),
      el('button', { class: 'btn ghost sm', text: 'Close', onclick: close }),
    ]),
    el('p', { class: 'small dim', text: 'Sandboxed: scripts run, but it cannot reach your page, storage, or the network.' }),
    frame,
  ]));
  document.body.appendChild(back);
}

function exportZip(files, proj) {
  if (!files.length) return toast('Nothing to export', 'err');
  const blob = makeZip(files.map(f => ({ path: f.path, content: f.content })));
  download(`${slug(proj.name, 'project')}.zip`, blob);
  toast('Exported ' + files.length + ' files', 'ok');
}
