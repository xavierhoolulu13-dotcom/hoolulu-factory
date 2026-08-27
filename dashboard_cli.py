#!/usr/bin/env python3

from librarian import (
    build_workspace_snapshot,
    get_workspace_summary,
    get_today_focus,
    get_stalled,
    get_needs_outreach,
    get_needs_delivery,
)
import service_manager

def show_dashboard():
    snapshot = build_workspace_snapshot()

    summary = get_workspace_summary(snapshot)
    today_focus = get_today_focus(snapshot)
    stalled = get_stalled(snapshot)
    needs_outreach = get_needs_outreach(snapshot)
    needs_delivery = get_needs_delivery(snapshot)
    services = service_manager.get_service_status()

    print("\n=== HOOLULU OS DASHBOARD ===\n")
    print("Summary:", summary)
    print("\nToday Focus:", [i.id for i in today_focus])
    print("Stalled:", [i.id for i in stalled])
    print("Needs Outreach:", [i.id for i in needs_outreach])
    print("Needs Delivery:", [i.id for i in needs_delivery])
    print("\nServices:", services)

def main():
    while True:
        show_dashboard()
        cmd = input("\n> ").strip().lower()
        if cmd == "exit":
            break
        elif cmd == "refresh":
            continue
        elif cmd.startswith("start"):
            _, svc = cmd.split(" ", 1)
            service_manager.start_service(svc)
        elif cmd.startswith("stop"):
            _, svc = cmd.split(" ", 1)
            service_manager.stop_service(svc)

if __name__ == "__main__":
    main()
