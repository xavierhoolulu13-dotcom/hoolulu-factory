"""The Hoolulu Factory engine.

A self-contained, dependency-free implementation of the lead pipeline that the
legacy scripts describe but never fully wire together:

    NEW -> SCORED -> ENRICHED -> READY_FOR_OUTREACH -> CONTACTED
        -> REPLIED -> BOOKED -> CLIENT

Every stage is a pure function over lead dictionaries, so the same logic is
reused by the CLI, the web agent and the tests.
"""

import os
import re
import sqlite3
from datetime import datetime

from . import config

# --------------------------------------------------------------------------
# Domain knowledge
# --------------------------------------------------------------------------

PIPELINE = [
    "NEW",
    "SCORED",
    "NURTURE",
    "ENRICHED",
    "READY_FOR_OUTREACH",
    "CONTACTED",
    "REPLIED",
    "BOOKED",
    "CLIENT",
    "ARCHIVED",
]

STAGES = ["score", "enrich", "outreach", "closer", "delivery", "report"]

HAWAII_CITIES = [
    "honolulu", "hilo", "kailua", "kaneohe", "waipahu", "pearl city",
    "mililani", "ewa beach", "kapolei", "waikele", "aiea", "pearl harbor",
    "kahului", "kihei", "lahaina", "wailuku", "lihue", "kapaa", "kona",
    "kailua-kona", "waimea", "hawi", "paia", "makawao", "haiku", "wailua",
    "hawaii", "oahu", "maui", "kauai", "big island", "molokai", "lanai",
]

CATEGORY_SIGNALS = {
    "restaurant": ["restaurant", "cafe", "coffee", "bakery", "food truck", "bar", "grill", "sushi", "poke", "diner", "eatery"],
    "salon & spa": ["salon", "barber", "spa", "nails", "hair", "lash", "massage", "tattoo"],
    "home services": ["plumber", "plumbing", "electric", "hvac", "roofing", "landscap", "lawn", "pest", "cleaning", "handyman", "contractor", "remodel", "pool"],
    "health & wellness": ["dentist", "dental", "chiro", "clinic", "medical", "therapy", "gym", "fitness", "yoga", "wellness", "vet", "pharmacy", "optometr"],
    "professional services": ["law", "attorney", "account", "cpa", "insurance", "realtor", "real estate", "property manage", "consult", "architect"],
    "auto": ["auto", "car ", "mechanic", "tire", "detailing", "motor", "towing"],
    "retail": ["boutique", "shop", "store", "retail", "surf shop", "gift", "jewel", "market"],
    "hospitality": ["hotel", "resort", "vacation rental", "airbnb", "tour", "hostel", "bed and breakfast"],
}

INTENT_KEYWORDS = [
    "no website", "outdated", "bad reviews", "google", "seo", "marketing",
    "leads", "booking", "instagram", "yelp", "reviews", "ads", "facebook",
    "social media", "growth", "rebrand", "new location", "expanding",
    "referrals", "word of mouth", "not online", "hidden", "competitor",
]

POSITIVE_REPLIES = ["yes", "interested", "sure", "call me", "booked", "let's talk", "send info", "ok"]
NEGATIVE_REPLIES = ["no", "not interested", "stop", "unsubscribe", "remove me"]

DEFAULT_OFFER = "$1,500 setup + $99/month"


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

SCHEMA = {
    "leads": """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY,
            business TEXT,
            industry TEXT,
            category TEXT,
            city TEXT,
            location TEXT,
            website TEXT,
            phone TEXT,
            email TEXT,
            score REAL DEFAULT 0,
            status TEXT DEFAULT 'NEW',
            source TEXT,
            notes TEXT,
            outreach_status TEXT,
            outreach_channel TEXT,
            message TEXT,
            sent_at TEXT,
            reply_status TEXT,
            enriched_at TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            agent TEXT,
            task TEXT,
            status TEXT DEFAULT 'OPEN',
            created_at TEXT
        )
    """,
    "opportunities": """
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY,
            business TEXT,
            problem TEXT,
            solution TEXT,
            offer TEXT,
            status TEXT,
            created_at TEXT
        )
    """,
    "proposals": """
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY,
            business TEXT,
            headline TEXT,
            investment TEXT,
            status TEXT,
            created_at TEXT
        )
    """,
    "clients": """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            business TEXT,
            service TEXT,
            revenue TEXT,
            status TEXT,
            created_at TEXT
        )
    """,
    "delivery_tasks": """
        CREATE TABLE IF NOT EXISTS delivery_tasks (
            id INTEGER PRIMARY KEY,
            business TEXT,
            task TEXT,
            status TEXT DEFAULT 'OPEN',
            created_at TEXT
        )
    """,
    "outreach_queue": """
        CREATE TABLE IF NOT EXISTS outreach_queue (
            id INTEGER PRIMARY KEY,
            business TEXT,
            problem TEXT,
            offer TEXT,
            message TEXT,
            status TEXT DEFAULT 'READY',
            created TEXT
        )
    """,
    "agent_runs": """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY,
            stage TEXT,
            processed INTEGER DEFAULT 0,
            detail TEXT,
            created_at TEXT
        )
    """,
}


