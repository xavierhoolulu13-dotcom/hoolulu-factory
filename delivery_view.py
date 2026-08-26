import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def show_delivery():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        """
        SELECT
        business,
        task,
        owner,
        status
        FROM delivery_tasks
        """
    ).fetchall()


    print("")
    print("HOOLULU DELIVERY QUEUE")
    print("======================")

    for row in rows:

        print("")
        print("Client:", row[0])
        print("Task:", row[1])
        print("Owner:", row[2])
        print("Status:", row[3])


    conn.close()


if __name__ == "__main__":
    show_delivery()
