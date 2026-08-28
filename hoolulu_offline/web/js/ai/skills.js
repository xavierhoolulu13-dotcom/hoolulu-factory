// Offline skills. Deterministic, template-driven, and — importantly — they read
// your actual local data, so the answers are about your business, not generic
// filler. These are what make the app useful with the network unplugged.

import * as db from '../db.js';
import { money, hours, fmtDate, uid, now, slug } from '../util.js';

// ------------------------------------------------------------------ helpers

function findByMention(items, prompt, key = 'name') {
  const p = String(prompt || '').toLowerCase();
  let best = null, bestLen = 0;
  for (const it of items) {
    const name = String(it[key] || it.title || '').toLowerCase();
    if (name.length > 2 && p.includes(name) && name.length > bestLen) {
      best = it; bestLen = name.length;
    }
  }
  return best;
}

function amounts(prompt) {
  const out = [];
  const re = /\$\s?(\d[\d,]*(?:\.\d+)?)(k|m)?/gi;
  let m;
  while ((m = re.exec(prompt))) {
    let v = parseFloat(m[1].replace(/,/g, ''));
    if (m[2] && m[2].toLowerCase() === 'k') v *= 1000;
    if (m[2] && m[2].toLowerCase() === 'm') v *= 1000000;
    out.push(v);
  }
  if (!out.length) {
    const bare = String(prompt).match(/\b(\d[\d,]{2,})\b/);
    if (bare) out.push(parseFloat(bare[1].replace(/,/g, '')));
  }
  return out;
}

function hoursMentioned(prompt) {
  const m = String(prompt).match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b/i);
  return m ? parseFloat(m[1]) : null;
}

function bullets(items) { return items.map(i => `- ${i}`).join('\n'); }

function table(rows) {
  if (!rows.length) return '_nothing yet_';
  const head = `| ${Object.keys(rows[0]).join(' | ')} |\n|${Object.keys(rows[0]).map(() => '---').join('|')}|`;
  const body = rows.map(r => `| ${Object.values(r).join(' | ')} |`).join('\n');
  return `${head}\n${body}`;
}

async function nextInvoiceNumber() {
  const all = await db.all('invoices');
  const prefix = 'INV-' + new Date().toISOString().slice(0, 7).replace('-', '');
  const n = all.filter(i => (i.number || '').startsWith(prefix)).length + 1;
  return `${prefix}-${String(n).padStart(3, '0')}`;
}

// ------------------------------------------------------------------- skills

