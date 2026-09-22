"""
CodingAgent — Autonomous code generation, editing, and execution agent.

Plugs into the hoolulu-factory architecture:
  - Registers with registry.py
  - Pulls tasks from coding_queue.py
  - Stores context in agent_memory.py
  - Reports through coding_view.py
  - State managed by coding_agent_state.py

Usage:
    from coding_agent import CodingAgent
    agent = CodingAgent()
    agent.run_task("Create a Python script that scrapes stock prices")
"""

import os
import sys
import json
import subprocess
import traceback
import importlib.util
from pathlib import Path
from datetime import datetime


class CodingAgent:
    """An autonomous coding agent that can write, edit, test, and deploy code."""

    def __init__(self, workspace=None, name="coding_agent"):
        self.name = name
        self.workspace = Path(workspace or os.getcwd())
        self.version = "1.0.0"
        self.capabilities = [
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
            "run_code",
            "debug_code",
            "create_module",
            "refactor_module",
            "forge_agent",  # meta capability — delegates to AgentForge
        ]
        self.state = "idle"
        self.memory = {}
        self.task_history = []
        self._forge = None  # lazy-loaded AgentForge

    # ─── Lifecycle ───────────────────────────────────────────────

    def register(self, registry=None):
        """Register this agent with the factory's service registry."""
        reg = registry or self._get_registry()
        if reg:
            reg.register(self.name, {
                "type": "coding_agent",
                "version": self.version,
                "capabilities": self.capabilities,
                "state": self.state,
                "module": "coding_agent",
            })
            print(f"[{self.name}] Registered with factory registry")
        return self

    def start(self):
        """Transition to active state."""
        self.state = "active"
        print(f"[{self.name}] Agent started — state: {self.state}")

    def stop(self):
        """Transition to idle state."""
        self.state = "idle"
        print(f"[{self.name}] Agent stopped — state: {self.state}")

    # ─── Task Execution ──────────────────────────────────────────

    def run_task(self, task_description, context=None):
        """
        Main entry point — accepts a natural-language coding task and executes it.
        Returns a task result dict.
        """
        self.start()
        task_id = f"task_{len(self.task_history) + 1:04d}"
        task = {
            "id": task_id,
            "description": task_description,
            "context": context or {},
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "steps": [],
            "result": None,
            "error": None,
        }

        try:
            # Parse the task into steps
            steps = self._plan_task(task_description, context)
            task["steps"] = steps

            # Execute each step
            for i, step in enumerate(steps):
                step["status"] = "running"
                self._log(task_id, f"Step {i+1}: {step['action']} — {step.get('detail', '')}")

                result = self._execute_step(step)
                step["result"] = result
                step["status"] = "completed" if result.get("ok") else "failed"

                if not result.get("ok") and step.get("required", True):
                    raise RuntimeError(f"Step failed: {result.get('error')}")

            task["status"] = "completed"
            task["result"] = {"ok": True, "steps_completed": len(steps)}
            self._remember(task)

        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)
            task["traceback"] = traceback.format_exc()
            self._log(task_id, f"FAILED: {e}")

        task["completed_at"] = datetime.now().isoformat()
        self.task_history.append(task)
        self.stop()
        return task

    def _plan_task(self, description, context=None):
        """
        Break a task description into executable steps.
        Override or extend this for more sophisticated planning.
        """
        desc_lower = description.lower().strip()
        steps = []

        # Detect task type and build a plan
        if desc_lower.startswith("create") or desc_lower.startswith("build") or desc_lower.startswith("make"):
            steps.append({"action": "create_module", "detail": description, "required": True})
            steps.append({"action": "run_code", "detail": "Verify the module runs", "required": False})

        elif desc_lower.startswith("edit") or desc_lower.startswith("fix") or desc_lower.startswith("update"):
            target = context.get("target_file") if context else None
            steps.append({"action": "read_file", "detail": f"Read {target or 'target file'}", "required": True})
            steps.append({"action": "edit_file", "detail": description, "required": True})

        elif desc_lower.startswith("forge") or desc_lower.startswith("spawn"):
            steps.append({"action": "forge_agent", "detail": description, "required": True})

        elif desc_lower.startswith("debug"):
            target = context.get("target_file") if context else None
            steps.append({"action": "read_file", "detail": f"Read {target or 'target file'}", "required": True})
            steps.append({"action": "run_code", "detail": "Reproduce the error", "required": True})
            steps.append({"action": "debug_code", "detail": "Diagnose and fix", "required": True})

        elif desc_lower.startswith("read") or desc_lower.startswith("analyze"):
            steps.append({"action": "read_file", "detail": description, "required": True})

        else:
            # Generic — try to write a module
            steps.append({"action": "create_module", "detail": description, "required": True})

        return steps

    def _execute_step(self, step):
        """Execute a single step and return a result dict."""
        action = step["action"]
        detail = step.get("detail", "")

        try:
            if action == "read_file":
                path = step.get("path") or self.workspace
                return self.read_file(path)

            elif action == "write_file":
                path = step.get("path", "")
                content = step.get("content", "")
                return self.write_file(path, content)

            elif action == "edit_file":
                path = step.get("path", "")
                edits = step.get("edits", [])
                return self.edit_file(path, edits)

            elif action == "list_files":
                path = step.get("path") or self.workspace
                return self.list_files(path)

            elif action == "run_code":
                file_path = step.get("path", "")
                return self.run_code(file_path)

            elif action == "debug_code":
                return self.debug_code(step.get("path", ""), step.get("error", ""))

            elif action == "create_module":
                return self.create_module(detail, step.get("path"), step.get("context"))

            elif action == "refactor_module":
                return self.refactor_module(step.get("path", ""), detail)

            elif action == "forge_agent":
                return self.forge_agent(detail, step.get("context"))

            else:
                return {"ok": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}

    # ─── Capabilities ───────────────────────────────────────────

    def read_file(self, path):
        """Read a file or list a directory."""
        p = Path(path)
        if p.is_file():
            content = p.read_text(encoding="utf-8", errors="replace")
            self._stash_memory(f"read:{p}", content[:5000])
            return {"ok": True, "path": str(p), "content": content, "lines": len(content.splitlines())}
        elif p.is_dir():
            items = [str(f) for f in p.rglob("*") if f.is_file()][:200]
            return {"ok": True, "path": str(p), "files": items}
        else:
            return {"ok": False, "error": f"Path not found: {p}"}

    def write_file(self, path, content):
        """Write content to a file, creating directories as needed."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self._stash_memory(f"write:{p}", {"lines": len(content.splitlines()), "bytes": len(content)})
        return {"ok": True, "path": str(p), "lines": len(content.splitlines())}

    def edit_file(self, path, edits):
        """
        Apply a list of edits to a file.
        Each edit: {"find": "old text", "replace": "new text"} or
                   {"line": N, "replace": "new text"}
        """
        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {p}"}

        content = p.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        applied = 0

        for edit in edits:
            if "find" in edit:
                old = edit["find"]
                new = edit.get("replace", "")
                if old in content:
                    content = content.replace(old, new, 1)
                    applied += 1
                else:
                    return {"ok": False, "error": f"Pattern not found: {old[:80]}"}
            elif "line" in edit:
                idx = edit["line"] - 1
                if 0 <= idx < len(lines):
                    lines[idx] = edit["replace"] + ("\n" if not lines[idx].endswith("\n") else "")
                    applied += 1
                else:
                    return {"ok": False, "error": f"Line {edit['line']} out of range"}

        if any("line" in e for e in edits):
            content = "".join(lines)

        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "edits_applied": applied}

    def list_files(self, path=None):
        """List files in a directory."""
        p = Path(path or self.workspace)
        if not p.exists():
            return {"ok": False, "error": f"Path not found: {p}"}
        items = []
        for f in sorted(p.rglob("*")):
            if f.is_file() and "__pycache__" not in str(f) and ".git" not in str(f):
                items.append({
                    "path": str(f.relative_to(p)),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
        return {"ok": True, "path": str(p), "files": items}

    def run_code(self, file_path):
        """Run a Python file and capture output."""
        p = Path(file_path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {p}"}

        try:
            result = subprocess.run(
                [sys.executable, str(p)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(p.parent) if p.parent.exists() else None,
            )
            return {
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout[-5000:] if result.stdout else "",
                "stderr": result.stderr[-5000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Execution timed out (60s limit)"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def debug_code(self, file_path, error_msg=""):
        """Attempt to diagnose and fix a code error."""
        read_result = self.read_file(file_path)
        if not read_result.get("ok"):
            return read_result

        content = read_result["content"]
        diagnosis = []

        # Common Python error patterns
        common_issues = [
            ("IndentationError", "Check for mixed tabs/spaces or inconsistent indentation"),
            ("SyntaxError", "Check for missing colons, brackets, or quotes"),
            ("ImportError", "Check that the module exists and is in the Python path"),
            ("ModuleNotFoundError", "Install the missing package or add the path"),
            ("NameError", "Check for undefined variables — possibly a typo"),
            ("TypeError", "Check argument types and counts"),
            ("AttributeError", "Check that the object has the attribute — possibly None"),
            ("KeyError", "Check that the dict key exists before accessing"),
            ("IndexError", "Check list bounds before indexing"),
            ("FileNotFoundError", "Check the file path — use os.path.join for safety"),
        ]

        for pattern, fix in common_issues:
            if pattern.lower() in error_msg.lower():
                diagnosis.append({"error": pattern, "fix": fix})

        # Run the code to see the actual error
        run_result = self.run_code(file_path)
        if not run_result.get("ok"):
            stderr = run_result.get("stderr", "")
            for pattern, fix in common_issues:
                if pattern in stderr:
                    diagnosis.append({"error": pattern, "fix": fix, "source": "runtime"})

        return {
            "ok": True,
            "diagnosis": diagnosis,
            "run_result": run_result,
            "suggestion": diagnosis[0]["fix"] if diagnosis else "Run with verbose logging for more detail",
        }

    def create_module(self, description, path=None, context=None):
        """
        Create a new Python module based on a description.
        Generates boilerplate, function stubs, and a basic structure.
        """
        ctx = context or {}
        module_name = path or self._derive_module_name(description)
        p = Path(module_name)

        # Generate code from the description
        code = self._generate_module_code(description, p.stem, ctx)
        return self.write_file(str(p), code)

    def refactor_module(self, path, description=""):
        """Read a module and suggest/implement refactoring."""
        read_result = self.read_file(path)
        if not read_result.get("ok"):
            return read_result

        content = read_result["content"]
        suggestions = []

        # Basic refactoring checks
        lines = content.splitlines()
        if len(lines) > 500:
            suggestions.append("File is large (>500 lines) — consider splitting into submodules")
        if content.count("def ") > 20:
            suggestions.append("Many functions — consider grouping into classes")
        if "import *" in content:
            suggestions.append("Wildcard imports detected — use explicit imports")
        if content.count("    pass") > 3:
            suggestions.append("Multiple empty pass blocks — implement or remove")

        return {
            "ok": True,
            "path": str(path),
            "lines": len(lines),
            "suggestions": suggestions,
        }

    def forge_agent(self, description, context=None):
        """
        Meta capability — forge a NEW coding agent.
        Delegates to AgentForge which generates, writes, and optionally
        registers a new specialized agent module.
        """
        if self._forge is None:
            from agent_forge import AgentForge
            self._forge = AgentForge(workspace=str(self.workspace))
        return self._forge.forge(description, context or {}, parent=self.name)

    # ─── Helpers ─────────────────────────────────────────────────

    def _derive_module_name(self, description):
        """Derive a module filename from a task description."""
        words = description.lower().split()
        # Filter to alpha words, skip command words
        skip = {"create", "build", "make", "a", "an", "the", "that", "which", "script", "module", "file", "for", "to", "of"}
        filtered = [w for w in words if w.isalpha() and w not in skip]
        name = "_".join(filtered[:4]) if filtered else "new_module"
        return f"{name}.py"

    def _generate_module_code(self, description, module_name, context=None):
        """Generate Python boilerplate code for a new module."""
        ctx = context or {}
        functions = ctx.get("functions", [])
        classes = ctx.get("classes", [])

        code = f'''"""
{module_name} — Auto-generated by CodingAgent

