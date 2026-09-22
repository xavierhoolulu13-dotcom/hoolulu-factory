// Money: the whole business side, offline-first. Clients → gigs → proposals →
// invoices → products/sales → expenses. Every number here is computed locally.

import * as db from '../db.js';
import { state, rerender, navigate } from '../app.js';
import { el, clear, money, num, fmtDate, hours, toast, now, uid, slug, renderMarkdown, download } from '../util.js';
import { modal, confirmDialog } from './modal.js';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'clients', label: 'Clients' },
  { id: 'gigs', label: 'Gigs' },
  { id: 'proposals', label: 'Proposals' },
  { id: 'invoices', label: 'Invoices' },
  { id: 'products', label: 'Products' },
  { id: 'expenses', label: 'Expenses' },
];

const STAGES = ['lead', 'contacted', 'proposal', 'won', 'lost'];

let tab = 'overview';

export async function render(root) {
  const tabsEl = el('div', { class: 'tabs' });
  for (const t of TABS) {
    tabsEl.appendChild(el('button', {
      class: 'tab' + (tab === t.id ? ' active' : ''),
      text: t.label,
      onclick: () => { tab = t.id; rerender(); },
    }));
  }
  const body = el('div', { id: 'money-body', style: { marginTop: '4px' } });
  root.append(tabsEl, body);
  await renderTab(body);
}

async function renderTab(body) {
  clear(body);
  const s = state.settings || {};
  switch (tab) {
    case 'overview': return overview(body, s);
    case 'clients': return clients(body, s);
    case 'gigs': return gigs(body, s);
    case 'proposals': return proposals(body, s);
    case 'invoices': return invoices(body, s);
    case 'products': return products(body, s);
    case 'expenses': return expenses(body, s);
  }
}

/** Jump to chat and drop a prompt into the composer, waiting for it to mount. */
function ask(phrase) {
  navigate('chat');
  let tries = 0;
  const tick = () => {
    const ta = document.getElementById('composer-input');
    if (ta) {
      ta.value = phrase;
      ta.focus();
      ta.dispatchEvent(new Event('input'));
      return;
    }
    if (tries++ < 25) setTimeout(tick, 60);
  };
  setTimeout(tick, 40);
}

function field(label, input) {
  return el('label', { class: 'field' }, [el('span', { text: label }), input]);
}

// --------------------------------------------------------------- overview

