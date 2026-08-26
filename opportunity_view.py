import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def show_opportunities():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        """
        SELECT
        business,
        solution,
        offer,
        status
        FROM opportunities
        """
    ).fetchall()


    print("")
    print("HOOLULU OPPORTUNITY PIPELINE")
    print("============================")


    for row in rows:
        print("")
        print("Business:", row[0])
        print("Solution:", row[1])
        print("Offer:", row[2])
        print("Status:", row[3])


    conn.close()


if __name__ == "__main__":
    show_opportunities()
