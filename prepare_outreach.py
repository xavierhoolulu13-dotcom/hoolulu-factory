import sqlite3
import os

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def prepare():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE leads
        SET outreach_status = 'READY',
            reply_status = 'WAITING'
        WHERE status = 'BOOKED'
        AND outreach_status IS NULL
        AND business != 'Demo Hawaii Business'
    """)

    print("Prepared leads:", c.rowcount)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    prepare()
