"""Test suite for the Hoolulu Factory Agent.

Run with:  .venv/bin/python -m pytest -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import brain, config, dify_export, factory, tools  # noqa: E402

_REAL_GIT = tools._git


@pytest.fixture(autouse=True)
def temp_factory(tmp_path, monkeypatch):
    """Point the whole agent at a throwaway database for every test."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", str(db))
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(config, "SYSTEM_LOG", str(tmp_path / "logs" / "system.log"))
    monkeypatch.setattr(config, "AUDIT_LOG", str(tmp_path / "logs" / "audit.log"))
    # Git tools must never touch the real repository: stub the transport and
    # record what the agent asked for.
    calls = []

    def fake_git(*git_args, timeout=30):
        calls.append(git_args)
        output = "test-branch" if git_args[:1] == ("rev-parse",) \
            else "stubbed git " + " ".join(git_args)
        return {"exit_code": 0, "output": output, "branch": "test-branch"}

    monkeypatch.setattr(tools, "_git", fake_git)
    factory.init_db()

    class Ctx:
        """Fixture handle: tmp_path rejects attribute assignment."""

    ctx = Ctx()
    ctx.path = tmp_path
    ctx.git_calls = calls
    return ctx


# ---------------------------------------------------------------- factory ---

def test_init_creates_every_table():
    info = factory.init_db()
    expected = {"leads", "tasks", "opportunities", "proposals", "clients",
                "delivery_tasks", "outreach_queue", "agent_runs"}
    assert expected.issubset(set(info["tables"]))


def test_scoring_rewards_complete_contact_details():
    thin = factory.score_lead({"business": "Bare"})
    rich = factory.score_lead({
        "business": "Kailua Poke Shack", "city": "Kailua",
        "website": "https://x.example", "phone": "808-555-0142",
        "email": "a@b.example", "notes": "no website, wants more leads",
    })
    assert rich["score"] > thin["score"]
    assert rich["status"] == "SCORED"
    assert thin["status"] == "NURTURE"
    assert rich["score"] <= 100
    assert any("buying signal" in reason for reason in rich["reasons"])


def test_full_pipeline_moves_a_lead_to_client():
    factory.add_lead("Kailua Poke Shack", industry="restaurant", city="Kailua",
                     phone="808-555-0142", notes="no website wants more leads")
    result = factory.run_pipeline()
    assert result["processed"] >= 3

    lead = factory.get_lead("Kailua Poke Shack")
    assert lead["score"] > 0
    assert lead["category"] == "restaurant"
    assert lead["message"]  # outreach was drafted

    # a positive reply books the call, then delivery makes them a client
    factory.set_lead_status("Kailua Poke Shack", "CONTACTED")
    assert factory.run_closer()["processed"] == 1
    conn = factory.connect()
    conn.execute("UPDATE leads SET reply_status='CALL_BOOKED' WHERE business='Kailua Poke Shack'")
    conn.commit()
    conn.close()

    assert factory.run_closer()["processed"] == 1
    assert factory.get_lead("Kailua Poke Shack")["status"] == "BOOKED"

    factory.run_delivery()
    assert factory.get_lead("Kailua Poke Shack")["status"] == "CLIENT"

    status = factory.factory_status()
    assert status["totals"]["clients"] == 1
    assert status["totals"]["proposals"] == 1
    assert len(status["open_tasks"]) >= 1


def test_classify_reply_reads_intent():
    assert factory.classify_reply("yes let's book a call") == "CALL_BOOKED"
    assert factory.classify_reply("sure, send info") == "INTERESTED"
    assert factory.classify_reply("no, not interested") == "NOT_INTERESTED"
    assert factory.classify_reply("maybe later?") == "NEEDS_FOLLOW_UP"


def test_outreach_message_is_personalized():
    lead = factory.add_lead("Hilo Plumbing Co", city="Hilo",
                            industry="plumbing", notes="no website")
    draft = factory.build_outreach(lead)
    assert "Hilo Plumbing Co" in draft["message"]
    assert "Hilo" in draft["message"]
    assert draft["problem"]


def test_import_csv_and_skips_blank_rows():
    csv_text = ("business,city,phone\n"
                "Sunset Tacos,Kailua,808-555-1111\n"
                "Barefoot Bakery,Honolulu,808-555-2222\n"
                ",nowhere,808-000-0000\n")
    result = factory.import_leads_csv(csv_text)
    assert result["imported"] == 2
    assert result["skipped"] == 1
    assert factory.get_lead("Sunset Tacos")["city"] == "Kailua"