def connect():
    """Open a connection with sane concurrency settings for a web server."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create every table the factory (and the legacy scripts) expects."""
    created = config.ensure_dirs()
    conn = connect()
    try:
        for ddl in SCHEMA.values():
            conn.execute(ddl)
        conn.commit()
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
    finally:
        conn.close()
    return {"tables": tables, "folders_created": created, "db": config.DB_PATH}


def table_count(conn, table):
    try:
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    except sqlite3.OperationalError:
        return 0


# --------------------------------------------------------------------------
# Lead CRUD
# --------------------------------------------------------------------------

def add_lead(business, industry="", city="", location="", website="",
             phone="", email="", source="agent", notes="", status="NEW"):
    """Insert a lead, returning the full row."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO leads (business, industry, city, location, website, phone,
                               email, source, notes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (business, industry, city, location or city, website, phone,
             email, source, notes, status, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM leads WHERE id=?", (cur.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


def get_lead(identifier):
    """Fetch one lead by id or by (case-insensitive) business name."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ? OR lower(business) = lower(?) LIMIT 1",
            (identifier if str(identifier).isdigit() else -1, str(identifier)),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_leads(status=None, limit=50):
    query = "SELECT * FROM leads"
    params = []
    if status and status.upper() != "ALL":
        query += " WHERE upper(status) = ?"
        params.append(status.upper())
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    conn = connect()
    try:
        rows = [dict(r) for r in conn.execute(query, params)]
    finally:
        conn.close()
    return rows


def set_lead_status(business, status, reply_status=None):
    """Manual override used by the closer stage and the UI buttons."""
    if status.upper() not in PIPELINE:
        return {"ok": False, "error": f"'{status}' is not a valid state"}
    fields = {"status": status.upper(), "updated_at": datetime.now().isoformat(timespec="seconds")}
    if reply_status:
        fields["reply_status"] = reply_status.upper()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn = connect()
    try:
        cur = conn.execute(
            f"UPDATE leads SET {sets} WHERE lower(business) = lower(?)",
            (*fields.values(), business),
        )
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    return {"ok": changed > 0, "business": business, "status": status.upper(), "changed": changed}


def import_leads_csv(text, source="csv"):
    """Import leads from CSV text. First row must be a header."""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {"imported": 0, "error": "no header row found"}

    known = {"business", "industry", "city", "location", "website",
             "phone", "email", "source", "notes", "status"}
    imported, skipped = 0, []
    for row in reader:
        clean = {
            (k or "").strip().lower(): (v or "").strip()
            for k, v in row.items()
        }
        name = clean.get("business") or clean.get("name") or clean.get("company")
        if not name:
            skipped.append(clean)
            continue
        add_lead(
            business=name,
            industry=clean.get("industry", ""),
            city=clean.get("city", ""),
            location=clean.get("location", ""),
            website=clean.get("website", ""),
            phone=clean.get("phone", ""),
            email=clean.get("email", ""),
            source=clean.get("source", source),
            notes=clean.get("notes", ""),
            status=(clean.get("status") or "NEW").upper(),
        )
        imported += 1
    return {"imported": imported, "skipped": len(skipped),
            "columns_seen": list(reader.fieldnames), "unknown_columns":
            sorted(set(reader.fieldnames) - known)}


# --------------------------------------------------------------------------
# Stage logic (pure functions)
# --------------------------------------------------------------------------

def _text(*values):
    return " ".join(str(v) for v in values if v).lower()


