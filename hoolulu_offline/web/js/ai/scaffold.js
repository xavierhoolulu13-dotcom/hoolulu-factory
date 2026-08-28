// Offline project generator. Deterministic, dependency-free templates so you can
// go from "build me a landing page" to runnable files with zero network.

import { slug } from '../util.js';

export const STACKS = [
  { id: 'landing', label: 'Landing page', ex: 'html, css, js',
    match: ['landing page', 'landing', 'sales page', 'waitlist', 'coming soon', 'signup page', 'splash'] },
  { id: 'dashboard', label: 'Dashboard UI', ex: 'html, css, js',
    match: ['dashboard', 'admin panel', 'analytics', 'metrics', 'chart', 'kpi'] },
  { id: 'chrome', label: 'Chrome extension', ex: 'json, html, js',
    match: ['chrome extension', 'browser extension', 'extension'] },
  { id: 'flask', label: 'Flask API', ex: 'python',
    match: ['flask', 'python api', 'python server', 'python backend'] },
  { id: 'fastapi', label: 'FastAPI', ex: 'python',
    match: ['fastapi', 'async api'] },
  { id: 'express', label: 'Express API', ex: 'javascript',
    match: ['express', 'node api', 'node server', 'nodejs'] },
  { id: 'telegram', label: 'Telegram bot', ex: 'python',
    match: ['telegram', 'telegram bot'] },
  { id: 'discord', label: 'Discord bot', ex: 'python',
    match: ['discord', 'discord bot'] },
  { id: 'python', label: 'Python script / CLI', ex: 'python',
    match: ['python', 'script', 'cli', 'command line', 'automate', 'automation', 'scraper', 'bot'] },
  { id: 'static', label: 'Static site', ex: 'html, css, js',
    match: ['website', 'site', 'html', 'web app', 'webapp', 'portfolio', 'page', 'app', 'tool', 'calculator'] },
];

export function detectStack(prompt) {
  const p = String(prompt || '').toLowerCase();
  let best = null, bestScore = 0;
  for (const s of STACKS) {
    for (const m of s.match) {
      if (p.includes(m) && m.length > bestScore) { best = s; bestScore = m.length; }
    }
  }
  return best || STACKS.find(s => s.id === 'static');
}

const titleize = s => String(s || 'Untitled')
  .replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).trim();

/** "build a weather dashboard" -> "weather dashboard" */
export function extractTopic(prompt) {
  let p = String(prompt || '').trim();
  p = p.replace(/^(please\s+)?(can you\s+|could you\s+)?/i, '');
  p = p.replace(/^(build|create|make|scaffold|generate|write|start|spin up|set up|new)\s+/i, '');
  p = p.replace(/^(me\s+)?(a|an|the)\s+/i, '');
  p = p.replace(/\s+(project|app|application)\s*$/i, '');
  p = p.replace(/\s+using\s+.*$/i, '').replace(/\s+in\s+(python|javascript|node|js)\s*$/i, '');
  p = p.replace(/[.?!]+$/, '').trim();
  return titleize(p.slice(0, 60)) || 'Untitled Project';
}

const CSS_BASE = (accent = '#22d3ee') => `:root {
  --bg: #0b1220;
  --panel: #121b2e;
  --panel-2: #0f1728;
  --line: #1f2a44;
  --text: #e6edf7;
  --muted: #8ea0bf;
  --accent: ${accent};
  --radius: 14px;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  line-height: 1.6;
}

a { color: var(--accent); }

.wrap { max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; }

header.hero { padding: 56px 0 32px; }
header.hero h1 { font-size: clamp(30px, 6vw, 52px); line-height: 1.1; margin: 0 0 12px; letter-spacing: -0.02em; }
header.hero p.lede { color: var(--muted); font-size: 18px; margin: 0 0 24px; max-width: 60ch; }

.btn {
  display: inline-block;
  background: var(--accent);
  color: #04121b;
  font-weight: 650;
  border: 0;
  border-radius: 10px;
  padding: 12px 20px;
  cursor: pointer;
  text-decoration: none;
  font-size: 15px;
}
.btn:hover { filter: brightness(1.08); }
.btn.ghost { background: transparent; color: var(--text); border: 1px solid var(--line); }

.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); margin: 32px 0; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 20px; }
.card h3 { margin: 0 0 6px; font-size: 17px; }
.card p { margin: 0; color: var(--muted); font-size: 14px; }

label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
input, textarea, select {
  width: 100%;
  background: var(--panel-2);
  border: 1px solid var(--line);
  color: var(--text);
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  font-family: inherit;
}
input:focus, textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }

footer { border-top: 1px solid var(--line); margin-top: 48px; padding-top: 20px; color: var(--muted); font-size: 13px; }
`;

