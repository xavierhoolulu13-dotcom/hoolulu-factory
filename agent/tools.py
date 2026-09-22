"""The agent's hands: every action the Hoolulu Agent can take.

Each tool is a plain function with a declarative spec so the same registry
drives the chat UI, the one-click buttons, the CLI and LLM function calling.

Safety model
------------
* File access is confined to the repository root; ``.git``, ``.venv`` and
  ``data`` are never writable.
* Shell execution is never used. ``run_script`` builds an argument list and
  only ever launches the interpreter on a file inside the repo.
* Every action is appended to ``logs/agent_audit.log``.
"""

import os
import re
import subprocess
import sys
from datetime import datetime

from . import config, factory

REPO_ROOT = config.REPO_ROOT


# --------------------------------------------------------------------------
# Path + audit helpers
# --------------------------------------------------------------------------

def audit(tool, args, ok, summary):
    os.makedirs(config.LOG_DIR, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    line = f"{stamp} | {'OK ' if ok else 'ERR'} | {tool} | {summary}\n"
    try:
        with open(config.AUDIT_LOG, "a") as handle:
            handle.write(line)
    except OSError:
        pass
    return line.strip()


def safe_path(relative):
    """Resolve a user-supplied path inside the repo, or raise ValueError."""
    if not relative:
        raise ValueError("no path given")
    candidate = relative if os.path.isabs(relative) else os.path.join(REPO_ROOT, relative)
    resolved = os.path.realpath(candidate)
    root = os.path.realpath(REPO_ROOT)

    if resolved != root and not resolved.startswith(root + os.sep):
        raise ValueError(f"'{relative}' is outside the repository")

    parts = set(resolved[len(root):].strip(os.sep).split(os.sep))
    blocked = parts & set(config.FORBIDDEN_DIRS)
    if blocked:
        raise ValueError(f"refusing to write inside {sorted(blocked)[0]}/")
    return resolved


def _fail(tool, args, error):
    audit(tool, args, False, str(error)[:200])
    return {"ok": False, "error": str(error)}


def _ok(tool, args, payload, summary=""):
    audit(tool, args, True, summary or str(payload)[:200])
    payload = dict(payload)
    payload.setdefault("ok", True)
    return payload


# --------------------------------------------------------------------------
# Factory control
# --------------------------------------------------------------------------

def factory_init(args=None):
    """Create the factory database and folder skeleton."""
    result = factory.init_db()
    return _ok("factory_init", args or {}, {
        "message": "Factory online.",
        "database": result["db"],
        "tables": result["tables"],
        "folders_created": result["folders_created"],
    }, f"tables={len(result['tables'])}")


def factory_status(args=None):
    """Live counts for every pipeline stage."""
    return _ok("factory_status", args or {}, factory.factory_status(), "status snapshot")


def factory_report(args=None):
    """Markdown report of the whole factory."""
    return _ok("factory_report", args or {}, factory.factory_report(), "report generated")


def pipeline_run(args):
    """Run one pipeline stage, or the whole pipeline with stage='all'."""
    stage = (args or {}).get("stage", "all")
    send = bool((args or {}).get("send", False))
    if stage == "all":
        result = factory.run_pipeline(send=send)
    else:
        result = factory.run_stage(stage)
    result["stage"] = stage
    return _ok("pipeline_run", args, result, f"stage={stage} processed={result.get('processed')}")


def leads_list(args):
    """List leads, optionally filtered by status."""
    status = (args or {}).get("status")
    limit = int((args or {}).get("limit", 50))
    rows = factory.list_leads(status=status, limit=limit)
    return _ok("leads_list", args or {}, {"count": len(rows), "leads": rows},
               f"{len(rows)} leads")


def lead_add(args):
    """Add a single lead to the factory."""
    business = (args or {}).get("business", "").strip()
    if not business:
        return _fail("lead_add", args or {}, "a business name is required")
    lead = factory.add_lead(
        business=business,
        industry=args.get("industry", ""),
        city=args.get("city", ""),
        location=args.get("location", ""),
        website=args.get("website", ""),
        phone=args.get("phone", ""),
        email=args.get("email", ""),
        source=args.get("source", "agent"),
        notes=args.get("notes", ""),
    )
    return _ok("lead_add", args, {"message": f"{business} added to the factory.",
                                  "lead": lead}, business)


def lead_import(args):
    """Import leads from pasted CSV text."""
    text = (args or {}).get("csv", "")
    if not text.strip():
        return _fail("lead_import", args or {}, "no CSV text provided")
    result = factory.import_leads_csv(text)
    return _ok("lead_import", args, result, f"imported={result.get('imported')}")


def lead_status(args):
    """Move a lead to a specific pipeline state by hand."""
    business = (args or {}).get("business", "").strip()
    status = (args or {}).get("status", "").strip()
    if not business or not status:
        return _fail("lead_status", args or {}, "business and status are required")
    result = factory.set_lead_status(business, status, args.get("reply_status"))
    tool_result = _ok if result.get("ok") else _fail
    return tool_result("lead_status", args, result, f"{business}->{status}")


def seed_demo(args=None):
    """Load a realistic Hawaii demo pipeline."""
    count = int((args or {}).get("count", 6))
    return _ok("seed_demo", args or {}, factory.seed_demo(count), f"seeded {count}")


def reset_factory(args=None):
    """Clear all pipeline data (schema is kept)."""
    result = factory.reset_demo(confirm=bool((args or {}).get("confirm", True)))
    return _ok("reset_factory", args or {}, result, "pipeline wiped")


def outreach_draft(args):
    """Write the outreach message for one lead."""
    business = (args or {}).get("business", "").strip()
    if not business:
        return _fail("outreach_draft", args or {}, "business name is required")
    lead = factory.get_lead(business)
    if not lead:
        return _fail("outreach_draft", args or {}, f"no lead called '{business}'")
    draft = factory.build_outreach(lead)
    return _ok("outreach_draft", args, {"business": business, **draft}, business)


def mark_replied(args):
    """Record a reply from a lead and let Cass react to it."""
    business = (args or {}).get("business", "").strip()
    reply = (args or {}).get("reply", "").strip()
    if not business or not reply:
        return _fail("mark_replied", args or {}, "business and reply are required")
    lead = factory.get_lead(business)
    if not lead:
        return _fail("mark_replied", args or {}, f"no lead called '{business}'")

    signal = factory.classify_reply(reply)
    conn = factory.connect()
    try:
        fields = {"reply_status": signal, "notes": f"{lead.get('notes') or ''} | reply: {reply}".strip(" |"),
                  "updated_at": datetime.now().isoformat(timespec="seconds")}
        if signal == "CALL_BOOKED":
            fields["status"] = "BOOKED"
            conn.execute(
                "INSERT INTO tasks (agent, task, status, created_at) VALUES (?,?,?,?)",
                ("Cass", f"Prepare closing call for {business}", "OPEN",
                 datetime.now().isoformat(timespec="seconds")),
            )
        elif signal == "INTERESTED":
            fields["status"] = "REPLIED"
        elif signal == "NOT_INTERESTED":
            fields["status"] = "ARCHIVED"
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", (*fields.values(), lead["id"]))
        conn.commit()
    finally:
        conn.close()
    return _ok("mark_replied", args, {"business": business, "signal": signal,
                                      "status": fields["status"]}, f"{business}:{signal}")


# --------------------------------------------------------------------------
# Coding tools
# --------------------------------------------------------------------------

def code_list(args=None):
    """List the files in the factory."""
    pattern = (args or {}).get("pattern", "")
    only = (args or {}).get("dir", "")
    out = []
    base = safe_path(only) if only else REPO_ROOT
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in config.FORBIDDEN_DIRS]
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, REPO_ROOT)
            if pattern and pattern.lower() not in rel.lower():
                continue
            out.append({"path": rel, "bytes": os.path.getsize(full)})
    out.sort(key=lambda item: item["path"])
    return _ok("code_list", args or {}, {"count": len(out), "files": out[:400]},
               f"{len(out)} files")