async function overview(body, s) {
  const [gigs, invoices, sales, expenses, entries, clients] = await Promise.all([
    db.all('gigs'), db.all('invoices'), db.all('sales'),
    db.all('expenses'), db.all('time_entries'), db.all('clients'),
  ]);
  const cur = s.currency || 'USD';

  let pipeline = 0;
  const byStage = {};
  for (const g of gigs) {
    const st = String(g.stage || 'lead').toLowerCase();
    byStage[st] = (byStage[st] || 0) + (Number(g.value) || 0);
    if (!['won', 'lost'].includes(st)) pipeline += Number(g.value) || 0;
  }
  const paid = invoices.filter(i => i.status === 'paid').reduce((a, i) => a + (Number(i.total) || 0), 0);
  const outstanding = invoices.filter(i => ['sent', 'due', 'unpaid'].includes(i.status))
    .reduce((a, i) => a + (Number(i.total) || 0), 0);
  const drafts = invoices.filter(i => (i.status || 'draft') === 'draft')
    .reduce((a, i) => a + (Number(i.total) || 0), 0);
  const productRev = sales.reduce((a, x) => a + (Number(x.amount) || 0), 0);
  const costs = expenses.reduce((a, e) => a + (Number(e.amount) || 0), 0);
  const income = paid + productRev;
  const net = income - costs;
  const secs = entries.reduce((a, e) => a + (Number(e.seconds) || 0), 0);
  const rate = Number(s.hourlyRate) || 0;

  const kpis = el('div', { class: 'grid cols-4' });
  const kpi = (label, value, sub, cls = '') => kpis.appendChild(
    el('div', { class: 'kpi ' + cls }, [
      el('div', { class: 'label', text: label }),
      el('div', { class: 'value', text: value }),
      el('div', { class: 'sub', text: sub || '' }),
    ]));
  kpi('Open pipeline', money(pipeline, cur), gigs.filter(g => !['won', 'lost'].includes(String(g.stage || 'lead'))).length + ' live');
  kpi('Collected', money(income, cur), `${invoices.filter(i => i.status === 'paid').length} invoices + ${sales.length} sales`);
  kpi('Outstanding', money(outstanding, cur),
    `${invoices.filter(i => ['sent', 'due', 'unpaid'].includes(i.status)).length} awaiting payment` +
    (drafts ? ` · ${money(drafts, cur)} in drafts` : ''));
  kpi('Net', money(net, cur), `after ${money(costs, cur)} costs`, net >= 0 ? 'pos' : 'neg');
  kpi('Hours tracked', hours(secs) + 'h', rate ? money(secs / 3600 * rate, cur) + ' at your rate' : 'set a rate');
  kpi('Clients', String(clients.length), 'in your book');
  body.appendChild(kpis);

  // ---- pipeline by stage
  const pipe = el('div', { class: 'card', style: { marginTop: '16px' } });
  pipe.appendChild(el('h3', { text: 'Pipeline' }));
  if (!Object.keys(byStage).length) {
    pipe.appendChild(el('p', { class: 'small dim', text: 'No gigs yet. Add one in the Gigs tab.' }));
  } else {
    const max = Math.max(...Object.values(byStage)) || 1;
    for (const st of STAGES) {
      const v = byStage[st] || 0;
      const row = el('div', { style: { marginBottom: '10px' } }, [
        el('div', { class: 'spread' }, [
          el('span', { class: 'small', text: st }),
          el('strong', { class: 'small', text: money(v, cur) }),
        ]),
      ]);
      const bar = el('div', { class: 'bar' });
      bar.appendChild(el('i', { style: { width: Math.max(2, (v / max) * 100) + '%' } }));
      row.appendChild(bar);
      pipe.appendChild(row);
    }
  }
  body.appendChild(pipe);

  // ---- AI quick actions
  body.appendChild(el('div', { class: 'card', style: { marginTop: '12px' } }, [
    el('h3', { text: 'Do it with the offline brain' }),
    el('p', { class: 'small muted', text: 'These run with no network and read the numbers above.' }),
    el('div', { class: 'chips' }, [
      el('button', { class: 'chip', text: 'Money report', onclick: () => ask('show me my money report') }),
      el('button', { class: 'chip', text: 'Invoice unbilled time', onclick: () => ask('invoice unbilled time') }),
      el('button', { class: 'chip', text: 'Draft a proposal', onclick: () => ask('draft a proposal') }),
      el('button', { class: 'chip', text: 'Price a job', onclick: () => ask('price 20 hours') }),
      el('button', { class: 'chip', text: 'Cold email', onclick: () => ask('write a cold email') }),
      el('button', { class: 'chip', text: 'Launch checklist', onclick: () => ask('launch checklist') }),
    ]),
  ]));

  // ---- recent
  const recentInv = invoices.slice(-5).reverse();
  if (recentInv.length) {
    body.appendChild(el('div', { class: 'card', style: { marginTop: '12px' } }, [
      el('h3', { text: 'Recent invoices' }),
      ...recentInv.map(i => el('div', { class: 'list-row' }, [
        el('div', {}, [
          el('div', { class: 'title', text: i.number || 'invoice' }),
          el('div', { class: 'sub', text: fmtDate(i.issued_at) }),
        ]),
        el('div', { class: 'row tight' }, [
          el('strong', { text: money(Number(i.total) || 0, cur) }),
          el('span', { class: 'tag ' + (i.status === 'paid' ? 'green' : i.status === 'sent' ? 'amber' : ''), text: i.status || 'draft' }),
        ]),
      ])),
    ]));
  }
}

// ---------------------------------------------------------------- clients