Task: {description}
Generated: {datetime.now().isoformat()}
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime


'''

        # Generate classes
        for cls in classes or []:
            cls_name = cls.get("name", "GeneratedClass")
            methods = cls.get("methods", ["run", "process", "handle"])
            code += f"class {cls_name}:\n"
            code += f'    """{cls.get("description", "Auto-generated class")}"""\n\n'
            code += f"    def __init__(self):\n"
            code += f'        self.name = "{cls_name.lower()}"\n'
            code += f"        self.state = 'idle'\n\n"
            for method in methods:
                code += f"    def {method}(self, *args, **kwargs):\n"
                code += f"        \"\"\"TODO: implement {method}\"\"\"\n"
                code += f"        pass\n\n"
            code += "\n"

        # If no classes specified, generate functions
        if not classes:
            if not functions:
                functions = ["main"]
            for func in functions:
                code += f"def {func}(*args, **kwargs):\n"
                code += f'    """TODO: implement {func}"""\n'
                code += f"    pass\n\n"

        # Main entry point
        code += f'''
if __name__ == "__main__":
    print("[{module_name}] Starting...")
    main()
'''
        return code

    def _get_registry(self):
        """Try to load the factory's registry module."""
        try:
            spec = importlib.util.spec_from_file_location("registry", self.workspace / "registry.py")
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.Registry() if hasattr(mod, "Registry") else mod
        except Exception:
            pass
        return None

    def _stash_memory(self, key, value):
        """Store something in agent memory."""
        self.memory[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }

    def _remember(self, task):
        """Store completed task in memory for future reference."""
        self._stash_memory(task["id"], {
            "description": task["description"],
            "status": task["status"],
            "steps": len(task.get("steps", [])),
            "error": task.get("error"),
        })

    def _log(self, task_id, message):
        """Log a message."""
        print(f"[{self.name}:{task_id}] {message}")

    def status(self):
        """Return current agent status."""
        return {
            "name": self.name,
            "version": self.version,
            "state": self.state,
            "capabilities": self.capabilities,
            "tasks_completed": len(self.task_history),
            "workspace": str(self.workspace),
        }


if __name__ == "__main__":
    agent = CodingAgent()
    print(json.dumps(agent.status(), indent=2))