def code_read(args):
    """Read a file from the factory."""
    path = (args or {}).get("path", "")
    try:
        resolved = safe_path(path)
        if not os.path.isfile(resolved):
            return _fail("code_read", args, f"no such file: {path}")
        with open(resolved, "r", errors="replace") as handle:
            content = handle.read(config.MAX_READ_BYTES)
    except (ValueError, OSError) as exc:
        return _fail("code_read", args, exc)
    return _ok("code_read", args, {"path": os.path.relpath(resolved, REPO_ROOT),
                                   "lines": content.count("\n") + 1,
                                   "content": content}, path)


def code_write(args):
    """Create or overwrite a file inside the factory."""
    path = (args or {}).get("path", "")
    content = (args or {}).get("content", "")
    if not path:
        return _fail("code_write", args or {}, "path is required")
    if len(content.encode()) > config.MAX_WRITE_BYTES:
        return _fail("code_write", args, "content too large")
    try:
        resolved = safe_path(path)
        existed = os.path.isfile(resolved)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w") as handle:
            handle.write(content)
    except (ValueError, OSError) as exc:
        return _fail("code_write", args or {}, exc)

    rel = os.path.relpath(resolved, REPO_ROOT)
    return _ok("code_write", args, {
        "path": rel,
        "action": "updated" if existed else "created",
        "bytes": len(content.encode()),
        "lines": content.count("\n") + 1,
    }, f"{rel} ({len(content.encode())} bytes)")


