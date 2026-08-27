"""
agent_memory — Memory store for the CodingAgent and AgentForge.
Follows the factory's memory pattern (memory_store, client_memory, etc.)

Provides:
  - remember(key, value) — store something
  - recall(key) — get the latest value for a key
  - recall_all(key) — get all entries for a key
  - forget(key) — remove entries for a key
  - snapshot() — export full memory state
  - restore(snapshot) — import a memory state
"""

import json
from datetime import datetime
from pathlib import Path


class AgentMemory:
    """Persistent memory store for coding agents."""

    def __init__(self, data_dir=None, store_name="agent"):
        self.data_dir = Path(data_dir or "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store_name = store_name
        self.mem_file = self.data_dir / f"{store_name}_memory.json"
        self.memory = self._load()

    def _load(self):
        if self.mem_file.exists():
            try:
                return json.loads(self.mem_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"entries": [], "metadata": {}}
        return {"entries": [], "metadata": {}}

    def _save(self):
        self.memory["metadata"]["last_updated"] = datetime.now().isoformat()
        self.memory["metadata"]["entry_count"] = len(self.memory["entries"])
        self.mem_file.write_text(
            json.dumps(self.memory, indent=2, default=str),
            encoding="utf-8"
        )

    def remember(self, key, value, category="general"):
        """Store a value in memory."""
        entry = {
            "id": f"mem_{len(self.memory['entries'])+1:04d}",
            "key": key,
            "value": value,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }
        self.memory["entries"].append(entry)
        self._save()
        return entry

    def recall(self, key):
        """Get the most recent value for a key."""
        for entry in reversed(self.memory["entries"]):
            if entry["key"] == key:
                return entry["value"]
        return None

    def recall_all(self, key=None):
        """Get all entries, optionally filtered by key."""
        if key:
            return [e for e in self.memory["entries"] if e["key"] == key]
        return self.memory["entries"]

    def recall_category(self, category):
        """Get all entries in a category."""
        return [e for e in self.memory["entries"] if e.get("category") == category]

    def forget(self, key):
        """Remove all entries for a key."""
        before = len(self.memory["entries"])
        self.memory["entries"] = [e for e in self.memory["entries"] if e["key"] != key]
        self._save()
        return before - len(self.memory["entries"])

    def search(self, query):
        """Search memory entries by query string."""
        query_lower = query.lower()
        return [
            e for e in self.memory["entries"]
            if query_lower in str(e["key"]).lower() or query_lower in str(e["value"]).lower()
        ]

    def snapshot(self):
        """Export the full memory state."""
        return json.dumps(self.memory, indent=2, default=str)

    def restore(self, snapshot_json):
        """Import a memory state from JSON."""
        try:
            self.memory = json.loads(snapshot_json)
            self._save()
            return True
        except json.JSONDecodeError:
            return False

    def stats(self):
        """Return memory statistics."""
        categories = {}
        for entry in self.memory["entries"]:
            cat = entry.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "total_entries": len(self.memory["entries"]),
            "categories": categories,
            "last_updated": self.memory.get("metadata", {}).get("last_updated"),
        }


if __name__ == "__main__":
    mem = AgentMemory()
    print(json.dumps(mem.stats(), indent=2))
    mem.remember("test_key", "test_value", category="test")
    print(f"Recall: {mem.recall('test_key')}")
    mem.forget("test_key")
    print(f"After forget: {mem.recall('test_key')}")
