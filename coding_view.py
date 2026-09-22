"""
coding_view — View layer for the CodingAgent.
Follows the factory's view pattern (client_view, opportunity_view, etc.)

Provides CLI and formatted output for coding agent tasks, queue status,
and agent status.
"""

import json
from datetime import datetime


class CodingView:
    """Renders coding agent data for CLI and dashboard consumption."""

    def __init__(self, agent=None, queue=None):
        self.agent = agent
        self.queue = queue

    def render_status(self, agent=None):
        """Render agent status as a formatted string."""
        a = agent or self.agent
        if not a:
            return "No agent connected"

        status = a.status() if hasattr(a, "status") else {}
        lines = [
            "╔══════════════════════════════════════╗",
            "║       CODING AGENT STATUS            ║",
            "╠══════════════════════════════════════╣",
            f"║  Name:     {status.get('name', 'N/A'):<26} ║",
            f"║  Version:  {status.get('version', 'N/A'):<26} ║",
            f"║  State:    {status.get('state', 'N/A'):<26} ║",
            f"║  Tasks:    {status.get('tasks_completed', 0):<26} ║",
            f"║  Workspace:{str(status.get('workspace', 'N/A')):<25} ║",
            "╚══════════════════════════════════════╝",
        ]
        return "\n".join(lines)

    def render_task(self, task):
        """Render a task result."""
        lines = [
            f"┌── Task: {task.get('id', 'N/A')} ──",
            f"│ Description: {task.get('description', '')[:60]}",
            f"│ Status:      {task.get('status', 'N/A')}",
            f"│ Steps:       {len(task.get('steps', []))}",
            f"│ Started:     {task.get('started_at', 'N/A')[:19]}",
            f"│ Completed:   {task.get('completed_at', 'N/A')[:19] if task.get('completed_at') else 'N/A'}",
        ]
        if task.get("error"):
            lines.append(f"│ Error:       {task['error'][:60]}")
        lines.append("└─────────────────────────────")
        return "\n".join(lines)

    def render_queue(self, queue=None):
        """Render queue status."""
        q = queue or self.queue
        if not q:
            return "No queue connected"

        stats = q.stats() if hasattr(q, "stats") else {}
        lines = [
            "╔══════════════════════════════════════╗",
            "║       CODING QUEUE STATUS            ║",
            "╠══════════════════════════════════════╣",
            f"║  Total:      {stats.get('total', 0):<26} ║",
            f"║  Pending:    {stats.get('pending', 0):<26} ║",
            f"║  Processing: {stats.get('processing', 0):<26} ║",
            f"║  Completed:  {stats.get('completed', 0):<26} ║",
            f"║  Failed:     {stats.get('failed', 0):<26} ║",
            "╚══════════════════════════════════════╝",
        ]
        return "\n".join(lines)

    def render_task_list(self, tasks, title="Tasks"):
        """Render a list of tasks."""
        if not tasks:
            return f"No {title.lower()}"

        lines = [f"┌── {title} ──"]
        for t in tasks:
            task_id = t.get("id", t.get("task_id", "?"))
            status = t.get("status", "?")
            desc = t.get("description", t.get("task", ""))[:50]
            lines.append(f"│ [{status:10s}] {task_id}: {desc}")
        lines.append("└─────────────────────────────")
        return "\n".join(lines)

    def render_forged_agents(self, forged_list):
        """Render a list of forged agents from AgentForge."""
        if not forged_list:
            return "No agents forged yet"

        lines = ["╔══════════════════════════════════════╗",
                 "║       FORGED AGENTS                 ║",
                 "╠══════════════════════════════════════╣"]
        for agent in forged_list:
            name = agent.get("agent_name", "?")
            template = agent.get("template", "?")
            caps = ", ".join(agent.get("capabilities", []))
            lines.append(f"║  {name} ({template})")
            lines.append(f"║    caps: {caps[:34]}")
        lines.append("╚══════════════════════════════════════╝")
        return "\n".join(lines)

    def to_json(self, data):
        """Export data as JSON."""
        return json.dumps(data, indent=2, default=str)

    def to_table(self, rows, headers=None):
        """Render a list of dicts as a simple table."""
        if not rows:
            return "No data"

        if not headers:
            headers = list(rows[0].keys())

        # Calculate column widths
        widths = {}
        for h in headers:
            widths[h] = max(len(str(h)), max(len(str(r.get(h, ""))) for r in rows))
            widths[h] = min(widths[h], 30)  # cap width

        # Build header
        header_line = " | ".join(str(h).ljust(widths[h]) for h in headers)
        separator = "-+-".join("-" * widths[h] for h in headers)

        # Build rows
        data_lines = []
        for r in rows:
            data_lines.append(" | ".join(str(r.get(h, "")).ljust(widths[h])[:widths[h]] for h in headers))

        return "\n".join([header_line, separator] + data_lines)


if __name__ == "__main__":
    view = CodingView()
    print(view.render_status())
    print()
    print(view.render_queue())