const README = (name, desc, howto, stack) => `# ${name}

${desc}

## Run it

${howto}

## Files

${stack}

## Notes

Generated offline by Hoolulu Offline. Everything here runs with no network
connection and no build step unless the section above says otherwise.
`;

// --------------------------------------------------------------- generators

function genStatic(topic, prompt) {
  const name = topic;
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${name}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>${name}</h1>
      <p class="lede">A clean starting point. Edit <code>index.html</code> to make it yours.</p>
      <button class="btn" id="cta">Get started</button>
      <button class="btn ghost" id="reset">Reset counter</button>
    </header>

    <section class="grid">
      <div class="card"><h3>Fast</h3><p>No frameworks, no build step, no network needed.</p></div>
      <div class="card"><h3>Offline</h3><p>Everything is local. Works on a plane.</p></div>
      <div class="card"><h3>Yours</h3><p>Plain HTML, CSS and JS you fully control.</p></div>
    </section>

    <section>
      <h2>Try it</h2>
      <p>You clicked the button <strong id="count">0</strong> times.</p>
      <form id="form" style="max-width:420px">
        <label for="note">Save a note (kept in localStorage)</label>
        <input id="note" placeholder="Type something..." autocomplete="off">
      </form>
      <p id="saved" style="color:var(--muted)"></p>
    </section>

    <footer>Built offline with Hoolulu Offline.</footer>
  </div>
  <script src="app.js"></script>
</body>
</html>
`;
  const js = `const KEY = 'click-count';
const NOTE = 'saved-note';

const countEl = document.getElementById('count');
const savedEl = document.getElementById('saved');
const noteEl = document.getElementById('note');

let count = Number(localStorage.getItem(KEY) || 0);
countEl.textContent = count;

document.getElementById('cta').addEventListener('click', () => {
  count += 1;
  localStorage.setItem(KEY, String(count));
  countEl.textContent = count;
});

document.getElementById('reset').addEventListener('click', () => {
  count = 0;
  localStorage.setItem(KEY, '0');
  countEl.textContent = count;
});

noteEl.value = localStorage.getItem(NOTE) || '';
document.getElementById('form').addEventListener('submit', (e) => {
  e.preventDefault();
  localStorage.setItem(NOTE, noteEl.value);
  savedEl.textContent = 'Saved at ' + new Date().toLocaleTimeString();
});
`;
  return {
    files: [
      { path: 'index.html', content: html },
      { path: 'styles.css', content: CSS_BASE() },
      { path: 'app.js', content: js },
      { path: 'README.md', content: README(name, `A static site for ${name}.`, 'Open `index.html` in a browser. That is the whole setup.', 'index.html, styles.css, app.js') },
    ],
    entry: 'index.html',
    notes: ['Pure static files — open index.html directly, no server needed.'],
  };
}

function genLanding(topic, prompt) {
  const name = topic;
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${name}</title>
<meta name="description" content="${name} — ${String(prompt).slice(0, 140)}">
<link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <p style="color:var(--accent);font-weight:650;letter-spacing:.14em;text-transform:uppercase;font-size:12px;margin:0 0 10px">Now available</p>
      <h1>${name}</h1>
      <p class="lede">Replace this line with the single clearest promise you make to the person landing here. One sentence. Concrete outcome.</p>
      <form id="signup" style="display:flex;gap:10px;max-width:460px;flex-wrap:wrap">
        <input id="email" type="email" placeholder="you@example.com" required style="flex:1;min-width:220px">
        <button class="btn" type="submit">Get early access</button>
      </form>
      <p id="msg" style="color:var(--muted);font-size:14px;min-height:22px"></p>
    </header>

    <section class="grid">
      <div class="card"><h3>Benefit one</h3><p>Outcome, not a feature. What changes for them?</p></div>
      <div class="card"><h3>Benefit two</h3><p>Tie it to time saved or money earned.</p></div>
      <div class="card"><h3>Benefit three</h3><p>Remove the risk. Guarantee, free trial, or proof.</p></div>
    </section>

    <section>
      <h2>How it works</h2>
      <ol style="color:var(--muted);max-width:60ch">
        <li>Do the first small thing.</li>
        <li>Get the first result fast.</li>
        <li>Repeat until it is done.</li>
      </ol>
    </section>

    <section>
      <h2>Proof</h2>
      <div class="card">
        <p>"Swap in a real quote from a real customer. Specific numbers beat adjectives."</p>
        <p style="margin-top:10px"><strong>Name</strong> — Role, Company</p>
      </div>
    </section>

    <footer>© ${new Date().getFullYear()} ${name}. Built offline.</footer>
  </div>
  <script src="app.js"></script>
</body>
</html>
`;
  const js = `const form = document.getElementById('signup');
const email = document.getElementById('email');
const msg = document.getElementById('msg');

form.addEventListener('submit', (e) => {
  e.preventDefault();
  // Demo only: store locally. Wire this to your real backend or form service.
  const list = JSON.parse(localStorage.getItem('waitlist') || '[]');
  list.push({ email: email.value, at: new Date().toISOString() });
  localStorage.setItem('waitlist', JSON.stringify(list));
  msg.textContent = 'You are on the list. (' + list.length + ' so far)';
  email.value = '';
});
`;
  return {
    files: [
      { path: 'index.html', content: html },
      { path: 'styles.css', content: CSS_BASE('#f5b642') },
      { path: 'app.js', content: js },
      { path: 'README.md', content: README(name, `Landing page for ${name}.`, 'Open `index.html`. To publish, drag the folder into any static host (Netlify Drop, GitHub Pages, S3).', 'index.html, styles.css, app.js') },
    ],
    entry: 'index.html',
    notes: ['Hero, benefits, how-it-works, proof, and a waitlist form that stores to localStorage.'],
  };
}

