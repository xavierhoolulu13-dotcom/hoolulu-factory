#!/usr/bin/env python3

import time
import service_manager
from librarian import build_workspace_snapshot, get_today_focus, get_needs_outreach, get_needs_delivery

def run_daemon():
    print("=== Hoolulu OS Daemon Mode ===")
    while True:
        snapshot = build_workspace_snapshot()
        service_manager.start_service("autopilot")
        service_manager.start_service("outreach")
        service_manager.start_service("delivery")
        time.sleep(300)

if __name__ == "__main__":
    run_daemon()
