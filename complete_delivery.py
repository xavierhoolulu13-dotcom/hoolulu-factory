import sqlite3
import os
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def complete_delivery(business):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE tasks
        SET status='COMPLETE'
        WHERE agent='Delivery'
        AND task LIKE ?
        AND status='OPEN'
    """, (f"%{business}%",))


    c.execute("""
        UPDATE leads
        SET notes=?
        WHERE business=?
    """, (
        f"Delivery completed at {datetime.now().isoformat()}",
        business
    ))


    conn.commit()

    print("DELIVERY COMPLETE:", business)

    conn.close()


if __name__ == "__main__":

    business = input("Business name: ")

    complete_delivery(business)


