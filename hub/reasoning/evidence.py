"""Evidence: the artifacts a gated action must carry.

Rules live in ``commercial-reasoning/evidence/schemas/claim-types.json``.
A claim without the required artifacts stays a hypothesis — it never quietly
becomes a fact that a release decision rests on.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..contracts import check

LEDGER = None  # resolved lazily so tests can point it elsewhere


def ledger_path() -> Path:
    return Path(LEDGER or (config.STATE_DIR / "evidence.jsonl"))


def claim_types() -> dict:
    path = config.EVIDENCE_DIR / "claim-types.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("claim_types", {})


def sha256_of(path: Path | str) -> str:
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def record(claim: str, evidence_type: str, artifacts: list, *, confidence: float = 0.5,
           collector: str | None = None) -> dict:
    """Append one evidence record, validated against the evidence contract."""
    stamped = []
    for artifact in artifacts:
        if isinstance(artifact, (str, Path)):
            path = Path(artifact)
            entry = {"path": config.rel(path)}
            if path.exists() and path.is_file():
                entry["sha256"] = sha256_of(path)
                entry["bytes"] = path.stat().st_size
        else:
            entry = dict(artifact)
        stamped.append(entry)

    entry = {
        "claim": claim,
        "evidence_type": evidence_type,
        "artifacts": stamped,
        "confidence": round(float(confidence), 2),
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "collector": collector or config.OPERATOR,
    }
    check("evidence", entry)
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    with ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def all_records() -> list[dict]:
    path = ledger_path()
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def for_claim(claim: str) -> list[dict]:
    return [r for r in all_records() if r.get("claim") == claim]


def sufficient(claim: str, claim_type: str) -> dict:
    """Is there enough evidence to promote ``claim`` to a decision?"""
    rules = claim_types().get(claim_type)
    if rules is None:
        return {"ok": False, "reason": f"unknown claim type '{claim_type}'",
                "missing": [], "records": 0}
    records = for_claim(claim)
    have = {r["evidence_type"] for r in records}
    missing = [t for t in rules.get("requires", []) if t not in have]
    threshold = float(rules.get("min_confidence", 0.5))
    best = max((float(r.get("confidence", 0)) for r in records), default=0.0)
    ok = not missing and best >= threshold
    return {
        "ok": ok,
        "missing": missing,
        "records": len(records),
        "best_confidence": best,
        "min_confidence": threshold,
        "reason": ("ok" if ok else
                   f"missing {missing}" if missing else
                   f"confidence {best:.2f} < {threshold:.2f}"),
    }
