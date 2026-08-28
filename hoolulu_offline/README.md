# Hoolulu Offline

An installable app that works with the network switched off: talk to AI, build
projects, and run the money side of your business — then sync everything when
you reconnect.

No npm install. No build step. No third-party backend. The server is ~400 lines
of Python standard library; the app is vanilla JS + IndexedDB.

```
python3 server.py --port 8080
# open http://localhost:8080
```

---

## The idea

Most "AI apps" are a thin client that dies the moment your connection does. This
one is built the other way round:

1. **Your device owns the data.** Every conversation, project, file, client,
   invoice and time entry lives in IndexedDB. Reads and writes never touch the
   network, so the UI is instant and never spins.
2. **AI degrades instead of failing.** There is always something that can
   answer, even with no model and no wifi.
3. **Sync is a background detail.** Writes drop into an outbox; when a server
   is reachable they go out, and newer records come back. Offline for a month
   is fine.

## Quick start

```bash
cd hoolulu_offline
python3 server.py --port 8080          # or ./run.sh
```

Open the URL, then **Install** (the button in the sidebar, or your browser's
"Install app" / "Add to Home Screen"). After that it opens with no connection
at all.

> The server is only needed for the first load and for syncing between devices.
> Once installed, the app runs with the server off.

---

## Talking to AI with no network

Every message goes down a chain and uses the first brain that answers. The
bubble always shows which one it was.

| Order | Brain | Needs | Quality |
| --- | --- | --- | --- |
| 1 | **On-device model** (WebGPU, in your browser) | one-time ~1 GB download | good |
| 2 | **Local Ollama** (proxied through your server) | `ollama serve` on your machine | better |
| 3 | **Cloud** (OpenAI / Anthropic / Groq / OpenRouter) | online + a key | best |
| 4 | **Offline brain** — deterministic local skills | nothing | useful, not chatty |
| 5 | **Queue** — saved and answered automatically later | nothing | deferred |

Set the chain in **Settings → AI engine**:

- **Auto** (default) — on-device first if *Prefer privacy* is on, otherwise
  best-quality-first.
- **Offline only** — guarantees nothing ever leaves the device.

### The offline brain

This is the floor the app never drops below. It is not an LLM; it is a set of
local skills that read your actual data. It works on first run, with nothing
installed:

| Say this | You get |
| --- | --- |
| `what can you do offline` | the full capability list |
| `money` | revenue, pipeline, outstanding, drafts, profit, hours — from your records |
| `proposal for Acme about a website rebuild` | a written proposal, saved as a draft |
| `invoice Acme for $1200` / `invoice unbilled time` | a numbered invoice; time entries get marked billed |
| `price 30 hours` | floor / target / premium, plus a three-tier package |
| `plan a client onboarding system` | a phased plan — say *"create it as a project"* to save it with tasks |
| `build a landing page for a surf school` | runnable files, scaffolded locally |
| `standup` | what moved today |
| `cold email to Acme` | three outreach variants |
| `regex` · `sql` · `cron` · `git` · `css` · `fetch` | battle-tested snippets |
| `debug why my api 500s` | a structured debugging path |
| `checklist` | launch / client-onboarding checklists |

### On-device models (real LLM, fully offline)

Settings → **On-device model** → pick one → *Download & load*. Weights come
from HuggingFace once, then the browser caches them. After that it answers with
wifi off, forever, and nothing leaves the machine.

Recommended: **Qwen2.5 Coder 1.5B** (~1.1 GB) for code, **Qwen3 1.7B** for
general work, **Qwen2.5 0.5B** for phones. Requires WebGPU — Chrome/Edge 113+,
Safari 18+, or Firefox 141+.

### Ollama

```bash
ollama serve
ollama pull qwen2.5-coder:1.5b
```

Then in Settings → **Local Ollama**, hit *Test*. Requests go through your sync
server's `/api/ollama` proxy, which sidesteps CORS and mixed-content blocks —
so this works even when the app is open on your phone over HTTPS.

---

## Building projects offline

Chat → `build a dashboard for tracking surf conditions`. The offline brain
writes real files into the project, and you get:

- a file tree and a code editor (Ctrl/Cmd+S to save, everything in IndexedDB)
- **Preview** — HTML/CSS/JS projects render in a sandboxed iframe, offline
- **Export .zip** — a real zip, written by a ~60-line store-only encoder
- tasks (to-do / doing / done) and a **timer** that feeds straight into invoices

Stacks it can scaffold with no network:

| Stack | Files | Runs with |
| --- | --- | --- |
| Landing page | `index.html`, `styles.css`, `app.js` | nothing — open the file |
| Dashboard | canvas charts, KPI cards, table | nothing |
| Static site | HTML/CSS/JS + localStorage | nothing |
| Python CLI | argparse, subcommands, JSON out | `python3` |
| Flask API | CRUD + JSON persistence | `pip install flask` |
| FastAPI | typed models, auto docs at `/docs` | `pip install fastapi uvicorn` |
| Express API | zero-dependency `node:http` | `node` |
| Chrome extension | Manifest V3, popup + service worker | load unpacked |
| Telegram bot | long polling | `pip install pyTelegramBotAPI` |
| Discord bot | slash commands | `pip install discord.py` |

All generated Python and JS is syntax-checked; all JSON parses.

---

## Money

Seven tabs, all local: **Overview · Clients · Gigs · Proposals · Invoices ·
Products · Expenses**.

The loop it supports:

```
Client ──▶ Gig (lead → contacted → proposal → won/lost)
              │
              ├──▶ Proposal (draft → sent → accepted)
              │
              └──▶ Invoice (draft → sent → paid)   ◀── tracked time
```

- **Overview** — pipeline, collected, outstanding, drafts, net, hours. Values
  are computed from your records, never typed in by hand.