function genDashboard(topic, prompt) {
  const name = topic;
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${name}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>${name}</h1>
      <p class="lede">Local dashboard with seeded demo data. Swap <code>seed()</code> in app.js for your real source.</p>
    </header>

    <section class="grid" id="kpis"></section>

    <section class="card">
      <h3 style="margin-top:0">Revenue — last 14 days</h3>
      <canvas id="chart" width="880" height="260" style="width:100%;height:260px"></canvas>
    </section>

    <section class="card" style="margin-top:16px">
      <h3 style="margin-top:0">Recent activity</h3>
      <table id="table" style="width:100%;border-collapse:collapse;font-size:14px"></table>
    </section>

    <footer>Runs entirely in the browser. No network calls.</footer>
  </div>
  <script src="app.js"></script>
</body>
</html>
`;
  const js = `// ---------------------------------------------------------------- demo data
function seed() {
  const days = 14;
  const rows = [];
  let v = 1200;
  for (let i = days - 1; i >= 0; i--) {
    v = Math.max(200, v + (Math.random() - 0.42) * 320);
    rows.push({
      date: new Date(Date.now() - i * 86400000),
      revenue: Math.round(v),
      orders: Math.max(1, Math.round(v / 48)),
    });
  }
  return rows;
}

const rows = seed();
const money = (n) => '$' + Math.round(n).toLocaleString();

// -------------------------------------------------------------------- KPIs
function renderKpis() {
  const total = rows.reduce((s, r) => s + r.revenue, 0);
  const orders = rows.reduce((s, r) => s + r.orders, 0);
  const half = rows.slice(7);
  const prev = rows.slice(0, 7);
  const sum = (a) => a.reduce((s, r) => s + r.revenue, 0);
  const growth = sum(prev) ? Math.round(((sum(half) - sum(prev)) / sum(prev)) * 100) : 0;

  const cards = [
    { label: 'Revenue (14d)', value: money(total) },
    { label: 'Orders', value: orders.toLocaleString() },
    { label: 'Avg order', value: money(total / Math.max(1, orders)) },
    { label: 'Week over week', value: (growth >= 0 ? '+' : '') + growth + '%' },
  ];
  document.getElementById('kpis').innerHTML = cards
    .map(c => '<div class="card"><p style="margin:0 0 4px">' + c.label + '</p>' +
              '<h3 style="margin:0;font-size:26px">' + c.value + '</h3></div>').join('');
}

// ------------------------------------------------------------------- chart
function drawChart() {
  const c = document.getElementById('chart');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  const pad = 34;
  const max = Math.max(...rows.map(r => r.revenue)) * 1.15;

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#1f2a44';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad + ((h - pad * 2) * i) / 4;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke();
  }

  const bw = (w - pad * 2) / rows.length;
  rows.forEach((r, i) => {
    const bh = ((h - pad * 2) * r.revenue) / max;
    const x = pad + i * bw + 4;
    const y = h - pad - bh;
    const g = ctx.createLinearGradient(0, y, 0, h - pad);
    g.addColorStop(0, '#22d3ee');
    g.addColorStop(1, 'rgba(34,211,238,0.15)');
    ctx.fillStyle = g;
    ctx.fillRect(x, y, bw - 8, bh);
  });

  ctx.fillStyle = '#8ea0bf';
  ctx.font = '12px system-ui';
  ctx.fillText(money(max), 4, pad - 8);
  ctx.fillText(rows[0].date.toLocaleDateString(), pad, h - 12);
  ctx.fillText(rows[rows.length - 1].date.toLocaleDateString(), w - pad - 60, h - 12);
}