def infer_category(lead):
    blob = _text(lead.get("industry"), lead.get("category"), lead.get("notes"),
                 lead.get("business"))
    for category, signals in CATEGORY_SIGNALS.items():
        if any(signal in blob for signal in signals):
            return category
    return "general"


def infer_city(lead):
    blob = _text(lead.get("city"), lead.get("location"), lead.get("notes"))
    if not blob:
        return ""
    for city in HAWAII_CITIES:
        if city in blob:
            return city.title()
    raw = (lead.get("city") or lead.get("location") or "").strip()
    return raw.title() if raw else ""


def find_pain_point(lead):
    """Derive the single most useful talking point for this lead."""
    if not (lead.get("website") or "").strip():
        return "there is no website for customers to find, which usually means lost calls"
    if not (lead.get("email") or "").strip():
        return "there is no clear way for customers to get a fast answer online"
    notes = _text(lead.get("notes"))
    for keyword in ("reviews", "google", "seo", "instagram", "yelp", "ads"):
        if keyword in notes:
            return f"your {keyword} presence could be working much harder for you"
    return "customers are finding competitors before they find you"


def score_lead(lead):
    """Deterministic, explainable lead score (0-100) plus a reason trail."""
    reasons = []
    score = 35
    reasons.append("base score 35")

    if (lead.get("website") or "").strip():
        score += 10
        reasons.append("+10 has website")
    if (lead.get("phone") or "").strip():
        score += 10
        reasons.append("+10 has phone")
    if (lead.get("email") or "").strip():
        score += 10
        reasons.append("+10 has email")

    if infer_city(lead) and any(c in _text(lead.get("city"), lead.get("location"))
                                for c in HAWAII_CITIES):
        score += 15
        reasons.append("+15 Hawaii location")

    notes = _text(lead.get("notes"), lead.get("industry"))
    hits = [k for k in INTENT_KEYWORDS if k in notes]
    if hits:
        score += min(20, 8 * len(hits))
        reasons.append(f"+{min(20, 8 * len(hits))} buying signals: {', '.join(hits[:3])}")

    score = max(0, min(100, score))
    return {"score": score, "reasons": reasons,
            "status": "SCORED" if score >= 60 else "NURTURE"}


def enrich_lead(lead):
    """Fill in category/city/notes so outreach can be personalized."""
    category = infer_category(lead)
    city = infer_city(lead)
    score_info = score_lead(lead)
    pain = find_pain_point(lead)

    notes = lead.get("notes") or ""
    tag = f"[{category}] {pain}"
    if tag not in notes:
        notes = f"{notes} {tag}".strip()

    return {
        "category": category,
        "city": city,
        "notes": notes,
        "enriched_at": datetime.now().isoformat(timespec="seconds"),
        "score": score_info["score"],
        # Only leads we can actually reach move forward.
        "status": "READY_FOR_OUTREACH" if (lead.get("email") or lead.get("phone"))
        else "ENRICHED",
    }


def build_outreach(lead, offer=DEFAULT_OFFER):
    """Write the outreach message for one lead."""
    business = lead.get("business") or "there"
    city = lead.get("city") or infer_city(lead) or "your area"
    category = lead.get("category") or infer_category(lead)
    pain = find_pain_point(lead)

    message = (
        f"Aloha {business},\n\n"
        f"I was looking at {category} businesses in {city} and noticed {pain}.\n\n"
        f"We build AI Visibility Installs for Hawaii businesses - so when someone "
        f"asks ChatGPT, Google or Siri for the best {category} near them, your "
        f"business is the one that comes up.\n\n"
        f"Would you be open to a 15 minute call this week to see what that would "
        f"look like for {business}?\n\n"
        f"Mahalo,\nHoolulu Factory"
    )
    return {"message": message, "offer": offer, "problem": pain}


def classify_reply(reply):
    """Turn a free-text reply into a pipeline signal."""
    blob = _text(reply)
    if any(word in blob for word in NEGATIVE_REPLIES):
        return "NOT_INTERESTED"
    if any(word in blob for word in POSITIVE_REPLIES):
        return "CALL_BOOKED" if any(w in blob for w in ("call", "book", "meet", "zoom")) else "INTERESTED"
    return "NEEDS_FOLLOW_UP"


# --------------------------------------------------------------------------
# Stage runners
# --------------------------------------------------------------------------

