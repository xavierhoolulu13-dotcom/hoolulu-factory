import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def book_call(business):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE leads
        SET status = 'BOOKED',
            reply_status = 'CALL_BOOKED',
            notes = ?
        WHERE business = ?
        AND reply_status = 'POSITIVE_REPLY'
    """, (
        f"Call booked at {datetime.now().isoformat()}",
        business
    ))

    updated = c.rowcount

    if updated:
        print("CALL BOOKED:", business)

        c.execute("""
            INSERT INTO tasks(agent, task, status)
            VALUES (?, ?, ?)
        """, (
            "Cass",
            f"Prepare closing call for {business}",
            "OPEN"
        ))

        print("Closer task created")

    else:
        print("Lead not found or not POSITIVE_REPLY")

    conn.commit()
    conn.close()


if __name__ == "__main__":

    business = input("Business name: ")

    book_call(business)
