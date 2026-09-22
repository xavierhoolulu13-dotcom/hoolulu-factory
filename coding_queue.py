"""
coding_queue — Task queue for the CodingAgent.
Follows the factory's queue pattern (cass_queue, delivery_queue, etc.)

Provides:
  - enqueue(task) — add a coding task
  - dequeue() — get the next pending task
  - complete(task_id, result) — mark done
  - pending() — list pending tasks
  - failed() — list failed tasks
  - stats() — queue statistics
"""

import json
from datetime import datetime
from pathlib import Path


class CodingQueue:
    """Manages the coding task queue with persistence."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.data_dir / "coding_queue.json"
        self.queue = self._load()

    def _load(self):
        if self.queue_file.exists():
            try:
                return json.loads(self.queue_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
        return []

    def _save(self):
        self.queue_file.write_text(
            json.dumps(self.queue, indent=2, default=str),
            encoding="utf-8"
        )

    def enqueue(self, task, priority="normal", context=None):
        """Add a task to the queue."""
        item = {
            "id": f"code_{len(self.queue)+1:04d}",
            "task": task,
            "priority": priority,
            "context": context or {},
            "status": "pending",
            "created": datetime.now().isoformat(),
            "attempts": 0,
        }
        self.queue.append(item)
        self._save()
        print(f"[coding_queue] Enqueued {item['id']}: {task[:60]}...")
        return item

    def dequeue(self):
        """Get the next pending task (highest priority first)."""
        pending = [q for q in self.queue if q["status"] == "pending"]
        if not pending:
            return None

        # Sort by priority: urgent > high > normal > low
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        pending.sort(key=lambda q: priority_order.get(q.get("priority", "normal"), 2))

        item = pending[0]
        item["status"] = "processing"
        item["attempts"] += 1
        item["processing_started"] = datetime.now().isoformat()
        self._save()
        return item

    def complete(self, task_id, result=None):
        """Mark a task as completed."""
        for item in self.queue:
            if item["id"] == task_id:
                item["status"] = "completed"
                item["result"] = result
                item["completed"] = datetime.now().isoformat()
                self._save()
                return item
        return None

    def fail(self, task_id, error=None):
        """Mark a task as failed."""
        for item in self.queue:
            if item["id"] == task_id:
                item["status"] = "failed"
                item["error"] = error
                item["failed_at"] = datetime.now().isoformat()
                self._save()
                return item
        return None

    def requeue(self, task_id):
        """Move a failed task back to pending."""
        for item in self.queue:
            if item["id"] == task_id:
                item["status"] = "pending"
                item["requeued"] = datetime.now().isoformat()
                self._save()
                return item
        return None

    def pending(self):
        """Return all pending tasks."""
        return [q for q in self.queue if q["status"] == "pending"]

    def processing(self):
        """Return tasks currently being processed."""
        return [q for q in self.queue if q["status"] == "processing"]

    def completed(self):
        """Return completed tasks."""
        return [q for q in self.queue if q["status"] == "completed"]

    def failed(self):
        """Return failed tasks."""
        return [q for q in self.queue if q["status"] == "failed"]

    def stats(self):
        """Return queue statistics."""
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        for item in self.queue:
            status = item.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(self.queue),
            **counts,
        }

    def clear_completed(self):
        """Remove completed tasks from the queue."""
        before = len(self.queue)
        self.queue = [q for q in self.queue if q["status"] != "completed"]
        self._save()
        return before - len(self.queue)


if __name__ == "__main__":
    q = CodingQueue()
    print(json.dumps(q.stats(), indent=2))
    q.enqueue("Create a stock price scraper", priority="high")
    print(json.dumps(q.stats(), indent=2))
    task = q.dequeue()
    print(f"Dequeued: {task['id']}")
    q.complete(task["id"], {"ok": True, "file": "stock_scraper.py"})
    print(json.dumps(q.stats(), indent=2))