// ------------------------------------------------------------------- table
function renderTable() {
  const head = '<tr style="text-align:left;color:var(--muted)"><th style="padding:8px">Date</th><th>Orders</th><th>Revenue</th></tr>';
  const body = rows.slice().reverse().slice(0, 8).map(r =>
    '<tr style="border-top:1px solid var(--line)"><td style="padding:8px">' +
    r.date.toLocaleDateString() + '</td><td>' + r.orders + '</td><td>' + money(r.revenue) + '</td></tr>'
  ).join('');
  document.getElementById('table').innerHTML = head + body;
}

renderKpis();
drawChart();
renderTable();
window.addEventListener('resize', drawChart);
`;
  return {
    files: [
      { path: 'index.html', content: html },
      { path: 'styles.css', content: CSS_BASE() },
      { path: 'app.js', content: js },
      { path: 'README.md', content: README(name, `Dashboard for ${name}.`, 'Open `index.html`. Replace `seed()` in app.js with a fetch to your real data.', 'index.html, styles.css, app.js') },
    ],
    entry: 'index.html',
    notes: ['Canvas bar chart + KPI cards + activity table, all local, zero libraries.'],
  };
}

function genPython(topic, prompt) {
  const name = slug(topic, 'tool').replace(/-/g, '_');
  const py = `#!/usr/bin/env python3
"""${topic}

${String(prompt).slice(0, 200)}

Usage:
    python ${name}.py --help
    python ${name}.py run --input data.txt
    python ${name}.py demo
"""

import argparse
import json
import sys
from pathlib import Path


