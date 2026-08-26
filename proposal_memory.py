import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def save_proposal(data):

    conn = sqlite3.connect(DB)
    c = conn.cursor()


    c.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY,
            business TEXT,
            headline TEXT,
            investment TEXT,
            status TEXT
        )
        """
    )


    c.execute(
        """
        INSERT INTO proposals
        (
        business,
        headline,
        investment,
        status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            data["business"],
            data["headline"],
            data["investment"],
            data["status"]
        )
    )


    conn.commit()
    conn.close()


    print("Proposal saved")


if __name__ == "__main__":

    proposal = {
        "business": "Honolulu Test Company",
        "headline": "AI Visibility Growth Plan",
        "investment": "$1500 setup + $99/month",
        "status": "PROPOSAL_READY"
    }

    save_proposal(proposal)
