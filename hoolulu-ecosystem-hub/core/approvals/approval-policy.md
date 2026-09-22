# Approval policy

The hub can build, test and stage on its own. It cannot **release, reprice,
spend, or contact in bulk** on its own. Those stop here.

## What is gated

| Action | Tier | Gate | Evidence required |
| --- | --- | --- | --- |
| `release_to_production` | production | human | test-result + build-output |
| `change_price` | both | human | intel-report + operator-note |
| `bulk_outreach` | both | human | operator-note |
| `spend_money` | both | human | receipt (after the fact) |
| `delete_deployment` | both | human | operator-note |
| release to `development` | development | auto after QA | test-result |

Set in `../deployments.yaml`; enforced in code by `hub/approvals/gates.py`.
A gate is a hard stop, not a warning: the stage returns `status: blocked` and
the loop waits.

## What counts as evidence

| Type | Examples | Collected by |
| --- | --- | --- |
| `build-output` | build log, artifact list, checksums | build stage |
| `test-result` | compile check, smoke test, QA score | qa stage |
| `screenshot` | rendered page, terminal capture | operator |
| `intel-report` | research findings, competitor notes | research stage |
| `receipt` | payment record, invoice | revenue stage |
| `operator-note` | a sentence from a human, with a timestamp | operator |

Minimum confidence per claim type lives in
`../../commercial-reasoning/evidence/schemas/claim-types.json`. Below the
threshold the claim stays a **hypothesis** and is printed as one.

## Lifecycle

```
blocked  →  awaiting human  →  approved (with evidence)  →  executed
                           └→  rejected (reason recorded)
```

Every transition is appended to `data/hub/approvals.jsonl` with the operator id,
the action, the evidence paths and the timestamp. Approvals are never deleted —
a rejection is data too.

## Commands

```bash
python -m amanda gate list                 # what is waiting
python -m amanda gate approve <id> --evidence <path> [--note "..."]
python -m amanda gate reject  <id> --note "why"
```
