"""Amanda's hands.

Every tool returns the same shape — ``{ok, text, data}`` — so the CLI, the web
API and the LLM-facing registry are three views of one implementation.
"""

from __future__ import annotations

from hub import config
from . import orchestrator

# --------------------------------------------------------------------------


def tool_status(args=None) -> dict:
    from hub.approvals import pending
    from hub.delivery import list_deployments
    from hub.offline import status_line
    from hub.skills import list_skills

    config.ensure_dirs()
    deployments = list_deployments()
    waiting = pending()
    builds = sorted(p.name for p in config.BUILD_ROOT.glob("*")
                    if p.is_dir()) if config.BUILD_ROOT.exists() else []
    lines = [
        f"brain       : {status_line()}",
        f"tier        : {config.TIER}",
        f"deployments : {len(deployments)}",
    ]
    for record in deployments:
        lines.append(f"   {record['slug']:<20} {record.get('status', '?'):<10} "
                     f"{record.get('url', '')}")
    lines.append(f"builds      : {', '.join(builds) if builds else 'none'}")
    lines.append(f"approvals   : {len(waiting)} waiting")
    for record in waiting:
        lines.append(f"   {record['id']}  {record['action']}  "
                     f"{record.get('slug') or '-'}")
    lines.append(f"skills      : {len(list_skills())} installed")
    return {"ok": True, "text": "\n".join(lines),
            "data": {"deployments": deployments, "builds": builds,
                     "approvals": waiting}}


def tool_doctor(args=None) -> dict:
    from hub.ops import doctor, format_doctor

    result = doctor()
    return {"ok": result["ok"], "text": format_doctor(result), "data": result}


def tool_maintain(args=None) -> dict:
    outcome = orchestrator.maintain_all()
    healthy = outcome["healthy"]
    broken = outcome["broken"]
    lines = [f"maintenance: {len(healthy)} healthy, {len(broken)} unhealthy"]
    for name in healthy:
        lines.append(f"   ✓ {name}")
    for name, problems in broken.items():
        lines.append(f"   ✗ {name}: {', '.join(problems)}")
    if broken:
        lines.append("   redeploy with: python -m amanda deploy <slug>")
    return {"ok": not broken, "text": "\n".join(lines), "data": outcome}