def _log_run(stage, processed, detail):
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO agent_runs (stage, processed, detail, created_at) VALUES (?,?,?,?)",
            (stage, processed, detail[:2000], datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def _touch(conn, lead_id, fields):
    fields = dict(fields)
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", (*fields.values(), lead_id))


def _fetch(conn, statuses):
    marks = ",".join("?" * len(statuses))
    rows = conn.execute(
        f"SELECT * FROM leads WHERE upper(status) IN ({marks}) ORDER BY id",
        [s.upper() for s in statuses],
    ).fetchall()
    return [dict(r) for r in rows]


def run_score():
    conn = connect()
    results = []
    try:
        for lead in _fetch(conn, ["NEW"]):
            info = score_lead(lead)
            _touch(conn, lead["id"], {
                "score": info["score"],
                "status": info["status"],
                "notes": (f"{lead.get('notes') or ''} | score {info['score']}: "
                          f"{'; '.join(info['reasons'])}").strip(" |"),
            })
            results.append({"business": lead["business"], "score": info["score"],
                            "status": info["status"]})
        conn.commit()
    finally:
        conn.close()
    _log_run("score", len(results), "; ".join(r["business"] for r in results))
    return {"agent": "Scoring", "processed": len(results), "results": results}


def run_enrich():
    conn = connect()
    results = []
    try:
        for lead in _fetch(conn, ["SCORED", "NURTURE"]):
            update = enrich_lead(lead)
            _touch(conn, lead["id"], update)
            results.append({"business": lead["business"],
                            "category": update["category"],
                            "city": update["city"],
                            "status": update["status"]})
        conn.commit()
    finally:
        conn.close()
    _log_run("enrich", len(results), "; ".join(r["business"] for r in results))
    return {"agent": "Enrichment Echo", "processed": len(results), "results": results}


def run_outreach(send=False):
    """Draft outreach for every reachable lead; optionally mark it sent."""
    conn = connect()
    results = []
    try:
        for lead in _fetch(conn, ["ENRICHED", "READY_FOR_OUTREACH"]):
            draft = build_outreach(lead)
            fields = {
                "message": draft["message"],
                "outreach_status": "SENT" if send else "READY",
                "notes": (f"{lead.get('notes') or ''} | offer {draft['offer']}").strip(" |"),
            }
            if send:
                fields.update({
                    "sent_at": datetime.now().isoformat(timespec="seconds"),
                    "outreach_channel": "MANUAL",
                    "reply_status": "WAITING_REPLY",
                    "status": "CONTACTED",
                })
            _touch(conn, lead["id"], fields)
            conn.execute(
                """INSERT INTO outreach_queue (business, problem, offer, message, status, created)
                   VALUES (?,?,?,?,?,?)""",
                (lead["business"], draft["problem"], draft["offer"],
                 draft["message"], "SENT" if send else "READY",
                 datetime.now().isoformat(timespec="seconds")),
            )
            results.append({"business": lead["business"],
                            "outreach_status": fields["outreach_status"],
                            "message": draft["message"]})
        conn.commit()
    finally:
        conn.close()
    _log_run("outreach", len(results), "; ".join(r["business"] for r in results))
    return {"agent": "Outreach", "processed": len(results), "sent": bool(send),
            "results": results}


def run_closer():
    """Handle replies, book calls, and queue tasks for Cass."""
    conn = connect()
    results = []
    try:
        for lead in _fetch(conn, ["CONTACTED", "REPLIED"]):
            reply = lead.get("reply_status") or ""
            signal = classify_reply(reply) if reply.upper() not in (
                "WAITING_REPLY", "WAITING") else "WAITING_REPLY"

            fields = {"reply_status": signal}
            if signal == "CALL_BOOKED":
                fields["status"] = "BOOKED"
            elif signal == "INTERESTED":
                fields["status"] = "REPLIED"
            elif signal == "NOT_INTERESTED":
                fields["status"] = "ARCHIVED"
            else:
                fields["status"] = lead["status"]
            _touch(conn, lead["id"], fields)

            if fields["status"] == "BOOKED":
                conn.execute(
                    "INSERT INTO tasks (agent, task, status, created_at) VALUES (?,?,?,?)",
                    ("Cass", f"Prepare closing call for {lead['business']}", "OPEN",
                     datetime.now().isoformat(timespec="seconds")),
                )
            results.append({"business": lead["business"], "reply": signal,
                            "status": fields["status"]})
        conn.commit()
    finally:
        conn.close()
    _log_run("closer", len(results), "; ".join(r["business"] for r in results))
    return {"agent": "Closer Cass", "processed": len(results), "results": results}


def run_delivery():
    """Turn booked calls into clients, proposals and delivery tasks."""
    conn = connect()
    results = []
    try:
        for lead in _fetch(conn, ["BOOKED"]):
            pain = find_pain_point(lead)
            now = datetime.now().isoformat(timespec="seconds")

            conn.execute(
                """INSERT INTO opportunities (business, problem, solution, offer, status, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (lead["business"], pain, "AI Visibility Install",
                 DEFAULT_OFFER, "WON", now),
            )
            conn.execute(
                """INSERT INTO proposals (business, headline, investment, status, created_at)
                   VALUES (?,?,?,?,?)""",
                (lead["business"], f"AI Visibility Growth Plan for {lead['business']}",
                 DEFAULT_OFFER, "ACCEPTED", now),
            )
            conn.execute(
                """INSERT INTO clients (business, service, revenue, status, created_at)
                   VALUES (?,?,?,?,?)""",
                (lead["business"], "AI Visibility Install", DEFAULT_OFFER, "ACTIVE", now),
            )
            for task in ("Kickoff call", "Audit current online presence",
                         "Install AI Visibility setup", "30 day review"):
                conn.execute(
                    """INSERT INTO delivery_tasks (business, task, status, created_at)
                       VALUES (?,?,?,?)""",
                    (lead["business"], task, "OPEN", now),
                )
            _touch(conn, lead["id"], {"status": "CLIENT"})
            results.append({"business": lead["business"], "status": "CLIENT"})
        conn.commit()
    finally:
        conn.close()
    _log_run("delivery", len(results), "; ".join(r["business"] for r in results))
    return {"agent": "Delivery", "processed": len(results), "results": results}


def run_stage(stage):
    stage = (stage or "").lower().strip()
    handlers = {
        "score": run_score,
        "enrich": run_enrich,
        "outreach": run_outreach,
        "closer": run_closer,
        "delivery": run_delivery,
    }
    if stage in handlers:
        return handlers[stage]()
    if stage in ("all", "pipeline", "factory", "run"):
        return run_pipeline()
    if stage == "report":
        return factory_report()
    return {"agent": "Orchestrator", "processed": 0,
            "error": f"unknown stage '{stage}'", "valid": STAGES}


def run_pipeline(send=False):
    """Run every stage in order and return one combined result."""
    stages = []
    for stage in ("score", "enrich", "outreach", "closer", "delivery"):
        if stage == "outreach":
            stages.append(run_outreach(send=send))
        else:
            stages.append(run_stage(stage))
    total = sum(s.get("processed", 0) for s in stages)
    _log_run("pipeline", total, "full pipeline run")
    return {"agent": "Orchestrator", "processed": total, "stages": stages,
            "sent": bool(send)}


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def factory_status():
    """Live snapshot of the factory: counts, health, and last runs."""
    init = {"tables": [], "folders_created": []}
    conn = connect()
    try:
        by_status = {}
        for row in conn.execute(
            "SELECT upper(status) AS s, COUNT(*) AS n FROM leads GROUP BY upper(status)"
        ):
            by_status[row["s"] or "UNSET"] = row["n"]

        totals = {table: table_count(conn, table) for table in SCHEMA}
        top = [dict(r) for r in conn.execute(
            """SELECT id, business, category, city, score, status, reply_status
               FROM leads ORDER BY score DESC, id DESC LIMIT 10"""
        )]
        open_tasks = [dict(r) for r in conn.execute(
            "SELECT id, agent, task, status FROM tasks WHERE status='OPEN' ORDER BY id DESC LIMIT 10"
        )]
        runs = [dict(r) for r in conn.execute(
            "SELECT stage, processed, created_at FROM agent_runs ORDER BY id DESC LIMIT 10"
        )]
    finally:
        conn.close()

    return {
        "database": config.DB_PATH,
        "database_online": os.path.exists(config.DB_PATH),
        "by_status": by_status,
        "totals": totals,
        "top_leads": top,
        "open_tasks": open_tasks,
        "recent_runs": runs,
        "pipeline": PIPELINE,
        "initialized": init["tables"] or None,
    }


def factory_report():
    """Human-readable markdown report of the whole factory."""
    status = factory_status()
    total_leads = status["totals"].get("leads", 0)
    by = status["by_status"]
    clients = status["totals"].get("clients", 0)
    booked = by.get("BOOKED", 0)

    lines = [
        "# Hoolulu Factory Report",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Pipeline",
        f"| Stage | Count |",
        f"| --- | --- |",
    ]
    for stage in PIPELINE:
        lines.append(f"| {stage} | {by.get(stage, 0)} |")

    lines += [
        "",
        "## Numbers",
        f"- Leads in system: **{total_leads}**",
        f"- Calls booked: **{booked}**",
        f"- Active clients: **{clients}**",
        f"- Open tasks: **{len(status['open_tasks'])}**",
        f"- Proposals sent: **{status['totals'].get('proposals', 0)}**",
        "",
        "## Top scored leads",
    ]
    if status["top_leads"]:
        for lead in status["top_leads"]:
            lines.append(
                f"- **{lead['business']}** — {lead['score']:.0f} pts — "
                f"{lead['category'] or 'uncategorized'} — {lead['city'] or 'no city'} — {lead['status']}"
            )
    else:
        lines.append("- No leads yet. Add one with the **Add lead** button.")

    if status["open_tasks"]:
        lines += ["", "## Open tasks"]
        lines += [f"- {t['agent']}: {t['task']}" for t in status["open_tasks"]]

    conversion = (clients / total_leads * 100) if total_leads else 0
    lines += [
        "",
        "## Read on it",
        f"- Lead to client conversion: **{conversion:.1f}%**",
        f"- Database: `{config.DB_PATH}`",
        "",
        "Aloha — the factory is running. 🤙",
    ]
    report = "\n".join(lines)
    _log_run("report", total_leads, "report generated")
    return {"agent": "Reporting", "processed": total_leads, "report": report,
            "conversion_pct": round(conversion, 1)}


def reset_demo(confirm=False):
    """Wipe the pipeline data (never the schema) for a clean demo."""
    if not confirm:
        return {"ok": False, "error": "pass confirm=True to wipe pipeline data"}
    conn = connect()
    try:
        for table in ("leads", "tasks", "opportunities", "proposals",
                      "clients", "delivery_tasks", "outreach_queue", "agent_runs"):
            conn.execute(f"DELETE FROM {table}")
        # sqlite_sequence only exists if some table used AUTOINCREMENT — its
        # absence must not roll back the deletes above.
        try:
            conn.execute("DELETE FROM sqlite_sequence")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True, "message": "Pipeline data cleared, schema kept."}


def seed_demo(count=6):
    """Insert a realistic Hawaii demo pipeline."""
    demo = [
        ("Kailua Poke Shack", "restaurant", "Kailua", "", "808-555-0142", "",
         "no website, great google reviews, relies on word of mouth"),
        ("Aloha Surf & Skate", "retail", "Honolulu", "https://alohasurf.example",
         "808-555-0177", "hello@alohasurf.example", "outdated website, strong instagram"),
        ("Pearl City Dental", "health", "Pearl City", "", "808-555-0110", "",
         "bad reviews on google, wants more leads"),
        ("Maui Massage & Spa", "spa", "Kihei", "https://mauimassage.example",
         "", "", "booking through instagram only, no seo"),
        ("Hilo Plumbing Co", "home services", "Hilo", "", "808-555-0198",
         "office@hiloplumb.example", "expanding to Kona, needs marketing"),
        ("Waikiki Yoga Studio", "fitness", "Honolulu", "", "", "namaste@waikikiyoga.example",
         "new location, no online presence, competitor ads everywhere"),
    ]
    created = []
    for row in demo[:count]:
        business, industry, city, website, phone, email, notes = row
        created.append(add_lead(business=business, industry=industry, city=city,
                                website=website, phone=phone, email=email,
                                notes=notes, source="demo"))
    return {"created": len(created), "leads": [c["business"] for c in created]}


# --------------------------------------------------------------------------
# Filesystem log (shared with the legacy scripts)
# --------------------------------------------------------------------------

def log(message):
    os.makedirs(config.LOG_DIR, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} | {message}\n"
    with open(config.SYSTEM_LOG, "a") as handle:
        handle.write(line)
    return line.strip()


def read_log(lines=40):
    if not os.path.exists(config.SYSTEM_LOG):
        return []
    with open(config.SYSTEM_LOG, "r", errors="replace") as handle:
        return handle.read().splitlines()[-int(lines):]
