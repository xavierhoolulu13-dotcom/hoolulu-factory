#!/usr/bin/env python3
import os
import json

DATA_DIR = os.path.join(os.getcwd(), "data")
INDEX = os.path.join(DATA_DIR, "librarian_index.json")

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(INDEX):
    with open(INDEX, "w") as f:
        f.write("{}")
    print("\n=========================\n HOOLULU LIBRARIAN\n=========================\n")
    print("INDEX CREATED")
    print(INDEX)

def load_index():
    with open(INDEX, "r") as f:
        return json.load(f)

def save_index(data):
    with open(INDEX, "w") as f:
        json.dump(data, f, indent=2)

# ---------------------------------------------------------
# WORKSPACE SNAPSHOT (MINIMAL WORKING VERSION)
# ---------------------------------------------------------

def build_workspace_snapshot():
    """Return a minimal snapshot so dashboard/daemon can run."""
    idx = load_index()
    return {
        "clients": idx.get("clients", []),
        "opportunities": idx.get("opportunities", []),
        "delivery": idx.get("delivery", [])
    }

def get_workspace_summary(snapshot):
    return {
        "clients": len(snapshot["clients"]),
        "opportunities": len(snapshot["opportunities"]),
        "delivery": len(snapshot["delivery"])
    }

def get_today_focus(snapshot):
    return snapshot["clients"][:3]  # placeholder

def get_stalled(snapshot):
    return snapshot["opportunities"][:3]  # placeholder

def get_needs_outreach(snapshot):
    return snapshot["clients"][:2]  # placeholder

def get_needs_delivery(snapshot):
    return snapshot["delivery"][:2]  # placeholder

# ---------------------------------------------------------
# BASIC QUERY INTERFACE
# ---------------------------------------------------------

def answer(q):
    snap = build_workspace_snapshot()
    if q == "summary":
        return get_workspace_summary(snap)
    if q == "today":
        return get_today_focus(snap)
    if q == "stalled":
        return get_stalled(snap)
    return "Unknown query"