def load_rows(path):
    """Read a file into a list of stripped, non-empty lines."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"input file not found: {path}")
    return [line.rstrip("\\n") for line in p.read_text().splitlines() if line.strip()]


def process(rows):
    """The actual work. Replace this with your logic."""
    out = []
    for i, row in enumerate(rows, 1):
        out.append({
            "index": i,
            "value": row,
            "length": len(row),
            "words": len(row.split()),
        })
    return out


def summarize(rows):
    if not rows:
        return {"count": 0}
    lengths = [len(r) for r in rows]
    return {
        "count": len(rows),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "avg_length": round(sum(lengths) / len(lengths), 2),
        "total_words": sum(len(r.split()) for r in rows),
    }


def cmd_run(args):
    rows = load_rows(args.input)
    result = process(rows)
    summary = summarize(rows)

    if args.json:
        print(json.dumps({"summary": summary, "rows": result}, indent=2))
    else:
        for r in result:
            print(f"{r['index']:>4}  {r['length']:>4}ch  {r['value']}")
        print("\\n--- summary ---")
        for k, v in summary.items():
            print(f"{k:>12}: {v}")

    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": result}, indent=2))
        print(f"\\nwrote {args.out}")


def cmd_demo(args):
    sample = [
        "first sample line",
        "a slightly longer second line",
        "third",
    ]
    print(json.dumps({"summary": summarize(sample), "rows": process(sample)}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="${topic}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="process an input file")
    p_run.add_argument("--input", "-i", default="data.txt", help="path to input file")
    p_run.add_argument("--out", "-o", help="write JSON result to this path")
    p_run.add_argument("--json", action="store_true", help="print JSON instead of a table")
    p_run.set_defaults(func=cmd_run)

    p_demo = sub.add_parser("demo", help="run on built-in sample data")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
`;
  return {
    files: [
      { path: `${name}.py`, content: py },
      { path: 'data.txt', content: 'first sample line\na slightly longer second line\nthird\n' },
      { path: 'README.md', content: README(topic, `A command-line tool for ${topic}.`, `python ${name}.py demo\npython ${name}.py run --input data.txt --json`, `${name}.py, data.txt`) },
    ],
    entry: `${name}.py`,
    notes: ['Standard library only. `python ' + name + '.py demo` runs immediately.'],
  };
}

function genFlask(topic, prompt) {
  const py = `#!/usr/bin/env python3
"""${topic} — a small Flask API with an in-memory store.

Run:
    pip install flask
    python app.py

Then:
    curl http://localhost:5000/api/items
    curl -X POST http://localhost:5000/api/items -H 'Content-Type: application/json' -d '{"title":"first"}'
"""

import json
import os
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)
DATA_FILE = os.environ.get("DATA_FILE", "data.json")


def load():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE) as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return []


def save(items):
    with open(DATA_FILE, "w") as fh:
        json.dump(items, fh, indent=2)


@app.get("/api/health")
def health():
    return jsonify(ok=True, time=datetime.utcnow().isoformat() + "Z")


@app.get("/api/items")
def list_items():
    return jsonify(items=load())


@app.post("/api/items")
def create_item():
    payload = request.get_json(silent=True) or {}
    if not payload.get("title"):
        return jsonify(error="title is required"), 400
    items = load()
    item = {
        "id": (max((i.get("id", 0) for i in items), default=0) + 1),
        "title": payload["title"],
        "done": bool(payload.get("done", False)),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    items.append(item)
    save(items)
    return jsonify(item=item), 201


@app.patch("/api/items/<int:item_id>")
def update_item(item_id):
    items = load()
    for item in items:
        if item.get("id") == item_id:
            item.update(request.get_json(silent=True) or {})
            save(items)
            return jsonify(item=item)
    return jsonify(error="not found"), 404


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    items = load()
    remaining = [i for i in items if i.get("id") != item_id]
    if len(remaining) == len(items):
        return jsonify(error="not found"), 404
    save(remaining)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
`;
  return {
    files: [
      { path: 'app.py', content: py },
      { path: 'requirements.txt', content: 'flask==3.0.3\n' },
      { path: 'README.md', content: README(topic, `A Flask API for ${topic}.`, 'pip install -r requirements.txt\npython app.py', 'app.py, requirements.txt') },
    ],
    entry: 'app.py',
    notes: ['Full CRUD with JSON file persistence. Needs `pip install flask`.'],
  };
}

function genFastAPI(topic, prompt) {
  const py = `#!/usr/bin/env python3
"""${topic} — FastAPI service.

Run:
    pip install fastapi uvicorn
    uvicorn main:app --reload

