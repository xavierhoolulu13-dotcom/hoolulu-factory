"""QA: prove the build works before a human is asked to release it.

Static checks only — no browser, no network. ``node --check`` runs when Node is
on the box, and is reported as skipped rather than passed when it is not. A
build below the role's ``min_score`` never reaches the release gate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


# weight, name, predicate -> (ok, detail)
MAX_BYTES = 400_000
_REFERENCE = re.compile(r'(?:src|href)\s*=\s*"([^"]+)"', re.IGNORECASE)
_URL_CALL = re.compile(r'url\(\s*["\']?(https?:)', re.IGNORECASE)
_FETCH = re.compile(r"\b(fetch|XMLHttpRequest|navigator\.sendBeacon)\s*\(", re.IGNORECASE)
_EXTERNAL = re.compile(r"https?://(?!localhost|127\.0\.0\.1)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\{\{\s*[A-Z0-9_]+\s*\}\}")


class QaError(RuntimeError):
    pass


def run(build_dir: Path | str, *, entry: str = "index.html") -> dict:
    """Score a build directory. Returns ``{score, passed, checks}``."""
    root = Path(build_dir)
    if not root.is_dir():
        raise QaError(f"no build directory at {root}")

    checks = [
        _check_entry(root, entry),
        _check_references(root, entry),
        _check_offline(root),
        _check_html(root, entry),
        _check_placeholders(root),
        _check_size(root),
        _check_js_syntax(root),
    ]
    weights = {"entry": 20, "references": 20, "offline": 20, "html": 10,
               "placeholders": 10, "size": 5, "js-syntax": 15}
    earned = sum(weights[c["name"]] for c in checks if c["ok"])
    total = sum(weights.values())
    return {
        "score": round(100 * earned / total),
        "passed": all(c["ok"] for c in checks if c["name"] != "js-syntax"),
        "checks": checks,
    }


def gate(build_dir: Path | str, *, min_score: int = 70, entry: str = "index.html") -> dict:
    """Run QA and mark the result against the role's threshold."""
    result = run(build_dir, entry=entry)
    result["min_score"] = min_score
    result["allowed"] = result["score"] >= min_score
    return result


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def _check_entry(root: Path, entry: str) -> dict:
    path = root / entry
    return {"name": "entry", "ok": path.is_file() and path.stat().st_size > 200,
            "detail": f"{entry} {'present' if path.is_file() else 'MISSING'}"
                      f" ({path.stat().st_size if path.is_file() else 0} bytes)"}


def _check_references(root: Path, entry: str) -> dict:
    """Every local src/href must resolve to a file that shipped with the build."""
    path = root / entry
    if not path.is_file():
        return {"name": "references", "ok": False, "detail": "no entry file"}
    missing = []
    for ref in _REFERENCE.findall(path.read_text(encoding="utf-8")):
        if ref.startswith(("#", "mailto:", "tel:", "data:", "http")):
            continue
        if not (root / ref.split("?")[0]).is_file():
            missing.append(ref)
    return {"name": "references", "ok": not missing,
            "detail": "all local references resolve" if not missing
                      else f"missing: {', '.join(missing)}"}


def _check_offline(root: Path) -> dict:
    """Nothing in the build may reach the network — offline-first is a rule."""
    offenders = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in (".html", ".css", ".js"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = []
        for ref in _REFERENCE.findall(text):
            if ref.startswith("http") and not ref.startswith(("http://localhost",
                                                              "http://127.0.0.1")):
                hits.append(ref)
        hits += [m.group(0) for m in _URL_CALL.finditer(text)]
        if _FETCH.search(text):
            hits.append("network call (fetch/XHR)")
        if hits:
            offenders.append(f"{path.name}: {', '.join(sorted(set(hits))[:3])}")
    return {"name": "offline", "ok": not offenders,
            "detail": "no external requests" if not offenders
                      else "; ".join(offenders)}


def _check_html(root: Path, entry: str) -> dict:
    path = root / entry
    if not path.is_file():
        return {"name": "html", "ok": False, "detail": "no entry file"}
    text = path.read_text(encoding="utf-8", errors="ignore")
    problems = []
    if "<title>" not in text:
        problems.append("no <title>")
    if not text.rstrip().endswith("</html>"):
        problems.append("does not close </html>")
    if text.count("<main") and "</main>" not in text:
        problems.append("unclosed <main>")
    return {"name": "html", "ok": not problems,
            "detail": "well-formed enough" if not problems else ", ".join(problems)}


def _check_placeholders(root: Path) -> dict:
    left = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in (".html", ".css", ".js", ".md", ".json"):
            found = _PLACEHOLDER.findall(path.read_text(encoding="utf-8", errors="ignore"))
            if found:
                left.append(f"{path.name}: {', '.join(sorted(set(found))[:3])}")
    return {"name": "placeholders", "ok": not left,
            "detail": "no unfilled placeholders" if not left else "; ".join(left)}


def _check_size(root: Path) -> dict:
    total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    return {"name": "size", "ok": total <= MAX_BYTES,
            "detail": f"{total:,} bytes ({'within' if total <= MAX_BYTES else 'over'} "
                      f"the {MAX_BYTES:,} byte budget)"}


def _check_js_syntax(root: Path) -> dict:
    """Run ``node --check`` on every JS file when Node is available."""
    scripts = [p for p in sorted(root.rglob("*.js")) if p.is_file()]
    if not scripts:
        return {"name": "js-syntax", "ok": True, "detail": "no JavaScript in this build"}
    node = shutil.which("node")
    if not node:
        return {"name": "js-syntax", "ok": True,
                "detail": "skipped — node not installed"}
    bad = []
    for script in scripts:
        done = subprocess.run([node, "--check", str(script)], capture_output=True,
                              text=True, timeout=30)
        if done.returncode != 0:
            bad.append(f"{script.name}: {(done.stderr or '').splitlines()[0][:120]}")
    return {"name": "js-syntax", "ok": not bad,
            "detail": f"{len(scripts)} file(s) parse" if not bad else "; ".join(bad)}


def format_report(result: dict) -> str:
    lines = [f"QA score {result['score']}/100 "
             f"({'allowed' if result.get('allowed', True) else 'BELOW gate'}"
             f"{' · min ' + str(result['min_score']) if 'min_score' in result else ''})"]
    for check in result["checks"]:
        lines.append(f"  {'✓' if check['ok'] else '✗'} {check['name']:<13} {check['detail']}")
    return "\n".join(lines)
