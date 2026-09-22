"""The loop.

research → reasoning → approval → build → qa → package → deliver → maintain

Every stage appends one event to the loop log and hands the next stage a
validated contract. A stage either completes, blocks on a human, or fails — and
says which.
"""

from __future__ import annotations

from hub import config
from hub.approvals import GateBlocked
from hub.contracts import check
from hub.delivery import deploy as deploy_stage
from hub.factory import load_swarm, qa as qa_stage
from hub.factory import builders
from hub.market_intel.research import research as research_stage
from hub.ops import Loop
from hub.reasoning import analyze as gap_analyze
from hub.reasoning import productizer
from hub.revenue import projection
from hub.packaging import package as package_stage


def run(request: str, *, tier: str | None = None, template: str | None = None,
        slug: str | None = None, deploy: bool = True, maintain: bool = False,
        actor: str | None = None) -> dict:
    """Turn one sentence into a shipped product. Never raises."""
    config.ensure_dirs()
    tier = (tier or config.TIER).lower()
    parsed = productizer.parse_request(request, template)
    loop = Loop(new_loop_id(parsed["slug"]), actor=actor)

    result: dict = {
        "ok": False,
        "loop_id": loop.loop_id,
        "request": request,
        "tier": tier,
        "stages": [],
        "blocked": None,
    }

    # --- intake ------------------------------------------------------------
    result["stages"].append(loop.ok(
        "intake", f"“{request}” → {parsed['name']} [{parsed['template']}]",
        data={"parsed": parsed}, next=["research"]))

    # --- research ----------------------------------------------------------
    try:
        research = research_stage(request, slug=parsed["slug"],
                                  template=parsed["template"])
        result["research"] = research
        result["stages"].append(loop.ok(
            "research", f"{len(research['findings'])} findings, "
                        f"{len(research['gaps'])} gaps",
            data={"findings": len(research["findings"])}, next=["reasoning"]))
    except Exception as exc:  # noqa: BLE001 - a stage failure must not kill the run
        result["stages"].append(loop.failed("research", f"{type(exc).__name__}: {exc}"))
        result["error"] = f"research failed: {exc}"
        return result

    # --- reasoning ---------------------------------------------------------
    try:
        spec = productizer.build_spec(request, template=parsed["template"],
                                      slug=slug or parsed["slug"],
                                      name=parsed["name"], research=research)
        check("product", spec)
        gaps = gap_analyze(spec)
        spec["whitespace"] = gaps
        spec["projection"] = projection(spec)
        result["spec"] = spec
        result["stages"].append(loop.ok(
            "reasoning",
            f"{spec['name']} · sell {spec['scores']['sellability']} · "
            f"scale {spec['scores']['scalability']} · "
            f"whitespace {gaps['differentiation_score']}%",
            data={"scores": spec["scores"], "provenance": spec["provenance"]},
            model=spec["provenance"].get("model"),
            next=["build"]))
    except Exception as exc:  # noqa: BLE001
        result["stages"].append(loop.failed("reasoning", f"{type(exc).__name__}: {exc}"))
        result["error"] = f"reasoning failed: {exc}"
        return result

    # --- build -------------------------------------------------------------
    try:
        build = builders.build(spec)
        result["build"] = build
        result["stages"].append(loop.ok(
            "build", f"{len(build['artifacts'])} files in builds/{build['slug']} "
                     f"({build['duration_ms']} ms)",
            data={"artifacts": len(build["artifacts"])}, next=["qa"]))
    except Exception as exc:  # noqa: BLE001
        result["stages"].append(loop.failed("build", f"{type(exc).__name__}: {exc}"))
        result["error"] = f"build failed: {exc}"
        return result

    # --- qa ----------------------------------------------------------------
    min_score = _qa_threshold()
    scored = qa_stage.gate(config.BUILD_ROOT / build["slug"], min_score=min_score)
    build["checks"] = scored["checks"]
    result["qa"] = scored
    if not scored["allowed"]:
        result["stages"].append(loop.failed(
            "qa", f"score {scored['score']}/100 below the {min_score} gate",
            data={"score": scored["score"]}))
        result["error"] = (f"QA scored {scored['score']}/100, below the {min_score} "
                           f"gate — nothing was released")
        return result
    result["stages"].append(loop.ok(
        "qa", f"score {scored['score']}/100", data={"score": scored["score"]},
        next=["package"]))

    # --- package -----------------------------------------------------------
    try:
        manifest = package_stage(build["slug"], qa=scored)
        result["package"] = manifest
        result["stages"].append(loop.ok(
            "package", f"{manifest['package']} ({manifest['package_bytes']:,} bytes)",
            data={"sha256": manifest["package_sha256"][:12]}, next=["deliver"]))
    except Exception as exc:  # noqa: BLE001
        result["stages"].append(loop.failed("package", f"{type(exc).__name__}: {exc}"))
        result["error"] = f"packaging failed: {exc}"
        return result

    # --- deliver -----------------------------------------------------------
    if not deploy:
        result["stages"].append(loop.event(
            "deliver", "skipped", "build packaged but not released (deploy=False)"))
        result["ok"] = True
        return result

    try:
        record = deploy_stage(
            build["slug"], tier=tier, qa=scored,
            evidence=[config.BUILD_ROOT / build["slug"] / "manifest.json"])
        result["deployment"] = record
        result["stages"].append(loop.ok(
            "deliver", f"live at {record['url']}", data={"url": record["url"]},
            next=["maintain" if maintain else "idle"]))
    except GateBlocked as blocked:
        result["blocked"] = blocked.approval
        result["stages"].append(loop.blocked(
            "deliver", f"{blocked.approval['action']} needs a human "
                       f"(approval {blocked.approval['id']})",
            data={"approval": blocked.approval["id"]}, next=["approval"]))
        result["ok"] = True  # built and packaged; only the release is waiting
        return result
    except Exception as exc:  # noqa: BLE001
        result["stages"].append(loop.failed("deliver", f"{type(exc).__name__}: {exc}"))
        result["error"] = f"delivery failed: {exc}"
        return result

    if maintain:
        result["maintenance"] = maintain_all(loop=loop)

    result["ok"] = True
    return result