Docs are generated for you at http://localhost:8000/docs
"""

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="${topic}")


class ItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    done: bool = False


class Item(ItemIn):
    id: int


DB: List[Item] = []
NEXT_ID = 1


@app.get("/api/health")
def health():
    return {"ok": True, "items": len(DB)}


@app.get("/api/items", response_model=List[Item])
def list_items(done: Optional[bool] = None):
    return [i for i in DB if done is None or i.done == done]


@app.post("/api/items", response_model=Item, status_code=201)
def create_item(payload: ItemIn):
    global NEXT_ID
    item = Item(id=NEXT_ID, **payload.model_dump())
    NEXT_ID += 1
    DB.append(item)
    return item


@app.patch("/api/items/{item_id}", response_model=Item)
def update_item(item_id: int, payload: ItemIn):
    for i, existing in enumerate(DB):
        if existing.id == item_id:
            updated = Item(id=item_id, **payload.model_dump())
            DB[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="not found")


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    for i, existing in enumerate(DB):
        if existing.id == item_id:
            DB.pop(i)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="not found")
`;
  return {
    files: [
      { path: 'main.py', content: py },
      { path: 'requirements.txt', content: 'fastapi==0.115.0\nuvicorn[standard]==0.30.6\n' },
      { path: 'README.md', content: README(topic, `A FastAPI service for ${topic}.`, 'pip install -r requirements.txt\nuvicorn main:app --reload\n# open http://localhost:8000/docs', 'main.py, requirements.txt') },
    ],
    entry: 'main.py',
    notes: ['Typed request/response models and free interactive docs at /docs.'],
  };
}

function genExpress(topic, prompt) {
  const pkg = JSON.stringify({
    name: slug(topic, 'api'),
    version: '1.0.0',
    private: true,
    type: 'module',
    description: topic,
    main: 'server.js',
    scripts: { start: 'node server.js', dev: 'node --watch server.js' },
    engines: { node: '>=18' },
  }, null, 2) + '\n';

  const js = `import http from 'node:http';

/** Tiny dependency-free HTTP API. Run: npm start */

const PORT = Number(process.env.PORT || 3000);

/** @type {{id:number,title:string,done:boolean}[]} */
const items = [];
let nextId = 1;

const json = (res, code, body) => {
  const payload = JSON.stringify(body);
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(payload);
};

const readBody = (req) => new Promise((resolve) => {
  let raw = '';
  req.on('data', (c) => { raw += c; });
  req.on('end', () => {
    try { resolve(raw ? JSON.parse(raw) : {}); } catch { resolve({}); }
  });
});

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;

  if (req.method === 'OPTIONS') return json(res, 204, {});

  if (path === '/api/health') {
    return json(res, 200, { ok: true, items: items.length, uptime: process.uptime() });
  }

  if (path === '/api/items' && req.method === 'GET') {
    return json(res, 200, { items });
  }

  if (path === '/api/items' && req.method === 'POST') {
    const body = await readBody(req);
    if (!body.title) return json(res, 400, { error: 'title is required' });
    const item = { id: nextId++, title: String(body.title).slice(0, 120), done: !!body.done };
    items.push(item);
    return json(res, 201, { item });
  }

  const match = path.match(/^\\/api\\/items\\/(\\d+)$/);
  if (match) {
    const id = Number(match[1]);
    const idx = items.findIndex((i) => i.id === id);
    if (idx === -1) return json(res, 404, { error: 'not found' });

    if (req.method === 'PATCH') {
      const body = await readBody(req);
      items[idx] = { ...items[idx], ...body, id };
      return json(res, 200, { item: items[idx] });
    }
    if (req.method === 'DELETE') {
      items.splice(idx, 1);
      return json(res, 200, { ok: true });
    }
  }

  return json(res, 404, { error: 'not found', path });
});

server.listen(PORT, () => {
  console.log('listening on http://localhost:' + PORT);
});
`;
  return {
    files: [
      { path: 'server.js', content: js },
      { path: 'package.json', content: pkg },
      { path: 'README.md', content: README(topic, `A Node HTTP API for ${topic}.`, 'npm start\n# curl http://localhost:3000/api/health', 'server.js, package.json') },
    ],
    entry: 'server.js',
    notes: ['Zero npm dependencies — uses only node:http. `npm start` just works.'],
  };
}

function genChrome(topic, prompt) {
  const manifest = JSON.stringify({
    manifest_version: 3,
    name: topic.slice(0, 45),
    version: '1.0.0',
    description: String(prompt).slice(0, 130),
    action: { default_popup: 'popup.html', default_title: topic.slice(0, 40) },
    permissions: ['storage'],
    background: { service_worker: 'background.js' },
  }, null, 2) + '\n';

  const popupHtml = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="popup.css">
</head>
<body>
  <h1>${topic}</h1>
  <p id="status">Ready.</p>
  <button id="grab">Capture this tab</button>
  <button id="clear" class="ghost">Clear saved</button>
  <ul id="list"></ul>
  <script src="popup.js"></script>
</body>
</html>
`;
  const popupCss = `body {
  width: 320px;
  margin: 0;
  padding: 16px;
  background: #0b1220;
  color: #e6edf7;
  font-family: system-ui, sans-serif;
}
h1 { font-size: 16px; margin: 0 0 8px; }
p { font-size: 12px; color: #8ea0bf; margin: 0 0 12px; }
button {
  width: 100%;
  padding: 9px;
  margin-bottom: 8px;
  border: 0;
  border-radius: 8px;
  background: #22d3ee;
  color: #04121b;
  font-weight: 650;
  cursor: pointer;
}
button.ghost { background: transparent; color: #e6edf7; border: 1px solid #1f2a44; }
ul { list-style: none; padding: 0; margin: 8px 0 0; max-height: 220px; overflow: auto; }
li { font-size: 12px; padding: 6px 0; border-top: 1px solid #1f2a44; }
li span { color: #8ea0bf; display: block; }
`;
  const popupJs = `const statusEl = document.getElementById('status');
const listEl = document.getElementById('list');

async function render() {
  const { saved = [] } = await chrome.storage.local.get('saved');
  listEl.innerHTML = saved
    .slice(-8)
    .reverse()
    .map(s => '<li>' + (s.title || '(untitled)') + '<span>' + new Date(s.at).toLocaleString() + '</span></li>')
    .join('');
}

document.getElementById('grab').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const { saved = [] } = await chrome.storage.local.get('saved');
  saved.push({ title: tab?.title || '', url: tab?.url || '', at: Date.now() });
  await chrome.storage.local.set({ saved });
  statusEl.textContent = 'Saved ' + saved.length + ' item(s).';
  render();
});

document.getElementById('clear').addEventListener('click', async () => {
  await chrome.storage.local.set({ saved: [] });
  statusEl.textContent = 'Cleared.';
  render();
});

render();
`;
  const bg = `// Service worker. Installed once; wakes up for the events it listens for.
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ installed_at: Date.now() });
  console.log('extension installed');
});
`;
  return {
    files: [
      { path: 'manifest.json', content: manifest },
      { path: 'popup.html', content: popupHtml },
      { path: 'popup.css', content: popupCss },
      { path: 'popup.js', content: popupJs },
      { path: 'background.js', content: bg },
      { path: 'README.md', content: README(topic, `A Chrome extension for ${topic}.`, '1. Open chrome://extensions\n2. Enable Developer mode\n3. Click "Load unpacked" and pick this folder', 'manifest.json, popup.html, popup.css, popup.js, background.js') },
    ],
    entry: 'popup.html',
    notes: ['Manifest V3. Load it unpacked from chrome://extensions — no build step.'],
  };
}

function genTelegram(topic, prompt) {
  const py = `#!/usr/bin/env python3
"""${topic} — Telegram bot (long polling, no webhook needed).

