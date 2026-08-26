import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def add_column(name):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    try:
        c.execute(
            f"ALTER TABLE leads ADD COLUMN {name} TEXT"
        )

        print(f"Added: {name}")

    except sqlite3.OperationalError:

        print(f"Already exists: {name}")

    conn.commit()
    conn.close()


if __name__ == "__main__":

    columns = [
        "category",
        "city",
        "source",
        "notes",
        "website",
        "phone",
        "email"
    ]

    for column in columns:
        add_column(column)

    print("Database upgrade complete")