def test_set_lead_status_rejects_unknown_states():
    factory.add_lead("Test Co")
    assert factory.set_lead_status("Test Co", "NOT_A_STATE")["ok"] is False
    assert factory.set_lead_status("Test Co", "BOOKED")["status"] == "BOOKED"


def test_reset_keeps_schema():
    factory.add_lead("Temp Co")
    assert factory.reset_demo(confirm=True)["ok"] is True
    assert factory.list_leads() == []
    assert "leads" in factory.init_db()["tables"]


# ------------------------------------------------------------------ tools ---

def test_every_registered_tool_is_callable():
    specs = tools.public_specs()
    assert len(specs) >= 20
    for spec in specs:
        assert callable(tools.REGISTRY[spec["name"]]["fn"])


def test_path_guard_blocks_escapes_and_protected_dirs():
    with pytest.raises(ValueError):
        tools.safe_path("../../etc/passwd")
    with pytest.raises(ValueError):
        tools.safe_path(".git/config")
    with pytest.raises(ValueError):
        tools.safe_path("data/hoolulu.db")
    assert tools.safe_path("agents/new_agent.py").endswith("agents/new_agent.py")


def test_code_write_then_read_then_patch_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(tools, "REPO_ROOT", str(tmp_path))

    written = tools.dispatch("code_write", {"path": "agents/thing.py",
                                            "content": "VALUE = 1\n"})
    assert written["ok"] and written["action"] == "created"

    read = tools.dispatch("code_read", {"path": "agents/thing.py"})
    assert "VALUE = 1" in read["content"]

    patched = tools.dispatch("code_patch", {"path": "agents/thing.py",
                                            "find": "VALUE = 1", "replace": "VALUE = 2"})
    assert patched["replacements"] == 1
    assert "VALUE = 2" in tools.dispatch("code_read", {"path": "agents/thing.py"})["content"]

    missing = tools.dispatch("code_patch", {"path": "agents/thing.py",
                                            "find": "NOT HERE", "replace": "x"})
    assert missing["ok"] is False


