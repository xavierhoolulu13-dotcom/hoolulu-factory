# Hoolulu Factory 🤙

Two things live here.

**Amanda** — say one sentence and she researches it, scopes it, builds it,
tests it, packages it, puts it online, and keeps checking on it.

**The agent** — the original lead pipeline: score → enrich → outreach → close →
deliver, with a UI and an API.

```bash
python -m amanda "build me a snake game and host it"   # the factory
./start.sh                                             # the lead agent (:8000)
```

---

## Amanda

```bash
.venv/bin/python -m pip install -r requirements.txt
python -m amanda "build me a booking page for a Kailua surf school"
python -m amanda serve          # console + hosted products on :8010
```

That is the whole install. Nothing needs an API key: with no model server
reachable, Amanda reasons deterministically and says so.

```
$ python -m amanda "build me a snake game and host it"

Snake Game — a one-thumb browser game that loads instantly, plays offline
and is easy to share.
  sell 72 · scale 76 · build 82 · whitespace 100%  [offline-heuristic]
  money: free play, tip jar, then white-label licence to venues — $0/player
  projection: $0 in month 1 → $0 by month 12 (assumptions, not measurements)
  built: builds/snake-game (5 files, 1 ms)
  qa: 100/100 ✓
  package: packages/snake-game-1.0.0.zip (8,734 bytes)
  live: http://localhost:8010/p/snake-game/

  ✓ intake     “build me a snake game and host it” → Snake Game [web_game]
  ✓ research   6 findings, 3 gaps
  ✓ reasoning  Snake Game · sell 72 · scale 76 · whitespace 100%
  ✓ build      5 files in builds/snake-game (1 ms)
  ✓ qa         score 100/100
  ✓ package    packages/snake-game-1.0.0.zip (8,734 bytes)
  ✓ deliver    live at http://localhost:8010/p/snake-game/
```

### What she says

| You say | She does |
| --- | --- |
| `build me a snake game and host it` | the whole loop, then a URL |
| `spec a QR menu for a food truck` | scores the idea without building it |
| `status` | deployments, builds, approvals, brain |
| `maintain` | health check everything that is live |
| `deploy snake-game --tier production` | release — asks a human in production |
| `gate list` / `gate approve <id> --evidence <path>` | the human gate |
| `doctor` | what is broken and how to fix it |
| `report` | what shipped, how it is priced, what it earned |
| `swarm` | the crew from `agents/factory.yaml` |

Free text works too: `python -m amanda build me a snake game`, or
`python -m amanda chat` for a REPL.

### How she thinks

Every stage writes one validated contract and one line in
`hoolulu-ecosystem-hub/core/event-log/loops/events.jsonl`:

```
intake → research → reasoning → approval → build → qa → package → deliver → maintain
```

- **research** — a local corpus of buyer, price band, competitor archetypes and
  unmet needs. Optional network adapters (SearXNG, Firecrawl) merge in when you
  configure them; when they are off, that is recorded as a *gap*, never filled in
  with invented findings.
- **reasoning** — turns the request into a `product` contract: audience, problem,
  features, MVP, monetization, distribution, risks, scale path, and four scores
  (sellability, scalability, buildability, confidence). The gap engine scores how
  much known whitespace the spec actually occupies.
- **build** — instantiates a template from
  `hoolulu-ecosystem-hub/factory/templates/` (`web_game`, `landing_page`, `tool`).
- **qa** — entry file, local references, zero external requests, well-formed HTML,
  no unfilled placeholders, size budget, and `node --check` on every script.
  Below the gate, nothing is released.
- **package / deliver** — zip + manifest + checksum, then served at
  `/p/<slug>/`. Production releases stop for a human with evidence.
- **maintain** — health checks every deployment and logs what it found.

Two brains, one interface. `deterministic` always works. If a llama.cpp server
answers at `HOOLULU_OFFLINE_URL` (default `http://localhost:8080/v1`), the model
drafts specs and routes commands, and its output is rejected unless it validates
against the contract. The badge in the console tells you which one answered.

### Guardrails

Releasing to production, changing a price, spending money, bulk outreach and
deleting a deployment stop at a human with evidence. Configured in
`hoolulu-ecosystem-hub/deployments.yaml`, enforced in `hub/approvals/gates.py`:

