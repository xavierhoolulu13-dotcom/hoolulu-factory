import json
import os
from datetime import datetime

ROOT = os.path.expanduser("~/hoolulu-factory")

FILE = os.path.join(
    ROOT,
    "data",
    "clients",
    "clients.json"
)

os.makedirs(
    os.path.dirname(FILE),
    exist_ok=True
)


client = {
    "id": "CLIENT-001",
    "business": "Honolulu Test Company",
    "service": "AI Visibility Install",
    "investment": "$1500 setup + $99/month",
    "status": "ACTIVE",
    "created": str(datetime.now()),
    "assets": [
        "Audit",
        "Proposal",
        "Delivery Queue",
        "Reports"
    ]
}


clients = []

if os.path.exists(FILE):

    with open(FILE,"r") as f:
        clients = json.load(f)


clients.append(client)


with open(FILE,"w") as f:

    json.dump(
        clients,
        f,
        indent=4
    )


print("CLIENT ZERO CREATED")
print(client["business"])
