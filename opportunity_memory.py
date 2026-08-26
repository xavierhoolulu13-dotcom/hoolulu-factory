import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def save_opportunity(data):

    conn = sqlite3.connect(DB)
    c = conn.cursor()


    c.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY,
            business TEXT,
            problem TEXT,
            solution TEXT,
            offer TEXT,
            status TEXT
        )
        """
    )


    c.execute(
        """
        INSERT INTO opportunities
        (
        business,
        problem,
        solution,
        offer,
        status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["business"],
            data["problem"],
            data["solution"],
            data["offer"],
            data["status"]
        )
    )


    conn.commit()
    conn.close()


    print(
        "Opportunity saved"
    )


if __name__ == "__main__":

    test = {
        "business": "Honolulu Test Company",
        "problem": "Digital visibility",
        "solution": "AI Visibility Install",
        "offer": "$1500 setup + $99/month",
        "status": "OPPORTUNITY"
    }


    save_opportunity(test)
