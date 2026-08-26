import os
import json
from datetime import datetime

ROOT = os.path.expanduser("~/hoolulu-factory")

INDEX = os.path.join(
    ROOT,
    "data",
    "librarian_index.json"
)


folders = [
    "agents",
    "core",
    "skills",
    "data",
    "tasks",
    "logs",
    "backups"
]


index = {
    "updated": str(datetime.now()),
    "locations": {}
}


for folder in folders:

    path = os.path.join(
        ROOT,
        folder
    )

    if os.path.exists(path):

        index["locations"][folder] = os.listdir(path)


with open(INDEX,"w") as f:

    json.dump(
        index,
        f,
        indent=4
    )


print("""
=========================
 HOOLULU LIBRARIAN
=========================
""")

print("INDEX CREATED")
print(INDEX)
