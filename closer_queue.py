import sqlite3
import os

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def show_closer_queue():

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            business,
            category,
            city,
            status,
            reply_status,
            notes
        FROM leads
        WHERE reply_status = 'CALL_BOOKED'
        ORDER BY id DESC
    """)

    rows = c.fetchall()

    print("\nCASS CLOSER QUEUE")
    print("=================\n")

    if not rows:
        print("No booked calls.")
        return

    for row in rows:
        print("BUSINESS:", row["business"])
        print("CATEGORY:", row["category"])
        print("CITY:", row["city"])
        print("STATUS:", row["status"])
        print("CALL:", row["reply_status"])
        print("NOTES:", row["notes"])
        print("-----------------")


    conn.close()


if __name__ == "__main__":
    show_closer_queue()
