import os
import sqlite3

ROOT = os.path.expanduser("~/hoolulu-factory")

def check_system():

    db = os.path.exists(
        os.path.join(ROOT,"data","hoolulu.db")
    )

    folders = [
        "core",
        "agents",
        "skills",
        "config",
        "data",
        "tasks",
        "logs",
        "backups"
    ]

    online = []

    for folder in folders:
        if os.path.exists(
            os.path.join(ROOT,folder)
        ):
            online.append(folder)

    return {
        "database": "ONLINE" if db else "OFFLINE",
        "folders": len(online)
    }
