import os

while True:

    print("\n==============================")
    print(" HOOLULU COMMAND CENTER")
    print("==============================")
    print("1. View Leads")
    print("2. Run Factory Report")
    print("3. Run Nurture Engine")
    print("4. Run Forge")
    print("5. Exit")

    choice = input("\nSelect: ")

    if choice == "1":
        os.system("python core/view.py")

    elif choice == "2":
        os.system("python core/factory_report.py")

    elif choice == "3":
        os.system("python agents/nurture.py")

    elif choice == "4":
        os.system("python agents/forge/forge.py")

    elif choice == "5":
        print("Aloha 🤙")
        break

    else:
        print("Invalid selection")
