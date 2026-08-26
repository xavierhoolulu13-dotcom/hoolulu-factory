import sqlite3
import os

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def setup():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY,
        business TEXT,
        industry TEXT,
        location TEXT,
        website TEXT,
        phone TEXT,
        email TEXT,
        score REAL,
        status TEXT,
        source TEXT,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY,
        agent TEXT,
        task TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_new_leads():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT *
        FROM leads
        WHERE status = 'NEW'
    """)

    leads = [dict(row) for row in c.fetchall()]

    conn.close()
    return leads


def get_scored_leads():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT *
        FROM leads
        WHERE status = 'SCORED'
    """)

    leads = [dict(row) for row in c.fetchall()]

    conn.close()
    return leads


def update_lead_score(lead_id, score, status, notes):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE leads
        SET score = ?,
            status = ?,
            notes = ?
        WHERE id = ?
    """, (score, status, notes, lead_id))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    setup()
    print("Memory online")
