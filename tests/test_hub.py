"""Tests for the ecosystem hub and Amanda.

Everything writes to ``tmp_path``: the real factory in ``data/``, ``builds/``
and ``deployed/`` is never touched.
"""

from __future__ import annotations

import json
import zipfile

import pytest

from hub import config
from hub.approvals import gates
from hub.contracts import validate_contract
from hub.factory import builders, qa
from hub.factory.agent_factory import load_swarm
from hub.ops.events import Loop, read_events
from hub.reasoning import productizer
from hub.skills import formats

PRODUCT = {
    "slug": "test-game",
    "name": "Test Game",
    "one_liner": "A small browser game that loads instantly and plays offline.",
    "template": "web_game",
    "audience": {"who": "players", "where": "mobile web", "pain_level": 2},
    "problem": "Arcade clones are slow, ad-ridden and want an install.",
    "value_prop": "Open the link and you are playing in under a second.",
    "features": [{"name": "instant load", "why": "survives hotel wifi", "effort": "s"}],
    "mvp_scope": ["game loop", "score"],
    "monetization": {"model": "free play + tip jar", "price_usd": 0, "unit": "player",
                     "billing": "once", "first_dollar_path": "QR on a table tent"},
    "distribution": [{"channel": "QR code", "why": "foot traffic", "effort": "s"}],
    "scores": {"sellability": 60, "scalability": 70, "buildability": 80},
    "provenance": {"source": "offline-heuristic", "model": None},
}


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """Point every writable path at tmp_path."""
    monkeypatch.setattr(config, "BUILD_ROOT", tmp_path / "builds")
    monkeypatch.setattr(config, "DEPLOY_ROOT", tmp_path / "deployed")
    monkeypatch.setattr(config, "PACKAGE_ROOT", tmp_path / "packages")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(config, "APPROVALS_FILE", tmp_path / "state" / "approvals.jsonl")
    monkeypatch.setattr(config, "DEPLOYMENTS_DB", tmp_path / "state" / "deployments.json")
    monkeypatch.setattr(config, "EVENT_LOG", tmp_path / "events.jsonl")
    monkeypatch.setattr(config, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(config, "TIER", "development")
    monkeypatch.setattr(config, "OPERATOR", "tester")
    # hermetic: never reach a real (or accidentally running) model server
    monkeypatch.setattr(config, "OFFLINE_URL", "http://127.0.0.1:1/v1")
    yield tmp_path


# --------------------------------------------------------------------------
# contracts
# --------------------------------------------------------------------------

def test_product_contract_accepts_a_valid_spec():
    assert validate_contract("product", PRODUCT) == []


def test_contract_reports_missing_fields():
    broken = {**PRODUCT}
    del broken["monetization"]
    errors = validate_contract("product", broken)
    assert any("monetization" in error for error in errors)


def test_contract_rejects_bad_enum_and_range():
    spec = json.loads(json.dumps(PRODUCT))
    spec["scores"]["sellability"] = 400
    spec["monetization"]["billing"] = "fortnightly"
    errors = validate_contract("product", spec)
    assert any("maximum" in error for error in errors)
    assert any("billing" in error for error in errors)


# --------------------------------------------------------------------------
# reasoning
# --------------------------------------------------------------------------

def test_parse_request_picks_template_and_slug():
    parsed = productizer.parse_request("build me a snake game and host it")
    assert parsed["template"] == "web_game"
    assert parsed["slug"] == "snake-game"
    assert parsed["name"] == "Snake Game"
    assert parsed["wants_hosting"] is True


def test_slug_stays_short():
    parsed = productizer.parse_request("a mileage tracker for my delivery crew")
    assert len(parsed["slug"]) <= 32
    assert parsed["slug"] == "mileage-tracker-delivery-crew"


def test_build_spec_is_valid_and_deterministic():
    spec = productizer.build_spec("build me a snake game")
    assert validate_contract("product", spec) == []
    assert spec["slug"] == "snake-game"
    assert spec["provenance"]["source"] == "offline-heuristic"
    assert 0 <= spec["scores"]["sellability"] <= 100


def test_gap_engine_scores_whitespace():
    from hub.reasoning import analyze

    spec = productizer.build_spec("build me a snake game")
    gaps = analyze(spec)
    assert 0 <= gaps["differentiation_score"] <= 100
    assert isinstance(gaps["advice"], list)


# --------------------------------------------------------------------------
# build → qa → package → deploy
# --------------------------------------------------------------------------

def test_build_renders_every_placeholder():
    build = builders.build(PRODUCT)
    assert validate_contract("build", build) == []
    target = config.BUILD_ROOT / "test-game"
    assert (target / "index.html").is_file()
    assert (target / "app.js").is_file()
    assert (target / "style.css").is_file()
    assert (target / "product.json").is_file()

    text = (target / "index.html").read_text()
    assert "{{" not in text
    assert "Test Game" in text


def test_qa_passes_a_clean_build_and_flags_a_broken_one():
    builders.build(PRODUCT)
    result = qa.gate(config.BUILD_ROOT / "test-game", min_score=70)
    assert result["score"] == 100
    assert result["allowed"] is True
    names = {check["name"] for check in result["checks"]}
    assert {"entry", "references", "offline", "html", "placeholders"} <= names

    # a build that reaches out to the network must fail the offline rule
    (config.BUILD_ROOT / "test-game" / "index.html").write_text(
        '<html><title>x</title><script src="https://cdn.example.com/a.js"></script>'
        '</html>')
    result = qa.gate(config.BUILD_ROOT / "test-game", min_score=70)
    assert result["allowed"] is False
    assert any(not check["ok"] and check["name"] == "offline"
               for check in result["checks"])


def test_package_writes_a_zip_and_manifest():
    from hub.packaging import manifest_for, package

    builders.build(PRODUCT)
    manifest = package("test-game", qa={"score": 100})
    zip_path = config.PACKAGE_ROOT / "test-game-1.0.0.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as archive:
        assert "index.html" in archive.namelist()
        assert "manifest.json" in archive.namelist()
    assert manifest["package_sha256"]
    assert manifest_for("test-game")["artifacts"]


def test_deploy_registers_and_health_checks():
    from hub.delivery import deploy, get, health, list_deployments

    builders.build(PRODUCT)
    record = deploy("test-game", tier="development", qa={"score": 100})
    assert validate_contract("delivery", record) == []
    assert record["status"] == "live"
    assert (config.DEPLOY_ROOT / "test-game" / "index.html").is_file()
    assert get("test-game")["slug"] == "test-game"
    assert health("test-game")["test-game"]["ok"] is True
    assert [r["slug"] for r in list_deployments()] == ["test-game"]


# --------------------------------------------------------------------------
# guardrails
# --------------------------------------------------------------------------

def test_only_production_release_is_gated():
    assert gates.is_gated("release_to_production", tier="production") is True
    assert gates.is_gated("release_to_production", tier="development") is False
    assert gates.is_gated("change_price", tier="development") is True
    assert gates.is_gated("release_to_development", tier="development") is False


def test_production_release_blocks_then_consumes_an_approval():
    from hub.delivery import deploy

    builders.build(PRODUCT)
    with pytest.raises(gates.GateBlocked) as blocked:
        deploy("test-game", tier="production")
    approval = blocked.value.approval
    assert approval["status"] == "pending"
    assert gates.pending()

    gates.approve(approval["id"], evidence=["builds/test-game/manifest.json"])

    record = deploy("test-game", tier="production")
    assert record["tier"] == "production"
    assert not gates.pending()


def test_approval_without_evidence_is_refused_in_production():
    from hub.delivery import deploy

    builders.build(PRODUCT)
    with pytest.raises(gates.GateBlocked):
        deploy("test-game", tier="production")
    approval = gates.pending()[0]
    gates.approve(approval["id"], evidence=[])
    with pytest.raises(gates.GateBlocked) as blocked:
        deploy("test-game", tier="production")
    assert blocked.value.approval["status"] == "evidence-required"


# --------------------------------------------------------------------------
# the swarm
# --------------------------------------------------------------------------

def test_swarm_loads_the_workforce():
    swarm = load_swarm()
    assert len(swarm) >= 4
    assert swarm.for_stage("qa").role == "qa_engineer"
    assert swarm.for_stage("build").role == "rapid_prototyper"
    assert [a.name for a in swarm.gated()] == ["Ship808"]
    assert swarm.for_stage("qa").min_score >= 70


# --------------------------------------------------------------------------
# offline brain
# --------------------------------------------------------------------------

def test_offline_health_degrades_without_crashing():
    from hub.offline import health

    status = health()
    assert "ok" in status
    assert status["url"] == config.OFFLINE_URL


def test_json_parsing_tolerates_fences():
    from hub.offline.provider import parse_json_object

    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('sure: {"a": 1} hope that helps') == {"a": 1}
    assert parse_json_object("no json here") is None


# --------------------------------------------------------------------------
# loop log
# --------------------------------------------------------------------------

def test_loop_log_is_append_only():
    loop = Loop("test-loop")
    loop.ok("intake", "first")
    loop.failed("build", "nope")
    events = read_events(config.EVENT_LOG)
    assert [event["stage"] for event in events] == ["intake", "build"]
    assert [event["status"] for event in events] == ["ok", "failed"]
    assert loop.events()[0]["loop_id"] == "test-loop"


# --------------------------------------------------------------------------
# skills
# --------------------------------------------------------------------------

def _make_pack(root, kind):
    root.mkdir(parents=True, exist_ok=True)
    if kind == "claude":
        (root / "SKILL.md").write_text(
            "---\nname: pdf-tables\ndescription: Pull tables out of PDFs.\n---\n"
            "# PDF Tables\n\nDo the thing.\n")
        (root / "scripts").mkdir()
        (root / "scripts" / "extract.py").write_text("print('hi')\n")
    elif kind == "openclaw":
        (root / "openclaw.yaml").write_text("name: oc-notifier\ndescription: Notify.\n")
        (root / "SKILL.md").write_text("# Notifier\n")
    elif kind == "soul":
        (root / "SOUL.md").write_text("# Kaimana\n\nA calm local guide.\n")
    elif kind == "mcp":
        (root / "mcp.json").write_text(json.dumps(
            {"mcpServers": {"tide": {"description": "Tide tables"}}}))
        (root / "scripts").mkdir()
        (root / "scripts" / "tide.py").write_text("print('tide')\n")
    elif kind == "agentscope":
        (root / "agentscope.yaml").write_text(
            "agentscope:\n  toolkit: reef\nname: reef-scan\ndescription: Reef scan\n")
    return root


@pytest.mark.parametrize("kind,detected", [
    ("claude", "claude"), ("openclaw", "openclaw"), ("soul", "soul"),
    ("mcp", "mcp-server"), ("agentscope", "agentscope"),
])
def test_import_detects_every_format(tmp_path, kind, detected):
    pack = _make_pack(tmp_path / f"src-{kind}", kind)
    report = formats.import_skill(pack)
    assert report["ok"] is True
    assert report["source_format"] == detected
    assert (config.SKILLS_DIR / report["name"] / "skill.yaml").is_file()
    assert formats.list_skills()


def test_import_refuses_to_clobber_without_force(tmp_path):
    pack = _make_pack(tmp_path / "src", "claude")
    formats.import_skill(pack)
    with pytest.raises(formats.SkillError):
        formats.import_skill(pack)
    assert formats.import_skill(pack, force=True)["ok"] is True


def test_import_accepts_a_zip(tmp_path):
    pack = _make_pack(tmp_path / "src", "claude")
    archive = tmp_path / "clawhub-skill.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        for path in pack.rglob("*"):
            if path.is_file():
                zip_file.write(path, path.relative_to(pack.parent))
    report = formats.import_skill(archive)
    assert report["name"] == "pdf-tables"
    assert (config.SKILLS_DIR / "pdf-tables" / "scripts" / "extract.py").is_file()


def test_export_round_trips_through_every_format(tmp_path):
    _make_pack(tmp_path / "src", "claude")
    formats.import_skill(tmp_path / "src", name="pdf-tools")
    out = tmp_path / "exports"
    for name in formats.FORMATS_BY_NAME:
        report = formats.export_skill("pdf-tools", name, out=out)
        assert report["ok"] is True, name
        target = out / ("pdf-tools-mcp" if name == "mcp-server" else "pdf-tools")
        assert target.is_dir(), name
        if name != "mcp-server":
            assert (target / "SKILL.md").is_file()
    # a claude export re-imports cleanly (its own directory, so the markus
    # export above cannot shadow it in detection)
    claude_dir = tmp_path / "claude-out"
    formats.export_skill("pdf-tools", "claude", out=claude_dir)
    again = formats.import_skill(claude_dir / "pdf-tools", name="pdf-tools-2")
    assert again["source_format"] == "claude"


def test_export_drops_the_source_manifest(tmp_path):
    _make_pack(tmp_path / "src", "mcp")
    formats.import_skill(tmp_path / "src")
    out = tmp_path / "out"
    formats.export_skill("tide", "markus", out=out)
    assert (out / "tide" / "skill.yaml").is_file()
    assert not (out / "tide" / "mcp.json").exists()
    assert (out / "tide" / "scripts" / "tide.py").is_file()


def test_unknown_source_is_reported(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(formats.UnknownFormat):
        formats.import_skill(tmp_path / "empty")


# --------------------------------------------------------------------------
# Amanda
# --------------------------------------------------------------------------

def test_amanda_routes_and_builds(tmp_path):
    from amanda import brain

    result = brain.handle("build me a snake game and host it", use_model=False)
    assert result["intent"] == "build"
    assert "snake-game" in result["reply"]
    assert (config.DEPLOY_ROOT / "snake-game" / "index.html").is_file()


def test_amanda_answers_status_and_doctor():
    from amanda import brain

    assert brain.handle("status", use_model=False)["reply"]
    assert "FACTORY STATUS" in brain.handle("doctor", use_model=False)["reply"]


def test_amanda_tools_are_dispatchable():
    from amanda import tools

    assert tools.dispatch("status")["ok"] is True
    assert tools.dispatch("maintain")["ok"] is True
    assert tools.dispatch("swarm")["ok"] is True
    assert tools.dispatch("nope")["ok"] is False


def test_full_run_produces_a_deployed_product(tmp_path):
    from amanda import orchestrator

    result = orchestrator.run("build me a snake game and host it",
                              deploy=True, maintain=True)
    assert result["ok"] is True
    assert result["deployment"]["status"] == "live"
    assert result["qa"]["score"] >= 70
    assert result["maintenance"]["healthy"] == ["snake-game"]
    stages = [stage["stage"] for stage in result["stages"]]
    assert stages[:4] == ["intake", "research", "reasoning", "build"]
