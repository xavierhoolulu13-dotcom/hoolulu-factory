"""Flask app that puts the Hoolulu Agent behind a clickable UI.

Run it with ``./start.sh`` or ``python -m agent.server``.
"""

import os
import traceback

from flask import Flask, jsonify, render_template, request

from . import __version__, config, factory
from .brain import HELP_TEXT, get_brain
from .tools import audit, dispatch, public_specs

app = Flask(
    __name__,
    template_folder=config.TEMPLATE_DIR,
    static_folder=config.STATIC_DIR,
)
app.config["JSON_SORT_KEYS"] = False
app.json.sort_keys = False

_state = {"brain": get_brain()}


def _snapshot():
    """Everything the UI needs to render its side panel."""
    try:
        status = factory.factory_status()
    except Exception as exc:  # database missing/unreadable must not 500 the UI
        status = {"error": str(exc), "by_status": {}, "totals": {},
                  "top_leads": [], "open_tasks": [], "recent_runs": [],
                  "pipeline": factory.PIPELINE, "database": config.DB_PATH}
    return {
        "status": status,
        "pipeline": factory.PIPELINE,
        "stages": factory.STAGES,
        "tools": public_specs(),
        "brain": _state["brain"].name,
        "llm_configured": bool(config.LLM_API_KEY),
        "version": __version__,
        "repo_root": config.REPO_ROOT,
    }


@app.get("/")
def index():
    return render_template("index.html", version=__version__)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "version": __version__,
                    "brain": _state["brain"].name,
                    "database": config.DB_PATH,
                    "database_online": os.path.exists(config.DB_PATH)})


@app.get("/api/state")
def state():
    return jsonify(_snapshot())


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"reply": HELP_TEXT, "actions": [], "state": _snapshot()})
    try:
        result = _state["brain"].think(message)
    except Exception as exc:
        audit("chat", {"message": message[:80]}, False, traceback.format_exc()[-300:])
        result = {"reply": f"⚠️ I hit an error: `{type(exc).__name__}: {exc}`",
                  "actions": [], "brain": _state["brain"].name}
    return jsonify({**result, "state": _snapshot()})


@app.post("/api/tool")
def run_tool():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("tool") or "").strip()
    args = payload.get("args") or {}
    if not isinstance(args, dict):
        return jsonify({"ok": False, "error": "args must be an object"}), 400
    result = dispatch(name, args)
    return jsonify({"tool": name, "result": result, "state": _snapshot()})


@app.get("/api/logs")
def logs():
    lines = min(int(request.args.get("lines", 40)), 400)
    system, agent_log = factory.read_log(lines), []
    if os.path.exists(config.AUDIT_LOG):
        with open(config.AUDIT_LOG, "r", errors="replace") as handle:
            agent_log = handle.read().splitlines()[-lines:]
    return jsonify({"system": system, "agent": agent_log})


def main():
    factory.init_db()
    print(f"Hoolulu Agent v{__version__}")
    print(f"  brain    : {_state['brain'].name}")
    print(f"  database : {config.DB_PATH}")
    print(f"  repo     : {config.REPO_ROOT}")
    print(f"  listening: http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
