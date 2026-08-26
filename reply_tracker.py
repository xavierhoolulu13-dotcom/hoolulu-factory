import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def update_reply(business, reply):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE leads
        SET reply_status = ?,
            notes = ?
        WHERE business = ?
        AND outreach_status = 'SENT'
    """, (
        reply,
        f"Reply received at {datetime.now().isoformat()}",
        business
    ))

    if c.rowcount:
        print("Reply updated:", business)
    else:
        print("Lead not found or not SENT")

    conn.commit()
    conn.close()


if __name__ == "__main__":

    business = input("Business name: ")
    reply = input("Reply status (POSITIVE_REPLY / NEGATIVE_REPLY): ")

    update_reply(business, reply)