async function clients(body, s) {
  const rows = await db.all('clients');
  body.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Add a client' }),
    el('div', { class: 'grid cols-2' }, [
      field('Name', el('input', { id: 'c-name', placeholder: 'Jane Kaui' })),
      field('Company', el('input', { id: 'c-company', placeholder: 'Kaui Surf Co.' })),
      field('Email', el('input', { id: 'c-email', placeholder: 'jane@example.com', type: 'email' })),
      field('Phone', el('input', { id: 'c-phone', placeholder: 'optional' })),
    ]),
    field('Notes', el('input', { id: 'c-notes', placeholder: 'How you met, what they need' })),
    el('button', {
      class: 'btn', text: 'Save client', onclick: async () => {
        const name = document.getElementById('c-name').value.trim();
        if (!name) return toast('Name is required', 'err');
        await db.put('clients', {
          name,
          company: document.getElementById('c-company').value.trim(),
          email: document.getElementById('c-email').value.trim(),
          phone: document.getElementById('c-phone').value.trim(),
          notes: document.getElementById('c-notes').value.trim(),
          created_at: now(),
        });
        toast('Client saved', 'ok');
        rerender();
      },
    }),
  ]));

  if (!rows.length) return body.appendChild(empty('No clients yet', 'Add one above — proposals and invoices get much faster.'));

  body.appendChild(el('h2', { class: 'section', text: `${rows.length} client${rows.length === 1 ? '' : 's'}` }));
  for (const c of rows) {
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title', text: c.name }),
        el('div', { class: 'sub', text: [c.company, c.email, c.phone].filter(Boolean).join(' · ') || 'no contact details' }),
        c.notes ? el('div', { class: 'sub', text: c.notes }) : null,
      ]),
      el('div', { class: 'actions' }, [
        el('button', { class: 'btn ghost sm', text: 'Proposal', onclick: () => ask(`draft a proposal for ${c.name}`) }),
        el('button', { class: 'btn ghost sm', text: 'Delete', onclick: () => confirmDialog(`Delete ${c.name}?`, async () => { await db.remove('clients', c.id); rerender(); }) }),
      ]),
    ]));
  }
}

// ------------------------------------------------------------------- gigs

async function gigs(body, s) {
  const [rows, clients] = await Promise.all([db.all('gigs'), db.all('clients')]);
  const cur = s.currency || 'USD';

  const sel = el('select', { id: 'g-client' }, [
    el('option', { value: '' }, ['— no client —']),
    ...clients.map(c => el('option', { value: c.id }, [c.name])),
  ]);

  body.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Add a gig' }),
    el('div', { class: 'grid cols-2' }, [
      field('What is it?', el('input', { id: 'g-title', placeholder: 'Website rebuild' })),
      field('Value', el('input', { id: 'g-value', type: 'number', placeholder: '2500' })),
      field('Client', sel),
      field('Stage', el('select', { id: 'g-stage' }, STAGES.map(st => el('option', { value: st }, [st])))),
    ]),
    el('button', {
      class: 'btn', text: 'Save gig', onclick: async () => {
        const title = document.getElementById('g-title').value.trim();
        if (!title) return toast('Give it a title', 'err');
        await db.put('gigs', {
          title,
          value: Number(document.getElementById('g-value').value) || 0,
          client_id: document.getElementById('g-client').value || null,
          stage: document.getElementById('g-stage').value,
          created_at: now(),
        });
        toast('Gig saved', 'ok');
        rerender();
      },
    }),
  ]));

  if (!rows.length) return body.appendChild(empty('No gigs yet', 'Every job starts as a gig. Add one above.'));

  body.appendChild(el('h2', { class: 'section', text: 'Pipeline' }));
  const sorted = rows.slice().sort((a, b) => (STAGES.indexOf(a.stage) - STAGES.indexOf(b.stage)) || ((b.value || 0) - (a.value || 0)));
  for (const g of sorted) {
    const client = clients.find(c => c.id === g.client_id);
    const idx = STAGES.indexOf(String(g.stage || 'lead'));
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title', text: g.title }),
        el('div', { class: 'sub', text: [client ? client.name : null, fmtDate(g.created_at)].filter(Boolean).join(' · ') }),
      ]),
      el('div', { class: 'actions' }, [
        el('strong', { text: money(Number(g.value) || 0, cur) }),
        el('span', { class: 'tag ' + tagForStage(g.stage), text: g.stage || 'lead' }),
        el('button', { class: 'btn ghost sm', text: '◀', title: 'Move back', onclick: async () => { await db.put('gigs', { ...g, stage: STAGES[Math.max(0, idx - 1)] }); rerender(); } }),
        el('button', { class: 'btn ghost sm', text: '▶', title: 'Move forward', onclick: async () => { await db.put('gigs', { ...g, stage: STAGES[Math.min(STAGES.length - 1, idx + 1)] }); rerender(); } }),
        el('button', { class: 'btn ghost sm', text: '×', title: 'Delete', onclick: () => confirmDialog(`Delete "${g.title}"?`, async () => { await db.remove('gigs', g.id); rerender(); }) }),
      ]),
    ]));
  }
}

