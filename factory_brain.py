import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def create_task(agent, task):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    existing = c.execute(
        """
        SELECT id FROM tasks
        WHERE task=?
        """,
        (task,)
    ).fetchone()

    if not existing:
        c.execute(
            """
            INSERT INTO tasks(agent, task, status)
            VALUES (?, ?, ?)
            """,
            (agent, task, "OPEN")
        )
        conn.commit()
        print("TASK CREATED:", agent, task)

    conn.close()


def run_brain():

    conn = sqlite3.connect(DB)

    leads = conn.execute(
        """
        SELECT business, status, reply_status
        FROM leads
        """
    ).fetchall()

    conn.close()

    print("FACTORY BRAIN")
    print("================")

    for business, status, reply in leads:

        if status == "BOOKED":
            create_task(
                "Cass",
                f"Prepare closing call for {business}"
            )

        elif status == "CLIENT":
            create_task(
                "Delivery",
                f"Review client delivery for {business}"
            )

        print(
            business,
            "→",
            status
        )


if __name__ == "__main__":
    run_brain()
