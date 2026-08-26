import os
import sqlite3
from datetime import datetime

DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")


def header(title):
    print("\n" + "=" * 32)
    print(title)
    print("=" * 32)


conn = sqlite3.connect(DB)
c = conn.cursor()

header("HOOLULU FACTORY RUN")

print("\nChecking database")
print("----------------")

# Counts
tables = [
    "leads",
    "opportunities",
    "proposals",
    "clients",
    "delivery_tasks"
]

print("\nFACTORY STATUS")
print("----------------")

for table in tables:
    try:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table.upper()}: {c.fetchone()[0]}")
    except:
        print(f"{table.upper()}: 0")

print("\nLast Run:")
print(datetime.now())

print("\nLEADS TABLE SCHEMA")
print("----------------")

c.execute("PRAGMA table_info(leads)")
cols = c.fetchall()

for col in cols:
    print(col)

print("\nFIRST 5 RECORDS")
print("----------------")

try:
    c.execute("SELECT * FROM leads LIMIT 5")
    rows = c.fetchall()

    for row in rows:
        print(row)

except Exception as e:
    print(e)

conn.close()

print("\nFACTORY COMPLETE")