def code_patch(args):
    """Search-and-replace inside one file."""
    path = (args or {}).get("path", "")
    find = (args or {}).get("find", "")
    replace = (args or {}).get("replace", "")
    if not find:
        return _fail("code_patch", args or {}, "find text is required")
    try:
        resolved = safe_path(path)
        with open(resolved, "r", errors="replace") as handle:
            content = handle.read()
        count = content.count(find)
        if count == 0:
            return _fail("code_patch", args, "search text not found in file")
        limit = int((args or {}).get("count", 1))
        content = content.replace(find, replace, limit)
        with open(resolved, "w") as handle:
            handle.write(content)
    except (ValueError, OSError) as exc:
        return _fail("code_patch", args or {}, exc)
    return _ok("code_patch", args, {"path": os.path.relpath(resolved, REPO_ROOT),
                                    "replacements": min(count, limit)}, f"{path} x{min(count, limit)}")


def code_search(args):
    """Grep the factory for a string or regex."""
    pattern = (args or {}).get("pattern", "")
    if not pattern:
        return _fail("code_search", args or {}, "pattern is required")
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return _fail("code_search", args, f"bad regex: {exc}")

    hits = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in config.FORBIDDEN_DIRS]
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if not name.endswith((".py", ".md", ".txt", ".json", ".html", ".js", ".css", ".csv", ".sh")):
                continue
            try:
                with open(full, "r", errors="replace") as handle:
                    for number, line in enumerate(handle, 1):
                        if regex.search(line):
                            hits.append({"path": os.path.relpath(full, REPO_ROOT),
                                         "line": number, "text": line.strip()[:200]})
            except OSError:
                continue
    return _ok("code_search", args, {"count": len(hits), "matches": hits[:200]},
               f"{len(hits)} matches")


