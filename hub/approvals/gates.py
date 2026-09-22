"""The human gate.

Enforced here, configured in ``hoolulu-ecosystem-hub/deployments.yaml``. A gate
is a hard stop: the stage returns ``blocked`` and the loop waits for a human
with evidence. Approvals are append-only — a rejection is data too.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import config

ALWAYS_GATED = ("change_price", "bulk_outreach", "spend_money", "delete_deployment")
TIER_GATED = ("release_to_production",)


class GateBlocked(RuntimeError):
    """Raised when a stage tries to do something that needs a human."""

    def __init__(self, approval: dict):
        self.approval = approval
        hint = ""
        if approval.get("status") == "evidence-required":
            hint = (" — the approval has no evidence; approve it again with "
                    "`gate approve <id> --evidence <path>`")
        super().__init__(
            f"{approval['action']} is gated in tier '{approval['tier']}' "
            f"(approval {approval['id']}){hint}"
        )


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------

def load_policy() -> dict:
    path = Path(config.DEPLOYMENTS_FILE)
    if not path.exists():
        return {"deployments": {}, "gated_actions": list(ALWAYS_GATED)}
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("PyYAML is required to read deployments.yaml "
                           "(pip install pyyaml)") from exc
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def policy_for(tier: str | None = None) -> dict:
    tier = (tier or config.TIER).lower()
    policy = load_policy()
    return (policy.get("deployments") or {}).get(tier, {})


def is_gated(action: str, tier: str | None = None) -> bool:
    tier = (tier or config.TIER).lower()
    policy = load_policy()
    gated = set(policy.get("gated_actions") or ALWAYS_GATED)
    if action in gated:
        return True
    if tier == "production":
        guardrails = policy_for("production").get("guardrails") or {}
        if guardrails.get("human_gate"):
            return action in TIER_GATED
    return False


# --------------------------------------------------------------------------
# approvals
# --------------------------------------------------------------------------

def _path() -> Path:
    return Path(config.APPROVALS_FILE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(record: dict) -> dict:
    _path().parent.mkdir(parents=True, exist_ok=True)
    with _path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return record


def _read_all() -> list[dict]:
    path = _path()
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


def latest() -> dict[str, dict]:
    """Collapse the append-only log into the current state of each approval."""
    state: dict[str, dict] = {}
    for record in _read_all():
        state[record.get("id", "?")] = record
    return state


def request(action: str, *, slug: str | None = None, tier: str | None = None,
            context: dict | None = None, evidence: list | None = None) -> dict:
    """Open an approval request. Gated actions start ``pending``, others ``auto``."""
    tier = (tier or config.TIER).lower()
    return _append({
        "id": uuid.uuid4().hex[:8],
        "ts": _now(),
        "action": action,
        "slug": slug,
        "tier": tier,
        "status": "pending" if is_gated(action, tier) else "auto-approved",
        "context": context or {},
        "evidence": [str(e) for e in (evidence or [])],
        "operator": None,
        "note": "",
    })


def require(action: str, *, slug: str | None = None, tier: str | None = None,
            context: dict | None = None, evidence: list | None = None) -> dict:
    """Check the gate. Raises ``GateBlocked`` if a human has to decide."""
    approval = request(action, slug=slug, tier=tier, context=context, evidence=evidence)
    if approval["status"] == "pending":
        raise GateBlocked(approval)
    return approval


def resolve(action: str, *, slug: str | None = None, tier: str | None = None,
            context: dict | None = None, evidence: list | None = None) -> dict:
    """Check the gate, spending an approval a human already granted.

    This is what a stage calls: if the action is not gated it passes; if a human
    has approved this exact action/slug/tier it passes and the approval is
    consumed; otherwise it blocks and raises ``GateBlocked`` with the request a
    human has to answer.
    """
    tier = (tier or config.TIER).lower()
    if not is_gated(action, tier):
        return request(action, slug=slug, tier=tier, context=context, evidence=evidence)

    for record in reversed(_read_all()):
        if (record.get("action") == action and record.get("slug") == slug
                and record.get("tier") == tier and record.get("status") == "approved"):
            guardrails = policy_for(tier).get("guardrails") or {}
            if guardrails.get("trace_evidence") and not record.get("evidence"):
                raise GateBlocked({**record, "status": "evidence-required"})
            _append({**record, "ts": _now(), "status": "consumed"})
            return record

    raise GateBlocked(request(action, slug=slug, tier=tier, context=context,
                              evidence=evidence))


def approve(approval_id: str, *, evidence: list | None = None, note: str = "",
            operator: str | None = None) -> dict:
    state = latest().get(approval_id)
    if state is None:
        raise KeyError(f"no approval '{approval_id}'")
    return _append({
        **state,
        "ts": _now(),
        "status": "approved",
        "evidence": [str(e) for e in (evidence or state.get("evidence") or [])],
        "operator": operator or config.OPERATOR,
        "note": note,
    })


def reject(approval_id: str, *, note: str = "", operator: str | None = None) -> dict:
    state = latest().get(approval_id)
    if state is None:
        raise KeyError(f"no approval '{approval_id}'")
    return _append({
        **state, "ts": _now(), "status": "rejected",
        "operator": operator or config.OPERATOR, "note": note,
    })


def pending() -> list[dict]:
    return [r for r in latest().values() if r.get("status") == "pending"]


def get(approval_id: str) -> dict | None:
    return latest().get(approval_id)


def format_pending() -> str:
    waiting = pending()
    if not waiting:
        return "No approvals waiting."
    lines = [f"{len(waiting)} action(s) waiting on a human:"]
    for record in waiting:
        lines.append(
            f"  {record['id']}  {record['action']}  {record.get('slug') or '-'}  "
            f"[{record['tier']}]  {record['ts']}"
        )
        if record.get("context"):
            lines.append(f"        context: {record['context']}")
    lines.append("  approve with: python -m amanda gate approve <id> --evidence <path>")
    return "\n".join(lines)
