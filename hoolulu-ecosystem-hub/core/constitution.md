# Constitution

Non-negotiable rules. A change that breaks one of these does not get merged,
no matter how convenient.

## 1. Offline first
The hub must produce a complete answer with no network and no API key. A missing
model server degrades quality, never availability: every reasoning step has a
deterministic fallback and labels itself `offline-heuristic` in
`provenance.source` so nobody mistakes a guess for research.

## 2. Privacy is architecture
Prompts, leads, drafts and customer data are processed by the local model.
Nothing is uploaded to a third party unless an operator explicitly enables an
adapter in `.env` and a stage says out loud that it is going to the network.

## 3. Humans hold the high-impact switches
Releasing to production, changing a price, spending money, bulk outreach and
deleting a deployment stop at a human. Auto-release is allowed in the
`development` tier only — see `../deployments.yaml`.

## 4. No evidence, no action
A gated action carries artifacts: build output, test results, screenshots,
receipts, operator notes. Missing evidence downgrades a claim to a hypothesis.
It never becomes a fact silently (`commercial-reasoning/evidence/schemas/`).

## 5. Typed at every boundary
Stages hand each other JSON validated against `core/contracts/`. A field that
matters downstream can never be missing — that is why `opportunity_score`-style
gaps are a schema error, not a runtime surprise.

## 6. Idempotent by default
Every script in `ops/` and every hub command can run twice in a row and leave
the same state. Scaffolding never clobbers an existing file without `--force`.

## 7. The honest failure
When something is wrong the hub says what is wrong and what to do next.
It does not invent a model, fake a deployment, or claim a build passed QA.
