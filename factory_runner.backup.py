import os
from datetime import datetime

ROOT = os.path.expanduser("~/hoolulu-factory")

print("""
================================
      HOOLULU FACTORY RUN
================================
""")

steps = [
    ("Checking database", "python core/view.py"),
    ("Running qualification", "python agents/qualification.py"),
    ("Running nurture", "python agents/nurture.py"),
    ("Generating report", "python core/factory_report.py")
]

results = []

for name, command in steps:

    print("\n" + name)
    print("----------------")

    code = os.system(command)

    if code == 0:
        status = "COMPLETE"
    else:
        status = "FAILED"

    results.append({
        "step": name,
        "status": status
    })


os.makedirs(
    os.path.join(ROOT,"logs","factory"),
    exist_ok=True
)

report = os.path.join(
    ROOT,
    "logs",
    "factory",
    "factory_run_report.txt"
)

with open(report,"w") as f:

    f.write("HOOLULU FACTORY RUN REPORT\n")
    f.write("==========================\n\n")
    f.write(str(datetime.now()))
    f.write("\n\n")

    for item in results:
        f.write(
            item["step"] +
            " : " +
            item["status"] +
            "\n"
        )


print("""
================================
      FACTORY RUN COMPLETE
================================
""")

print("Report saved:")
print(report)
