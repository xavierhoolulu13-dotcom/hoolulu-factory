import os

path = os.path.expanduser(
"~/hoolulu-factory/logs/factory/factory_run_report.txt"
)

print("""
================================
     FACTORY RUN REPORT
================================
""")

if os.path.exists(path):

    with open(path,"r") as f:
        print(f.read())

else:
    print("No factory run found yet.")
