# The hub contract

One sentence in, one shipped product out. This is the path a request travels.

```
operator says "build me a snake game and host it"
        │
        ▼
  ┌─────────────┐  intake        Amanda parses intent, opens a loop_id
  ├─────────────┤  research      Researcher808 → market + competitor + demand notes
  ├─────────────┤  reasoning     Productizer808 → product spec, validated against
  │             │                core/contracts/product.schema.json
  ├─────────────┤  approval      human gate (production tier only, with evidence)
  ├─────────────┤  build         Builder808-Dev → builds/<slug>/ from a template
  ├─────────────┤  qa            QA808 → compile, smoke, score ≥ 70 or it stops
  ├─────────────┤  package       Ship808 → packages/<slug>.zip + manifest
  ├─────────────┤  deliver       Ship808 → deployed/<slug>/ served at /p/<slug>/
  └─────────────┘  maintain      Keeper808 → health checks, drift, rebuild advice
```

Every stage appends to `core/event-log/loops/events.jsonl` and returns the same
shape: `{stage, status, outputs, next}`. Stages never call each other directly —
they read the contract written by the stage before them. That is why a stage can
be re-run, skipped or handed to a human without rewiring anything.

## Contracts

| Contract | File | Written by | Read by |
| --- | --- | --- | --- |
| research | `core/contracts/research.schema.json` | research | reasoning |
| product | `core/contracts/product.schema.json` | reasoning | build, package |
| evidence | `core/contracts/evidence.schema.json` | any | approval |
| build | `core/contracts/build.schema.json` | build, qa | package |
| delivery | `core/contracts/delivery.schema.json` | deliver | maintain |
| revenue | `core/contracts/revenue.schema.json` | reasoning, revenue | operator |
| loop | `core/contracts/loop.schema.json` | every stage | orchestrator |

Contracts are validated in-process by `hub/contracts/validator.py` — a small
JSON-Schema subset checker, so validation works on a phone with no pip install.

## Where the code lives

Python package `hub/` (importable) drives the tree in this directory (data).
`amanda/` is the operator interface: CLI + web UI + hosted product server.
The legacy lead pipeline stays in `agent/` and shares nothing but the repo.
