import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def send_lead(business):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE leads
        SET outreach_status = 'SENT',
            outreach_channel = 'MANUAL',
            sent_at = ?,
            reply_status = 'WAITING_REPLY'
        WHERE business = ?
        AND outreach_status = 'READY'
    """, (
        datetime.now().isoformat(),
        business
    ))

    if c.rowcount:
        print("Marked as SENT:", business)
    else:
        print("Lead not found or not READY:", business)

    conn.commit()
    conn.close()


if __name__ == "__main__":

    business = input("Business name: ")

    send_lead(business)
