import os

REPORT = os.path.expanduser(
"~/hoolulu-factory/logs/autopilot/autopilot_report.txt"
)


print("""
================================
     AUTOPILOT REPORT
================================
""")


if os.path.exists(REPORT):

    with open(REPORT,"r") as f:
        print(f.read())

else:

    print("No autopilot run found.")
