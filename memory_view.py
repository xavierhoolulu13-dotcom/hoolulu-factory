import json
import os

ROOT = os.path.expanduser("~/hoolulu-factory")

MEMORY = os.path.join(
    ROOT,
    "data",
    "memory",
    "history.json"
)


print("""
================================
      HOOLULU MEMORY BANK
================================
""")


if os.path.exists(MEMORY):

    with open(MEMORY, "r") as f:
        data = json.load(f)

    for item in data:

        print("Business:",
              item.get("business"))

        print("Action:",
              item.get("action"))

        print("Status:",
              item.get("status"))

        print("Time:",
              item.get("timestamp"))

        print("----------------")

else:

    print("No memory records found")
