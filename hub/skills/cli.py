"""Command line for skill packs: ``markus skill …``.

    markus skill list
    markus skill import ~/Downloads/clawhub-skill.zip --force
    markus skill import ./skills/pdf-tables --name pdf-tools
    markus skill import ~/projects/agent-scope-skill --to ~/.markus/skills/my-scope
    markus skill export pdf-tools --format claude
    markus skill export pdf-tools --format openclaw --out ~/publish
    markus skill export pdf-tools --from ~/.markus/skills/pdf-tools
    markus skill formats
"""

from __future__ import annotations

import argparse
import sys

from .. import config
from . import formats as fmt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="markus", description="Hoolulu skill pack manager (markus-compatible)")
    subparsers = parser.add_subparsers(dest="group", required=True)

    skill = subparsers.add_parser("skill", help="manage skill packs")
    actions = skill.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="list installed skills")
    listing.add_argument("--dir", default=None, help="skills directory "
                                                     f"(default {config.SKILLS_DIR})")

    importing = actions.add_parser("import", help="import and normalize a skill pack")
    importing.add_argument("source", help="a directory or a .zip")
    importing.add_argument("--name", default=None, help="override the skill name")
    importing.add_argument("--to", dest="dest", default=None,
                           help=f"destination root (default {config.SKILLS_DIR})")
    importing.add_argument("--force", action="store_true",
                           help="replace an existing skill of the same name")

    exporting = actions.add_parser("export", help="export a skill to another format")
    exporting.add_argument("name", help="installed skill name")
    exporting.add_argument("--format", required=True, dest="format",
                           help="target: " + ", ".join(fmt.FORMATS_BY_NAME))
    exporting.add_argument("--out", default=None,
                           help="output directory (default ./<name>-<format>/)")
    exporting.add_argument("--from", dest="src", default=None,
                           help=f"skills root (default {config.SKILLS_DIR})")

    removing = actions.add_parser("remove", help="delete an installed skill")
    removing.add_argument("name")
    removing.add_argument("--dir", default=None)

    actions.add_parser("formats", help="show supported formats and detection rules")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "list":
            skills = fmt.list_skills(args.dir)
            if not skills:
                print(f"No skills installed in {args.dir or config.SKILLS_DIR}")
                return 0
            print(f"{len(skills)} skill(s) in {args.dir or config.SKILLS_DIR}:")
            for skill in skills:
                scripts = f" · {len(skill['scripts'])} script(s)" if skill["scripts"] else ""
                print(f"  {skill['name']:<20} v{skill['version']:<8} "
                      f"[{skill['source_format']}]{scripts}")
                print(f"      {skill['description'][:110]}")
            return 0

        if args.action == "import":
            report = fmt.import_skill(args.source, name=args.name, dest_root=args.dest,
                                      force=args.force)
            print(f"✓ imported {report['name']} "
                  f"(detected: {report['source_format']}) → {report['path']}")
            print(f"  {report['description'][:110]}")
            return 0

        if args.action == "export":
            report = fmt.export_skill(args.name, args.format, out=args.out,
                                      src_root=args.src)
            print(f"✓ exported {report['name']} → {report['format']} at {report['path']}")
            return 0

        if args.action == "remove":
            removed = fmt.remove_skill(args.name, root=args.dir)
            print(f"✓ removed {args.name}" if removed else f"no skill '{args.name}'")
            return 0 if removed else 1

        if args.action == "formats":
            print("Supported skill formats (detection runs in this order):")
            for row in fmt.formats_table():
                print(f"  {row['name']:<12} {row['description']}")
                print(f"                signature: {row['signature']}")
            return 0

    except fmt.SkillError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
