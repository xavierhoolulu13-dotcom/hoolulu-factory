import sqlite3
import os

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def show_queue():

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            business,
            category,
            city,
            message,
            outreach_status,
            reply_status
        FROM leads
        WHERE outreach_status='READY'
        LIMIT 20
    """)

    rows = c.fetchall()

    print("\nCASS CLOSER QUEUE")
    print("=================\n")

    for row in rows:
        print("BUSINESS:", row["business"])
        print("CATEGORY:", row["category"])
        print("CITY:", row["city"])
        print("STATUS:", row["outreach_status"])
        print("REPLY:", row["reply_status"])
        print("-----------------")


    conn.close()


if __name__ == "__main__":
    show_queue()

