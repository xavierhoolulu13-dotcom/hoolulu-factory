import sqlite3
import os
from datetime import datetime


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def create_outreach_queue():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS outreach_queue(
        id INTEGER PRIMARY KEY,
        business TEXT,
        problem TEXT,
        offer TEXT,
        message TEXT,
        status TEXT,
        created TEXT
    )
    """)


    leads = c.execute("""
    SELECT business, notes
    FROM leads
    WHERE status='SCORED'
    AND business != 'Honolulu Test Company'
    """).fetchall()


    for business, notes in leads:

        message = f"""
Aloha {business},

I noticed your business has a strong local presence, but there may be opportunities to improve how customers find you online.

We help Hawaii businesses improve their digital visibility with an AI Visibility Install.

Would you be open to a quick conversation about ways to bring in more local customers?

Mahalo.
"""

        c.execute("""
        INSERT INTO outreach_queue
        (
        business,
        problem,
        offer,
        message,
        status,
        created
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            business,
            notes,
            "$1500 setup + $99/month",
            message.strip(),
            "READY",
            str(datetime.now())
        ))

    conn.commit()
    conn.close()

    print("Outreach queue created")


if __name__ == "__main__":
    create_outreach_queue()