def test_build_agent_produces_a_runnable_module(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(config, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(tools, "REPO_ROOT", str(tmp_path))
    # the generated module imports the real `agent` package, so give it one
    shutil.copytree(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent"),
        tmp_path / "agent",
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    result = tools.dispatch("build_agent", {"name": "Review Watcher"})
    assert result["ok"] and result["compiles"] is True

    built = tmp_path / "agents" / "review_watcher.py"
    assert built.exists()
    assert "sys.path.insert" in built.read_text()

    # a second build without overwrite must refuse rather than clobber
    again = tools.dispatch("build_agent", {"name": "Review Watcher"})
    assert again["ok"] is False

    run = tools.dispatch("run_script", {"script": "agents/review_watcher.py"})
    assert run["ok"] and run["exit_code"] == 0


def test_dispatch_never_raises():
    result = tools.dispatch("does_not_exist", {})
    assert result["ok"] is False and "unknown tool" in result["error"]

    result = tools.dispatch("lead_add", {})
    assert result["ok"] is False

    result = tools.dispatch("code_read", {"path": "/etc/passwd"})
    assert result["ok"] is False


def test_repo_check_reports_broken_python(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(tools, "REPO_ROOT", str(tmp_path))
    (tmp_path / "good.py").write_text("X = 1\n")
    (tmp_path / "bad.py").write_text("def broken(:\n")

    result = tools.dispatch("repo_check", {})
    assert result["checked"] == 2
    assert result["broken_count"] == 1
    assert result["broken"][0]["path"] == "bad.py"


def test_git_commit_really_commits_in_a_throwaway_repo(tmp_path, monkeypatch):
    """git_commit must work for real — just never against this repository."""
    import subprocess

    monkeypatch.setattr(tools, "_git", _REAL_GIT)
    monkeypatch.setattr(config, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(tools, "REPO_ROOT", str(tmp_path))

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                              text=True, check=False)

    git("init", "-q")
    git("config", "user.email", "agent@hoolulu.test")
    git("config", "user.name", "Hoolulu Agent")

    (tmp_path / "note.txt").write_text("built by the agent\n")
    result = tools.dispatch("git_commit", {"message": "agent change"})
    assert result["ok"] is True, result

    log = git("log", "--oneline").stdout.strip()
    assert "agent change" in log
    # the change really landed in the commit (untracked = the agent's own
    # audit log, which the fixture writes into this same temp dir)
    assert "note.txt" in git("show", "--name-only", "--format=").stdout
    assert git("status", "--porcelain", "--untracked-files=no").stdout.strip() == ""


def test_git_tools_never_touch_the_real_repo(temp_factory):
    """The stub in the fixture must have absorbed the call."""
    result = tools.dispatch("git_status", {})
    assert result["ok"] is True
    assert result["branch"] == "test-branch"
    assert temp_factory.git_calls, "git call was not intercepted by the stub"


# ------------------------------------------------------------------ brain ---

@pytest.mark.parametrize("message,expected", [
    ("status", "factory_status"),
    ("how's the factory", "factory_status"),
    ("full report", "factory_report"),
    ("run the pipeline", "pipeline_run"),
    ("run everything", "pipeline_run"),
    ("score the leads", "pipeline_run"),
    ("enrich them", "pipeline_run"),
    ("draft outreach", "pipeline_run"),
    ("run the closer", "pipeline_run"),
    ("deliver clients", "pipeline_run"),
    ("show leads", "leads_list"),
    ("show leads status=BOOKED", "leads_list"),
    ("write the message for Kailua Poke Shack", "outreach_draft"),
    ("build me an agent called Review Watcher", "build_agent"),
    ("check the code", "repo_check"),
    ("read orchestrator.py", "code_read"),
    ("run dashboard.py", "run_script"),
    ("search for outreach_status", "code_search"),
    ("list files", "code_list"),
    ("git status", "git_status"),
    ("git log", "git_log"),
    ("commit this as wired the pipeline", "git_commit"),  # stubbed, see fixture
    ("load demo data", "seed_demo"),
    ("init the database", "factory_init"),
    ("reset the factory", "reset_factory"),
])
def test_intent_routing(message, expected):
    result = brain.LocalBrain().think(message)
    assert result["actions"], f"no action for '{message}'"
    assert result["actions"][0]["tool"] == expected


def test_stage_argument_is_correct():
    think = brain.LocalBrain().think
    assert think("score the leads")["actions"][0]["args"]["stage"] == "score"
    assert think("run the closer")["actions"][0]["args"]["stage"] == "closer"
    assert think("run the pipeline")["actions"][0]["args"]["stage"] == "all"


def test_add_lead_extracts_slots():
    result = brain.LocalBrain().think(
        'add lead "Sunset Tacos" city=Kailua phone=808-555-9999 notes=no website'
    )
    args = result["actions"][0]["args"]
    assert result["actions"][0]["ok"] is True
    assert args["business"] == "Sunset Tacos"
    assert args["city"] == "Kailua"
    assert args["phone"] == "808-555-9999"
    assert factory.get_lead("Sunset Tacos") is not None


def test_add_lead_without_quotes():
    result = brain.LocalBrain().think("add lead Barefoot Bakery in Honolulu")
    assert result["actions"][0]["args"]["business"] == "Barefoot Bakery"


def test_reply_parsing_puts_name_and_reply_in_the_right_slots():
    factory.add_lead("Kailua Poke Shack", city="Kailua")
    result = brain.LocalBrain().think('Kailua Poke Shack replied "yes lets book a call"')
    action = result["actions"][0]
    assert action["tool"] == "mark_replied"
    assert action["args"]["business"] == "Kailua Poke Shack"
    assert "yes" in action["args"]["reply"]
    assert action["result"]["signal"] == "CALL_BOOKED"
    assert factory.get_lead("Kailua Poke Shack")["status"] == "BOOKED"


def test_unknown_input_returns_helpful_text_without_crashing():
    result = brain.LocalBrain().think("asdf qwer zxcv")
    assert result["actions"] == []
    assert "status" in result["reply"]


def test_help_lists_commands():
    assert "run the pipeline" in brain.LocalBrain().think("help")["reply"]


def test_llm_falls_back_to_local_on_error():
    def boom(request, timeout=None):
        raise OSError("network down")

    offline = brain.LLMBrain(api_key="fake-key", opener=boom)
    result = offline.think("status")
    assert result["actions"][0]["tool"] == "factory_status"
    assert "local" in result["brain"]


def test_llm_brain_executes_a_tool_call():
    """Drive LLMBrain with a stub transport that asks for one tool call."""
    calls = {"n": 0}

    class FakeResponse:
        def __init__(self, payload):
            self._payload = json.dumps(payload).encode()

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_opener(request, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse({"choices": [{"message": {
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "call_1", "type": "function", "function": {
                    "name": "factory_status", "arguments": "{}"}}],
            }}]})
        return FakeResponse({"choices": [{"message": {
            "role": "assistant", "content": "The factory is online."}}]})

    llm = brain.LLMBrain(api_key="fake-key", base_url="https://fake.test/v1",
                         opener=fake_opener)
    result = llm.think("status")
    assert result["reply"] == "The factory is online."
    assert result["actions"][0]["tool"] == "factory_status"
    assert result["actions"][0]["ok"] is True
    assert result["brain"] == "llm"


def test_tool_schemas_match_the_registry():
    schemas = brain.tool_schemas()
    names = {schema["function"]["name"] for schema in schemas}
    assert names == set(tools.REGISTRY)
    for schema in schemas:
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        for required in params["required"]:
            assert required in params["properties"]


# ----------------------------------------------------------------- server ---

@pytest.fixture()
def client():
    from agent import server
    server.app.config["TESTING"] = True
    with server.app.test_client() as test_client:
        yield test_client


def test_index_and_health(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Hoolulu Factory Agent" in page.data

    health = client.get("/api/health").get_json()
    assert health["ok"] is True
    assert health["database"] == config.DB_PATH


def test_state_endpoint_exposes_tools_and_pipeline(client):
    data = client.get("/api/state").get_json()
    assert data["pipeline"] == factory.PIPELINE
    assert len(data["tools"]) >= 20
    assert "totals" in data["status"]
    assert data["status"]["totals"]["leads"] == 0


def test_chat_endpoint_runs_a_real_tool(client):
    reply = client.post("/api/chat", json={"message": "load demo data"}).get_json()
    assert reply["actions"][0]["tool"] == "seed_demo"
    assert reply["actions"][0]["ok"] is True
    assert reply["state"]["status"]["totals"]["leads"] == 6


def test_chat_endpoint_handles_empty_message(client):
    reply = client.post("/api/chat", json={"message": "  "}).get_json()
    assert "Hoolulu" in reply["reply"]


def test_tool_endpoint_rejects_bad_args(client):
    bad = client.post("/api/tool", json={"tool": "lead_add", "args": "not-an-object"})
    assert bad.status_code == 400

    unknown = client.post("/api/tool", json={"tool": "nope", "args": {}}).get_json()
    assert unknown["result"]["ok"] is False


def test_tool_endpoint_runs_a_tool(client):
    result = client.post("/api/tool", json={
        "tool": "lead_add",
        "args": {"business": "API Test Co", "city": "Hilo"},
    }).get_json()
    assert result["result"]["ok"] is True
    assert result["state"]["status"]["totals"]["leads"] == 1


def test_logs_endpoint(client):
    client.post("/api/tool", json={"tool": "factory_status", "args": {}})
    data = client.get("/api/logs").get_json()
    assert "agent" in data and "system" in data
    assert any("factory_status" in line for line in data["agent"])


# ------------------------------------------------------------ dify export ---

def test_openapi_export_covers_every_tool(tmp_path):
    result = dify_export.export(base_url="https://factory.example", out_dir=str(tmp_path))
    assert result["missing_tools"] == []
    assert result["tools_exported"] == len(tools.REGISTRY)

    spec = json.loads((tmp_path / "openapi.json").read_text())
    assert spec["openapi"].startswith("3.")
    assert spec["servers"][0]["url"] == "https://factory.example"
    for name in tools.REGISTRY:
        path = spec["paths"][f"/api/tool/{name}"]
        assert "post" in path
        assert path["post"]["operationId"] == f"hoolulu_{name}"


def test_dify_dsl_mentions_the_tools(tmp_path):
    result = dify_export.export(out_dir=str(tmp_path))
    dsl = (tmp_path / "dify-hoolulu-agent.yml").read_text()
    assert "kind: app" in dsl
    assert "mode: agent-chat" in dsl
    assert "hoolulu_pipeline_run" in dsl
    assert "hoolulu_build_agent" in dsl
    assert result["dsl"].endswith(".yml")
