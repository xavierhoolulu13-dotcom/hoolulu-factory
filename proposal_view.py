import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def show_proposals():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        """
        SELECT
        business,
        headline,
        investment,
        status
        FROM proposals
        """
    ).fetchall()


    print("")
    print("HOOLULU SALES PIPELINE")
    print("======================")

    for row in rows:

        print("")
        print("Business:", row[0])
        print("Offer:", row[1])
        print("Investment:", row[2])
        print("Stage:", row[3])


    conn.close()


if __name__ == "__main__":
    show_proposals()