export const SKILLS = [
  // ----------------------------------------------------------------- help
  {
    id: 'help',
    title: 'What I can do offline',
    keywords: ['help', 'what can you do', 'commands', 'capabilities', 'how do i',
      'what do you do', 'menu', 'options', '?'],
    patterns: [/^help\b/i, /^what can you/i],
    async run({ settings }) {
      const rate = money(settings.hourlyRate || 85, settings.currency);
      return {
        text: `## Offline brain — what I can do

I run **entirely on your device**. No network, no API key, no cost. I read and
write your local data, so the answers are about *your* business.

**Money**
- \`money\` — revenue, pipeline, outstanding invoices, profit, hours
- \`proposal for <client> about <work>\` — drafts and saves a proposal
- \`invoice <client> for $1200\` — or \`invoice unbilled time\`
- \`price 40 hours\` / \`quote a website for <client>\` — rate card and tiers

**Projects**
- \`plan a <thing>\` — phased plan, optionally creates the project + tasks
- \`build a <thing>\` — scaffolds runnable files (landing page, dashboard,
  Flask/FastAPI/Express API, Chrome extension, Python CLI, Telegram/Discord bot)
- \`standup\` — summary of what moved today

**Sales**
- \`cold email to <client>\` / \`dm <client>\` / \`follow up with <client>\`
- \`checklist\` — launch or client-onboarding checklists

**Coding**
- \`code <what>\` — snippets (regex, SQL, fetch, cron, git, CSS grid)
- \`debug <problem>\` — a structured debugging path

Your default rate is **${rate}/hour** — change it in Settings.

> Tip: when you're back online (or once an on-device model is loaded), the same
> prompt gets answered by a real LLM instead. I always show which brain replied.`,
      };
    },
  },

  // ---------------------------------------------------------------- status
  {
    id: 'status',
    title: 'System status',
    keywords: ['status', 'sync status', 'am i online', 'offline status', 'connection',
      'is sync working', 'health'],
    patterns: [/^status\b/i, /\bsync status\b/i],
    async run({ runtime }) {
      const r = runtime || {};
      const lines = [
        `**Network:** ${r.online ? 'online' : 'offline'}`,
        `**Sync server:** ${r.serverOk ? 'connected' : (r.serverUrl ? 'unreachable' : 'not configured')}`,
        `**Pending changes:** ${r.pending ?? 0}`,
        `**Last sync:** ${r.lastSyncAt ? fmtDate(r.lastSyncAt) + ' ' + new Date(r.lastSyncAt).toLocaleTimeString() : 'never'}`,
        `**AI engine:** ${r.engine || 'offline brain'}`,
        `**On-device model:** ${r.webllmModel || 'not loaded'}`,
      ];
      return {
        text: `## Status\n\n${bullets(lines)}\n\n${
          r.pending > 0 && !r.serverOk
            ? 'Your data is safe locally. The moment a sync server is reachable, these changes go out automatically.'
            : r.serverOk
              ? 'Everything is backed up to your sync server.'
              : 'Running fully local. Add a server URL in Settings → Sync to replicate between devices.'
        }`,
      };
    },
  },

  // ----------------------------------------------------------------- money
  {
    id: 'money',
    title: 'Money report',
    keywords: ['money', 'revenue', 'income', 'profit', 'earnings', 'how much did i make',
      'financial', 'cash', 'report', 'kpi', 'numbers', 'summary', 'earned', 'padding'],
    patterns: [/\bhow much (did|have) i\b/i, /\bmoney report\b/i, /^money\b/i],
    async run({ settings }) {
      const [gigs, invoices, sales, expenses, timeEntries, clients] = await Promise.all([
        db.all('gigs'), db.all('invoices'), db.all('sales'),
        db.all('expenses'), db.all('time_entries'), db.all('clients'),
      ]);
      const cur = settings.currency;

      const stage = {};
      let pipeline = 0, won = 0;
      for (const g of gigs) {
        const s = g.stage || 'lead';
        stage[s] = (stage[s] || 0) + (Number(g.value) || 0);
        if (['won', 'closed', 'delivered', 'paid'].includes(String(s).toLowerCase())) won += Number(g.value) || 0;
        else pipeline += Number(g.value) || 0;
      }

      const paid = invoices.filter(i => (i.status || '').toLowerCase() === 'paid')
        .reduce((s, i) => s + (Number(i.total) || 0), 0);
      const isDue = (i) => ['sent', 'due', 'unpaid'].includes((i.status || '').toLowerCase());
      const outstanding = invoices.filter(isDue).reduce((s, i) => s + (Number(i.total) || 0), 0);
      const drafts = invoices.filter(i => (i.status || 'draft').toLowerCase() === 'draft')
        .reduce((s, i) => s + (Number(i.total) || 0), 0);
      const productRevenue = sales.reduce((s, x) => s + (Number(x.amount) || 0), 0);
      const costs = expenses.reduce((s, e) => s + (Number(e.amount) || 0), 0);
      const secs = timeEntries.reduce((s, t) => s + (Number(t.seconds) || 0), 0);
      const billableSecs = timeEntries.filter(t => t.billable !== false)
        .reduce((s, t) => s + (Number(t.seconds) || 0), 0);
      const income = paid + productRevenue;
      const profit = income - costs;

      const rows = [
        ['Open pipeline', money(pipeline, cur), gigs.filter(g => !['won', 'closed', 'lost'].includes((g.stage || '').toLowerCase())).length + ' open'],
        ['Invoiced & paid', money(paid, cur), invoices.filter(i => i.status === 'paid').length + ' invoices'],
        ['Outstanding', money(outstanding, cur), invoices.filter(isDue).length + ' awaiting payment'],
        ['Drafts (not sent)', money(drafts, cur), invoices.filter(i => (i.status || 'draft') === 'draft').length + ' unsent'],
        ['Product sales', money(productRevenue, cur), sales.length + ' sales'],
        ['Expenses', '−' + money(costs, cur), expenses.length + ' entries'],
        ['**Net**', '**' + money(profit, cur) + '**', `${hours(billableSecs)}h tracked`],
      ];

      const actions = [];
      const due = invoices.filter(i => ['sent', 'due', 'unpaid'].includes((i.status || '').toLowerCase()));
      if (due.length) {
        actions.push(`Chase ${due.length} unpaid invoice${due.length > 1 ? 's' : ''} — ${money(outstanding, cur)} sitting there. Oldest first.`);
      }
      const stale = gigs.filter(g => !['won', 'closed', 'lost'].includes((g.stage || '').toLowerCase()) &&
        (Date.now() - (g.updated_at || 0)) > 7 * 86400000);
      if (stale.length) {
        actions.push(`${stale.length} gig${stale.length > 1 ? 's' : ''} untouched for a week. Follow up or close them.`);
      }
      if (billableSecs === 0 && gigs.length) actions.push('No time tracked yet — start the timer so you can prove the value of the work.');
      if (!clients.length) actions.push('Add your clients first; proposals and invoices get much faster with them saved.');
      if (!actions.length) actions.push('Pipeline is clean. Spend the hour finding two new leads.');

      return {
        text: `## Money — ${new Date().toLocaleDateString()}

${table(rows.map(([k, v, note]) => ({ Item: k, Amount: v, Note: note })))}

**Pipeline by stage**
${Object.keys(stage).length
          ? bullets(Object.entries(stage).map(([s, v]) => `${s}: ${money(v, cur)}`))
          : '_No gigs yet. Add one in Money → Gigs._'}

**Next three moves**
${bullets(actions.slice(0, 3).map((a, i) => `${i + 1}. ${a}`))}`,
      };
    },
  },

  // -------------------------------------------------------------- proposal
  {
    id: 'proposal',
    title: 'Draft a proposal',
    keywords: ['proposal', 'pitch', 'quote', 'scope of work', 'sow', 'bid', 'offer',
      'send a proposal', 'draft a proposal'],
    patterns: [/\bproposal\b/i, /\bscope of work\b/i, /\bquote for\b/i],
    async run({ prompt, settings, lower }) {
      const clients = await db.all('clients');
      const client = findByMention(clients, prompt) || null;
      const amt = amounts(prompt)[0] || null;
      const hrs = hoursMentioned(prompt);
      const rate = Number(settings.hourlyRate) || 85;
      const cur = settings.currency;
      const price = amt || (hrs ? hrs * rate : null);

      const topic = (() => {
        let t = String(prompt).replace(/^(draft|write|create|make|send)\s+(a|an|the)?\s*/i, '');
        t = t.replace(/\bproposal\b/i, '').replace(/\bfor\b/i, ' ');
        if (client) t = t.replace(new RegExp(client.name, 'i'), '');
        t = t.replace(/\b(for|to|about|worth|budget)\b.*$/i, '').replace(/[\s,.]+$/, '');
        return t.trim().slice(0, 70) || (client ? `Work for ${client.name}` : 'the work');
      })();

      const deliverables = price
        ? ['Discovery call and written scope', 'Build and iterate to sign-off', 'Handover with a short loom-style walkthrough', 'Two weeks of fixes after delivery']
        : ['Discovery call and written scope', 'Build and iterate to sign-off', 'Handover walkthrough'];

      const text = `## Proposal — ${topic}
**For:** ${client ? client.name : '{{client name}}'}
**From:** ${settings.businessName || settings.ownerName || 'Me'}
**Date:** ${fmtDate(Date.now())}
**Valid for:** 14 days

### The situation
${client ? `${client.name} needs ${topic.toLowerCase()} done properly, without it turning into a six-week saga.` : `You need ${topic.toLowerCase()} handled end to end.`}

### What success looks like
${topic} shipped, working, and handed over so your team can run it without me.

### What you get
${bullets(deliverables)}

### Timeline
| Phase | When | What happens |
| --- | --- | --- |
| Kickoff | Day 1 | Scope locked, access granted |
| Build | Days 2–${Math.max(4, Math.round((hrs || 20) / 6))} | Working version you can click through |
| Review | +2 days | Your feedback, my revisions |
| Handover | Final | Walkthrough + written notes |

### Investment
${price
          ? `**${money(price, cur)}**${hrs ? ` (${hrs}h at ${money(rate, cur)}/h)` : ''} — fixed price, no surprises.\n\nPayment: 50% to start, 50% on delivery. ${settings.paymentTerms || 'Net 14'}.`
          : `| Option | Price | Includes |\n| --- | --- | --- |\n| Essential | ${money(rate * 8, cur)} | Core build, 1 revision round |\n| Standard | ${money(rate * 20, cur)} | Everything in Essential + integrations + 2 revision rounds |\n| Partner | ${money(rate * 40, cur)} | Everything + priority turnaround + 30 days support |`}

### What I need from you
- One decision maker who can approve
- Access to the relevant accounts or files
- Feedback within 48 hours at each review point

### Terms
${settings.paymentTerms || 'Net 14'} from invoice date. Two revision rounds included;
further scope is quoted separately. Either side can walk away before kickoff
with a full refund.

---
_Saved as a draft. Edit it in Money → Proposals, then send._`;

      const saved = await db.put('proposals', {
        title: topic,
        client_id: client ? client.id : null,
        body: text,
        amount: price || 0,
        status: 'draft',
        created_at: Date.now(),
      });

      return {
        text,
        created: [{ type: 'proposal', id: saved.id, label: `Draft proposal: ${topic}` }],
        followups: ['Turn this into an invoice', 'Write a follow-up email for this proposal'],
      };
    },
  },

  // --------------------------------------------------------------- invoice
  {
    id: 'invoice',
    title: 'Create an invoice',
    keywords: ['invoice', 'bill', 'bill them', 'charge', 'get paid', 'send invoice',
      'create invoice', 'unbilled'],
    patterns: [/\binvoice\b/i, /\bbill (the )?client\b/i],
    async run({ prompt, settings, lower }) {
      const clients = await db.all('clients');
      const projects = await db.all('projects');
      const client = findByMention(clients, prompt);
      const amt = amounts(prompt)[0] || null;
      const wantsUnbilled = /unbilled|track(ed)? time|hours worked|my time/i.test(lower);

      let items = [];
      let source = '';

      if (wantsUnbilled || (!amt && (await db.all('time_entries')).some(t => !t.invoice_id))) {
        const entries = (await db.all('time_entries')).filter(t => !t.invoice_id);
        const byProject = new Map();
        for (const e of entries) {
          const key = e.project_id || 'general';
          const proj = projects.find(p => p.id === (e.project_id || ''));
          const bucket = byProject.get(key) || {
            description: proj ? `${proj.name} — time` : 'Consulting time',
            qty: 0, unit: Number(proj && proj.rate) || Number(settings.hourlyRate) || 85,
            entries: [],
          };
          bucket.qty += (Number(e.seconds) || 0) / 3600;
          bucket.entries.push(e.id);
          byProject.set(key, bucket);
        }
        for (const b of byProject.values()) {
          if (b.qty > 0) {
            items.push({
              description: b.description,
              qty: Math.round(b.qty * 100) / 100,
              unit: b.unit,
              _entries: b.entries,
            });
          }
        }
        if (items.length) source = `${entries.length} unbilled time entries`;
      }

      if (!items.length && amt) {
        items = [{ description: (client ? `${client.name} — ` : '') + 'Professional services', qty: 1, unit: amt }];
        source = 'a flat amount from your prompt';
      }

      if (!items.length) {
        return {
          text: `I need a number or some tracked time before I can bill it.

Try one of these:
- \`invoice ${clients[0] ? clients[0].name : 'Acme'} for $1200\`
- \`invoice unbilled time\`
- Start a timer in **Projects**, then run \`invoice unbilled time\` again.

${clients.length ? `Your clients: ${clients.map(c => c.name).join(', ')}` : '_No clients saved yet — add one in Money → Clients._'}`,
        };
      }

      const subtotal = items.reduce((s, i) => s + i.qty * i.unit, 0);
      const taxRate = Number(settings.taxRate) || 0;
      const tax = subtotal * taxRate;
      const total = subtotal + tax;
      const number = await nextInvoiceNumber();
      const cur = settings.currency;

      const inv = await db.put('invoices', {
        number,
        client_id: client ? client.id : null,
        status: 'draft',
        items: items.map(({ _entries, ...i }) => i),
        subtotal, tax, total,
        issued_at: Date.now(),
        due_at: Date.now() + 14 * 86400000,
        notes: settings.paymentTerms || 'Net 14',
        created_at: Date.now(),
      });

      // Mark the time entries as billed so you never double-charge.
      for (const it of items) {
        for (const id of it._entries || []) {
          const e = await db.get('time_entries', id);
          if (e) await db.put('time_entries', { ...e, invoice_id: inv.id });
        }
      }

      const lines = items.map(i =>
        `| ${i.description} | ${i.qty} | ${money(i.unit, cur)} | ${money(i.qty * i.unit, cur)} |`).join('\n');

      return {
        text: `## ${number}
**Bill to:** ${client ? client.name : '{{client}}'}
**Issued:** ${fmtDate(Date.now())} · **Due:** ${fmtDate(Date.now() + 14 * 86400000)}

| Description | Qty | Rate | Amount |
| --- | --- | --- | --- |
${lines}
| | | **Subtotal** | **${money(subtotal, cur)}** |
${taxRate ? `| | | Tax (${(taxRate * 100).toFixed(1)}%) | ${money(tax, cur)} |\n` : ''}| | | **Total due** | **${money(total, cur)}** |

Built from ${source}. ${settings.paymentTerms || 'Net 14'}.

Saved as a **draft** — open Money → Invoices to mark it sent, then paid.`,
        created: [{ type: 'invoice', id: inv.id, label: `${number} · ${money(total, cur)}` }],
        followups: ['Write a follow-up email for this invoice', 'Show me my money report'],
      };
    },
  },

  // -------------------------------------------------------------- outreach
  {
    id: 'outreach',
    title: 'Write outreach',
    keywords: ['cold email', 'outreach', 'follow up', 'followup', 'dm', 'message',
      'email', 'pitch', 'reach out', 'chase', 'nudge', 'intro'],
    patterns: [/\b(cold email|follow ?up|reach out|write (a|an)? ?(email|dm|message))\b/i],
    async run({ prompt, lower }) {
      const clients = await db.all('clients');
      const gigs = await db.all('gigs');
      const client = findByMention(clients, prompt) ||
        findByMention(gigs, prompt, 'title') || null;
      const who = client ? (client.name || client.title) : 'there';
      const what = (() => {
        let t = String(prompt).replace(/^(write|draft|send)\s+(a|an|the)?\s*/i, '');
        t = t.replace(/\b(cold email|follow ?up|followup|dm|email|message|outreach)\b/gi, '');
        t = t.replace(/\b(to|for|with|about)\b/gi, ' ');
        return t.trim().slice(0, 60) || 'the work we discussed';
      })();

      return {
        text: `## Outreach for ${who}

**1. Cold email** (under 90 words)

> Subject: ${what.slice(0, 48)}
>
> Hi ${who === 'there' ? 'first name' : who.split(' ')[0]},
>
> ${what.charAt(0).toUpperCase() + what.slice(1)} is the thing teams your size
> keep putting off — usually because it feels like a two-week project.
>
> It isn't. I did it for a similar team in four days, and it paid for itself in
> the first month.
>
> Worth 15 minutes this week? I'll come with a specific plan, not a deck.
>
> — ${'(your name)'}

**2. Short DM**

> Hey ${who === 'there' ? 'first name' : who.split(' ')[0]} — saw you're working
> on ${what}. I build exactly that. Happy to send over a one-page plan, no
> strings. Interested?

**3. Follow-up (send 3 days later)**

> Hi ${who === 'there' ? 'first name' : who.split(' ')[0]} — bumping this once in
> case it got buried. Quick version: I'll deliver ${what}, fixed price, two weeks
> or less. If it's a no, just say no and I'll stop.

---
**Rules that actually matter:** one ask per message, send the follow-up (most
replies come from message 2 or 3), and always name the specific outcome.
${client ? `_Matched to your saved contact: **${who}**._` : '_Save this person in Money → Clients so I can pull their details in next time._'}`,
        followups: ['Draft a proposal for them', 'Add them as a client'],
      };
    },
  },

  // --------------------------------------------------------------- pricing
  {
    id: 'pricing',
    title: 'Price a job',
    keywords: ['price', 'pricing', 'how much should i charge', 'rate', 'quote', 'cost',
      'charge', 'estimate', 'worth', 'what do i charge'],
    patterns: [/\bhow much should i charge\b/i, /\bprice (this|the|a|it)\b/i, /\brate card\b/i],
    async run({ prompt, settings }) {
      const hrs = hoursMentioned(prompt);
      const amt = amounts(prompt)[0];
      const rate = Number(settings.hourlyRate) || 85;
      const cur = settings.currency;
      const h = hrs || (amt ? amt / rate : 20);

      const base = h * rate;
      const overhead = base * 0.25;       // admin, revisions, scope creep
      const risk = base * 0.15;           // unknowns
      const floor = base + overhead;
      const target = base + overhead + risk;
      const premium = target * 1.6;

      return {
        text: `## Pricing — ${h}h of work

| | Amount | Notes |
| --- | --- | --- |
| Floor (never go below) | ${money(floor, cur)} | ${h}h × ${money(rate, cur)} + 25% overhead |
| **Target** | **${money(target, cur)}** | + 15% for the unknown unknowns |
| Premium / value-based | ${money(premium, cur)} | Use when you're priced against an outcome |

**Package it as three options** — people rarely pick the cheapest or dearest:

| Tier | Price | What they get |
| --- | --- | --- |
| Essential | ${money(floor, cur)} | The core deliverable. One revision. |
| **Standard** | **${money(target, cur)}** | Core + integrations + two revisions. Flag this one. |
| Partner | ${money(premium, cur)} | Everything + priority + 30 days support. |

**Anchor it in their outcome, not your hours.** If ${h} hours of your work makes
them ${money(base * 5, cur)} or saves them ${hours(h * 8)} of theirs a month,
${money(target, cur)} is a bargain — say that out loud in the call.

_Rate used: ${money(rate, cur)}/h. Change it in Settings._`,
        followups: [`Write a proposal at ${money(target, cur)}`, 'Show me my money report'],
      };
    },
  },

  // ------------------------------------------------------------------ plan
  {
    id: 'plan',
    title: 'Plan a project',
    keywords: ['plan', 'roadmap', 'break down', 'steps', 'how do i build',
      'project plan', 'outline', 'phases', 'strategy', 'approach'],
    patterns: [/\b(plan|roadmap|break ?down)\b/i, /\bhow (do|would) i (build|start|launch)\b/i],
    async run({ prompt, lower }) {
      const topic = extractTopicFrom(prompt);
      const wantsCreate = /\b(create|save|add|make) (it|the|this|a|these)\b/i.test(lower) ||
        /\bas (a|the) project\b/i.test(lower) ||
        /\b(create|save|add)\b.*\b(tasks?|project)\b/i.test(lower);

      const phases = [
        {
          name: 'Clarify (do not skip this)',
          why: 'Most projects fail here, not in the build.',
          tasks: [
            `Write one sentence: what does ${topic} do, for whom?`,
            'List the three things it must do to be worth shipping',
            'Name the single metric that means it worked',
            'Decide what you are explicitly NOT building',
          ],
        },
        {
          name: 'Skeleton',
          why: 'Get something clickable before you get it right.',
          tasks: [
            'Set up the folder and the entry file',
            'Build the smallest version that runs end to end',
            'Hardcode the data — no integrations yet',
            'Show it to one real person today',
          ],
        },
        {
          name: 'Make it real',
          why: 'Now swap the fake parts for real ones.',
          tasks: [
            'Wire in the real data source',
            'Handle the three most likely failures',
            'Persist state so a refresh does not lose work',
            'Add the one feature they asked for twice',
          ],
        },
        {
          name: 'Ship and get paid',
          why: 'Unshipped work is worth zero.',
          tasks: [
            'Write the 5-line README (what, why, how to run)',
            'Deploy it somewhere with a URL',
            'Send the invoice the same day you deliver',
            'Ask for a testimonial while they are still happy',
          ],
        },
      ];

      let created = [];
      if (wantsCreate) {
        const proj = await db.put('projects', {
          name: topic, stack: 'plan', status: 'planning',
          description: `Plan for ${topic}`, created_at: Date.now(),
        });
        for (const ph of phases) {
          for (const t of ph.tasks) {
            await db.put('tasks', {
              project_id: proj.id, title: t, status: 'todo',
              phase: ph.name, created_at: Date.now(),
            });
          }
        }
        created = [{ type: 'project', id: proj.id, label: `${topic} (+${phases.reduce((n, p) => n + p.tasks.length, 0)} tasks)` }];
      }

      const body = phases.map((p, i) =>
        `### ${i + 1}. ${p.name}\n_${p.why}_\n${bullets(p.tasks)}`).join('\n\n');

      return {
        text: `## Plan — ${topic}

${body}

**Rule of thumb:** if a phase takes more than two days, it is two phases.
${wantsCreate ? '\nSaved as a project with every task already in it — open Projects to see it.' : '\nSay _"create this as a project"_ and I will save it with all the tasks.'}`,
        created,
        followups: ['Create this as a project', `Build ${topic}`, `Price this project`],
      };
    },
  },

  // --------------------------------------------------------------- standup
  {
    id: 'standup',
    title: "Today's standup",
    keywords: ['standup', 'stand up', 'what did i do today', 'daily', 'today',
      'progress', 'recap', 'summary of today'],
    patterns: [/^standup\b/i, /\bwhat did i (do|get done) today\b/i],
    async run({ settings }) {
      const [tasks, entries, projects] = await Promise.all([
        db.all('tasks'), db.all('time_entries'), db.all('projects'),
      ]);
      const startOfDay = new Date(); startOfDay.setHours(0, 0, 0, 0);
      const t0 = startOfDay.getTime();

      const done = tasks.filter(t => t.status === 'done' && (t.updated_at || 0) >= t0);
      const doing = tasks.filter(t => t.status === 'doing');
      const todo = tasks.filter(t => t.status === 'todo');
      const todaySecs = entries.filter(e => (e.started_at || 0) >= t0)
        .reduce((s, e) => s + (Number(e.seconds) || 0), 0);

      const openProjects = projects.filter(p => p.status !== 'done' && p.status !== 'archived');

      return {
        text: `## Standup — ${new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}

**Shipped today**
${done.length ? bullets(done.map(t => t.title)) : '_Nothing marked done yet. Go tick one — momentum counts._'}

**In progress**
${doing.length ? bullets(doing.map(t => `${t.title}${t.project_id ? ` _(${projName(projects, t.project_id)})_` : ''}`)) : '_Nothing in flight._'}

**Next up**
${bullets((todo.slice(0, 5)).map(t => t.title))}

**Time today:** ${hours(todaySecs)}h ${todaySecs >= 3600 * 4 ? '— solid day.' : todaySecs > 0 ? '' : '— timer has not run yet.'}

**Open projects:** ${openProjects.length ? openProjects.map(p => p.name).join(', ') : 'none'}

${done.length === 0 && todaySecs === 0
          ? '> Nothing logged yet today. Pick the smallest thing on the list and close it before you do anything else.'
          : `> Blockers worth naming out loud: ${doing.length > 3 ? 'you have ' + doing.length + ' things in progress — that is the blocker. Finish one before starting another.' : 'none obvious. Keep going.'}`}`,
        followups: ['Show me my money report', 'Create this as a project'],
      };
    },
  },

  // ------------------------------------------------------------------ code
  {
    id: 'code',
    title: 'Code snippets',
    keywords: ['code', 'snippet', 'regex', 'sql', 'function', 'example', 'how do i write',
      'cron', 'git', 'curl', 'fetch', 'css'],
    patterns: [/\b(regex|sql query|snippet|cron|git command)\b/i, /\bcode for\b/i],
    async run({ prompt, lower }) {
      const p = lower;

      if (/regex|regular expression/.test(p)) {
        const email = /email/.test(p);
        const url = /url|link|http/.test(p);
        const phone = /phone|number/.test(p);
        const chosen = email ? ['Email', '/[^@\\s]+@[^@\\s]+\\.[a-z]{2,}/gi']
          : url ? ['URL', '/https?:\\/\\/[^\\s/$.?#][^\\s]*/gi']
            : phone ? ['Phone (loose)', '/\\+?\\d[\\d\\s().-]{7,}\\d/g']
              : ['Email', '/[^@\\s]+@[^@\\s]+\\.[a-z]{2,}/gi'];
        return {
          text: `## Regex — ${chosen[0]}

\`\`\`js
const re = ${chosen[1]};
const matches = input.match(re) || [];
\`\`\`

**Test it right now** in the console:
\`\`\`js
${chosen[1].replace(/\/[gimsuy]*$/, '/')}.test('test-string')
\`\`\`

**The four you will actually reuse**

| Need | Pattern |
| --- | --- |
| Email | \`[^@\\s]+@[^@\\s]+\\.[a-z]{2,}\` |
| URL | \`https?:\\/\\/[^\\s/$.?#][^\\s]*\` |
| Trailing whitespace | \`\\s+$\` |
| Duplicate words | \`\\b(\\w+)\\s+\\1\\b\` |

> Rule: if your regex needs a comment to explain, write a tiny parser instead.`,
        };
      }

      if (/\bsql\b/.test(p)) {
        return {
          text: `## SQL you will actually use

\`\`\`sql
-- Revenue by month, last 12
SELECT strftime('%Y-%m', created_at) AS month,
       SUM(amount)                   AS revenue,
       COUNT(*)                      AS orders
FROM sales
WHERE created_at >= date('now', '-12 months')
GROUP BY month
ORDER BY month;

-- Customers who bought but never came back
SELECT c.id, c.name, MAX(s.created_at) AS last_order
FROM clients c
JOIN sales s ON s.client_id = c.id
GROUP BY c.id
HAVING COUNT(*) = 1
   AND last_order < date('now', '-90 days');

-- Running total
SELECT created_at,
       amount,
       SUM(amount) OVER (ORDER BY created_at) AS running_total
FROM sales;
\`\`\`

**Indexes that matter:** anything in a \`WHERE\` or \`JOIN\` gets one. Run
\`EXPLAIN QUERY PLAN\` before you guess.`,
        };
      }

      if (/\bcron\b/.test(p)) {
        return {
          text: `## Cron

\`\`\`bash
# ┌─ minute (0-59)
# │ ┌─ hour (0-23)
# │ │ ┌─ day of month (1-31)
# │ │ │ ┌─ month (1-12)
# │ │ │ │ ┌─ day of week (0-6, Sun=0)
# * * * * *  command

0 9   * * 1-5   backup.sh      # 9am weekdays
*/15 * * * *    healthcheck.sh # every 15 min
0 0   1 * *     monthly.sh     # midnight, 1st of month
\`\`\`

\`\`\`bash
crontab -l          # list
crontab -e          # edit
crontab -l > bk.txt # back up first
\`\`\`

> Cron has no PATH and no shell niceties. Always use absolute paths, and
> redirect output: \`0 9 * * * /usr/bin/python3 /home/me/job.py >> /tmp/job.log 2>&1\``,
        };
      }

      if (/\bgit\b/.test(p)) {
        return {
          text: `## Git — the recovery kit

\`\`\`bash
git switch -c feature/thing        # new branch (modern, safer than checkout)
git switch main && git pull        # update

# Undo things, in order of how scary they are
git restore file.txt               # throw away local edits to a file
git restore --staged file.txt      # unstage, keep the edits
git commit --amend -m "better msg" # fix the last commit message
git reset --soft HEAD~1            # undo last commit, keep changes staged
git reset --hard HEAD~1            # undo last commit, DESTROYS changes
git reflog                         # the timeline of everything — find your commit
git cherry-pick <sha>              # copy one commit onto this branch

# "I committed to the wrong branch"
git reset --soft HEAD~1 && git stash && git switch right-branch && git stash pop

# Find which commit broke it
git bisect start && git bisect bad && git bisect good <old-sha>
\`\`\`

> \`git reflog\` has saved more work than every other command combined. Nothing
> is truly gone until garbage collection runs.`,
        };
      }

      if (/fetch|api call|http request|axios/.test(p)) {
        return {
          text: `## Fetch with retries and a timeout

\`\`\`js
async function request(url, options = {}, { retries = 2, timeout = 10000 } = {}) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(url, { ...options, signal: ctrl.signal });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return await res.json();
    } catch (err) {
      if (attempt === retries) throw err;
      await new Promise(r => setTimeout(r, 300 * 2 ** attempt)); // backoff
    } finally {
      clearTimeout(timer);
    }
  }
}

// usage
const data = await request('/api/items', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'new' }),
});
\`\`\`

**Two things everyone forgets:** always set a timeout (\`fetch\` has none by
default), and always handle \`res.ok\` — a 404 does not throw.`,
        };
      }

      if (/css|flex|grid|center|layout/.test(p)) {
        return {
          text: `## CSS layout, modern and short

\`\`\`css
/* Centre anything */
.centre { display: grid; place-items: center; }

/* Responsive columns, no media queries */
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }

/* Sticky footer, content fills the rest */
body { min-height: 100dvh; display: grid; grid-template-rows: auto 1fr auto; }

/* Fluid type without breakpoints */
h1 { font-size: clamp(2rem, 6vw, 4rem); }

/* Card that lifts */
.card { border-radius: 14px; transition: transform .15s ease; }
.card:hover { transform: translateY(-2px); }

/* Truncate to two lines */
.clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
\`\`\`

> \`auto-fit\` + \`minmax\` replaces about 80% of the media queries people write.`,
        };
      }

      return {
        text: `## Snippets ready to go

I have these offline: \`regex\`, \`sql\`, \`cron\`, \`git\`, \`fetch\`, \`css\`.

**The Python one-liners worth memorising**

\`\`\`python
# Flatten a list of lists
flat = [x for row in rows for x in row]

# Group by a key
from collections import defaultdict
groups = defaultdict(list)
for item in items: groups[item["key"]].append(item)

# Most common
from collections import Counter
Counter(words).most_common(10)

# Read/write JSON safely
import json
data = json.loads(Path("f.json").read_text() or "{}")

# Retry shelling out
import subprocess
subprocess.run(["git", "pull"], check=True, capture_output=True, text=True)

# Quick HTTP server for a folder
# python3 -m http.server 8000
\`\`\`

Ask for any of those by name and I'll go deeper.`,
      };
    },
  },

  // ----------------------------------------------------------------- debug
  {
    id: 'debug',
    title: 'Debug a problem',
    keywords: ['debug', 'error', 'broken', 'not working', 'fails', 'bug', 'crash',
      'why is', 'fix', 'stack trace', 'exception', 'doesnt work', "doesn't work"],
    patterns: [/\b(debug|not working|broken|error|fails)\b/i, /\bwhy (is|does|won't|wont)\b/i],
    async run({ prompt }) {
      const topic = String(prompt).replace(/^(debug|fix|help|why)\s*/i, '').slice(0, 90);
      return {
        text: `## Debugging: ${topic}

Work down this list in order. Most bugs die at step 2.

**1. Read the actual error.**
Not the summary in your head — the first line of the stack trace, and the file
and line number it points at. Say it out loud.

**2. Find the last thing that worked.**
\`git stash\` / comment out half / revert to the last commit. Binary search the
change that broke it. If you cannot name the last working state, that *is* the bug.

**3. Make it reproducible.**
A bug you can trigger on demand is a bug you can fix. Write down the exact
clicks, input, or command. If it is intermittent, log the input every time.

**4. Print the values you are assuming.**
\`\`\`python
print(f"{var=}")            # Python 3.8+
\`\`\`
\`\`\`js
console.log({ var, other }); // keeps the name attached
\`\`\`
Nine times out of ten the variable is not what you think it is.

**5. Check the boring infrastructure**
- Is it actually the file you're editing? (wrong path, stale build, cached module)
- Permissions, ports already in use, env vars not loaded
- Timezone / encoding / trailing newline

**6. Isolate it.**
Copy the failing bit into a 10-line file. If it works there, the bug is in how
it's being called, not in the code.

**7. Only now: fix it.** Write the failing case as a check first, then make it pass.

> Rubber duck it: explain the problem to someone who isn't listening. You'll
> hear your own wrong assumption about halfway through.`,
        followups: ['Show me git recovery commands', 'Plan a rewrite of this'],
      };
    },
  },

  // ------------------------------------------------------------- checklist
  {
    id: 'checklist',
    title: 'Checklists',
    keywords: ['checklist', 'check list', 'launch', 'ship', 'onboard', 'onboarding',
      'before i', 'pre-launch', 'go live'],
    patterns: [/\bchecklist\b/i, /\bbefore (i |we )?(launch|ship|go live)\b/i],
    async run({ lower }) {
      if (/client|onboard/.test(lower)) {
        return {
          text: `## Client onboarding checklist

**Before kickoff**
${bullets([
          'Signed proposal or written yes in email/chat',
          'Deposit invoiced and (ideally) paid',
          'Scope written down, including what is excluded',
          'One named decision maker on their side',
          'Kickoff call booked',
        ])}

**Week one**
${bullets([
          'Access granted: repos, hosting, analytics, brand assets',
          'Agree the definition of done, in writing',
          'Set the check-in rhythm (one short call a week beats daily pings)',
          'Put the deadline in both calendars',
        ])}

**During**
${bullets([
          'Send a Friday summary even when nothing dramatic happened',
          'Flag scope creep the day you see it, with a price',
          'Keep every approval in writing',
        ])}

**Handover**
${bullets([
          'Final invoice sent the day you deliver',
          'Walkthrough recorded',
          'Written notes on how to run it',
          'Ask for the testimonial while they are happy',
          'Ask for one referral',
        ])}
`,
        };
      }

      return {
        text: `## Launch checklist

**It works**
${bullets([
          'Happy path tested end to end, by you, today',
          'The three most likely user mistakes handled',
          'Refresh / restart does not lose state',
          'Works on a phone, not just your giant monitor',
          'Loads with a cold cache in under 3 seconds',
        ])}

**It is safe**
${bullets([
          'Secrets in env vars, never in the repo',
          'Input validated on the server, not just the client',
          'Backups exist and you have tested restoring one',
          'Rate limiting on anything that costs you money',
        ])}

**People can find and use it**
${bullets([
          'One sentence on the page saying what it does and for whom',
          'One obvious call to action above the fold',
          'A real way to contact you',
          'README: what it is, how to run it, how to deploy it',
        ])}

**You get paid**
${bullets([
          'Payment link live and tested with a real card',
          'Invoice template ready',
          'Analytics installed so you can prove it works',
        ])}

> Ship at 80%. The last 20% is feedback you cannot get until it's live.`,
      };
    },
  },

  // ----------------------------------------------------------------- tasks
  {
    id: 'tasks',
    title: 'Capture tasks',
    keywords: ['add task', 'add tasks', 'create task', 'new task', 'todo', 'to do',
      'remind me', 'task list'],
    patterns: [/\b(add|create|new)\s+(a\s+)?tasks?\b/i, /\bremind me to\b/i],
    async run({ prompt }) {
      const lines = String(prompt).split(/\n|;|,(?=\s*[A-Z0-9])/)
        .map(l => l.replace(/^\s*(add|create|new)\s+tasks?\s*:?\s*/i, '')
          .replace(/^\s*[-*\d.)\]]+\s*/, '').trim())
        .filter(l => l.length > 2 && l.length < 120);
      const items = lines.length ? lines : [String(prompt).replace(/^(add|create|new)\s+task\s*/i, '')];
      const projects = await db.all('projects');
      const proj = findByMention(projects, prompt, 'name');

      const created = [];
      for (const title of items.slice(0, 20)) {
        const t = await db.put('tasks', {
          title, status: 'todo', project_id: proj ? proj.id : null,
          created_at: Date.now(),
        });
        created.push(t);
      }
      return {
        text: `Captured **${created.length}** task${created.length === 1 ? '' : 's'}${proj ? ` under **${proj.name}**` : ''}.

${bullets(created.map(t => t.title))}

Find them in **Projects → Tasks**. ${proj ? '' : '_Say "add these to <project name>" and I will file them properly._'}`,
        created: [{ type: 'tasks', id: created[0].id, label: `${created.length} tasks` }],
      };
    },
  },
];

function projName(projects, id) {
  const p = projects.find(x => x.id === id);
  return p ? p.name : 'general';
}

function extractTopicFrom(prompt) {
  let p = String(prompt || '').trim();
  p = p.replace(/^(please\s+)?(can you\s+|could you\s+)?/i, '');
  p = p.replace(/^(plan|plan out|create a plan for|roadmap for|break down|outline)\s+/i, '');
  p = p.replace(/^(me\s+)?(a|an|the)\s+/i, '');
  p = p.replace(/\s+(project|app|plan|roadmap)\s*$/i, '');
  p = p.replace(/[.?!]+$/, '').trim();
  return p.slice(0, 60).replace(/\b\w/g, c => c.toUpperCase()) || 'this project';
}

export { amounts, hoursMentioned, findByMention };