Setup:
    pip install pyTelegramBotAPI
    export TELEGRAM_TOKEN=123:abc      # from @BotFather
    python bot.py
"""

import os

import telebot

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise SystemExit("Set TELEGRAM_TOKEN first (get it from @BotFather).")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


@bot.message_handler(commands=["start", "help"])
def send_help(message):
    bot.reply_to(message, (
        "<b>${topic}</b>\\n\\n"
        "/start — this message\\n"
        "/echo &lt;text&gt; — repeats your text\\n"
        "/sum &lt;a&gt; &lt;b&gt; — adds two numbers\\n"
        "/id — shows your chat id"
    ))


@bot.message_handler(commands=["id"])
def send_id(message):
    bot.reply_to(message, f"chat id: <code>{message.chat.id}</code>")


@bot.message_handler(commands=["echo"])
def do_echo(message):
    text = message.text.partition(" ")[2].strip()
    bot.reply_to(message, text or "Give me something to echo.")


@bot.message_handler(commands=["sum"])
def do_sum(message):
    parts = message.text.split()[1:]
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        bot.reply_to(message, "Usage: /sum 2 3")
        return
    bot.reply_to(message, f"= <b>{sum(nums):g}</b>")


@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Send /help to see what I can do.")


if __name__ == "__main__":
    print("bot running — press Ctrl+C to stop")
    bot.infinity_polling(skip_pending=True)
`;
  return {
    files: [
      { path: 'bot.py', content: py },
      { path: 'requirements.txt', content: 'pyTelegramBotAPI==4.23.0\n' },
      { path: '.env.example', content: 'TELEGRAM_TOKEN=123456:ABC-DEF\n' },
      { path: 'README.md', content: README(topic, `A Telegram bot for ${topic}.`, 'pip install -r requirements.txt\nexport TELEGRAM_TOKEN=...\npython bot.py', 'bot.py, requirements.txt') },
    ],
    entry: 'bot.py',
    notes: ['Uses long polling, so it works behind any firewall with no public URL.'],
  };
}

function genDiscord(topic, prompt) {
  const py = `#!/usr/bin/env python3
"""${topic} — Discord bot.

