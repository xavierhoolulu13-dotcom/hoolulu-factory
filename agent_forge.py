"""
AgentForge — Meta agent builder that creates new specialized coding agents.

This is the "coding agent with a coding agent" layer:
  - Takes a natural-language spec for a new agent
  - Generates the full Python module for that agent
  - Writes it to disk
  - Registers it with the factory registry
  - Optionally bootstraps its queue, memory, and view modules

Usage:
    from agent_forge import AgentForge
    forge = AgentForge()
    result = forge.forge("Build a stock price scraper agent that runs daily")
"""

import os
import re
import json
import importlib.util
from pathlib import Path
from datetime import datetime


class AgentForge:
    """Forge new coding agents from specs."""

    # Agent template types
    TEMPLATES = {
        "scraper": {
            "capabilities": ["fetch_url", "parse_html", "extract_data", "save_results"],
            "base_class": "CodingAgent",
            "imports": ["requests", "bs4", "json"],
        },
        "monitor": {
            "capabilities": ["check_status", "compare_state", "alert", "log_change"],
            "base_class": "CodingAgent",
            "imports": ["json", "datetime"],
        },
        "processor": {
            "capabilities": ["read_input", "transform", "validate", "write_output"],
            "base_class": "CodingAgent",
            "imports": ["json", "csv"],
        },
        "scheduler": {
            "capabilities": ["schedule_task", "check_due", "execute_task", "reschedule"],
            "base_class": "CodingAgent",
            "imports": ["datetime", "threading"],
        },
        "analyzer": {
            "capabilities": ["load_data", "analyze", "report", "visualize"],
            "base_class": "CodingAgent",
            "imports": ["json", "statistics"],
        },
        "generic": {
            "capabilities": ["run", "process", "handle"],
            "base_class": "CodingAgent",
            "imports": ["json"],
        },
    }

    def __init__(self, workspace=None, output_dir=None):
        self.workspace = Path(workspace or os.getcwd())
        self.output_dir = Path(output_dir or self.workspace)
        self.forge_version = "1.0.0"
        self.forged_agents = []

    def forge(self, description, context=None, parent=None):
        """
        Main entry — forge a new agent from a description.

        Args:
            description: Natural-language spec for the agent
            context: Optional dict with keys like 'name', 'template', 'capabilities'
            parent: Name of the parent agent (for tracking)

        Returns:
            dict with forge result — path, name, capabilities, registered
        """
        ctx = context or {}
        spec = self._parse_spec(description, ctx)

        # Generate the agent code
        code = self._generate_agent_code(spec)

        # Write the agent module
        file_path = self.output_dir / f"{spec['module_name']}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")

        # Generate supporting modules (queue, memory, view)
        support_modules = self._generate_support_modules(spec)

        # Register with factory registry
        registered = self._register_agent(spec)

        result = {
            "ok": True,
            "agent_name": spec["name"],
            "module_name": spec["module_name"],
            "file_path": str(file_path),
            "template": spec["template"],
            "capabilities": spec["capabilities"],
            "support_modules": support_modules,
            "registered": registered,
            "parent": parent,
            "forged_at": datetime.now().isoformat(),
        }

        self.forged_agents.append(result)
        print(f"[AgentForge] Forged agent '{spec['name']}' → {file_path}")
        return result

    def _parse_spec(self, description, context=None):
        """Parse a description into a structured agent spec."""
        ctx = context or {}
        desc_lower = description.lower()

        # Detect template type
        template = ctx.get("template", "generic")
        for key in self.TEMPLATES:
            if key in desc_lower:
                template = key
                break

        # Derive agent name
        if ctx.get("name"):
            name = ctx["name"]
        else:
            name = self._derive_name(description)

        module_name = name.lower().replace(" ", "_").replace("-", "_")
        # Clean up for Python module naming
        module_name = re.sub(r'[^a-z0-9_]', '', module_name)

        # Get capabilities
        base_caps = self.TEMPLATES.get(template, self.TEMPLATES["generic"])["capabilities"]
        capabilities = ctx.get("capabilities", base_caps)

        # Extra context from description
        schedule = None
        if "daily" in desc_lower or "every day" in desc_lower:
            schedule = "daily"
        elif "hourly" in desc_lower or "every hour" in desc_lower:
            schedule = "hourly"
        elif "weekly" in desc_lower:
            schedule = "weekly"

        return {
            "name": name,
            "module_name": module_name,
            "description": description,
            "template": template,
            "capabilities": capabilities,
            "base_class": self.TEMPLATES.get(template, self.TEMPLATES["generic"])["base_class"],
            "imports": self.TEMPLATES.get(template, self.TEMPLATES["generic"])["imports"],
            "schedule": schedule,
            "created_at": datetime.now().isoformat(),
        }

    def _derive_name(self, description):
        """Derive an agent name from the description."""
        # Try to find a noun phrase
        words = description.lower().split()
        skip = {"build", "create", "make", "a", "an", "the", "that", "agent", "which",
                "for", "to", "of", "can", "will", "should", "i", "want", "me", "we", "need"}

        filtered = [w for w in words if w.isalpha() and w not in skip]
        if not filtered:
            return "CustomAgent"
        # Take first 2-3 meaningful words
        name_parts = filtered[:3]
        return "_".join(name_parts).title().replace("_", "")

    def _generate_agent_code(self, spec):
        """Generate the full Python module code for a new agent."""
        name = spec["name"]
        module = spec["module_name"]
        caps = spec["capabilities"]
        imports = spec["imports"]
        template = spec["template"]
        desc = spec["description"]

        # Build imports — stdlib direct, third-party wrapped in try/except
        STDLIB = {"os", "sys", "json", "datetime", "pathlib", "csv", "threading", "statistics", "importlib"}
        import_lines = []
        for imp in imports:
            if imp in STDLIB:
                if imp == "datetime":
                    import_lines.append("from datetime import datetime")
                elif imp == "pathlib":
                    import_lines.append("from pathlib import Path")
                else:
                    import_lines.append(f"import {imp}")
            else:
                import_lines.append(f"try:\n    import {imp}\nexcept ImportError:\n    {imp} = None  # pip install {imp}")
        import_lines = "\n".join(import_lines)

        # Build capability methods
        methods_code = ""
        for cap in caps:
            methods_code += self._generate_method(cap, template)

        # Build schedule method if needed
        schedule_method = ""
        if spec.get("schedule"):
            schedule_method = f'''
    def schedule(self):
        """Return the schedule spec for the factory scheduler."""
        return {{"cadence": "{spec['schedule']}", "task": "run"}}
'''

        code = f'''"""
{module} — Forged by AgentForge

Description: {desc}
Template: {template}
Capabilities: {", ".join(caps)}
Forged: {spec["created_at"]}
"""

import os
import sys
{import_lines}
from pathlib import Path
from datetime import datetime

# Import the base CodingAgent if available
try:
    from coding_agent import CodingAgent
except ImportError:
    # Fallback: define a minimal base
    class CodingAgent:
        def __init__(self, workspace=None, name="agent"):
            self.name = name
            self.workspace = Path(workspace or os.getcwd())
            self.state = "idle"
            self.task_history = []
        def run_task(self, task, context=None):
            raise NotImplementedError("coding_agent.CodingAgent not found")
        def status(self):
            return {{"name": self.name, "state": self.state}}


class {name.replace("_", "")}(CodingAgent):
    """
    {desc}

    Capabilities: {", ".join(caps)}
    Template: {template}
    """

    def __init__(self, workspace=None):
        super().__init__(workspace=workspace, name="{module}")
        self.template = "{template}"
        self.capabilities = {json.dumps(caps)}
        self.state = "idle"
{schedule_method}

    def run(self, *args, **kwargs):
        """Main execution entry point."""
        self.state = "running"
        print(f"[{{self.name}}] Starting — template: {{self.template}}")
        try:
            result = self.execute(*args, **kwargs)
            self.state = "idle"
            return result
        except Exception as e:
            self.state = "error"
            print(f"[{{self.name}}] Error: {{e}}")
            raise

    def execute(self, *args, **kwargs):
        """Override this method to implement the agent's main logic."""
        result = {{}}
{methods_code}
        return result

    def register_with_factory(self, registry=None):
        """Register this forged agent with the factory."""
        try:
            if registry is None:
                import importlib.util
                reg_path = self.workspace / "registry.py"
                spec = importlib.util.spec_from_file_location("registry", reg_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    registry = mod.Registry() if hasattr(mod, "Registry") else mod
            if registry:
                registry.register(self.name, {{
                    "type": "forged_agent",
                    "template": self.template,
                    "capabilities": self.capabilities,
                    "state": self.state,
                    "module": "{module}",
                }})
                print(f"[{{self.name}}] Registered with factory")
                return True
        except Exception as e:
            print(f"[{{self.name}}] Registration failed: {{e}}")
        return False


if __name__ == "__main__":
    agent = {name.replace("_", "")}()
    print(json.dumps({{
        "name": agent.name,
        "template": agent.template,
        "capabilities": agent.capabilities,
        "state": agent.state,
    }}, indent=2))
    agent.run()
'''

        return code

    def _generate_method(self, cap_name, template):
        """Generate a method stub for a capability."""
        # Template-specific implementations
        template_impls = {
            "scraper": {
                "fetch_url": '''        result["url"] = kwargs.get("url")
        # TODO: implement fetch — requests.get(url)
''',
                "parse_html": '''        # TODO: parse with BeautifulSoup
        result["parsed"] = True
''',
                "extract_data": '''        # TODO: extract structured data
        result["data"] = []
''',
                "save_results": '''        # TODO: save to file or database
        result["saved"] = True
''',
            },
            "monitor": {
                "check_status": '''        # TODO: check the target's status
        result["status"] = "unknown"
''',
                "compare_state": '''        # TODO: compare current vs last known state
        result["changed"] = False
''',
                "alert": '''        # TODO: send alert
        result["alerted"] = False
''',
                "log_change": '''        # TODO: log the change
        result["logged"] = True
''',
            },
        }

        impls = template_impls.get(template, {})
        body = impls.get(cap_name, f'        # TODO: implement {cap_name}\n        result["{cap_name}"] = None\n')

        return f'''
    def {cap_name}(self, *args, **kwargs):
        """Capability: {cap_name}"""
{body}'''

    def _generate_support_modules(self, spec):
        """Generate queue, memory, and view modules for the new agent."""
        module = spec["module_name"]
        name = spec["name"]
        support = {}

        # Queue module
        queue_code = f'''"""
{module}_queue — Task queue for {name}
Auto-generated by AgentForge
"""

import json
from datetime import datetime
from pathlib import Path


class {name.replace("_", "")}Queue:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.data_dir / "{module}_queue.json"
        self.queue = self._load()

    def _load(self):
        if self.queue_file.exists():
            return json.loads(self.queue_file.read_text())
        return []

    def _save(self):
        self.queue_file.write_text(json.dumps(self.queue, indent=2))

    def enqueue(self, task):
        item = {{"id": f"q_{{len(self.queue)+1:04d}}", "task": task, "status": "pending", "created": datetime.now().isoformat()}}
        self.queue.append(item)
        self._save()
        return item

    def dequeue(self):
        for item in self.queue:
            if item["status"] == "pending":
                item["status"] = "processing"
                self._save()
                return item
        return None

    def complete(self, task_id, result=None):
        for item in self.queue:
            if item["id"] == task_id:
                item["status"] = "completed"
                item["result"] = result
                item["completed"] = datetime.now().isoformat()
                self._save()
                return item
        return None

    def pending(self):
        return [q for q in self.queue if q["status"] == "pending"]
'''
        queue_path = self.output_dir / f"{module}_queue.py"
        queue_path.write_text(queue_code, encoding="utf-8")
        support["queue"] = str(queue_path)

        # Memory module
        mem_code = f'''"""
{module}_memory — Memory store for {name}
Auto-generated by AgentForge
"""

import json
from datetime import datetime
from pathlib import Path


class {name.replace("_", "")}Memory:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.mem_file = self.data_dir / "{module}_memory.json"
        self.memory = self._load()

    def _load(self):
        if self.mem_file.exists():
            return json.loads(self.mem_file.read_text())
        return {{"entries": []}}

    def _save(self):
        self.mem_file.write_text(json.dumps(self.memory, indent=2))

    def remember(self, key, value):
        entry = {{"key": key, "value": value, "timestamp": datetime.now().isoformat()}}
        self.memory["entries"].append(entry)
        self._save()
        return entry

    def recall(self, key):
        for entry in reversed(self.memory["entries"]):
            if entry["key"] == key:
                return entry["value"]
        return None

    def recall_all(self, key=None):
        if key:
            return [e for e in self.memory["entries"] if e["key"] == key]
        return self.memory["entries"]
'''
        mem_path = self.output_dir / f"{module}_memory.py"
        mem_path.write_text(mem_code, encoding="utf-8")
        support["memory"] = str(mem_path)

        return support

    def _register_agent(self, spec):
        """Register the forged agent with the factory registry."""
        try:
            reg_path = self.output_dir / "registry.py"
            if not reg_path.exists():
                return False

            spec_loader = importlib.util.spec_from_file_location("registry", reg_path)
            if not spec_loader or not spec_loader.loader:
                return False

            mod = importlib.util.module_from_spec(spec_loader)
            spec_loader.loader.exec_module(mod)

            if hasattr(mod, "Registry"):
                reg = mod.Registry()
                reg.register(spec["module_name"], {
                    "type": "forged_agent",
                    "template": spec["template"],
                    "capabilities": spec["capabilities"],
                    "state": "idle",
                    "module": spec["module_name"],
                })
                return True
        except Exception as e:
            print(f"[AgentForge] Registration skipped: {e}")
        return False

    def list_forged(self):
        """List all agents forged by this instance."""
        return self.forged_agents


if __name__ == "__main__":
    forge = AgentForge()
    print("AgentForge — meta agent builder")
    print(f"Templates: {', '.join(forge.TEMPLATES.keys())}")
    print(f"Forged: {len(forge.forged_agents)} agents")