def run_script(args):
    """Run a Python script from the factory and capture its output."""
    script = (args or {}).get("script", "")
    if not script:
        return _fail("run_script", args or {}, "script is required")
    try:
        resolved = safe_path(script)
        if not os.path.isfile(resolved):
            return _fail("run_script", args, f"no such script: {script}")
        timeout = min(int((args or {}).get("timeout", config.COMMAND_TIMEOUT)), 120)
        proc = subprocess.run(
            [sys.executable, resolved],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return _fail("run_script", args, f"{script} timed out")
    except (ValueError, OSError) as exc:
        return _fail("run_script", args, exc)

    output = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    return _ok("run_script", args, {
        "script": os.path.relpath(resolved, REPO_ROOT),
        "exit_code": proc.returncode,
        "output": output[-8000:],
    }, f"{script} exit={proc.returncode}")


def repo_check(args=None):
    """Compile every Python file and report which ones are broken."""
    broken, checked = [], 0
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in config.FORBIDDEN_DIRS]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            checked += 1
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "py_compile", full],
                    capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                if proc.returncode != 0:
                    broken.append({"path": os.path.relpath(full, REPO_ROOT),
                                   "error": (proc.stderr or "").strip()[-400:]})
            except (subprocess.TimeoutExpired, OSError) as exc:
                broken.append({"path": os.path.relpath(full, REPO_ROOT), "error": str(exc)})
    return _ok("repo_check", args or {}, {
        "checked": checked,
        "broken_count": len(broken),
        "broken": broken,
        "verdict": "clean" if not broken else f"{len(broken)} file(s) need fixing",
    }, f"{checked} checked, {len(broken)} broken")


AGENT_TEMPLATE = '''"""{title} agent for the Hoolulu Factory.

Generated by the Hoolulu Agent. Wire it into a stage by importing it from
``agent/factory.py`` or calling it from ``agent/tools.py``.
"""

import os
import sys
from datetime import datetime

# Allow running this file directly: put the repository root on sys.path so the
# ``agent`` package resolves no matter where the script is launched from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import factory


def run(lead):
    """Process one lead and return the fields to write back."""
    return {{
        "notes": ((lead.get("notes") or "") + " | handled by {name}").strip(" |"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }}


def run_all(status="{status}"):
    """Process every lead currently sitting in ``status``."""
    results = []
    conn = factory.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE upper(status) = ?", (status.upper(),)
        )]
        for lead in rows:
            update = run(lead)
            sets = ", ".join(f"{{k}} = ?" for k in update)
            conn.execute(
                f"UPDATE leads SET {{sets}} WHERE id = ?",
                (*update.values(), lead["id"]),
            )
            results.append({{"business": lead["business"], **update}})
        conn.commit()
    finally:
        conn.close()
    return {{"agent": "{title}", "processed": len(results), "results": results}}


if __name__ == "__main__":
    output = run_all()
    print(f"{{output['agent']}} processed {{output['processed']}} lead(s)")
    for item in output["results"]:
        print(" -", item["business"])
'''