def tool_swarm(args=None) -> dict:
    from hub.factory import format_swarm, load_swarm

    try:
        swarm = load_swarm()
        return {"ok": True, "text": format_swarm(swarm),
                "data": {"agents": [str(a) for a in swarm.agents]}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": f"swarm unavailable: {exc}", "data": {}}


def tool_spec(args=None) -> dict:
    from hub.market_intel.research import research as research_stage
    from hub.reasoning import analyze, build_spec, format_spec
    from hub.reasoning.productizer import parse_request

    message = (args or {}).get("message", "").strip()
    if not message:
        return {"ok": False, "text": "Tell me what to scope, e.g. "
                                     "`spec a booking page for a surf school`"}
    parsed = parse_request(message)
    research = research_stage(message, slug=parsed["slug"],
                              template=parsed["template"])
    spec = build_spec(message, template=parsed["template"], slug=parsed["slug"],
                      name=parsed["name"], research=research)
    gaps = analyze(spec)
    text = "\n".join([
        format_spec(spec),
        "",
        f"whitespace  : {gaps['differentiation_score']}% of known needs covered",
    ] + [f"   · {advice}" for advice in gaps["advice"]])
    return {"ok": True, "text": text, "data": {"spec": spec, "whitespace": gaps}}


def tool_build(args=None) -> dict:
    message = (args or {}).get("message", "").strip()
    if not message:
        return {"ok": False, "text": "Tell me what to build, e.g. "
                                     "`build me a snake game and host it`"}
    result = orchestrator.run(
        message,
        tier=(args or {}).get("tier"),
        template=(args or {}).get("template"),
        slug=(args or {}).get("slug"),
        deploy=bool((args or {}).get("deploy", True)),
        maintain=bool((args or {}).get("maintain", False)),
    )
    return {"ok": result.get("ok", False), "text": orchestrator.format_run(result),
            "data": result}


def tool_deploy(args=None) -> dict:
    from hub.approvals import GateBlocked
    from hub.delivery import deploy as deploy_one

    slug = (args or {}).get("slug", "").strip()
    if not slug:
        return {"ok": False, "text": "Which build? e.g. `deploy snake-game`"}
    tier = (args or {}).get("tier") or config.TIER
    try:
        record = deploy_one(slug, tier=tier)
        return {"ok": True, "text": f"✓ {slug} live at {record['url']} [{tier}]",
                "data": record}
    except GateBlocked as blocked:
        approval = blocked.approval
        lines = [f"⏸ {blocked}"]
        if approval.get("status") == "evidence-required":
            lines.append("   production releases need trace evidence — a manifest, a "
                         "test result, a screenshot, anything on disk:")
            lines.append(f"   python -m amanda gate approve {approval['id']} "
                         f"--evidence builds/{slug}/manifest.json")
        else:
            lines.append(f"   python -m amanda gate approve {approval['id']} "
                         f"--evidence builds/{slug}/manifest.json")
            lines.append(f"   (slug {slug}, tier {tier})")
        return {"ok": False, "text": "\n".join(lines),
                "data": {"blocked": approval}}
    except FileNotFoundError as exc:
        return {"ok": False, "text": str(exc), "data": {}}


def tool_undeploy(args=None) -> dict:
    from hub.delivery import undeploy

    slug = (args or {}).get("slug", "").strip()
    if not slug:
        return {"ok": False, "text": "Which deployment? e.g. `undeploy snake-game`"}
    done = undeploy(slug)
    return {"ok": done,
            "text": f"✓ {slug} taken down (snapshot kept)" if done
                    else f"nothing deployed as {slug}",
            "data": {}}


def tool_gate_list(args=None) -> dict:
    from hub.approvals import format_pending, pending

    waiting = pending()
    return {"ok": True, "text": format_pending(), "data": waiting}


def tool_gate_approve(args=None) -> dict:
    from hub.approvals import approve

    approval_id = (args or {}).get("id", "").strip()
    if not approval_id:
        return {"ok": False, "text": "Which approval id? (`gate list` shows them)"}
    evidence = [e for e in str((args or {}).get("evidence", "")).split(",") if e.strip()]
    note = (args or {}).get("note", "")
    try:
        record = approve(approval_id, evidence=evidence or None, note=note)
    except KeyError:
        return {"ok": False, "text": f"no approval '{approval_id}'"}
    return {"ok": True,
            "text": f"✓ approved {record['action']} for {record.get('slug') or '-'} "
                    f"(evidence: {', '.join(record['evidence']) or 'none'})",
            "data": record}


def tool_gate_reject(args=None) -> dict:
    from hub.approvals import reject

    approval_id = (args or {}).get("id", "").strip()
    note = (args or {}).get("note", "")
    if not approval_id:
        return {"ok": False, "text": "Which approval id?"}
    try:
        record = reject(approval_id, note=note)
    except KeyError:
        return {"ok": False, "text": f"no approval '{approval_id}'"}
    return {"ok": True, "text": f"✗ rejected {record['action']} ({note or 'no reason'})",
            "data": record}


def tool_skill_list(args=None) -> dict:
    from hub.skills import list_skills

    skills = list_skills()
    if not skills:
        return {"ok": True, "text": f"No skills in {config.SKILLS_DIR}. Import one with "
                                    f"`./markus skill import <dir-or-zip>`", "data": []}
    lines = [f"{len(skills)} skill(s):"]
    for skill in skills:
        lines.append(f"   {skill['name']:<20} [{skill['source_format']}] "
                     f"{skill['description'][:70]}")
    return {"ok": True, "text": "\n".join(lines), "data": skills}


def tool_report(args=None) -> dict:
    """Everything worth knowing about what the factory has made and earned."""
    from hub.delivery import list_deployments
    from hub.revenue import actuals

    config.ensure_dirs()
    deployments = list_deployments()
    money = actuals()
    lines = [f"Factory report — {len(deployments)} deployment(s)"]
    for record in deployments:
        slug = record["slug"]
        spec_path = config.BUILD_ROOT / slug / "product.json"
        projection = ""
        if spec_path.is_file():
            import json

            spec = json.loads(spec_path.read_text())
            money_spec = spec.get("monetization", {})
            projection = (f" · {money_spec.get('model', '?')} "
                          f"${money_spec.get('price_usd', 0)}"
                          f"/{money_spec.get('unit', '?')}")
        gross = money.get(slug, {}).get("gross_usd", 0)
        lines.append(f"   {slug:<20} {record.get('status', '?'):<10}"
                     f"{projection}")
        lines.append(f"      {record.get('url', '')} · earned ${gross:,.2f}")
    if not deployments:
        lines.append("   nothing shipped yet — try: build me a snake game and host it")
    return {"ok": True, "text": "\n".join(lines),
            "data": {"deployments": deployments, "revenue": money}}


# --------------------------------------------------------------------------

TOOLS = {
    "status": {"fn": tool_status, "group": "factory", "label": "Status",
               "description": "What is deployed, built and waiting on a human.",
               "params": {}},
    "doctor": {"fn": tool_doctor, "group": "factory", "label": "Doctor",
               "description": "Health check the whole factory.", "params": {}},
    "swarm": {"fn": tool_swarm, "group": "factory", "label": "Swarm",
              "description": "Show the workforce declared in agents/factory.yaml.",
              "params": {}},
    "spec": {"fn": tool_spec, "group": "reasoning", "label": "Scope it",
             "description": "Scope and score a product idea without building it.",
             "params": {"message": "string: what to scope"}},
    "build": {"fn": tool_build, "group": "factory", "label": "Build",
              "description": "Research, scope, build, test, package and host a product.",
              "params": {"message": "string: what to build", "tier": "string",
                         "deploy": "boolean", "template": "string"}},
    "deploy": {"fn": tool_deploy, "group": "delivery", "label": "Deploy",
               "description": "Release a built product (gated in production).",
               "params": {"slug": "string: required", "tier": "string"}},
    "undeploy": {"fn": tool_undeploy, "group": "delivery", "label": "Take down",
                 "description": "Take a deployment down, keeping a snapshot.",
                 "params": {"slug": "string: required"}},
    "maintain": {"fn": tool_maintain, "group": "delivery", "label": "Maintain",
                 "description": "Health check every deployment.", "params": {}},
    "gate_list": {"fn": tool_gate_list, "group": "approvals", "label": "Waiting",
                  "description": "List actions waiting on a human.", "params": {}},
    "gate_approve": {"fn": tool_gate_approve, "group": "approvals",
                     "label": "Approve",
                     "description": "Approve a gated action with evidence.",
                     "params": {"id": "string: required",
                                "evidence": "string: comma separated paths",
                                "note": "string"}},
    "gate_reject": {"fn": tool_gate_reject, "group": "approvals", "label": "Reject",
                    "description": "Reject a gated action with a reason.",
                    "params": {"id": "string: required", "note": "string"}},
    "skill_list": {"fn": tool_skill_list, "group": "skills", "label": "Skills",
                   "description": "List installed skill packs.", "params": {}},
    "report": {"fn": tool_report, "group": "factory", "label": "Report",
               "description": "Deployments, monetization and receipts.", "params": {}},
}


def dispatch(name: str, args: dict | None = None) -> dict:
    """Run a tool by name. Never raises."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"ok": False, "text": f"unknown tool '{name}'",
                "data": {"available": sorted(TOOLS)}}
    try:
        return spec["fn"](args or {})
    except Exception as exc:  # noqa: BLE001 - a bad tool must not take Amanda down
        return {"ok": False, "text": f"{type(exc).__name__}: {exc}", "data": {}}


def public_specs() -> list[dict]:
    return [{"name": name, "group": spec["group"], "label": spec["label"],
             "description": spec["description"], "params": spec["params"]}
            for name, spec in TOOLS.items()]
