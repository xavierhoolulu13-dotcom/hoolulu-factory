"""Health checks for the whole factory. Used by ``ops/doctor.sh`` and ``amanda doctor``."""

from __future__ import annotations

import subprocess
import sys

from .. import config

REQUIRED_TEMPLATES = ("web_game", "landing_page", "tool")
REQUIRED_CONTRACTS = ("research", "product", "evidence", "build", "delivery",
                      "revenue", "loop")


def doctor() -> dict:
    checks = [
        _python(),
        _hub_tree(),
        _contracts(),
        _templates(),
        _swarm(),
        _offline_brain(),
        _deployments(),
        _approvals(),
        _skills(),
    ]
    return {
        "ok": all(check["ok"] for check in checks if check["severity"] == "hard"),
        "checks": checks,
    }


def format_doctor(result: dict) -> str:
    lines = ["Hoolulu Factory — doctor", ""]
    for check in result["checks"]:
        mark = "ok  " if check["ok"] else ("warn" if check["severity"] == "soft" else "FAIL")
        lines.append(f"  [{mark}] {check['name']:<16} {check['detail']}")
        if not check["ok"] and check.get("fix"):
            lines.append(f"          fix: {check['fix']}")
    lines.append("")
    lines.append("FACTORY STATUS: " + ("OPERATIONAL" if result["ok"] else
                                       "DEGRADED — see failures above"))
    return "\n".join(lines)


# --------------------------------------------------------------------------

def _python() -> dict:
    version = sys.version_info
    ok = version >= (3, 9)
    return {"name": "python", "ok": ok, "severity": "hard",
            "detail": f"{version.major}.{version.minor}.{version.micro} at {sys.executable}",
            "fix": "Python 3.9+ required"}


def _hub_tree() -> dict:
    ok, detail = run_scaffold_check()   # one definition of "the tree is whole"
    return {"name": "hub tree", "ok": ok, "severity": "hard",
            "detail": f"{config.HUB_ROOT.name}/ {detail.replace(chr(10), ' ')}",
            "fix": "run hoolulu-ecosystem-hub/ops/scaffold.sh"}


def _contracts() -> dict:
    from ..contracts import load

    broken = []
    for name in REQUIRED_CONTRACTS:
        try:
            if not load(name).get("properties"):
                broken.append(f"{name} (empty)")
        except Exception as exc:  # noqa: BLE001 - doctor reports, never raises
            broken.append(f"{name} ({exc})")
    return {"name": "contracts", "ok": not broken, "severity": "hard",
            "detail": f"all {len(REQUIRED_CONTRACTS)} contracts load" if not broken
                      else f"broken: {', '.join(broken)}",
            "fix": "restore hoolulu-ecosystem-hub/core/contracts/"}


def _templates() -> dict:
    missing = [t for t in REQUIRED_TEMPLATES
               if not (config.TEMPLATES_DIR / t / "index.html").is_file()]
    return {"name": "templates", "ok": not missing, "severity": "hard",
            "detail": f"{len(REQUIRED_TEMPLATES)} templates ready" if not missing
                      else f"missing: {', '.join(missing)}",
            "fix": "restore hoolulu-ecosystem-hub/factory/templates/"}


def _swarm() -> dict:
    from ..factory import load_swarm

    try:
        swarm = load_swarm()
    except Exception as exc:  # noqa: BLE001
        return {"name": "swarm", "ok": False, "severity": "hard",
                "detail": str(exc), "fix": "check agents/factory.yaml"}
    gated = ", ".join(a.name for a in swarm.gated()) or "none"
    return {"name": "swarm", "ok": True, "severity": "hard",
            "detail": f"{len(swarm)} agents loaded · gated: {gated}"}


def _offline_brain() -> dict:
    from ..offline import health, runtime

    status = health()
    if status["ok"]:
        model = (status["models"] or ["unknown"])[0]
        return {"name": "offline brain", "ok": True, "severity": "soft",
                "detail": f"model {model} at {status['url']}"}
    command = " ".join(runtime.serve_command())
    return {"name": "offline brain", "ok": False, "severity": "soft",
            "detail": f"no model at {status['url']} — running deterministic",
            "fix": f"serve one, e.g. {command}"}


def _deployments() -> dict:
    from ..delivery import health as deploy_health

    try:
        results = deploy_health()
    except Exception as exc:  # noqa: BLE001
        return {"name": "deployments", "ok": False, "severity": "soft",
                "detail": str(exc), "fix": "run amanda deploy <slug>"}
    if not results:
        return {"name": "deployments", "ok": True, "severity": "soft",
                "detail": "none yet — builds/<slug> is waiting"}
    problems = {name: r["problems"] for name, r in results.items() if not r["ok"]}
    return {"name": "deployments", "ok": not problems, "severity": "soft",
            "detail": f"{len(results)} live, all healthy" if not problems
                      else f"unhealthy: {problems}",
            "fix": "redeploy the affected slug"}


def _approvals() -> dict:
    from ..approvals import pending

    waiting = pending()
    return {"name": "approvals", "ok": True, "severity": "soft",
            "detail": f"{len(waiting)} waiting on a human" if waiting
                      else "nothing waiting"}


def _skills() -> dict:
    from ..skills import list_skills

    skills = list_skills()
    return {"name": "skills", "ok": True, "severity": "soft",
            "detail": f"{len(skills)} in {config.SKILLS_DIR}" if skills
                      else f"none in {config.SKILLS_DIR} (import one with `markus skill import`)"}


def run_scaffold_check() -> tuple[bool, str]:
    """Delegate to the shell scaffolder so there is one definition of the tree."""
    script = config.HUB_ROOT / "ops" / "scaffold.sh"
    if not script.exists():
        return False, "ops/scaffold.sh missing"
    done = subprocess.run(["bash", str(script), "--check"], capture_output=True,
                          text=True, timeout=60)
    return done.returncode == 0, (done.stdout or done.stderr).strip()
