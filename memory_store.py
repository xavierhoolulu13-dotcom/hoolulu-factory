import json
import os
from datetime import datetime

ROOT = os.path.expanduser("~/hoolulu-factory")
MEMORY = os.path.join(ROOT, "data", "memory", "history.json")


def load_memory():

    if not os.path.exists(MEMORY):
        return []

    with open(MEMORY, "r") as f:
        return json.load(f)


def save_memory(entry):

    memory = load_memory()

    entry["timestamp"] = str(datetime.now())

    memory.append(entry)

    with open(MEMORY, "w") as f:
        json.dump(memory, f, indent=4)


if __name__ == "__main__":

    save_memory({
        "business": "Honolulu Test Company",
        "action": "Factory Memory Initialized",
        "status": "ACTIVE"
    })

    print("Memory saved")
