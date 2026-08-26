import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def onboard_client(business):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Close Cass task
    c.execute("""
        UPDATE tasks
        SET status='COMPLETE'
        WHERE agent='Cass'
        AND task LIKE ?
    """, (f"%{business}%",))


    # Create delivery task
    c.execute("""
        INSERT INTO tasks(agent, task, status)
        VALUES (?, ?, ?)
    """, (
        "Delivery",
        f"Setup AI Visibility Install for {business}",
        "OPEN"
    ))


    # Update notes
    c.execute("""
        UPDATE leads
        SET notes=?
        WHERE business=?
    """, (
        f"Client onboarding started at {datetime.now().isoformat()}",
        business
    ))


    conn.commit()
    conn.close()

    print("CLIENT ONBOARDED:", business)


if __name__ == "__main__":

    business = input("Business name: ")

    onboard_client(business)
