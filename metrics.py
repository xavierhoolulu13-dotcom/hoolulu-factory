import sqlite3
import os

ROOT = os.path.expanduser("~/hoolulu-factory")
DB = os.path.join(ROOT, "data", "hoolulu.db")


def table_count(cursor, table):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def get_counts():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    results = {}

    # Lead pipeline
    for status in [
        "NEW",
        "SCORED",
        "NURTURE",
        "BOOKED",
        "CLIENT"
    ]:
        c.execute(
            "SELECT COUNT(*) FROM leads WHERE status=?",
            (status,)
        )
        results[status] = c.fetchone()[0]

    # Sales tables
    results["OPPORTUNITIES"] = table_count(c, "opportunities")
    results["PROPOSALS"] = table_count(c, "proposals")

    conn.close()

    return results