def format_run(result: dict) -> str:
    """One readable summary of a whole loop."""
    lines = []
    spec = result.get("spec") or {}
    if spec:
        scores = spec.get("scores", {})
        name = str(spec.get("name", "?"))
        one_liner = str(spec.get("one_liner", "")).strip()
        header = one_liner if one_liner.lower().startswith(name.lower()) \
            else f"{name} — {one_liner}".strip(" —")
        lines.append(header)
        lines.append(
            f"  sell {scores.get('sellability', '?')} · "
            f"scale {scores.get('scalability', '?')} · "
            f"build {scores.get('buildability', '?')} · "
            f"whitespace {(spec.get('whitespace') or {}).get('differentiation_score', '?')}%"
            f"  [{spec.get('provenance', {}).get('source', '?')}]")
        money = spec.get("monetization", {})
        lines.append(f"  money: {money.get('model', '?')} — "
                     f"${money.get('price_usd', 0)}/{money.get('unit', '?')}")
        projection = spec.get("projection") or {}
        if projection:
            lines.append(f"  projection: ${projection['projection']['month_1_usd']:,.0f} "
                         f"in month 1 → ${projection['projection']['month_12_usd']:,.0f} "
                         f"by month 12 (assumptions, not measurements)")

    build = result.get("build") or {}
    if build:
        lines.append(f"  built: builds/{build.get('slug')} "
                     f"({len(build.get('artifacts', []))} files, "
                     f"{build.get('duration_ms')} ms)")
    qa = result.get("qa")
    if qa is not None:
        lines.append(f"  qa: {qa['score']}/100 "
                     f"{'✓' if qa.get('allowed') else '✗ below gate'}")
    manifest = result.get("package")
    if manifest:
        lines.append(f"  package: {manifest.get('package')} "
                     f"({manifest.get('package_bytes', 0):,} bytes)")
    deployment = result.get("deployment")
    if deployment:
        lines.append(f"  live: {deployment.get('url')}")

    blocked = result.get("blocked")
    if blocked:
        lines.append("")
        lines.append(f"  ⏸ {blocked['action']} is waiting on a human "
                     f"(approval {blocked['id']}, tier {blocked['tier']})")
        lines.append(f"    approve: python -m amanda gate approve {blocked['id']} "
                     f"--evidence builds/{build.get('slug', '?')}/manifest.json")

    if result.get("error"):
        lines.append("")
        lines.append(f"  ✗ {result['error']}")

    lines.append("")
    for stage in result.get("stages", []):
        mark = {"ok": "✓", "failed": "✗", "blocked": "⏸", "skipped": "–"}.get(
            stage.get("status"), "·")
        lines.append(f"  {mark} {stage['stage']:<10} {stage.get('message', '')}")
    return "\n".join(lines)


def maintain_all(*, loop: Loop | None = None, actor: str | None = None) -> dict:
    """Health check every deployment and record what was found."""
    from hub.delivery import health as deploy_health

    config.ensure_dirs()
    loop = loop or Loop(new_loop_id("maintain"), actor=actor)
    results = deploy_health()
    healthy = [name for name, record in results.items() if record["ok"]]
    broken = {name: record["problems"] for name, record in results.items()
              if not record["ok"]}

    event = (loop.ok if not broken else loop.failed)(
        "maintain",
        f"{len(healthy)} healthy, {len(broken)} unhealthy",
        data={"healthy": healthy, "broken": broken},
        next=["redeploy " + name for name in broken] if broken else ["idle"],
    )
    return {"healthy": healthy, "broken": broken, "event": event}


def new_loop_id(slug: str = "run") -> str:
    from hub.ops.events import new_loop_id as _new

    return _new(slug)


def _qa_threshold() -> int:
    """The QA score a build must clear, straight from the workforce definition."""
    try:
        swarm = load_swarm()
    except Exception:  # noqa: BLE001 - no swarm file should not block a build
        return 70
    agent = swarm.for_stage("qa")
    return agent.min_score if agent and agent.min_score else 70