```
$ python -m amanda deploy snake-game --tier production
⏸ release_to_production is gated in tier 'production' (approval 2fc47a13)
   python -m amanda gate approve 2fc47a13 --evidence builds/snake-game/manifest.json

$ python -m amanda gate approve 2fc47a13 --evidence builds/snake-game/manifest.json
✓ approved release_to_production for snake-game (evidence: builds/snake-game/manifest.json)

$ python -m amanda deploy snake-game --tier production
✓ snake-game live at http://localhost:8010/p/snake-game/ [production]
```

---

## Skills (`markus`)

Import a skill pack from anywhere, export it to anywhere. Detection is by file
signature; everything is rewritten into one normal form
(`skill.yaml` + `SKILL.md` + `scripts/` + `references/`).

```bash
./markus skill list
./markus skill import ~/Downloads/clawhub-skill.zip --force
./markus skill import ./skills/pdf-tables --name pdf-tools
./markus skill import ~/projects/agent-scope-skill --to ~/.markus/skills/my-scope

./markus skill export pdf-tools --format claude      # → ./pdf-tools-claude/
./markus skill export pdf-tools --format openclaw --out ~/publish
./markus skill export pdf-tools --format soul
./markus skill export pdf-tools --format mcp-server
./markus skill export pdf-tools --format agentscope
./markus skill export pdf-tools --from ~/.markus/skills/pdf-tools

./markus skill formats      # every format and the rule that detects it
```

| Format | Detected by |
| --- | --- |
| `markus` | `skill.yaml` |
| `claude` | `SKILL.md` with YAML frontmatter (name + description) |
| `openclaw` | `openclaw.yaml`, or `skill.json` with an `openclaw` key |
| `soul` | `soul.yaml` or `SOUL.md` |
| `mcp-server` | `mcp.json` / `server.json` containing `mcpServers` |
| `agentscope` | `agentscope.yaml`, or `config.json` with an `agentscope` key |
| `generic` | any folder with `README.md` or `SKILL.md` |

Scripts are copied byte-for-byte; what is generated is the descriptor, and every
export carries an `EXPORT-NOTES.md` saying exactly that.

---

## Layout

```
agent/                     the original lead-pipeline agent (Flask, :8000)
amanda/                    the operator interface — brain, tools, CLI, web (:8010)
hub/                       the runtime: contracts, reasoning, build, delivery
hoolulu-ecosystem-hub/     the data: contracts, templates, policy, ops scripts
agents/factory.yaml        the workforce, declared
markus                     skill pack CLI
builds/ deployed/ packages/   what the factory has made (gitignored)
```

`hub/` is importable Python; `hoolulu-ecosystem-hub/` holds the files it reads
and writes. The hyphenated tree is data, not code — that split is deliberate.

---

# The lead agent

An AI agent that runs your factory. Click a button or type a sentence and it
scores leads, writes outreach, books calls, delivers clients — and writes code
in this repo when the factory needs a new part.

```bash
./start.sh
```

Then open http://localhost:8000.

That is the whole install. `start.sh` creates a virtualenv, installs the
dependencies, builds the SQLite database, and starts the agent. Use
`./start.sh --demo` to wipe the pipeline and load six sample Hawaii leads first.

## What it can do

**Run the factory.** The pipeline is the one your scripts already describe:

```
NEW → SCORED → ENRICHED → READY_FOR_OUTREACH → CONTACTED → BOOKED → CLIENT
        └ NURTURE (score below 60)                    └ ARCHIVED (said no)
```

| You say | The agent does |
| --- | --- |
| `status` | live counts for every stage, top scored leads, open tasks |
| `run the pipeline` | score → enrich → outreach → closer → delivery in one go |
| `score the leads` | scores every `NEW` lead, with the reasons shown |
| `draft outreach` | writes a personalized message per lead |
| `Kailua Poke Shack replied "yes let's book a call"` | Cass books the call and queues the closing task |
| `deliver clients` | turns booked calls into clients, proposals, delivery tasks |
| `full report` | markdown report with conversion numbers |

**Work your leads.**

```
add lead "Sunset Tacos" city=Kailua phone=808-555-0142 notes=no website
show leads status=BOOKED
write the message for Kailua Poke Shack
import csv          (then paste: business,city,phone on the first row)
```

**Build the factory.** The agent writes and runs code in this repository:

