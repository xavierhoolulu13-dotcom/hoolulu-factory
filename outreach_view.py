import sqlite3
import os


DB = os.path.expanduser(
    "~/hoolulu-factory/data/hoolulu.db"
)


conn = sqlite3.connect(DB)

rows = conn.execute("""
SELECT 
business,
offer,
status,
message
FROM outreach_queue
ORDER BY id
LIMIT 20
""").fetchall()


print("\nHOOLULU OUTREACH QUEUE")
print("======================\n")


for r in rows:
    print("BUSINESS:", r[0])
    print("OFFER:", r[1])
    print("STATUS:", r[2])
    print("MESSAGE:")
    print(r[3])
    print("----------------------")


conn.close()
