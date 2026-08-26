import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


def count(table):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    result = c.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    conn.close()

    return result


print("")
print("HOOLULU FACTORY REPORT")
print("======================")

print("LEADS:", count("leads"))
print("OPPORTUNITIES:", count("opportunities"))
print("PROPOSALS:", count("proposals"))
print("CLIENTS:", count("clients"))
print("DELIVERY TASKS:", count("delivery_tasks"))
