"""The append-only loop log.

Every stage of every run writes one JSON line to
``hoolulu-ecosystem-hub/core/event-log/loops/events.jsonl``. Nothing is ever
rewritten, so a run can be reconstructed from the log alone.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import config

STAGES = ("intake", "research", "reasoning", "approval", "build",
          "qa", "package", "deliver", "maintain")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_loop_id(slug: str = "run") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{stamp}-{uuid.uuid4().hex[:4]}"


class Loop:
    """One pass through the factory. Writes events as it goes."""

    def __init__(self, loop_id: str | None = None, actor: str | None = None,
                 log_path: Path | None = None):
        self.loop_id = loop_id or new_loop_id()
        self.actor = actor or config.OPERATOR
        self.log_path = Path(log_path or config.EVENT_LOG)

    # -- writing ------------------------------------------------------------
    def event(self, stage: str, status: str, message: str = "", *,
              data=None, next=(), model=None) -> dict:
        """Append one event and return it."""
        record = {
            "ts": _now(),
            "loop_id": self.loop_id,
            "event_id": uuid.uuid4().hex[:12],
            "stage": stage,
            "status": status,
            "actor": self.actor,
            "message": message,
            "data": data or {},
            "next": list(next),
            "model": model,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=False) + "\n")
        return record

    def ok(self, stage, message="", **kw):
        return self.event(stage, "ok", message, **kw)

    def blocked(self, stage, message="", **kw):
        return self.event(stage, "blocked", message, **kw)

    def failed(self, stage, message="", **kw):
        return self.event(stage, "failed", message, **kw)

    # -- reading ------------------------------------------------------------
    def events(self) -> list[dict]:
        return [e for e in read_events(self.log_path) if e.get("loop_id") == self.loop_id]


def read_events(path: Path | None = None) -> list[dict]:
    """Read the whole log, skipping lines that are damaged rather than failing."""
    path = Path(path or config.EVENT_LOG)
    if not path.exists():
        return []
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn line must never stop the factory
    return events


def tail_events(limit: int = 25, loop_id: str | None = None,
                path: Path | None = None) -> list[dict]:
    events = read_events(path)
    if loop_id:
        events = [e for e in events if e.get("loop_id") == loop_id]
    return events[-limit:]


def loop_ids(path: Path | None = None) -> list[str]:
    """Distinct loop ids, oldest first — the order they were started in."""
    seen: dict[str, None] = {}
    for event in read_events(path):
        seen.setdefault(event.get("loop_id", "?"), None)
    return list(seen)


def next_counter(prefix: str = "run") -> int:
    return len(loop_ids()) + 1 if prefix else 0
