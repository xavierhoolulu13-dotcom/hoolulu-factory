import json
import os

ROOT = os.path.expanduser("~/hoolulu-factory")

FILE = os.path.join(
    ROOT,
    "data",
    "clients",
    "clients.json"
)


print("""
==============================
 HOOLULU CLIENT REPORT
==============================
""")


if os.path.exists(FILE):

    with open(FILE,"r") as f:
        clients = json.load(f)


    for client in clients:

        print("Client:",
              client["business"])

        print("Service:",
              client["service"])

        print("Status:",
              client["status"])

        print("Assets:")

        for asset in client["assets"]:
            print("-", asset)

        print("----------------")

else:

    print("No clients found")
