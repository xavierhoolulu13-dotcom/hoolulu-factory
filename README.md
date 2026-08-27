# Hoolulu Factory — Coding Agent Extension

This package adds a **CodingAgent** and **AgentForge** (meta agent builder) to your hoolulu-factory.

## What's inside

| File | Purpose |
|------|---------|
| `coding_agent.py` | Core coding agent — reads, writes, edits, runs, and debugs code |
| `agent_forge.py` | Meta agent builder — generates new specialized agents from specs |
| `coding_queue.py` | Task queue for coding tasks (matches your queue pattern) |
| `agent_memory.py` | Memory store (matches your memory_store pattern) |
| `coding_view.py` | View layer (matches your view pattern) |
| `coding_agent_state.py` | State machine (matches your state_machine.py pattern) |
| `freeze_factory.sh` | Freeze script — git commit + tag + tarball backup |

## Architecture

```
                    ┌─────────────┐
                    │  registry   │
                    └──────┬──────┘
                           │ registers
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴─────┐  ┌──────┴──────┐  ┌──────┴──────┐
    │CodingAgent│  │ AgentForge  │  │ Other agents│
    └─────┬─────┘  └──────┬──────┘  └─────────────┘
          │                │ forges
          │          ┌─────┴──────┐
          │          │ New Agent  │──→ new_queue.py
          │          │  module    │──→ new_memory.py
          │          └────────────┘
          │
    ┌─────┴─────────────────────────────┐
    │                                   │
┌───┴──────┐  ┌───────────┐  ┌──────────┴──┐
│coding_   │  │agent_     │  │coding_       │
│queue     │  │memory     │  │view          │
└──────────┘  └───────────┘  └──────────────┘
```

## Install

### 1. Copy the extension files into your factory

```bash
# From the hoolulu-factory directory
cp hoolulu-factory-extension/*.py .
cp hoolulu-factory-extension/freeze_factory.sh .
chmod +x freeze_factory.sh
```

### 2. Freeze the factory (stable baseline)

```bash
# Audit all files first, then freeze
bash freeze_factory.sh --audit

# Or just freeze without audit
bash freeze_factory.sh
```

This creates a git commit + tag (`v1.0-frozen-spine`) and a tarball backup.
After this, the frozen spine is locked — build forward, don't modify it.

### 3. Use the coding agent

```python
from coding_agent import CodingAgent
from coding_queue import CodingQueue
from coding_view import CodingView

# Initialize
agent = CodingAgent(workspace="/path/to/hoolulu-factory")
queue = CodingQueue()
view = CodingView(agent=agent, queue=queue)

# Register with the factory
agent.register()

# Run a coding task
result = agent.run_task("Create a Python script that fetches stock prices from Yahoo Finance")
print(view.render_task(result))

# Queue-based workflow
queue.enqueue("Build a daily price monitor", priority="high")
task = queue.dequeue()
result = agent.run_task(task["task"])
queue.complete(task["id"], result)
```

### 4. Forge new agents (the meta part)

```python
from agent_forge import AgentForge

forge = AgentForge(workspace="/path/to/hoolulu-factory")

# Forge a scraper agent
result = forge.forge("Build a stock price scraper agent that runs daily")
# → Creates: stock_price_scraper.py + stock_price_scraper_queue.py + stock_price_scraper_memory.py
# → Registers with factory registry

# Forge a monitor agent
result = forge.forge("Create a website monitor that checks for changes hourly")
# → Creates: website_monitor.py + supporting modules

# List what you've forged
print(forge.list_forged())
```

### 5. Use a forged agent

```python
from stock_price_scraper import StockPriceScraper

agent = StockPriceScraper()
agent.register_with_factory()
agent.run()
```

## State Machine

```
idle → planning → executing → testing → completed → frozen (terminal)
                                      ↓
                                   failed → retrying → planning
```

```python
from coding_agent_state import CodingAgentState

sm = CodingAgentState()
sm.on("completed", lambda old, new: print("Task done!"))
sm.transition("planning")
sm.transition("executing")
sm.transition("testing")
sm.transition("completed")
sm.freeze()  # → frozen (terminal, cannot change)
```

## Integration with existing factory

The coding agent modules follow your existing patterns:
- **Queues**: `coding_queue.py` matches `cass_queue.py`, `delivery_queue.py`, etc.
- **Memory**: `agent_memory.py` matches `memory_store.py`, `client_memory.py`, etc.
- **Views**: `coding_view.py` matches `client_view.py`, `opportunity_view.py`, etc.
- **Registry**: `CodingAgent.register()` calls your `registry.py`
- **State machine**: `coding_agent_state.py` matches `state_machine.py`

To wire it into the orchestrator, add to `orchestrator.py`:

```python
from coding_agent import CodingAgent
from coding_queue import CodingQueue

# In your orchestrator setup:
coding_agent = CodingAgent(workspace=self.workspace)
coding_agent.register(self.registry)
coding_queue = CodingQueue()

# In your dispatch:
if task_type == "coding":
    coding_queue.enqueue(task)
    item = coding_queue.dequeue()
    result = coding_agent.run_task(item["task"])
    coding_queue.complete(item["id"], result)
```

## Templates available in AgentForge

- `scraper` — web scraping agents
- `monitor` — status/uptime monitoring
- `processor` — data transformation
- `scheduler` — recurring task agents
- `analyzer` — data analysis
- `generic` — custom fallback

## File Safety

The freeze script:
1. Optionally audits all `.py` files for syntax errors
2. Creates a `.gitignore` (excludes `__pycache__`, `data/`, `logs/`, `.env`)
3. Commits everything to git
4. Tags as the frozen spine
5. Creates a tarball backup in `../hoolulu-factory-backups/`

**After freezing, don't modify the frozen files.** Build new features as new modules.
To restore the baseline: `git checkout v1.0-frozen-spine`