Setup:
    pip install discord.py
    export DISCORD_TOKEN=...          # from the Discord Developer Portal
    python bot.py

Invite it with the "bot" scope plus the "Send Messages" permission.
"""

import os

import discord
from discord import app_commands

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("Set DISCORD_TOKEN first.")


class Client(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("slash commands synced")


client = Client()


@client.event
async def on_ready():
    print(f"logged in as {client.user} (id {client.user.id})")


@client.tree.command(name="ping", description="Check the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong.", ephemeral=True)


@client.tree.command(name="estimate", description="Estimate hours for a task")
@app_commands.describe(hours="How many hours", rate="Your hourly rate")
async def estimate(interaction: discord.Interaction, hours: float, rate: float = 85.0):
    total = hours * rate
    await interaction.response.send_message(
        f"{hours:g}h x \${rate:g}/h = **\${total:,.0f}**"
    )


if __name__ == "__main__":
    client.run(TOKEN)
`;
  return {
    files: [
      { path: 'bot.py', content: py },
      { path: 'requirements.txt', content: 'discord.py==2.4.0\n' },
      { path: '.env.example', content: 'DISCORD_TOKEN=\n' },
      { path: 'README.md', content: README(topic, `A Discord bot for ${topic}.`, 'pip install -r requirements.txt\nexport DISCORD_TOKEN=...\npython bot.py', 'bot.py, requirements.txt') },
    ],
    entry: 'bot.py',
    notes: ['Modern slash commands via app_commands, auto-synced on startup.'],
  };
}

const GENERATORS = {
  static: genStatic, landing: genLanding, dashboard: genDashboard,
  python: genPython, flask: genFlask, fastapi: genFastAPI,
  express: genExpress, chrome: genChrome, telegram: genTelegram, discord: genDiscord,
};

/**
 * @returns {{stack, label, files, entry, notes, name}}
 */
export function generate(stackId, { prompt = '', name = null } = {}) {
  const stack = STACKS.find(s => s.id === stackId) || STACKS.find(s => s.id === 'static');
  const topic = name || extractTopic(prompt);
  const gen = GENERATORS[stack.id] || genStatic;
  const out = gen(topic, prompt);
  return { stack: stack.id, label: stack.label, name: topic, ...out };
}

export function listStacks() {
  return STACKS.map(s => ({ id: s.id, label: s.label, ex: s.ex }));
}
