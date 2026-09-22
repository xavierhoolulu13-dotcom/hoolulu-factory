"""The Hoolulu Agent's brain.

Two implementations behind one interface:

``LocalBrain``
    Deterministic intent matching + slot extraction. Needs no network and no
    API key, so the agent always works the moment you open it.

``LLMBrain``
    Function-calling against any OpenAI-compatible endpoint. Used automatically
    when ``OPENAI_API_KEY`` (or ``ANTHROPIC_API_KEY``) is set, and it falls back
    to ``LocalBrain`` on any error so the agent never goes dark.

Both return the same shape::

    {"reply": str, "actions": [{"tool", "args", "result", "ok"}], "brain": str}
"""

import json
import os
import re
import urllib.error
import urllib.request

from . import config, factory
from .tools import REGISTRY, dispatch, public_specs

HELP_TEXT = """I'm your Hoolulu factory agent. I can run the whole pipeline, work your leads, and write code in this repo.

**Try saying**
- `status` — what's in the factory right now
- `run the pipeline` — score → enrich → outreach → closer → delivery
- `score the leads` / `enrich them` / `draft outreach` / `run the closer`
- `add lead "Kailua Poke Shack" city=Kailua phone=808-555-0142 notes=no website`
- `show leads` / `show leads status=BOOKED`
- `write the message for Kailua Poke Shack`
- `Kailua Poke Shack replied "yes let's book a call"`
- `build me an agent called Review Watcher`
- `check the code` — compile every file and tell me what's broken
- `run dashboard.py` / `read orchestrator.py` / `search for outreach_status`
- `git status` / `commit this as "wired the pipeline"`
- `full report`

Or just click a button on the right. 🤙"""


# --------------------------------------------------------------------------
# Slot extraction
# --------------------------------------------------------------------------

QUOTED = re.compile(r'["\u201c]([^"\u201d]+)["\u201d]|\'([^\']+)\'')
FIELD_KEYS = ("business", "industry", "category", "city", "location", "website",
              "phone", "email", "notes", "source", "status", "reply", "name",
              "message", "stage", "path", "script", "pattern", "limit", "count")
# Value runs lazily until the next `key=`, a comma/semicolon, or end of input,
# so `city=Kailua phone=808-555-1234` yields two fields, not one greedy one.
FIELD_RE = re.compile(
    r"\b(" + "|".join(FIELD_KEYS) + r")\s*[:=]\s*(.+?)"
    r"(?=\s+\b(?:" + "|".join(FIELD_KEYS) + r")\s*[:=]|[,;]|$)",
    re.IGNORECASE | re.MULTILINE,
)


def extract_fields(text):
    """Pull ``key=value`` / ``key: value`` pairs out of a message."""
    fields = {}
    for key, value in FIELD_RE.findall(text):
        fields[key.lower()] = value.strip().strip("\"'")
    return fields


def extract_quoted(text):
    match = QUOTED.search(text)
    if match:
        return (match.group(1) or match.group(2)).strip()
    return ""


def _guess_business(text, fields):
    """Best-effort business name when it wasn't quoted or keyed."""
    if fields.get("business"):
        return fields["business"]
    quoted = extract_quoted(text)
    if quoted:
        return quoted
    # 'write the message for Kailua Poke Shack' -> 'Kailua Poke Shack'
    for_target = re.search(r"\bfor\s+(.+)$", text.strip(), flags=re.IGNORECASE)
    if for_target:
        candidate = for_target.group(1)
        candidate = re.sub(r"\b(city|phone|email|website|industry|notes|source|status)\s*[:=].*$",
                           "", candidate, flags=re.IGNORECASE)
        candidate = candidate.strip(" .,-?").strip()
        if 2 < len(candidate) < 90:
            return candidate

    # 'add lead Kailua Poke Shack in Kailua' -> 'Kailua Poke Shack'
    cleaned = re.sub(
        r"^(please\s+)?(add|create|new|insert)\s+(a\s+)?(new\s+)?lead\s*",
        "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(city|phone|email|website|industry|notes|source|status)\s*[:=].*$",
                     "", cleaned, flags=re.IGNORECASE)
    cleaned = re.split(r"\s+(in|from|,)\s+", cleaned, maxsplit=1)[0]
    cleaned = cleaned.strip(" .,-").strip()
    return cleaned if 2 < len(cleaned) < 90 else ""


