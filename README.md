# Hoolulu Factory 🤙

An AI agent that runs your factory. Click a button or type a sentence and it
scores leads, writes outreach, books calls, delivers clients — and writes code
in this repo when the factory needs a new part.

```bash
./start.sh
```

Then open http://localhost:8000.

That is the whole install. `start.sh` creates a virtualenv, installs Flask,
builds the SQLite database, and starts the agent. Use `./start.sh --demo` to
wipe the pipeline and load six sample Hawaii leads first.

---

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

Generated agents are self-contained: they bootstrap `sys.path`, import the
factory engine, and run standalone with `python agents/<name>.py`.

---

## How it works

```
agent/
  server.py     Flask app — the UI and the JSON API
  brain.py      intent routing (LocalBrain) + optional LLM function calling
  tools.py      24 tools: the agent's hands, with safety rails
  factory.py    the pipeline engine (SQLite) — pure functions over leads
  cli.py        the same agent in your terminal
  dify_export.py  OpenAPI + Dify DSL export
  templates/, static/   the one-click UI
tests/test_agent.py     57 tests
start.sh        one-click launcher
```

**Two brains, one interface.** `LocalBrain` is deterministic intent matching
with slot extraction — no network, no API key, so it always works the moment
you open the page. If you export `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`)
before starting, `LLMBrain` takes over with real function calling and falls
back to local on any error. The badge in the header tells you which one is
answering.

**The factory engine** (`agent/factory.py`) is the real implementation of the
pipeline your legacy scripts sketch. It is dependency-free and self-contained,
so the CLI, the web agent and the tests all run the exact same code.

**Safety rails.** File access is confined to the repository; `.git`, `.venv`
and `data/` are never writable. Nothing is ever run through a shell — the agent
builds an argument list and only launches the interpreter on a file inside the
repo, with a timeout. Every action lands in `logs/agent_audit.log`.

---

## Data

Everything lives in `data/hoolulu.db` (SQLite, WAL mode) — the same path your
existing scripts already point at, so old and new code share one database.
Tables: `leads`, `tasks`, `opportunities`, `proposals`, `clients`,
`delivery_tasks`, `outreach_queue`, `agent_runs`.

`data/`, `logs/` and `backups/` are gitignored. Nothing is committed by default.

---

## Terminal use

```bash
.venv/bin/python -m agent.cli                      # interactive REPL
.venv/bin/python -m agent.cli "run the pipeline"   # one shot
.venv/bin/python -m agent.cli --once "status"      # exit non-zero on failure
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

57 tests cover the pipeline stages, every tool, intent routing, the safety
rails, the HTTP API and the exports. They run against a throwaway database, so
your real factory is never touched.

---

## Plugging into Dify, ChatGPT, or anything else

```bash
.venv/bin/python -m agent.dify_export
```

writes two files to `generated/`:

- **`openapi.json`** — OpenAPI 3.0 describing all 24 tools. Point Dify's Custom
  Tool, a ChatGPT Action, or any function-calling host at it. Regenerate it
  after adding tools; it refuses to export an incomplete registry.
- **`dify-hoolulu-agent.yml`** — a Dify agent-chat DSL carrying the same system
  prompt. Dify's DSL schema moves between releases, so treat this as a starting
  point and check it against the version you run. The OpenAPI file is the
  stable contract.

Set `HOOLULU_PUBLIC_URL` before exporting if the agent will be reached from
somewhere other than `http://127.0.0.1:8000`.

---

## Configuration

| Variable | Default | What it does |
| --- | --- | --- |
| `HOOLULU_PORT` | `8000` | port to listen on |
| `HOOLULU_HOST` | `0.0.0.0` | bind address |
| `HOOLULU_DB` | `data/hoolulu.db` | database location |
| `HOOLULU_ROOT` | `~/hoolulu-factory` | factory root for logs and folders |
| `OPENAI_API_KEY` | — | enables the LLM brain |
| `HOOLULU_MODEL` | `gpt-4o-mini` | model for the LLM brain |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | any OpenAI-compatible endpoint |

---

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

They are left untouched and share one database with the agent. `./start.sh`
creates the folder skeleton they expect, and `check the code` in the agent
compiles everything and lists what's broken. New work belongs in `agent/`.
