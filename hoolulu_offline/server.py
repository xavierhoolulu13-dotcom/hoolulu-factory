#!/usr/bin/env python3
"""
Hoolulu Offline — sync server + PWA host.

Zero dependencies. Python 3.8+ standard library only (http.server + sqlite3).
Nothing to pip install, so it runs the same on your laptop, a Raspberry Pi,
or a $5 VPS.

    python3 server.py --port 8080
    python3 server.py --port 8080 --token my-secret      # require a sync token
    python3 server.py --data ~/.hoolulu/sync.db

Endpoints
    GET  /api/health            health + server stats
    POST /api/sync              push local changes, pull remote changes (cursor based)
    POST /api/wipe              delete every record on the server (needs token)
    GET  /api/ollama/tags       proxy to a local Ollama daemon
    POST /api/ollama/chat       proxy to a local Ollama daemon
    POST /api/ai/openai         proxy to any OpenAI-compatible endpoint
    POST /api/ai/anthropic      proxy to the Anthropic messages API
    GET  /...                   static PWA files (installable, works offline)

Sync model
    Last-write-wins per record, resolved on `updated_at` (milliseconds), with
    a monotonically increasing server sequence number used as the pull cursor.
    Deletes are tombstones so they replicate correctly to other devices.
"""

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, "web")
DEFAULT_DATA = os.path.expanduser("~/.hoolulu/sync.db")

