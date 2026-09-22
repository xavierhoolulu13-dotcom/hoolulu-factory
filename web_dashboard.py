#!/usr/bin/env python3

from flask import Flask, jsonify
from librarian import (
    build_workspace_snapshot,
    get_workspace_summary,
    get_today_focus,
    get_stalled,
    get_needs_outreach,
    get_needs_delivery,
)
import service_manager

app = Flask(__name__)

@app.route("/")
def dashboard():
    snapshot = build_workspace_snapshot()
    return jsonify({
        "summary": get_workspace_summary(snapshot),
        "today_focus": [i.id for i in get_today_focus(snapshot)],
        "stalled": [i.id for i in get_stalled(snapshot)],
        "needs_outreach": [i.id for i in get_needs_outreach(snapshot)],
        "needs_delivery": [i.id for i in get_needs_delivery(snapshot)],
        "services": service_manager.get_service_status()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
