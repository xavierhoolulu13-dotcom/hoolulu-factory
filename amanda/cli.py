"""Amanda in your terminal.

    python -m amanda "build me a snake game and host it"   # or just: amanda build me a snake game
    python -m amanda status
    python -m amanda maintain
    python -m amanda gate list
    python -m amanda gate approve 1a2b3c4d --evidence builds/snake-game/manifest.json
    python -m amanda serve --port 8010
    python -m amanda chat
"""

from __future__ import annotations

import argparse
import sys

from hub import config
from . import brain, tools

COMMANDS = ("build", "spec", "status", "doctor", "maintain", "report", "swarm",
            "skills", "deploy", "undeploy", "gate", "serve", "chat", "help")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amanda",
        description="Amanda — the operator interface to the Hoolulu Factory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Anything that is not one of the commands above is read as a "
               "sentence, so `amanda build me a snake game` works too.")
    sub = parser.add_subparsers(dest="command")

    building = sub.add_parser("build", help="research, scope, build, test, ship")
    building.add_argument("message", nargs="+")
    building.add_argument("--tier", choices=("development", "production"))
    building.add_argument("--template", choices=("web_game", "landing_page", "tool"))
    building.add_argument("--slug")
    building.add_argument("--no-deploy", action="store_true")
    building.add_argument("--maintain", action="store_true")

    scoping = sub.add_parser("spec", help="scope an idea without building it")
    scoping.add_argument("message", nargs="+")

    sub.add_parser("status", help="what is deployed, built and waiting")
    sub.add_parser("doctor", help="health check the factory")
    sub.add_parser("maintain", help="health check every deployment")
    sub.add_parser("report", help="deployments, monetization, receipts")
    sub.add_parser("swarm", help="the workforce in agents/factory.yaml")
    sub.add_parser("skills", help="installed skill packs")

    deploying = sub.add_parser("deploy", help="release a built product")
    deploying.add_argument("slug")
    deploying.add_argument("--tier", choices=("development", "production"))

    undoing = sub.add_parser("undeploy", help="take a deployment down")
    undoing.add_argument("slug")

    gate = sub.add_parser("gate", help="the human gate")
    gate_actions = gate.add_subparsers(dest="gate_action", required=True)
    gate_actions.add_parser("list", help="what is waiting")
    approving = gate_actions.add_parser("approve", help="approve with evidence")
    approving.add_argument("id")
    approving.add_argument("--evidence", default="",
                           help="comma separated paths to artifacts")
    approving.add_argument("--note", default="")
    rejecting = gate_actions.add_parser("reject", help="reject with a reason")
    rejecting.add_argument("id")
    rejecting.add_argument("--note", default="")

    serving = sub.add_parser("serve", help="run the web interface")
    serving.add_argument("--port", type=int, default=None)
    serving.add_argument("--host", default=None)

    sub.add_parser("chat", help="interactive REPL")
    sub.add_parser("help", help="what Amanda can do")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    config.ensure_dirs()

    # not a known command → read the whole line as a sentence
    if not argv or argv[0].startswith("-") or argv[0] not in COMMANDS:
        return _say(" ".join(argv))

    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command

    if command == "help":
        print(brain.HELP)
        return 0
    if command == "chat":
        return chat()
    if command == "serve":
        return serve(port=args.port, host=args.host)

    if command in ("build", "spec"):
        message = " ".join(args.message)
        slots = {"message": message}
        if command == "build":
            slots.update({"deploy": not args.no_deploy})
            for key in ("tier", "template", "slug", "maintain"):
                value = getattr(args, key, None)
                if value is not None:
                    slots[key] = value
        return _run(command, slots)

    if command == "deploy":
        slots = {"slug": args.slug}
        if args.tier:
            slots["tier"] = args.tier
        return _run("deploy", slots)
    if command == "undeploy":
        return _run("undeploy", {"slug": args.slug})
    if command == "gate":
        action = args.gate_action
        if action == "list":
            return _run("gate_list", {})
        if action == "approve":
            return _run("gate_approve", {"id": args.id, "evidence": args.evidence,
                                         "note": args.note})
        return _run("gate_reject", {"id": args.id, "note": args.note})
    if command == "skills":
        return _run("skill_list", {})
    return _run(command, {})


def _run(tool_name: str, slots: dict) -> int:
    outcome = tools.dispatch(tool_name, slots)
    print(outcome.get("text", ""))
    return 0 if outcome.get("ok", True) else 1


def _say(message: str) -> int:
    """Free text: let Amanda route it."""
    if not message.strip():
        print(brain.HELP)
        return 0
    result = brain.handle(message)
    print(result["reply"])
    return 0


def chat() -> int:
    print(brain.HELP)
    print("\n(type 'quit' to leave)\n")
    while True:
        try:
            message = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 🤙")
            return 0
        if message.lower() in ("quit", "exit", "q"):
            print("bye 🤙")
            return 0
        if not message:
            continue
        result = brain.handle(message)
        marker = {"deterministic": "·", "offline-model": "◆"}.get(result["brain"], "·")
        print(f"amanda {marker} {result['reply']}\n")


def serve(*, port: int | None = None, host: str | None = None) -> int:
    from . import server

    if port:
        config.PORT = port
    if host:
        config.HOST = host
    server.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