def build_agent(args):
    """Scaffold a brand new agent module — the 'build my factory' action."""
    name = (args or {}).get("name", "").strip()
    if not name:
        return _fail("build_agent", args or {}, "give the agent a name")
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug:
        return _fail("build_agent", args, f"'{name}' is not a usable module name")

    rel = f"agents/{slug}.py"
    try:
        resolved = safe_path(rel)
        if os.path.exists(resolved) and not (args or {}).get("overwrite"):
            return _fail("build_agent", args, f"{rel} already exists")
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        init_file = os.path.join(os.path.dirname(resolved), "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()
        content = AGENT_TEMPLATE.format(
            title=name.title().replace("_", " "),
            name=slug,
            status=(args or {}).get("status", "SCORED"),
        )
        with open(resolved, "w") as handle:
            handle.write(content)
    except (ValueError, OSError) as exc:
        return _fail("build_agent", args or {}, exc)

    check = subprocess.run(
        [sys.executable, "-m", "py_compile", resolved],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return _ok("build_agent", args, {
        "path": rel,
        "message": f"Agent '{name}' built at {rel}.",
        "compiles": check.returncode == 0,
        "compile_error": (check.stderr or "").strip()[-300:],
        "next_step": f"python {rel}",
    }, f"built {rel}")


# --------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------

def _git(*git_args, timeout=30):
    proc = subprocess.run(
        ["git", *git_args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout
    )
    return {"exit_code": proc.returncode,
            "output": ((proc.stdout or "") + (proc.stderr or "")).strip()[:8000]}


def git_status(args=None):
    """Show uncommitted changes in the factory."""
    result = _git("status", "--short", "--branch")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")["output"]
    return _ok("git_status", args or {}, {**result, "branch": branch}, "git status")


def git_diff(args=None):
    """Show the working diff."""
    return _ok("git_diff", args or {}, _git("diff", "--stat"), "git diff --stat")


def git_log(args=None):
    """Show recent commits."""
    limit = str((args or {}).get("limit", 10))
    return _ok("git_log", args or {},
               _git("log", f"-{limit}", "--oneline"), f"git log -{limit}")


def git_commit(args):
    """Commit the current changes."""
    message = (args or {}).get("message", "").strip()
    if not message:
        return _fail("git_commit", args or {}, "a commit message is required")
    staged = _git("add", "-A")
    if staged["exit_code"] != 0:
        return _fail("git_commit", args, staged["output"])
    result = _git("commit", "-m", message)
    if result["exit_code"] != 0:
        return _fail("git_commit", args, result["output"] or "nothing to commit")
    return _ok("git_commit", args, result, message[:80])


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

TOOL_SPECS = [
    {"name": "factory_init", "fn": factory_init, "group": "factory",
     "label": "Init factory", "confirm": False,
     "description": "Create the factory database, tables and folder skeleton.",
     "params": {}},
    {"name": "factory_status", "fn": factory_status, "group": "factory",
     "label": "Factory status", "confirm": False,
     "description": "Live counts for every pipeline stage, top leads and open tasks.",
     "params": {}},
    {"name": "factory_report", "fn": factory_report, "group": "factory",
     "label": "Full report", "confirm": False,
     "description": "Markdown report of pipeline, numbers and top leads.",
     "params": {}},
    {"name": "pipeline_run", "fn": pipeline_run, "group": "factory",
     "label": "Run pipeline", "confirm": False,
     "description": "Run a pipeline stage (score, enrich, outreach, closer, delivery, report) or 'all'.",
     "params": {"stage": "string: one of score|enrich|outreach|closer|delivery|report|all (default all)",
                "send": "boolean: also mark outreach as sent (default false)"}},
    {"name": "leads_list", "fn": leads_list, "group": "leads",
     "label": "View leads", "confirm": False,
     "description": "List leads, optionally filtered by status.",
     "params": {"status": "string: optional pipeline status", "limit": "integer: max rows"}},
    {"name": "lead_add", "fn": lead_add, "group": "leads",
     "label": "Add lead", "confirm": False,
     "description": "Add one lead to the factory.",
     "params": {"business": "string: required business name", "industry": "string",
                "city": "string", "website": "string", "phone": "string",
                "email": "string", "notes": "string"}},
    {"name": "lead_import", "fn": lead_import, "group": "leads",
     "label": "Import CSV", "confirm": False,
     "description": "Import many leads from pasted CSV text with a header row.",
     "params": {"csv": "string: CSV text including header row"}},
    {"name": "lead_status", "fn": lead_status, "group": "leads",
     "label": "Set lead status", "confirm": False,
     "description": "Move a lead to a specific pipeline state by hand.",
     "params": {"business": "string: required", "status": "string: required pipeline state",
                "reply_status": "string: optional"}},
    {"name": "mark_replied", "fn": mark_replied, "group": "leads",
     "label": "Log a reply", "confirm": False,
     "description": "Record a lead's reply; Cass books the call if it sounds positive.",
     "params": {"business": "string: required", "reply": "string: required reply text"}},
    {"name": "outreach_draft", "fn": outreach_draft, "group": "leads",
     "label": "Draft outreach", "confirm": False,
     "description": "Write the personalized outreach message for one lead.",
     "params": {"business": "string: required business name"}},
    {"name": "seed_demo", "fn": seed_demo, "group": "factory",
     "label": "Load demo data", "confirm": False,
     "description": "Insert a realistic Hawaii demo pipeline.",
     "params": {"count": "integer: how many demo leads (default 6)"}},
    {"name": "reset_factory", "fn": reset_factory, "group": "factory",
     "label": "Reset pipeline", "confirm": True,
     "description": "Delete all pipeline data. Schema is kept.",
     "params": {"confirm": "boolean: must be true"}},
    {"name": "code_list", "fn": code_list, "group": "code",
     "label": "List files", "confirm": False,
     "description": "List files in the factory, optionally filtered.",
     "params": {"pattern": "string: substring filter", "dir": "string: subdirectory"}},
    {"name": "code_read", "fn": code_read, "group": "code",
     "label": "Read file", "confirm": False,
     "description": "Read one file from the factory.",
     "params": {"path": "string: required repo-relative path"}},
    {"name": "code_write", "fn": code_write, "group": "code",
     "label": "Write file", "confirm": True,
     "description": "Create or overwrite a file inside the factory.",
     "params": {"path": "string: required repo-relative path", "content": "string: required file body"}},
    {"name": "code_patch", "fn": code_patch, "group": "code",
     "label": "Patch file", "confirm": True,
     "description": "Search-and-replace inside one file.",
     "params": {"path": "string: required", "find": "string: required exact text",
                "replace": "string: replacement text", "count": "integer: max replacements"}},
    {"name": "code_search", "fn": code_search, "group": "code",
     "label": "Search code", "confirm": False,
     "description": "Search the factory for a string or regex.",
     "params": {"pattern": "string: required regex or plain text"}},
    {"name": "run_script", "fn": run_script, "group": "code",
     "label": "Run script", "confirm": False,
     "description": "Run a Python script from the factory and capture output.",
     "params": {"script": "string: required repo-relative .py path", "timeout": "integer: seconds"}},
    {"name": "repo_check", "fn": repo_check, "group": "code",
     "label": "Check code", "confirm": False,
     "description": "Compile every Python file and report the broken ones.",
     "params": {}},
    {"name": "build_agent", "fn": build_agent, "group": "code",
     "label": "Build new agent", "confirm": True,
     "description": "Scaffold a new factory agent module and verify it compiles.",
     "params": {"name": "string: required agent name", "status": "string: lead status it processes",
                "overwrite": "boolean"}},
    {"name": "git_status", "fn": git_status, "group": "git",
     "label": "Git status", "confirm": False,
     "description": "Show uncommitted changes.", "params": {}},
    {"name": "git_diff", "fn": git_diff, "group": "git",
     "label": "Git diff", "confirm": False,
     "description": "Show the working diff stat.", "params": {}},
    {"name": "git_log", "fn": git_log, "group": "git",
     "label": "Git log", "confirm": False,
     "description": "Show recent commits.", "params": {"limit": "integer"}},
    {"name": "git_commit", "fn": git_commit, "group": "git",
     "label": "Git commit", "confirm": True,
     "description": "Stage and commit all current changes.",
     "params": {"message": "string: required commit message"}},
]

REGISTRY = {spec["name"]: spec for spec in TOOL_SPECS}


def dispatch(name, args=None):
    """Run a registered tool by name. Never raises."""
    spec = REGISTRY.get(name)
    if not spec:
        return {"ok": False, "error": f"unknown tool '{name}'",
                "available": sorted(REGISTRY)}
    args = args or {}
    if not isinstance(args, dict):
        return {"ok": False, "error": "tool arguments must be an object"}
    try:
        return spec["fn"](args)
    except Exception as exc:  # a bad tool must never take the agent down
        return _fail(name, args, f"{type(exc).__name__}: {exc}")


def public_specs():
    """Tool metadata for the UI and for LLM function calling."""
    return [
        {"name": s["name"], "description": s["description"], "group": s["group"],
         "label": s["label"], "confirm": s["confirm"], "params": s["params"]}
        for s in TOOL_SPECS
    ]
