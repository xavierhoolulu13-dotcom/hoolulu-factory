from metrics import get_counts
from status import check_system


print("""
================================
       HOOLULU CEO DASHBOARD
================================
""")

data = get_counts()
system = check_system()

print("PIPELINE")
print("----------------")

print("NEW:", data.get("NEW",0))
print("SCORED:", data.get("SCORED",0))
print("NURTURE:", data.get("NURTURE",0))
print("BOOKED:", data.get("BOOKED",0))
print("CLIENT:", data.get("CLIENT",0))

print()

print("SALES")
print("----------------")

print("OPPORTUNITIES:",
      data.get("OPPORTUNITIES",0))

print("PROPOSALS:",
      data.get("PROPOSALS",0))
print()

print("SYSTEM")
print("----------------")

print("DATABASE:",
      system["database"])

print("FACTORY FOLDERS:",
      system["folders"])

print("""
================================
        DASHBOARD ONLINE
================================
""")
