import os
from datetime import datetime

ROOT = os.path.expanduser("~/hoolulu-factory")

print("""
================================
       HOOLULU AUTOPILOT
================================
""")

steps = [
    ("System Check",
     "python core/status.py"),

    ("Factory Run",
     "python core/factory_runner.py"),

    ("Memory Update",
     "python core/memory_store.py"),

    ("Dashboard Refresh",
     "python core/dashboard.py")
]


results = []


for name, command in steps:

    print("\n" + name)
    print("----------------")

    code = os.system(command)

    status = "COMPLETE" if code == 0 else "FAILED"

    results.append(
        {
            "step": name,
            "status": status
        }
    )


os.makedirs(
    os.path.join(ROOT,"logs","autopilot"),
    exist_ok=True
)


report = os.path.join(
    ROOT,
    "logs",
    "autopilot",
    "autopilot_report.txt"
)


with open(report,"w") as f:

    f.write("HOOLULU AUTOPILOT REPORT\n")
    f.write("========================\n\n")
    f.write(str(datetime.now()))
    f.write("\n\n")

    for item in results:
        f.write(
            item["step"]
            + " : "
            + item["status"]
            + "\n"
        )


print("""
================================
      AUTOPILOT COMPLETE
================================
""")

print("Report:")
print(report)