function tagForStage(stage) {
  const s = String(stage || '').toLowerCase();
  if (s === 'won') return 'green';
  if (s === 'lost') return 'red';
  if (s === 'proposal' || s === 'contacted') return 'amber';
  return '';
}

// -------------------------------------------------------------- proposals

async function proposals(body, s) {
  const [rows, clients] = await Promise.all([db.all('proposals'), db.all('clients')]);
  const cur = s.currency || 'USD';

  if (!rows.length) {
    return body.appendChild(el('div', { class: 'empty' }, [
      el('h3', { text: 'No proposals yet' }),
      el('p', { text: 'Say "draft a proposal for <client>" in Chat and one appears here, fully written.' }),
      el('button', { class: 'btn', text: 'Draft one now', onclick: () => ask('draft a proposal') }),
    ]));
  }

  for (const p of rows.slice().reverse()) {
    const client = clients.find(c => c.id === p.client_id);
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title', text: p.title || 'Proposal' }),
        el('div', { class: 'sub', text: [client ? client.name : 'no client', fmtDate(p.created_at)].filter(Boolean).join(' · ') }),
      ]),
      el('div', { class: 'actions' }, [
        p.amount ? el('strong', { text: money(Number(p.amount) || 0, cur) }) : null,
        el('span', { class: 'tag ' + (p.status === 'accepted' ? 'green' : p.status === 'sent' ? 'amber' : ''), text: p.status || 'draft' }),
        el('button', { class: 'btn ghost sm', text: 'View', onclick: () => viewText(p.title || 'Proposal', p.body) }),
        el('button', { class: 'btn sm', text: p.status === 'draft' ? 'Mark sent' : 'Mark accepted', onclick: async () => {
          await db.put('proposals', { ...p, status: p.status === 'draft' ? 'sent' : 'accepted' });
          rerender();
        } }),
        el('button', { class: 'btn ghost sm', text: 'Invoice', onclick: () => ask(`invoice ${client ? client.name : ''} for ${p.amount || 0}`) }),
        el('button', { class: 'btn ghost sm', text: '×', onclick: () => confirmDialog('Delete this proposal?', async () => { await db.remove('proposals', p.id); rerender(); }) }),
      ]),
    ]));
  }
}

// --------------------------------------------------------------- invoices

