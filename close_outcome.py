import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def close_outcome(business, outcome):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if outcome == "WON":
        status = "CLIENT"
    elif outcome == "FOLLOW_UP":
        status = "FOLLOW_UP"
    else:
        status = "LOST"

    c.execute("""
        UPDATE leads
        SET status = ?,
            notes = ?
        WHERE business = ?
        AND reply_status = 'CALL_BOOKED'
    """, (
        status,
        f"Sales outcome: {outcome} at {datetime.now().isoformat()}",
        business
    ))

    if c.rowcount:
        print("Outcome recorded:", outcome)
    else:
        print("Lead not found or not CALL_BOOKED")

    conn.commit()
    conn.close()


if __name__ == "__main__":

    business = input("Business name: ")
    outcome = input("Outcome (WON/FOLLOW_UP/LOST): ")

    close_outcome(business, outcome)
