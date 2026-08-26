import sqlite3
import os

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def show_delivery():

    conn = sqlite3.connect(DB)

    rows = conn.execute("""
        SELECT task, status
        FROM tasks
        WHERE agent='Delivery'
        AND status='OPEN'
    """).fetchall()

    print("\nDELIVERY QUEUE")
    print("================")

    if not rows:
        print("No delivery tasks")
    else:
        for task, status in rows:
            print("TASK:", task)
            print("STATUS:", status)
            print("----------------")


    conn.close()


if __name__ == "__main__":
    show_delivery()