async function invoices(body, s) {
  const [rows, clients] = await Promise.all([db.all('invoices'), db.all('clients')]);
  const cur = s.currency || 'USD';

  if (!rows.length) {
    return body.appendChild(el('div', { class: 'empty' }, [
      el('h3', { text: 'No invoices yet' }),
      el('p', { text: 'Track time in Projects, then say "invoice unbilled time" — or "invoice Acme for $1200".' }),
      el('button', { class: 'btn', text: 'Create one', onclick: () => ask('invoice unbilled time') }),
    ]));
  }

  for (const i of rows.slice().reverse()) {
    const client = clients.find(c => c.id === i.client_id);
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title mono', text: i.number || 'invoice' }),
        el('div', { class: 'sub', text: [client ? client.name : 'no client', `due ${fmtDate(i.due_at)}`].join(' · ') }),
      ]),
      el('div', { class: 'actions' }, [
        el('strong', { text: money(Number(i.total) || 0, cur) }),
        el('span', { class: 'tag ' + (i.status === 'paid' ? 'green' : i.status === 'sent' ? 'amber' : ''), text: i.status || 'draft' }),
        el('button', { class: 'btn ghost sm', text: 'View', onclick: () => viewInvoice(i, client, cur) }),
        el('button', { class: 'btn sm', text: i.status === 'paid' ? 'Reopen' : i.status === 'draft' ? 'Mark sent' : 'Mark paid', onclick: async () => {
          const next = i.status === 'paid' ? 'sent' : i.status === 'draft' ? 'sent' : 'paid';
          await db.put('invoices', { ...i, status: next, paid_at: next === 'paid' ? now() : null });
          toast(next === 'paid' ? 'Marked paid' : 'Marked sent', 'ok');
          rerender();
        } }),
        el('button', { class: 'btn ghost sm', text: '×', onclick: () => confirmDialog(`Delete ${i.number}?`, async () => { await db.remove('invoices', i.id); rerender(); }) }),
      ]),
    ]));
  }
}

function viewInvoice(inv, client, cur) {
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const rows = (inv.items || []).map(it => `
      <tr>
        <td>${esc(it.description)}</td>
        <td>${esc(it.qty)}</td>
        <td>${money(it.unit, cur)}</td>
        <td>${money((Number(it.qty) || 0) * (Number(it.unit) || 0), cur)}</td>
      </tr>`).join('');

  const html = `
    <h2>${esc(inv.number)}</h2>
    <p><strong>Bill to:</strong> ${esc(client ? client.name : '—')}<br>
    <strong>Issued:</strong> ${fmtDate(inv.issued_at)} · <strong>Due:</strong> ${fmtDate(inv.due_at)}</p>
    <table style="width:100%;border-collapse:collapse;margin:12px 0">
      <thead><tr style="text-align:left;color:#8ea0bf"><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p style="text-align:right"><strong>Subtotal:</strong> ${money(inv.subtotal || inv.total || 0, cur)}</p>
    ${inv.tax ? `<p style="text-align:right"><strong>Tax:</strong> ${money(inv.tax, cur)}</p>` : ''}
    <p style="text-align:right;font-size:18px"><strong>Total due: ${money(inv.total || 0, cur)}</strong></p>
    <p class="small dim">${esc(inv.notes || '')}</p>
  `;
  modal({
    title: 'Invoice',
    wide: true,
    body: el('div', { class: 'md', html }),
    actions: [
      { label: 'Print / save PDF', kind: '', run: () => window.print() },
      { label: 'Download .html', run: () => download(`${inv.number || 'invoice'}.html`, printable(html), 'text/html') },
    ],
  });
}

function printable(inner) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Invoice</title>
  <style>body{font-family:ui-sans-serif,system-ui;max-width:760px;margin:40px auto;color:#111;padding:0 20px}
  table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left}
  th{color:#666}</style></head><body>${inner}</body></html>`;
}

function viewText(title, text) {
  modal({
    title, wide: true,
    body: el('div', { class: 'md', html: renderMarkdown(text || '') }),
    actions: [{ label: 'Download .md', run: () => download(`${slug(title, 'doc')}.md`, text || '', 'text/markdown') }],
  });
}

// --------------------------------------------------------------- products