- **Gigs** — move deals between stages with one click; the pipeline chart
  follows.
- **Invoices** — view, print to PDF, or download as HTML. `invoice unbilled
  time` bills everything you've tracked and marks it billed so you can't
  double-charge.
- **Products** — for income that isn't hours: record sales against products.
- **Expenses** — feeds the net-profit number.

Set your currency, hourly rate, tax rate and payment terms in **Settings**; the
offline brain uses them in every proposal and invoice it writes.

---

## Sync

### How it works

```
 your phone ──┐
              ├──▶ /api/sync ──▶ SQLite (server_seq, monotonic)
 your laptop ─┘
```

- Every record carries `updated_at` (ms) and a device id.
- The server assigns a **monotonic sequence number** to each accepted write.
- Clients keep a **cursor** (last sequence seen) and pull `server_seq > cursor`.
- **Conflicts: last write wins** on `updated_at`. A stale write is dropped by
  the server, not merged — simple and predictable.
- **Deletes are tombstones**, so a delete on one device actually deletes on the
  others.
- Writes queue in an **outbox** and collapse: ten edits to one record produce
  one push.

### Setting it up

Same machine (the default — leave *Server URL* blank): it just works.

Two devices on your wifi:

```bash
python3 server.py --port 8080 --token $(openssl rand -base64 18)
# on the other device, Settings → Sync:
#   Server URL: http://192.168.1.20:8080
#   Sync token: <the token above>
```

Anywhere (a $5 VPS): copy the folder, run it behind Caddy or nginx for TLS, and
point your devices at it.

```bash
python3 server.py --port 8080 --token your-secret --data ~/.hoolulu/sync.db
```

**Always pass `--token` when the port is reachable beyond localhost.** Without
one, the server refuses only destructive calls; reads and writes stay open, and
it prints a warning on startup.

### No server at all

Sync → **Export backup** gives you a JSON file with every record and your
settings. Move it by hand, **Import** on the other side, choose merge
(newest wins) or replace.

### API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | status, record count, connected devices |
| POST | `/api/sync` | push changes, pull since cursor |
| POST | `/api/wipe` | delete everything (requires `--token`) |
| GET | `/api/ollama/tags` | proxy to a local Ollama daemon |
| POST | `/api/ollama/chat` | proxy to a local Ollama daemon |
| POST | `/api/ai/openai` | proxy to any OpenAI-compatible endpoint |
| POST | `/api/ai/anthropic` | proxy to the Anthropic messages API |

```bash
curl -X POST localhost:8080/api/sync -H 'Content-Type: application/json' -d '{
  "device_id": "laptop", "cursor": 0,
  "changes": [{"collection":"clients","id":"c1","updated_at":1700000000000,
               "deleted":false,"body":{"name":"Acme"}}]
}'
```

---

## Works with the wifi off

Confirmed by the service worker precache list:

- open the app and read/write every record
- chat with the offline brain, and with an on-device model if you've downloaded
  one
- create projects, scaffold stacks, edit code, preview in the iframe, export zips
- write proposals and invoices, check the money report
- queue prompts; they run when you reconnect

Things that need a network, obviously: cloud models, downloading model weights,
and syncing.

---

## Layout

```
hoolulu_offline/
├── server.py                  zero-dependency sync server + PWA host + AI proxies
├── run.sh                     thin launcher
└── web/
    ├── index.html             app shell
    ├── manifest.webmanifest   installable PWA
    ├── sw.js                  offline cache (bump CACHE_VERSION to force update)
    ├── css/app.css
    ├── icons/
    ├── vendor/webllm/         WebLLM runtime, vendored (no CDN)
    └── js/
        ├── app.js             shell, routing, provider status
        ├── db.js              IndexedDB + outbox + backup
        ├── sync.js            cursor sync engine
        ├── util.js            helpers, markdown, zip
        ├── ai/
        │   ├── provider.js    the fallback chain
        │   ├── local_brain.js offline skill router
        │   ├── skills.js      money / proposal / invoice / outreach / …
        │   ├── scaffold.js    project generators
        │   ├── webllm.js      on-device (WebGPU)
        │   ├── ollama.js      local daemon (via proxy)
        │   ├── cloud.js       OpenAI / Anthropic / compatible
        │   └── queue.js       queue-and-run-later
        └── ui/                chat, projects, money, settings, sync, modal
```

## Collections

`conversations`, `messages`, `projects`, `files`, `tasks`, `clients`, `gigs`,
`proposals`, `invoices`, `time_entries`, `products`, `sales`, `expenses`,
`queued_prompts`, `notes`. The server rejects anything outside this list.

## Troubleshooting

**"engine: offline brain" but I want a real model** — Settings → On-device
model → *Download & load*. It needs WebGPU; if the badge says WebGPU: no, use
Ollama or cloud instead.

**Ollama shows "not reachable"** — the proxy runs on whichever machine is
serving the app. If you're on your phone, that means your *server* machine
needs Ollama running, not your phone.

**Two devices, one is stuck** — Sync → *Re-download from server*. That rewinds
the local cursor and pulls everything again.

**I wiped a device and the data came back** — that's the server doing its job.
Wipe the server too if you want it gone.

**Cloud 401/403** — Settings → Cloud → *Test*. If you route through the proxy,
the key is sent to your own server, not to a third party.

## Security

- Data at rest is unencrypted browser storage. Use device encryption; this is
  not a vault.
- Set `--token` whenever the server is reachable beyond localhost, and put TLS
  in front of it if it crosses the internet.
- Cloud API keys are stored in local browser storage. With *Route through my
  sync server* on, keys go to your own server over that connection.
- The iframe preview runs with `sandbox="allow-scripts allow-modals"` — no
  access to your page, storage, origin, or network.
