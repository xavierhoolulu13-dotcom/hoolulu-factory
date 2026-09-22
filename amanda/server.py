"""Amanda's web interface: the chat, the API, and the products she hosts.

    python -m amanda serve

Serves three things on one port:
  /                the operator console
  /api/...         the same tools the CLI calls
  /p/<slug>/       every product the factory has deployed
"""

from __future__ import annotations


from flask import Flask, jsonify, render_template, request, send_from_directory

from hub import config
from . import brain, tools

app = Flask(__name__, static_folder="static", template_folder="templates")


# ------------------------------- pages ------------------------------------

@app.get("/")
def index():
    return render_template(
        "index.html",
        version=__import__("amanda").__version__,
        public_url=config.PUBLIC_URL,
    )


@app.get("/p/")
def product_index():
    """A plain list of everything deployed — handy to share."""
    from hub.delivery import list_deployments

    records = list_deployments()
    rows = "\n".join(
        f"<li><a href='{record.get('url')}'>{record['slug']}</a> "
        f"— {record.get('status', '?')} · {record.get('tier', '?')}</li>"
        for record in records
    ) or "<li>nothing deployed yet</li>"
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Deployed products</title>"
        "<h1>Deployed products</h1><ul>" + rows + "</ul>"
        "<p><a href='/'>back to the console</a></p>"
    )


@app.get("/p/<slug>/")
@app.get("/p/<slug>/<path:filename>")
def product(slug: str, filename: str = "index.html"):
    """Serve a deployed build. Static files only, no traversal."""
    root = (config.DEPLOY_ROOT / slug).resolve()
    if config.DEPLOY_ROOT.resolve() not in root.parents:
        return "not found", 404
    if not root.is_dir():
        return f"nothing deployed as '{slug}'", 404
    return send_from_directory(root, filename)


# ------------------------------- api --------------------------------------

@app.get("/api/health")
def health():
    from hub.offline import status_line

    return jsonify({"ok": True, "brain": status_line(), "tier": config.TIER,
                    "public_url": config.PUBLIC_URL})


@app.get("/api/state")
def state():
    from hub.approvals import pending
    from hub.delivery import list_deployments
    from hub.offline import health as model_health, runtime
    from hub.skills import list_skills

    config.ensure_dirs()
    builds = sorted(p.name for p in config.BUILD_ROOT.glob("*") if p.is_dir()) \
        if config.BUILD_ROOT.exists() else []
    status = model_health()
    return jsonify({
        "brain": ("offline-model" if status["ok"] else "deterministic"),
        "brain_detail": status,
        "tier": config.TIER,
        "public_url": config.PUBLIC_URL,
        "deployments": list_deployments(),
        "builds": builds,
        "approvals": pending(),
        "skills": list_skills(),
        "runtime": runtime.status(),
    })


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    result = brain.handle(message, use_model=bool(payload.get("use_model", True)))
    return jsonify(result)


@app.post("/api/tool")
def run_tool():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("tool", "")).strip()
    args = payload.get("args") or {}
    if not isinstance(args, dict):
        return jsonify({"ok": False, "text": "args must be an object"}), 400
    outcome = tools.dispatch(name, args)
    return jsonify({"tool": name, **outcome})


@app.get("/api/tools")
def list_tools():
    return jsonify(tools.public_specs())


@app.get("/api/events")
def events():
    from hub.ops import tail_events

    limit = int(request.args.get("limit", 30))
    return jsonify(tail_events(limit=limit))


@app.get("/api/product/<slug>")
def product_spec(slug: str):
    """The spec behind a build, as JSON."""
    import json

    path = config.BUILD_ROOT / slug / "product.json"
    if not path.is_file():
        return jsonify({"ok": False, "error": f"no build '{slug}'"}), 404
    return jsonify(json.loads(path.read_text()))


# ------------------------------- main -------------------------------------

def main() -> None:
    config.ensure_dirs()
    print("Amanda — Hoolulu Factory")
    print(f"  console : {config.PUBLIC_URL}/")
    print(f"  products: {config.PUBLIC_URL}/p/")
    print(f"  database: {config.DEPLOYMENTS_DB}")
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
