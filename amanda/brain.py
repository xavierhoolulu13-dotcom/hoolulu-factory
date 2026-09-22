"""Amanda's intent routing.

Deterministic first: keywords and slots, no network, no key, so the right thing
happens the moment you open it. When a local model is reachable it is offered
the same message first and its chosen tool is validated against the registry —
anything it gets wrong falls straight through to the rules below.
"""

from __future__ import annotations

import re

from hub import config
from hub.offline import available, json_complete
from . import tools

HELP = """Amanda runs the factory. Say it plainly and she does the whole loop:

  build me a snake game and host it     research → scope → build → test → ship → watch
  spec a booking page for a surf school score an idea without building it
  status                                what is deployed, built, waiting
  maintain                              health check everything that is live
  deploy snake-game --tier production   release (asks a human in production)
  gate list / gate approve <id>         the human gate
  doctor                                why is something not working
  report                                what shipped and what it earns
  swarm                                 who is on the crew

She writes to builds/<slug>/, serves from deployed/<slug>/, and logs every step
to hoolulu-ecosystem-hub/core/event-log/loops/events.jsonl."""

RULES = [
    ("help", r"^\s*(help|\?|what can you do|menu)\b|how do (i|you) work"),
    ("doctor", r"\b(doctor|diagnos\w+|why is|what.s (broken|wrong)|health check)\b"),
    ("maintain", r"\b(maintain|maintenance|keep .*\b(alive|running|up)\b|health check|"
                 r"is everything (up|ok|alive)|monitor)\b"),
    ("gate", r"\b(approve|reject|gate|waiting on (a )?human|pending approval)\b"),
    ("swarm", r"\b(swarm|workforce|who works here|show .*\bagents?\b|list .*\bagents?\b)\b"),
    ("skill", r"\bskills?\b"),
    ("report", r"\b(report|revenue|earn\w*|money|mrr)\b"),
    ("status", r"\b(status|what.s (deployed|live|running)|list (deploy|product)s?)\b"),
    ("undeploy", r"\b(undeploy|take down|remove .*deploy|stop hosting)\b"),
    # `build` and `spec` are checked before `deploy` so that
    # "build me a snake game and host it" reads as a build, not a release.
    ("build", r"\b(build|make|create|generate|whip up|spin up)\b"),
    ("spec", r"\b(spec|scope|plan|should i|worth (it|building)|idea)\b"),
    ("deploy", r"\b(host|deploy|publish|launch|ship)\b"),
]

SLUG = re.compile(r"\b([a-z0-9][a-z0-9-]{1,38})\b")
TIER = re.compile(r"\b(production|development)\b", re.IGNORECASE)
ID = re.compile(r"\b([0-9a-f]{8})\b")


def route(message: str) -> tuple[str, dict]:
    """Return ``(intent, slots)``. Unknown text is treated as a build request."""
    text = (message or "").strip()
    lowered = text.lower()
    for intent, pattern in RULES:
        if re.search(pattern, lowered):
            return intent, _slots(text, intent)
    return "build", _slots(text, "build")


def _slots(text: str, intent: str) -> dict:
    slots: dict = {"message": text}
    tier = TIER.search(text)
    if tier:
        slots["tier"] = tier.group(1).lower()
    identifier = ID.search(text)
    if identifier:
        slots["id"] = identifier.group(1)
    if intent in ("deploy", "undeploy"):
        words = SLUG.findall(text.lower())
        stop = {"deploy", "undeploy", "the", "it", "that", "my", "build", "host",
                "publish", "launch", "ship", "tier", "production", "development"}
        candidates = [w for w in words if w not in stop]
        if candidates:
            slots["slug"] = candidates[-1]
    return slots


def handle(message: str, *, use_model: bool = True) -> dict:
    """Answer one message. Always returns ``{reply, actions, intent, brain, data}``."""
    config.ensure_dirs()
    text = (message or "").strip()
    if not text:
        return {"reply": HELP, "actions": [], "intent": "help",
                "brain": "deterministic", "data": {}}

    model_reply = _try_model(text) if use_model else None
    if model_reply:
        return model_reply

    intent, slots = route(text)
    tool_name = {
        "help": None, "doctor": "doctor", "maintain": "maintain",
        "gate": "gate_list", "swarm": "swarm", "skill": "skill_list",
        "report": "report", "status": "status", "undeploy": "undeploy",
        "deploy": "deploy", "spec": "spec", "build": "build",
    }[intent]

    if tool_name is None:
        return {"reply": HELP, "actions": [], "intent": intent,
                "brain": "deterministic", "data": {}}

    if intent == "gate" and _looks_like_approval(text):
        tool_name = "gate_reject" if re.search(r"\breject|deny|no\b", text.lower()) \
            else "gate_approve"

    outcome = tools.dispatch(tool_name, slots)
    return {
        "reply": outcome.get("text", ""),
        "actions": [{"tool": tool_name, "args": slots, "ok": outcome.get("ok")}],
        "intent": intent,
        "brain": "deterministic",
        "data": outcome.get("data", {}),
    }


# --------------------------------------------------------------------------

def _looks_like_approval(text: str) -> bool:
    return bool(ID.search(text)) or bool(
        re.search(r"\b(approve|reject|deny)\b", text, re.IGNORECASE))


def _try_model(text: str) -> dict | None:
    """Offer the message to the local model first, if one is reachable."""
    if not available():
        return None
    system = (
        "You route an operator's request to one tool in an offline AI factory. "
        "Reply with one JSON object: {\"tool\": <name>, \"args\": {<...>}, "
        "\"say\": <one short sentence for the operator>}. "
        "Use the operator's own words for args.message."
    )
    listing = "\n".join(
        f"- {name}: {spec['description']} params: {spec['params'] or 'none'}"
        for name, spec in tools.TOOLS.items()
    )
    choice = json_complete(system, f"Tools:\n{listing}\n\nOperator: {text}")
    if not choice or not isinstance(choice, dict):
        return None
    name = choice.get("tool")
    if name not in tools.TOOLS:
        return None
    args = choice.get("args") if isinstance(choice.get("args"), dict) else {}
    # the operator's own words are the message, whatever the model thought it read
    args["message"] = text
    outcome = tools.dispatch(name, args)
    say = str(choice.get("say") or "").strip()
    reply = f"{say}\n\n{outcome.get('text', '')}".strip() if say \
        else outcome.get("text", "")
    return {
        "reply": reply,
        "actions": [{"tool": name, "args": args, "ok": outcome.get("ok")}],
        "intent": name,
        "brain": "offline-model",
        "data": outcome.get("data", {}),
    }