def _strip_command(text, words):
    pattern = r"^(please\s+)?(" + "|".join(words) + r")\b[\s:,-]*"
    return re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()


# --------------------------------------------------------------------------
# Local brain
# --------------------------------------------------------------------------

class LocalBrain:
    name = "local"

    def think(self, message):
        text = (message or "").strip()
        if not text:
            return self._say(HELP_TEXT)

        lowered = text.lower()
        fields = extract_fields(text)

        # Order matters: the most specific commands are matched first so a
        # generic word like "status" never swallows "git status" or
        # "show leads status=BOOKED".

        # --- 1. help ----------------------------------------------------
        if lowered in ("help", "?", "what can you do", "menu", "commands") or \
                re.search(r"\b(what can you do|how do (i|you) work|help me)\b", lowered):
            return self._say(HELP_TEXT)

        # --- 2. git (before the generic 'status' rule) ------------------
        git_match = re.search(r"\bgit (status|diff|log)\b", lowered)
        if git_match or lowered in ("status of git", "uncommitted changes"):
            return self._act(f"git_{git_match.group(1) if git_match else 'status'}", {},
                             formatter=format_git)

        if re.search(r"\b(commit|save this|check ?in)\b", lowered):
            message = _after(text, r"\b(commit|save this|check ?in)\b")
            message = re.sub(r"^(this|it|the changes|everything|all)\s*(as)?\s*", "",
                             message, flags=re.IGNORECASE).strip(" '\".,-")
            if len(message) < 3:
                message = "Factory update by the Hoolulu Agent"
            return self._act("git_commit", {"message": message}, formatter=format_git)

        # --- 3. code building ------------------------------------------
        if re.search(r"\b(build|create|make|scaffold)\b.*\b(agent|module|bot)\b", lowered):
            name = fields.get("name") or _after(text, r"\b(?:called|named|call it)\b") or ""
            if not name:
                name = _strip_command(text, ["build", "create", "make", "scaffold"])
                name = re.sub(r"\b(me\s+)?(an?\s+)?(new\s+)?(factory\s+)?(agent|module|bot)\b",
                              "", name, flags=re.IGNORECASE)
                name = re.sub(r"\b(called|named|call it)\b", "", name, flags=re.IGNORECASE)
                name = name.strip(" .,-")
            if not name:
                return self._say("What should I call the new agent? e.g. `build me an agent called Review Watcher`")
            return self._act("build_agent", {"name": name, "status": fields.get("status", "SCORED")},
                             formatter=format_build)

        # --- 4. coding (before 'status'/'run the factory') -------------
        if re.search(r"\b(check|verify|compile|lint)\b.*\b(code|files?|repo|everything)\b", lowered) \
                or lowered in ("check the code", "check code", "verify"):
            return self._act("repo_check", {}, formatter=format_check)

        if re.search(r"\b(run|execute|launch)\b.*\.(py|sh)\b", lowered):
            script = _find_path(text)
            if not script:
                return self._say("Which script? e.g. `run dashboard.py`")
            return self._act("run_script", {"script": script}, formatter=format_run)

        if re.search(r"\b(read|open|show me|cat)\b.*\.(py|md|txt|json|html|js|css)\b", lowered):
            path = _find_path(text)
            if not path:
                return self._say("Which file? e.g. `read orchestrator.py`")
            return self._act("code_read", {"path": path}, formatter=format_read)

        if re.search(r"\b(search|grep)\b", lowered):
            pattern = _strip_command(text, ["search", "grep"])
            pattern = re.sub(r"^(for|the code|code|in the repo|the repo)\s+", "", pattern,
                             flags=re.IGNORECASE).strip(" '\"")
            if not pattern:
                return self._say("What should I search for?")
            return self._act("code_search", {"pattern": pattern}, formatter=format_search)

        if re.search(r"\b(list|show)\b.*\bfiles?\b", lowered):
            return self._act("code_list", {"pattern": fields.get("pattern", "")},
                             formatter=format_file_list)

        # --- 5. replies (before lead add / status) ---------------------
        if re.search(r"\b(replied|responded)\b", lowered):
            business = fields.get("business")
            reply = fields.get("reply")
            if not business:
                # 'Kailua Poke Shack replied "yes"' -> name is before the verb
                business = re.split(r"\s+(replied|responded)\b", text,
                                    flags=re.IGNORECASE)[0].strip()
                business = re.sub(r"^(please\s+)?(log|record|mark|note)\s+(that\s+)?", "",
                                  business, flags=re.IGNORECASE).strip(" :,-")
            if not reply:
                reply = extract_quoted(text) or _after(text, r"\b(replied|responded)\b")
                reply = reply.strip(" :,-\"'")
            if not business or not reply:
                return self._say("Tell me who replied and what they said, e.g. "
                                 "`Kailua Poke Shack replied \"yes let's book a call\"`")
            return self._act("mark_replied", {"business": business, "reply": reply},
                             formatter=format_reply)

        # --- 6. leads ---------------------------------------------------
        if re.search(r"\b(add|create|new|insert)\b.*\blead\b", lowered) or \
                (lowered.startswith("add ") and len(lowered) < 160):
            business = _guess_business(text, fields)
            if not business:
                return self._say("Which business? e.g. `add lead \"Kailua Poke Shack\" city=Kailua phone=808-555-0142`")
            return self._act("lead_add", {k: v for k, v in fields.items() if k in
                                          ("industry", "city", "location", "website",
                                           "phone", "email", "notes", "source")}
                             | {"business": business},
                             formatter=format_lead_added)

        if re.search(r"\bimport\b.*\b(csv|leads)\b", lowered) and ("," in text and "\n" in text):
            return self._act("lead_import", {"csv": text[text.find("\n") + 1:]},
                             formatter=format_import)

        if re.search(r"\b(write|draft|generate)\b.*\b(message|outreach|email|dm)\b", lowered):
            # "write the message for X" targets one lead; a bare "draft
            # outreach" means run the whole outreach stage.
            specific = bool(extract_quoted(text) or re.search(r"\bfor\b", lowered)
                            or fields.get("business"))
            business = _guess_business(text, fields) if specific else ""
            if specific and business:
                return self._act("outreach_draft", {"business": business},
                                 formatter=format_outreach)
            if specific:
                return self._say("For which business? e.g. `write the message for Kailua Poke Shack`")

        if re.search(r"\b(show|list|view|see|who)\b.*\bleads?\b", lowered) or \
                re.search(r"\b(queue|pipeline list)\b", lowered):
            return self._act("leads_list", {"status": fields.get("status"),
                                            "limit": _to_int(fields.get("limit"), 25)},
                             formatter=format_leads)

        # --- 7. reporting / status -------------------------------------
        if re.search(r"\b(full report|report|summar(y|ize) the factory|how am i doing)\b", lowered):
            return self._act("factory_report", {}, formatter=lambda r: r.get("report", "No report."))

        if re.search(r"\b(status|how.?s the factory|where are we|dashboard|snapshot|counts)\b", lowered):
            return self._act("factory_status", {}, formatter=format_status)

        if re.search(r"\b(init|initiali[sz]e|set ?up the (factory|database)|create the database)\b", lowered):
            return self._act("factory_init", {}, formatter=format_init)

        if re.search(r"\b(seed|demo data|sample (leads|data)|load demo)\b", lowered):
            return self._act("seed_demo", {"count": _to_int(fields.get("count"), 6)},
                             formatter=format_seed)

        if re.search(r"\b(reset|wipe|clear|empty)\b.*\b(factory|pipeline|leads|data)\b", lowered):
            return self._act("reset_factory", {"confirm": True},
                             formatter=lambda r: r.get("message", "Done."))

        # --- 8. pipeline stages ----------------------------------------
        stage = self._match_stage(lowered, fields)
        if stage:
            send = bool(re.search(r"\b(send|sent|actually send|go ahead and send)\b", lowered))
            args = {"stage": stage}
            if stage == "outreach":
                args["send"] = send
            return self._act("pipeline_run", args, formatter=format_stage)

        # --- 9. fallback -----------------------------------------------
        return self._fallback(text)

    # -- internals -------------------------------------------------------

    def _match_stage(self, lowered, fields):
        if fields.get("stage"):
            stage = fields["stage"].lower()
            return stage if stage in factory.STAGES else None
        if re.search(r"\b(run|start|go|execute)\b.*\b(pipeline|factory|everything|all|the works|full run)\b", lowered) \
                or lowered.strip() in ("run", "go", "run it", "start the factory"):
            return "all"
        if re.search(r"\bscor", lowered):
            return "score"
        if re.search(r"\benrich", lowered):
            return "enrich"
        if re.search(r"\b(outreach|email them|message them|reach out|contact)", lowered):
            return "outreach"
        # NB: no trailing \b here — "closer" must still match the "clos" prefix.
        if re.search(r"\b(clos|cass|book(ed)? (the )?calls?|follow ?up)", lowered):
            return "closer"
        if re.search(r"\b(deliver|onboard|client setup)\b", lowered):
            return "delivery"
        return None

    def _fallback(self, text):
        hint = ("I didn't catch a command in that. Try `status`, `run the pipeline`, "
                "`add lead \"Name\" city=Kailua`, `check the code`, or `help` for the full list.")
        status = factory.factory_status()
        total = status["totals"].get("leads", 0)
        if total == 0:
            hint += "\n\nThe factory is empty right now — say `load demo data` and I'll fill it, then `run the pipeline`."
        return self._say(hint)

    def _say(self, reply):
        return {"reply": reply, "actions": [], "brain": self.name}

    def _act(self, tool, args, formatter=None):
        args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
        result = dispatch(tool, args)
        action = {"tool": tool, "args": args, "result": result, "ok": bool(result.get("ok"))}
        if formatter and result.get("ok"):
            reply = formatter(result)
        elif not result.get("ok"):
            reply = f"⚠️ {result.get('error', 'that failed')}"
        else:
            reply = f"Done — `{tool}`."
        return {"reply": reply, "actions": [action], "brain": self.name}


