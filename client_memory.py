import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def save_client(data):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            business TEXT,
            service TEXT,
            revenue TEXT,
            status TEXT
        )
        """
    )

    c.execute(
        """
        INSERT INTO clients
        (
        business,
        service,
        revenue,
        status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            data["business"],
            data["service"],
            data["revenue"],
            data["status"]
        )
    )

    conn.commit()
    conn.close()

    print("Client saved")


if __name__ == "__main__":

    client = {
        "business": "Honolulu Test Company",
        "service": "AI Visibility Install",
        "revenue": "$1500 setup + $99/month",
        "status": "ACTIVE"
    }

    save_client(client)
