"""Terminal front end for the Hoolulu Agent.

    python -m agent.cli                 interactive REPL
    python -m agent.cli "run the pipeline"
    python -m agent.cli --once "status"
"""

import sys

from . import factory
from .brain import HELP_TEXT, get_brain
from .tools import public_specs


def banner():
    brain = get_brain()
    print("=" * 46)
    print("  HOOLULU FACTORY AGENT")
    print("=" * 46)
    print(f"  brain    : {brain.name}")
    print(f"  database : {factory.config.DB_PATH}")
    print(f"  tools    : {len(public_specs())}")
    print("  type 'help' for commands, Ctrl-D to exit")
    print("=" * 46)


def run_once(message, quiet=False):
    result = get_brain().think(message)
    if not quiet:
        print(result["reply"])
    return result


def repl():
    banner()
    brain = get_brain()
    while True:
        try:
            message = input("\n🤙 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAloha 🤙")
            break
        if not message:
            continue
        if message in ("exit", "quit"):
            print("Aloha 🤙")
            break
        result = brain.think(message)
        print(result["reply"])
        for action in result.get("actions", []):
            mark = "✓" if action["ok"] else "✗"
            print(f"   {mark} {action['tool']} {action['args']}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    factory.init_db()

    if not argv:
        repl()
        return 0

    once = argv[0] in ("--once", "-1")
    args = argv[1:] if once else argv
    message = " ".join(args)

    if message in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    result = run_once(message)
    return 0 if all(a["ok"] for a in result.get("actions", [])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