```
build me an agent called Review Watcher     → agents/review_watcher.py, compile-checked
check the code                              → compiles every .py, lists what's broken
run dashboard.py                            → runs it and shows the output
read orchestrator.py / search for outreach_status
git status / commit this as "wired the pipeline"
```

## How the agent works

```
agent/
  server.py     Flask app — the UI and the JSON API
  brain.py      intent routing (LocalBrain) + optional LLM function calling
  tools.py      24 tools: the agent's hands, with safety rails
  factory.py    the pipeline engine (SQLite) — pure functions over leads
  cli.py        the same agent in your terminal
  dify_export.py  OpenAPI + Dify DSL export
  templates/, static/   the one-click UI
```

**Two brains, one interface.** `LocalBrain` is deterministic intent matching
with slot extraction — no network, no API key. If you export `OPENAI_API_KEY`
(or `ANTHROPIC_API_KEY`), `LLMBrain` takes over with real function calling and
falls back to local on any error.

**Safety rails.** File access is confined to the repository; `.git`, `.venv`
and `data/` are never writable. Nothing runs through a shell — the agent builds
an argument list and only launches the interpreter on a file inside the repo,
with a timeout. Every action lands in `logs/agent_audit.log`.

## Data

Everything lives in `data/hoolulu.db` (SQLite, WAL mode). Tables: `leads`,
`tasks`, `opportunities`, `proposals`, `clients`, `delivery_tasks`,
`outreach_queue`, `agent_runs`. `data/`, `logs/`, `backups/`, `builds/`,
`deployed/` and `packages/` are gitignored.

## Terminal use

```bash
.venv/bin/python -m agent.cli                      # interactive REPL
.venv/bin/python -m agent.cli "run the pipeline"   # one shot
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

91 tests cover both halves: the lead pipeline, every tool, intent routing, the
safety rails, the HTTP API and the exports — plus the hub's contracts,
reasoning, build/QA/package/deploy round trip, the approval gate, the skill
formats, and Amanda's end-to-end loop. They run against throwaway directories,
so your real factory is never touched.

## Configuration

| Variable | Default | What it does |
| --- | --- | --- |
| `HOOLULU_PORT` | `8010` (agent: `8000`) | port to listen on |
| `HOOLULU_HOST` | `0.0.0.0` | bind address |
| `HOOLULU_TIER` | `development` | `production` turns on the human gate |
| `HOOLULU_OFFLINE_URL` | `http://localhost:8080/v1` | llama.cpp endpoint |
| `HOOLULU_OFFLINE_MODEL` | `local` | model name to request |
| `HOOLULU_MODELS_DIR` | `~/models` | where `.gguf` files live |
| `HOOLULU_PUBLIC_URL` | `http://localhost:<port>` | base for hosted product links (empty = relative) |
| `HOOLULU_SKILLS_DIR` | `~/.markus/skills` | skill pack directory |
| `HOOLULU_SWARM` | `<root>/agents/factory.yaml` | workforce definition |
| `HOOLULU_DB` | `data/hoolulu.db` | lead database (the agent) |
| `OPENAI_API_KEY` | — | enables the LLM brain in `agent/` |
| `HOOLULU_MODEL` | `gpt-4o-mini` | model for that brain |

Copy `hoolulu-ecosystem-hub/.env.example` to `.env` for the full list.

## On a phone (Termux)

`hoolulu-ecosystem-hub/mobile/termux/setup.sh` installs Termux packages, clones
this repo, fetches a 3B Q4_K_M model, serves it on `:8080`, and starts the
factory. One brain, no cloud.

## The legacy scripts

The 47 flat scripts at the repo root still work against the same database, and
all of them compile. But they were written for a `core/` + `agents/` package
layout that was never committed:

- **5 reference paths that don't exist** — `orchestrator.py` and
  `sales_pipeline.py` fail at import (`No module named 'agents.scoring'`,
  `No module named 'core.database'`); `autopilot.py`, `command_center.py` and
  `factory_runner.backup.py` shell out to `core/*.py` files that aren't there.
- **3 are empty** — `pipeline_map.py`, `registry.py`, `repository.py`.
- `factory_runner.py`, `dashboard.py`, `view.py`, `metrics.py` and the queue
  scripts run fine as they are.

They are left untouched and share one database with the agent. New work belongs
in `amanda/` and `hub/`.