def _to_int(value, default):
    """Parse an int from user text without ever raising."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _after(text, pattern):
    parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)
    return parts[-1].strip() if len(parts) > 1 else ""


def _find_path(text):
    match = re.search(r"[\w./\-]+\.(?:py|sh|md|txt|json|html|js|css)", text)
    return match.group(0) if match else ""


# --------------------------------------------------------------------------
# Formatters
# --------------------------------------------------------------------------

def format_status(result):
    by = result.get("by_status", {})
    totals = result.get("totals", {})
    lines = ["**Factory status**", "",
             f"Leads: **{totals.get('leads', 0)}** · Clients: **{totals.get('clients', 0)}** · "
             f"Open tasks: **{len(result.get('open_tasks', []))}**", ""]
    if by:
        lines.append("| Stage | Count |")
        lines.append("| --- | --- |")
        for stage in factory.PIPELINE:
            if by.get(stage):
                lines.append(f"| {stage} | {by[stage]} |")
    else:
        lines.append("_No leads yet. Say `load demo data` or add one._")

    if result.get("top_leads"):
        lines += ["", "**Top scored**"]
        lines += [f"- {l['business']} — {l['score']:.0f} pts — {l['status']}"
                  for l in result["top_leads"][:5]]
    lines += ["", f"Database: `{result.get('database')}`"]
    return "\n".join(lines)


def format_stage(result):
    stage = result.get("stage", "all")
    if stage == "all":
        lines = ["**Pipeline run complete**", "", "| Stage | Processed |", "| --- | --- |"]
        for step in result.get("stages", []):
            lines.append(f"| {step.get('agent')} | {step.get('processed', 0)} |")
        lines.append(f"\nTotal moves: **{result.get('processed', 0)}**")
        if not result.get("processed"):
            lines.append("\nNothing to move — leads may already be at the end of the pipeline. "
                         "Try `load demo data` then `run the pipeline`.")
        return "\n".join(lines)

    lines = [f"**{result.get('agent')}** processed **{result.get('processed', 0)}** lead(s)."]
    for item in result.get("results", [])[:10]:
        detail = " · ".join(f"{k}={v}" for k, v in item.items() if k != "message")
        lines.append(f"- {detail}")
    if result.get("processed") == 0:
        lines.append("\nNo leads were waiting at that stage. Run `status` to see where everything sits.")
    return "\n".join(lines)


def format_report(result):
    return result.get("report", "No report generated.")


def format_init(result):
    return (f"**{result.get('message')}**\n\nDatabase: `{result.get('database')}`\n\n"
            f"Tables ({len(result.get('tables', []))}): {', '.join(result.get('tables', []))}")


def format_seed(result):
    return (f"Seeded **{result.get('created')}** demo leads: "
            + ", ".join(result.get("leads", [])) + "\n\nSay `run the pipeline` to work them.")


def format_lead_added(result):
    lead = result.get("lead", {})
    return (f"✅ **{lead.get('business')}** added (id {lead.get('id')}).\n\n"
            f"Status `{lead.get('status')}` — say `score the leads` to push it through the factory.")


def format_import(result):
    line = f"Imported **{result.get('imported')}** leads"
    if result.get("skipped"):
        line += f", skipped {result['skipped']} rows with no business name"
    if result.get("unknown_columns"):
        line += f"\n\n_Ignored unknown columns: {', '.join(result['unknown_columns'])}_"
    return line


def format_leads(result):
    leads = result.get("leads", [])
    if not leads:
        return "No leads match that filter."
    lines = [f"**{result.get('count')}** lead(s)", "",
             "| # | Business | Category | City | Score | Status |", "| --- | --- | --- | --- | --- | --- |"]
    for lead in leads[:25]:
        lines.append(f"| {lead['id']} | {lead['business']} | {lead.get('category') or '—'} | "
                     f"{lead.get('city') or '—'} | {lead.get('score') or 0:.0f} | {lead.get('status')} |")
    return "\n".join(lines)


def format_outreach(result):
    return (f"**Outreach for {result.get('business')}**\n\n> {result.get('message','').replace(chr(10), chr(10) + '> ')}"
            f"\n\n_Offer: {result.get('offer')} · Pain point: {result.get('problem')}_")


def format_reply(result):
    emoji = {"CALL_BOOKED": "📞", "INTERESTED": "🌱", "NOT_INTERESTED": "🚫"}.get(
        result["signal"], "⏳")
    return (f"{emoji} **{result.get('business')}** → reply read as `{result['signal']}`, "
            f"status now `{result.get('status')}`."
            + ("\n\nI put a closing-call task on Cass's list." if result["signal"] == "CALL_BOOKED" else ""))


def format_check(result):
    lines = [f"**Code check** — compiled **{result.get('checked')}** Python files."]
    if not result.get("broken"):
        lines.append("\n✅ Everything compiles cleanly.")
        return "\n".join(lines)
    lines.append(f"\n⚠️ {result.get('broken_count')} file(s) need fixing:\n")
    for item in result.get("broken", [])[:10]:
        tail = (item["error"] or "").splitlines()[-1] if item["error"] else ""
        lines.append(f"- `{item['path']}` — {tail}")
    return "\n".join(lines)


def format_read(result):
    content = result.get("content", "")
    if len(content) > 4000:
        content = content[:4000] + "\n... (truncated)"
    return f"**{result.get('path')}** ({result.get('lines')} lines)\n\n```python\n{content}\n```"


def format_run(result):
    output = result.get("output", "").strip() or "(no output)"
    if len(output) > 4000:
        output = output[:4000] + "\n... (truncated)"
    flag = "✅" if result.get("exit_code") == 0 else "❌"
    return (f"{flag} `{result.get('script')}` exited **{result.get('exit_code')}**\n\n"
            f"```\n{output}\n```")


def format_search(result):
    if not result.get("matches"):
        return "No matches."
    lines = [f"**{result.get('count')}** match(es)", ""]
    for hit in result["matches"][:20]:
        lines.append(f"- `{hit['path']}:{hit['line']}` — {hit['text']}")
    return "\n".join(lines)


def format_file_list(result):
    files = result.get("files", [])
    if not files:
        return "No files matched."
    return f"**{result.get('count')}** file(s)\n\n" + "\n".join(
        f"- `{f['path']}` ({f['bytes']} b)" for f in files[:60])


def format_git(result):
    output = result.get("output", "").strip() or "(clean)"
    branch = result.get("branch")
    head = f"**git** on `{branch}`\n\n" if branch else "**git**\n\n"
    return head + f"```\n{output[:3000]}\n```"


def format_build(result):
    line = f"🛠️ **{result.get('message')}**"
    line += "\n\n✅ Compiles cleanly." if result.get("compiles") else \
        f"\n\n⚠️ Compile error:\n```\n{result.get('compile_error')}\n```"
    line += f"\n\nRun it with `{result.get('next_step')}`."
    return line


# --------------------------------------------------------------------------
# LLM brain (optional upgrade)
# --------------------------------------------------------------------------

def _param_schema(description):
    """Turn 'string: required business name' into a JSON-schema property."""
    kind, _, detail = (description or "").partition(":")
    kind, detail = kind.strip().lower(), detail.strip()
    required = detail.lower().startswith("required")
    detail = re.sub(r"^required\s*", "", detail, flags=re.IGNORECASE)
    mapping = {"string": "string", "integer": "integer", "number": "number",
               "boolean": "boolean", "int": "integer", "bool": "boolean"}
    return {"type": mapping.get(kind, "string"),
            "description": detail or description or ""}, required


def tool_schemas():
    """OpenAI function-calling schema built from the live tool registry."""
    schemas = []
    for spec in public_specs():
        properties, required = {}, []
        for name, description in spec["params"].items():
            prop, is_required = _param_schema(description)
            properties[name] = prop
            if is_required:
                required.append(name)
        schemas.append({
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": {"type": "object", "properties": properties,
                               "required": required},
            },
        })
    return schemas


SYSTEM_PROMPT = """You are the Hoolulu Factory agent: a coding and operations agent for a Hawaii
lead-generation factory built in Python + SQLite.

