import sqlite3
import os

DB=os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")

conn=sqlite3.connect(DB)
c=conn.cursor()

for lead in c.execute("SELECT * FROM leads"):
    print(lead)

conn.close()
