"""Deployment as data.

A deployment is one JSON record validated against the ``delivery`` contract and
registered in ``data/hub/deployments.json``. Production releases stop at the
human gate; development releases go straight through once QA passes.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..approvals import GateBlocked, resolve
from ..contracts import check

SNAPSHOT_DIR = None  # resolved lazily: <state>/snapshots


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _snapshots() -> Path:
    return Path(SNAPSHOT_DIR or (config.STATE_DIR / "snapshots"))


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def _read_registry() -> dict:
    path = Path(config.DEPLOYMENTS_DB)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _write_registry(registry: dict) -> None:
    path = Path(config.DEPLOYMENTS_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def refresh_registry() -> dict:
    """Re-derive the registry from what is actually on disk in ``deployed/``."""
    registry = _read_registry()
    live = set()
    for directory in sorted(config.DEPLOY_ROOT.glob("*")) if config.DEPLOY_ROOT.exists() else []:
        if not directory.is_dir() or not (directory / "index.html").is_file():
            continue
        slug = directory.name
        live.add(slug)
        record = registry.get(slug, {})
        record.setdefault("slug", slug)
        record.setdefault("channel", "local-static")
        record.setdefault("tier", config.TIER)
        record.setdefault("deployed_at", _now())
        record.setdefault("status", "live")
        record["path"] = config.rel(directory)
        record["url"] = config.public_url(slug)
        registry[slug] = record
    for slug in list(registry):
        if slug not in live:
            registry[slug]["status"] = "missing"
    _write_registry(registry)
    return registry


def list_deployments() -> list[dict]:
    return sorted(refresh_registry().values(), key=lambda r: r.get("slug", ""))


def get(slug: str) -> dict | None:
    return refresh_registry().get(slug)


# --------------------------------------------------------------------------
# deploy / undeploy / rollback
# --------------------------------------------------------------------------

def deploy(slug: str, *, tier: str | None = None, channel: str = "local-static",
           qa: dict | None = None, evidence: list | None = None,
           approval_id: str | None = None, allow_gate: bool = False) -> dict:
    """Copy ``builds/<slug>`` to ``deployed/<slug>`` and register it.

    Production releases need a human (``allow_gate=True`` bypasses nothing — it
    only means the caller already holds an approved id).
    """
    config.ensure_dirs()
    tier = (tier or config.TIER).lower()
    build_dir = config.BUILD_ROOT / slug
    if not (build_dir / "index.html").is_file():
        raise FileNotFoundError(f"{build_dir} has no index.html — build it first")

    action = "release_to_production" if tier == "production" else "release_to_development"
    approval = {"id": approval_id or "-", "status": "skipped"}
    try:
        approval = resolve(action, slug=slug, tier=tier,
                           context={"qa_score": (qa or {}).get("score")},
                           evidence=evidence or [])
    except GateBlocked as blocked:
        if allow_gate and blocked.approval.get("status") != "evidence-required":
            approval = {"id": approval_id or "-", "status": "approved-bypass"}
        else:
            raise GateBlocked(blocked.approval) from None

    target = config.DEPLOY_ROOT / slug
    if target.exists():
        _snapshot(slug, target)
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir, target)

    record = {
        "slug": slug,
        "channel": channel,
        "tier": tier,
        "url": config.public_url(slug),
        "path": config.rel(target),
        "checksum": _checksum(target),
        "status": "live",
        "deployed_at": _now(),
        "qa_score": (qa or {}).get("score"),
        "approval": {"id": approval.get("id"), "status": approval.get("status")},
        "notes": [f"released by {config.OPERATOR} in {tier}"],
    }
    check("delivery", record)

    registry = _read_registry()
    registry[slug] = record
    _write_registry(registry)
    return record


def undeploy(slug: str, *, keep_snapshot: bool = True) -> bool:
    """Take a deployment down. Snapshot first so it can come back."""
    target = config.DEPLOY_ROOT / slug
    if not target.exists():
        return False
    if keep_snapshot:
        _snapshot(slug, target)
    shutil.rmtree(target)
    registry = _read_registry()
    registry.pop(slug, None)
    _write_registry(registry)
    return True


def rollback(slug: str) -> dict | None:
    """Restore the most recent snapshot of a deployment."""
    snapshots = sorted(_snapshots().glob(f"{slug}-*"), reverse=True)
    if not snapshots:
        return None
    target = config.DEPLOY_ROOT / slug
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(snapshots[0], target)
    registry = _read_registry()
    record = registry.get(slug, {})
    record.update({"slug": slug, "status": "rolled-back", "deployed_at": _now(),
                   "path": config.rel(target),
                   "url": config.public_url(slug), "checksum": _checksum(target),
                   "channel": record.get("channel", "local-static"),
                   "tier": record.get("tier", config.TIER)})
    check("delivery", record)
    registry[slug] = record
    _write_registry(registry)
    return record


# --------------------------------------------------------------------------
# health
# --------------------------------------------------------------------------

def health(slug: str | None = None) -> dict:
    """Check that what is registered is actually on disk and intact."""
    registry = refresh_registry()
    slugs = [slug] if slug else sorted(registry)
    results = {}
    for name in slugs:
        record = registry.get(name)
        problems: list[str] = []
        if record is None:
            results[name] = {"ok": False, "problems": ["not registered"]}
            continue
        path = config.REPO_ROOT / record.get("path", f"deployed/{name}")
        entry = path / "index.html"
        if not path.is_dir():
            problems.append("directory missing")
        elif not entry.is_file():
            problems.append("index.html missing")
        elif entry.stat().st_size < 200:
            problems.append("index.html suspiciously small")
        if record.get("status") == "missing":
            problems.append("registry says missing")
        results[name] = {
            "ok": not problems,
            "problems": problems,
            "url": record.get("url"),
            "tier": record.get("tier"),
            "qa_score": record.get("qa_score"),
            "deployed_at": record.get("deployed_at"),
        }
    return results if slug else results


# --------------------------------------------------------------------------

def format_deployments() -> str:
    records = list_deployments()
    if not records:
        return "Nothing deployed yet."
    lines = [f"{len(records)} deployment(s):"]
    for record in records:
        score = record.get("qa_score")
        lines.append(
            f"  {record['slug']:<20} {record.get('status', '?'):<12} "
            f"{record.get('tier', '?'):<12} qa {'-' if score is None else str(score) + '/100'}"
        )
        lines.append(f"     {record.get('url')}")
    return "\n".join(lines)


def _snapshot(slug: str, source: Path) -> Path:
    directory = _snapshots()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = directory / f"{slug}-{stamp}"
    shutil.copytree(source, destination)
    return destination


def _checksum(directory: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