You control the factory through tools only. Never invent data or claim you ran
something you did not call. Prefer tools over prose: if the user asks for
status, call factory_status; if they ask to run the pipeline, call pipeline_run.

Pipeline: NEW -> SCORED -> ENRICHED -> READY_FOR_OUTREACH -> CONTACTED -> BOOKED -> CLIENT.

Be concise and warm, a little Hawaii flavour is welcome. Report real numbers
from tool results."""


class LLMBrain:
    name = "llm"

    def __init__(self, api_key=None, base_url=None, model=None, opener=None):
        self.api_key = api_key if api_key is not None else config.LLM_API_KEY
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.model = model or config.LLM_MODEL
        self._opener = opener or urllib.request.urlopen
        self.local = LocalBrain()

    def think(self, message, history=None):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-10:]:
            messages.append(turn)
        messages.append({"role": "user", "content": message})

        try:
            for _ in range(5):
                payload = self._call(messages)
                choice = payload["choices"][0]["message"]
                calls = choice.get("tool_calls") or []
                if not calls:
                    return {"reply": choice.get("content") or "(no reply)",
                            "actions": [], "brain": self.name}

                messages.append(choice)
                actions = []
                for call in calls:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    if name not in REGISTRY:
                        result = {"ok": False, "error": f"unknown tool '{name}'"}
                    else:
                        result = dispatch(name, args)
                    actions.append({"tool": name, "args": args, "result": result,
                                    "ok": bool(result.get("ok"))})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(result, default=str)[:6000],
                    })
                final = self._call(messages)
                content = final["choices"][0]["message"].get("content") or "Done."
                return {"reply": content, "actions": actions, "brain": self.name}
        except Exception as exc:  # network, auth, schema — fall back, never fail
            fallback = self.local.think(message)
            fallback["brain"] = f"local (llm unavailable: {type(exc).__name__})"
            return fallback
        return self.local.think(message)

    def _call(self, messages):
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": tool_schemas(),
            "tool_choice": "auto",
            "temperature": 0.2,
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with self._opener(request, timeout=config.LLM_TIMEOUT) as response:
            return json.loads(response.read().decode())


def get_brain():
    """LLM brain when a key is present, otherwise the local brain."""
    if config.LLM_API_KEY:
        return LLMBrain()
    return LocalBrain()
