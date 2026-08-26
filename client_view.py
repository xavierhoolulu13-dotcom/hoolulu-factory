import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def show_clients():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        """
        SELECT
        business,
        service,
        revenue,
        status
        FROM clients
        """
    ).fetchall()


    print("")
    print("HOOLULU CLIENT PIPELINE")
    print("=======================")


    for row in rows:

        print("")
        print("Business:", row[0])
        print("Service:", row[1])
        print("Revenue:", row[2])
        print("Status:", row[3])


    conn.close()


if __name__ == "__main__":
    show_clients()