async function products(body, s) {
  const [rows, sales] = await Promise.all([db.all('products'), db.all('sales')]);
  const cur = s.currency || 'USD';

  body.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Add a product' }),
    el('div', { class: 'grid cols-3' }, [
      field('Name', el('input', { id: 'p-name', placeholder: 'Notion template pack' })),
      field('Channel', el('input', { id: 'p-channel', placeholder: 'Gumroad' })),
      field('Price', el('input', { id: 'p-price', type: 'number', placeholder: '29' })),
    ]),
    el('button', {
      class: 'btn', text: 'Save product', onclick: async () => {
        const name = document.getElementById('p-name').value.trim();
        if (!name) return toast('Name is required', 'err');
        await db.put('products', {
          name,
          channel: document.getElementById('p-channel').value.trim(),
          price: Number(document.getElementById('p-price').value) || 0,
          created_at: now(),
        });
        toast('Product saved', 'ok');
        rerender();
      },
    }),
  ]));

  if (!rows.length) return body.appendChild(empty('No products yet', 'Digital products, courses, templates — anything you sell without trading hours.'));

  body.appendChild(el('h2', { class: 'section', text: 'Products' }));
  for (const p of rows) {
    const sold = sales.filter(x => x.product_id === p.id);
    const rev = sold.reduce((a, x) => a + (Number(x.amount) || 0), 0);
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title', text: p.name }),
        el('div', { class: 'sub', text: `${p.channel || 'direct'} · ${money(p.price || 0, cur)} each · ${sold.length} sold` }),
      ]),
      el('div', { class: 'actions' }, [
        el('strong', { text: money(rev, cur) }),
        el('button', {
          class: 'btn sm', text: 'Record sale', onclick: () => {
            modal({
              title: 'Record a sale — ' + p.name,
              body: el('div', {}, [
                field('Amount', el('input', { id: 's-amount', type: 'number', value: String(p.price || 0) })),
                field('Quantity', el('input', { id: 's-qty', type: 'number', value: '1' })),
              ]),
              actions: [{
                label: 'Save sale', kind: '', run: async (close) => {
                  const qty = Number(document.getElementById('s-qty').value) || 1;
                  const amount = Number(document.getElementById('s-amount').value) || 0;
                  await db.put('sales', { product_id: p.id, qty, amount: amount * qty, sold_at: now(), created_at: now() });
                  close(); toast('Sale recorded', 'ok'); rerender();
                },
              }],
            });
          },
        }),
        el('button', { class: 'btn ghost sm', text: '×', onclick: () => confirmDialog(`Delete ${p.name}?`, async () => { await db.remove('products', p.id); rerender(); }) }),
      ]),
    ]));
  }
}

// --------------------------------------------------------------- expenses

async function expenses(body, s) {
  const rows = await db.all('expenses');
  const cur = s.currency || 'USD';

  body.appendChild(el('div', { class: 'card' }, [
    el('h3', { text: 'Add an expense' }),
    el('div', { class: 'grid cols-3' }, [
      field('What', el('input', { id: 'e-desc', placeholder: 'Domain renewal' })),
      field('Amount', el('input', { id: 'e-amount', type: 'number', placeholder: '12' })),
      field('Category', el('input', { id: 'e-cat', placeholder: 'software' })),
    ]),
    el('button', {
      class: 'btn', text: 'Save expense', onclick: async () => {
        const desc = document.getElementById('e-desc').value.trim();
        if (!desc) return toast('Describe it', 'err');
        await db.put('expenses', {
          description: desc,
          amount: Number(document.getElementById('e-amount').value) || 0,
          category: document.getElementById('e-cat').value.trim() || 'other',
          spent_at: now(), created_at: now(),
        });
        rerender();
      },
    }),
  ]));

  const total = rows.reduce((a, e) => a + (Number(e.amount) || 0), 0);
  body.appendChild(el('h2', { class: 'section', text: `Spend — ${money(total, cur)}` }));
  for (const e of rows.slice().reverse()) {
    body.appendChild(el('div', { class: 'list-row' }, [
      el('div', { class: 'grow' }, [
        el('div', { class: 'title', text: e.description }),
        el('div', { class: 'sub', text: `${e.category || 'other'} · ${fmtDate(e.spent_at)}` }),
      ]),
      el('div', { class: 'actions' }, [
        el('strong', { text: money(Number(e.amount) || 0, cur) }),
        el('button', { class: 'btn ghost sm', text: '×', onclick: () => confirmDialog('Delete this expense?', async () => { await db.remove('expenses', e.id); rerender(); }) }),
      ]),
    ]));
  }
}

function empty(title, text) {
  return el('div', { class: 'empty', style: { marginTop: '14px' } }, [
    el('h3', { text: title }), el('p', { text }),
  ]);
}
