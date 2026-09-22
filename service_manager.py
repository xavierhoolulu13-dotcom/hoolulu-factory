#!/usr/bin/env python3

import autopilot
import outreach_queue
import delivery_queue

SERVICE_STATE = {
    "autopilot": {"running": False},
    "outreach": {"running": False},
    "delivery": {"running": False},
}

def start_service(name):
    if name not in SERVICE_STATE:
        print(f"Unknown service: {name}")
        return
    SERVICE_STATE[name]["running"] = True
    print(f"[Service Manager] Starting {name}...")
    if name == "autopilot":
        autopilot.run_autopilot(None, [])
    elif name == "outreach":
        outreach_queue.enqueue_targets(None, [])
    elif name == "delivery":
        delivery_queue.enqueue_targets(None, [])

def stop_service(name):
    if name not in SERVICE_STATE:
        print(f"Unknown service: {name}")
        return
    SERVICE_STATE[name]["running"] = False
    print(f"[Service Manager] Stopped {name}.")

def get_service_status():
    return {svc: ("running" if data["running"] else "stopped") for svc, data in SERVICE_STATE.items()}