# Collections the server is willing to store. Anything else is rejected, so a
# buggy client cannot spray arbitrary tables into your database.
COLLECTIONS = {
    "conversations", "messages", "projects", "files", "tasks", "clients",
    "gigs", "proposals", "invoices", "time_entries", "products", "sales",
    "expenses", "queued_prompts", "notes",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    collection TEXT NOT NULL,
    id         TEXT NOT NULL,
    body       TEXT NOT NULL,
    updated_at REAL NOT NULL,
    deleted    INTEGER NOT NULL DEFAULT 0,
    device_id  TEXT NOT NULL DEFAULT '',
    server_seq INTEGER NOT NULL,
    PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS idx_records_seq ON records (server_seq);
CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""

_db_lock = threading.Lock()
_DB_PATH = DEFAULT_DATA
_TOKEN = None
_QUIET = False


# --------------------------------------------------------------------------
# database helpers
# --------------------------------------------------------------------------

def connect():
    conn = sqlite3.connect(_DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
    with _db_lock, connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO meta (k, v) VALUES ('seq', '0')")


def next_seq(conn, n=1):
    row = conn.execute("SELECT v FROM meta WHERE k='seq'").fetchone()
    cur = int(row["v"]) if row else 0
    conn.execute("UPDATE meta SET v=? WHERE k='seq'", (str(cur + n),))
    return cur + 1  # first seq handed out


def server_stats():
    with _db_lock, connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
        live = conn.execute(
            "SELECT COUNT(*) c FROM records WHERE deleted=0").fetchone()["c"]
        seq = conn.execute("SELECT v FROM meta WHERE k='seq'").fetchone()
        devices = conn.execute(
            "SELECT device_id, MAX(updated_at) last FROM records "
            "WHERE device_id != '' GROUP BY device_id").fetchall()
    return {
        "records": total,
        "live": live,
        "tombstones": total - live,
        "cursor": int(seq["v"]) if seq else 0,
        "devices": [{"id": d["device_id"], "last_seen": d["last"]} for d in devices],
    }


def apply_changes(changes, device_id):
    """Apply client changes with last-write-wins. Returns number applied."""
    applied = 0
    with _db_lock, connect() as conn:
        for ch in changes:
            coll = ch.get("collection")
            rid = ch.get("id")
            if coll not in COLLECTIONS or not isinstance(rid, str) or not rid:
                continue
            body = ch.get("body")
            if not isinstance(body, dict):
                continue
            try:
                updated_at = float(ch.get("updated_at") or 0)
            except (TypeError, ValueError):
                continue
            deleted = 1 if ch.get("deleted") else 0

            row = conn.execute(
                "SELECT updated_at FROM records WHERE collection=? AND id=?",
                (coll, rid)).fetchone()
            if row and float(row["updated_at"]) >= updated_at:
                continue  # server already has something at least as new

            seq = next_seq(conn)
            conn.execute(
                "INSERT INTO records "
                "(collection, id, body, updated_at, deleted, device_id, server_seq) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(collection,id) DO UPDATE SET "
                "body=excluded.body, updated_at=excluded.updated_at, "
                "deleted=excluded.deleted, device_id=excluded.device_id, "
                "server_seq=excluded.server_seq",
                (coll, rid, json.dumps(body, separators=(",", ":")),
                 updated_at, deleted, device_id or "", seq))
            applied += 1
        conn.commit()
    return applied


def pull_changes(cursor, limit=1000):
    with _db_lock, connect() as conn:
        rows = conn.execute(
            "SELECT collection, id, body, updated_at, deleted, device_id, server_seq "
            "FROM records WHERE server_seq > ? ORDER BY server_seq LIMIT ?",
            (int(cursor or 0), limit)).fetchall()
    out = []
    for r in rows:
        try:
            body = json.loads(r["body"])
        except ValueError:
            body = {}
        out.append({
            "collection": r["collection"],
            "id": r["id"],
            "body": body,
            "updated_at": r["updated_at"],
            "deleted": bool(r["deleted"]),
            "device_id": r["device_id"],
            "server_seq": r["server_seq"],
        })
    return out


def wipe_all():
    with _db_lock, connect() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("UPDATE meta SET v='0' WHERE k='seq'")
        conn.commit()


# --------------------------------------------------------------------------
# upstream proxies (Ollama + cloud AI)
# --------------------------------------------------------------------------

def _read_json_url(url, payload=None, headers=None, timeout=180.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw.decode("utf-8", "replace")}


def proxy_ollama(path, payload):
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    url = f"{host}/api/{path}"
    try:
        if path == "tags":
            return 200, _read_json_url(url, None, timeout=15.0)
        payload = dict(payload or {})
        payload["stream"] = False  # keep the proxy simple and non-chunked
        return 200, _read_json_url(url, payload, timeout=300.0)
    except urllib.error.URLError as exc:
        return 502, {"error": f"Ollama not reachable at {host}",
                     "detail": str(exc),
                     "hint": "Install Ollama (ollama.com), run 'ollama serve', "
                             "then pull a model: ollama pull qwen2.5-coder:1.5b"}
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def proxy_openai(payload):
    base = (payload.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    key = payload.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return 400, {"error": "Missing api_key"}
    body = {k: v for k, v in payload.items()
            if k in ("model", "messages", "temperature", "max_tokens",
                     "top_p", "stop", "response_format")}
    body["stream"] = False
    try:
        return 200, _read_json_url(f"{base}/chat/completions", body,
                                   {"Authorization": f"Bearer {key}"})
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode("utf-8", "replace")[:2000]}
    except urllib.error.URLError as exc:
        return 502, {"error": f"Upstream unreachable: {exc}"}


def proxy_anthropic(payload):
    key = payload.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return 400, {"error": "Missing api_key"}
    body = {
        "model": payload.get("model", "claude-sonnet-4-5"),
        "messages": payload.get("messages", []),
        "max_tokens": payload.get("max_tokens", 2048),
    }
    if payload.get("system"):
        body["system"] = payload["system"]
    if payload.get("temperature") is not None:
        body["temperature"] = payload["temperature"]
    try:
        return 200, _read_json_url(
            "https://api.anthropic.com/v1/messages", body,
            {"x-api-key": key,
             "anthropic-version": "2023-06-01",
             "anthropic-dangerous-direct-browser-access": "true"})
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode("utf-8", "replace")[:2000]}
    except urllib.error.URLError as exc:
        return 502, {"error": f"Upstream unreachable: {exc}"}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "HooluluOffline/1.0"
    protocol_version = "HTTP/1.1"

    # ----- plumbing -------------------------------------------------------

    def log_message(self, fmt, *args):
        if not _QUIET:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type,Authorization,X-Sync-Token")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send(self, code, obj, headers=None):
        if isinstance(obj, (dict, list)):
            raw = json.dumps(obj, separators=(",", ":")).encode()
            ctype = "application/json"
        elif isinstance(obj, bytes):
            raw, ctype = obj, "application/octet-stream"
        else:
            raw, ctype = str(obj).encode(), "text/plain; charset=utf-8"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _authorized(self):
        if not _TOKEN:
            return True
        given = self.headers.get("X-Sync-Token", "")
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            given = auth[7:]
        return hmac.compare_digest(given.strip(), _TOKEN)

    # ----- verbs ----------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/health":
            stats = server_stats()
            stats.update({"ok": True, "time": time.time(),
                          "token_required": bool(_TOKEN)})
            return self._send(200, stats)

        if path == "/api/ollama/tags":
            code, obj = proxy_ollama("tags", None)
            return self._send(code, obj)

        if path.startswith("/api/"):
            return self._send(404, {"error": "not found", "path": path})

        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self._body()

        if not self._authorized():
            return self._send(401, {"error": "bad or missing sync token"})

        if path == "/api/sync":
            return self._sync(payload)

        if path == "/api/wipe":
            if not _TOKEN:
                return self._send(403, {
                    "error": "refusing to wipe: start the server with --token "
                             "to enable destructive remote operations"})
            wipe_all()
            return self._send(200, {"ok": True, "wiped": True})

        if path == "/api/ollama/chat":
            code, obj = proxy_ollama("chat", payload)
            return self._send(code, obj)

        if path == "/api/ai/openai":
            code, obj = proxy_openai(payload)
            return self._send(code, obj)

        if path == "/api/ai/anthropic":
            code, obj = proxy_anthropic(payload)
            return self._send(code, obj)

        return self._send(404, {"error": "not found", "path": path})

    # ----- endpoints ------------------------------------------------------

    def _sync(self, payload):
        device_id = str(payload.get("device_id") or "")[:120]
        changes = payload.get("changes") or []
        if not isinstance(changes, list):
            return self._send(400, {"error": "changes must be a list"})
        if len(changes) > 5000:
            return self._send(413, {"error": "too many changes in one batch"})

        applied = apply_changes(changes, device_id)
        cursor = int(payload.get("cursor") or 0)
        outgoing = pull_changes(cursor)
        new_cursor = outgoing[-1]["server_seq"] if outgoing else cursor

        return self._send(200, {
            "ok": True,
            "applied": applied,
            "received": len(changes),
            "changes": outgoing,
            "cursor": new_cursor,
            "more": len(outgoing) >= 1000,
            "server_time": time.time(),
        })

    # ----- static ---------------------------------------------------------

    def _serve_static(self, path):
        if path in ("/", "/index.html"):
            rel = "index.html"
        else:
            rel = path.lstrip("/")

        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(os.path.normpath(WEB_DIR) + os.sep):
            return self._send(403, {"error": "forbidden"})

        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            # SPA fallback for extension-less routes (e.g. /money), 404 for assets
            if "." not in os.path.basename(path):
                full = os.path.join(WEB_DIR, "index.html")
            else:
                return self._send(404, {"error": "not found", "path": path})

        with open(full, "rb") as fh:
            raw = fh.read()
        ctype, _ = mimetypes.guess_type(full)
        if ctype is None:
            ctype = "application/octet-stream"
        if full.endswith((".html", ".js", ".json", ".webmanifest")):
            ctype += "; charset=utf-8"

        headers = {}
        # The service worker and app shell must never be served stale.
        if os.path.basename(full) in ("sw.js", "index.html"):
            headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        else:
            headers["Cache-Control"] = "public, max-age=3600"
        return self._send(200, raw, {"Content-Type": ctype, **headers})


def main():
    global _DB_PATH, _TOKEN, _QUIET

    ap = argparse.ArgumentParser(description="Hoolulu Offline sync server")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--token", default=os.environ.get("HOOLULU_SYNC_TOKEN"))
    ap.add_argument("--print-token", action="store_true",
                    help="generate a random token and print it")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    _DB_PATH = os.path.expanduser(args.data)
    _QUIET = args.quiet
    _TOKEN = args.token
    if args.print_token:
        _TOKEN = secrets.token_urlsafe(24)
    _TOKEN = _TOKEN or None

    init_db()

    bind = args.host
    if bind in ("0.0.0.0", "::") and not _TOKEN:
        print("  !  WARNING: listening on all interfaces with no --token set.")
        print("     Anyone who can reach this port can read and write your data.")
        print("     For anything beyond localhost, restart with: --token <secret>\n")

    httpd = ThreadingHTTPServer((bind, args.port), Handler)
    httpd.daemon_threads = True

    print("""
  ╔══════════════════════════════════════════════╗
  ║   HOOLULU OFFLINE — sync server              ║
  ╚══════════════════════════════════════════════╝

    App      http://{host}:{port}/
    Health   http://{host}:{port}/api/health
    Database {db}
    Token    {token}

    The app itself is fully offline. This server only
    moves your data between your devices.
""".format(host="localhost" if bind in ("0.0.0.0", "::") else bind,
           port=args.port, db=_DB_PATH,
           token=_TOKEN or "(none — open access)"))

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
