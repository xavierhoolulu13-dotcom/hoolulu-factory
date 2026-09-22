"""Skill packs: one normal form, many ecosystems.

Every skill imported from anywhere is rewritten into the **markus** normal form:

    <name>/
      skill.yaml    # {name, description, version, tags, allowed_tools, format, source_format}
      SKILL.md      # markdown body with YAML frontmatter (also valid as a Claude skill)
      scripts/      # executable helpers, copied verbatim
      references/   # docs the skill needs at runtime, copied verbatim

Export writes that normal form back out in whichever ecosystem you are moving
to. Detection is by file signature (``SKILL.md`` with frontmatter, ``soul.yaml``,
``mcp.json``, ...) and is listed by ``markus skill formats``.

Scripts are always copied byte-for-byte. What is generated is the *descriptor*,
and ``EXPORT-NOTES.md`` in every export says exactly what that means for the
target — no export pretends to be something it is not.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from .. import config

FRONTMATTER = "---"

# Manifest files belonging to a source format. They are read on import and then
# dropped: the normal form carries one descriptor (skill.yaml), so a pack never
# shows up with a stale mcp.json or openclaw.yaml riding along.
DESCRIPTOR_FILES = {
    "skill.yaml", "skill.json", "SKILL.md", "SOUL.md", "soul.yaml",
    "openclaw.yaml", "agentscope.yaml", "config.json", "mcp.json", "server.json",
}


class SkillError(RuntimeError):
    pass


class UnknownFormat(SkillError):
    pass


@dataclass
class Skill:
    """The normal form."""
    name: str
    description: str
    version: str = "0.1.0"
    body: str = ""
    tags: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    source_format: str = "markus"
    files: dict[str, str] = field(default_factory=dict)  # relpath -> text (non-script)

    def frontmatter(self) -> dict:
        data = {"name": self.name, "description": self.description}
        if self.allowed_tools:
            data["allowed-tools"] = list(self.allowed_tools)
        if self.tags:
            data["tags"] = list(self.tags)
        data["version"] = self.version
        return data

    def as_markdown(self) -> str:
        head = yaml.safe_dump(self.frontmatter(), sort_keys=False).strip()
        body = self.body.strip() or f"# {self.name}\n\n{self.description}"
        return f"{FRONTMATTER}\n{head}\n{FRONTMATTER}\n\n{body}\n"

    def as_yaml_doc(self, extra: dict | None = None) -> str:
        data = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "allowed_tools": self.allowed_tools,
            "format": "markus",
            "source_format": self.source_format,
        }
        if extra:
            data.update(extra)
        return yaml.safe_dump(data, sort_keys=False)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return ``(metadata, body)``. Missing frontmatter yields empty metadata."""
    if not text.startswith(FRONTMATTER):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 2:
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER:
            block = "\n".join(lines[1:index])
            try:
                metadata = yaml.safe_load(block) or {}
            except yaml.YAMLError:
                return {}, text
            if not isinstance(metadata, dict):
                return {}, text
            return metadata, "\n".join(lines[index + 1:]).lstrip("\n")
    return {}, text


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"{path} is not valid YAML: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillError(f"{path} is not valid JSON: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _collect_files(root: Path, skip: set[str] | None = None) -> dict[str, str]:
    skip = skip or set()
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in skip:
            continue
        relative = str(path.relative_to(root))
        try:
            files[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary assets are copied, not parsed
    return files


# --------------------------------------------------------------------------
# format specs
# --------------------------------------------------------------------------

@dataclass
class FormatSpec:
    name: str
    description: str
    signature: str
    detect: object          # (root: Path) -> bool
    load: object            # (root: Path) -> Skill
    export: object          # (skill: Skill, out: Path, extras: dict) -> Path


def _load_markdown_skill(root: Path, source: str, markdown: str) -> Skill:
    path = root / markdown
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    metadata, body = split_frontmatter(text)
    name = str(metadata.get("name") or _name_from_readme(root, body))
    description = str(metadata.get("description") or _first_line(body) or
                      f"Imported from {source}.")
    return Skill(
        name=skill_name(name),
        description=" ".join(description.split())[:300],
        version=str(metadata.get("version", "0.1.0")),
        body=body,
        tags=list(metadata.get("tags") or []),
        allowed_tools=list(metadata.get("allowed-tools") or metadata.get("allowed_tools") or []),
        source_format=source,
    )


def _name_from_readme(root: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return root.name or "unnamed-skill"


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def skill_name(value: str) -> str:
    """Normalize any name into a directory-safe skill id."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "unnamed-skill"


def _export_markdown_bundle(skill: Skill, out: Path, extras: dict) -> Path:
    target = out
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(skill.as_markdown(), encoding="utf-8")
    _copy_extras(skill, target)
    _write_notes(target, extras)
    return target


def _copy_extras(skill: Skill, target: Path) -> None:
    """Recreate scripts/ and references/ from the stored files."""
    for relative, content in skill.files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def _write_notes(target: Path, extras: dict) -> None:
    lines = [
        "# Export notes",
        "",
        f"- normalized from: **{extras.get('source_format', 'markus')}**",
        f"- exported by: **{extras.get('exporter', 'hoolulu hub')}**",
        f"- scripts: **{'copied verbatim' if extras.get('scripts') else 'none in this pack'}**",
        "",
        extras.get("notes", ""),
        "",
        "This export writes the descriptor the target ecosystem expects and copies the "
        "skill's own files unchanged. Execution semantics (how a host loads scripts, "
        "what a tool call looks like) are host-specific and are not emulated here.",
    ]
    (target / "EXPORT-NOTES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


FORMATS: list[FormatSpec] = [
    FormatSpec(
        name="markus",
        description="the hub's own normal form (skill.yaml + SKILL.md)",
        signature="skill.yaml with format: markus",
        detect=lambda root: (root / "skill.yaml").is_file(),
        load=lambda root: _load_markus(root),
        export=lambda skill, out, extras: _export_markus(skill, out, extras),
    ),
    FormatSpec(
        name="claude",
        description="Anthropic Claude agent skill (SKILL.md with frontmatter)",
        signature="SKILL.md with YAML frontmatter (name + description)",
        detect=lambda root: (root / "SKILL.md").is_file()
        and bool(split_frontmatter((root / "SKILL.md").read_text(encoding="utf-8"))[0].get("name")),
        load=lambda root: _load_markdown_skill(root, "claude", "SKILL.md"),
        export=lambda skill, out, extras: _export_markdown_bundle(skill, out, {
            **extras,
            "notes": "Claude reads SKILL.md only; scripts/ and references/ are bundled "
                     "resources it can open on demand.",
        }),
    ),
    FormatSpec(
        name="openclaw",
        description="OpenClaw skill pack (openclaw.yaml manifest)",
        signature="openclaw.yaml, or skill.json containing an 'openclaw' key",
        detect=lambda root: (root / "openclaw.yaml").is_file()
        or ((root / "skill.json").is_file()
            and "openclaw" in _read_json(root / "skill.json")),
        load=lambda root: _load_yaml_named(root, "openclaw"),
        export=lambda skill, out, extras: _export_yaml_bundle(
            skill, out, "openclaw.yaml", {
                **extras,
                "notes": "openclaw.yaml carries the manifest; SKILL.md carries the "
                         "instructions so the pack stays readable in Claude too.",
            }),
    ),
    FormatSpec(
        name="soul",
        description="SOUL.md persona/character pack",
        signature="soul.yaml, or SOUL.md",
        detect=lambda root: (root / "soul.yaml").is_file() or (root / "SOUL.md").is_file(),
        load=lambda root: _load_yaml_named(root, "soul"),
        export=lambda skill, out, extras: _export_yaml_bundle(
            skill, out, "soul.yaml", {
                **extras,
                "notes": "SOUL.md keeps the persona in prose; soul.yaml carries the same "
                         "fields as structured metadata.",
            }, markdown_name="SOUL.md"),
    ),
    FormatSpec(
        name="mcp-server",
        description="Model Context Protocol server descriptor",
        signature="mcp.json or server.json containing 'mcpServers'",
        detect=lambda root: any(
            (root / name).is_file() and "mcpServers" in _read_json(root / name)
            for name in ("mcp.json", "server.json")
        ),
        load=lambda root: _load_mcp(root),
        export=lambda skill, out, extras: _export_mcp(skill, out, extras),
    ),
    FormatSpec(
        name="agentscope",
        description="AgentScope tool/agent configuration",
        signature="agentscope.yaml, or config.json containing an 'agentscope' key",
        detect=lambda root: (root / "agentscope.yaml").is_file()
        or ((root / "config.json").is_file()
            and "agentscope" in _read_json(root / "config.json")),
        load=lambda root: _load_yaml_named(root, "agentscope"),
        export=lambda skill, out, extras: _export_yaml_bundle(
            skill, out, "agentscope.yaml", {
                **extras,
                "notes": "agentscope.yaml maps the skill to AgentScope's toolkit layout; "
                         "the scripts are unchanged.",
            }),
    ),
    FormatSpec(
        name="generic",
        description="any folder with a README or SKILL.md (best effort)",
        signature="README.md or SKILL.md without a known manifest",
        detect=lambda root: (root / "README.md").is_file()
        or (root / "SKILL.md").is_file(),
        load=lambda root: _load_generic(root),
        export=lambda skill, out, extras: _export_markdown_bundle(skill, out, {
            **extras,
            "notes": "No target-specific manifest for 'generic'; this is the normal "
                     "form, which every other exporter can read.",
        }),
    ),
]

FORMATS_BY_NAME = {spec.name: spec for spec in FORMATS}


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------

def _load_markus(root: Path) -> Skill:
    data = _read_yaml(root / "skill.yaml")
    body = ""
    markdown = root / "SKILL.md"
    if markdown.is_file():
        body = split_frontmatter(markdown.read_text(encoding="utf-8"))[1]
    return Skill(
        name=skill_name(str(data.get("name") or root.name)),
        description=" ".join(str(data.get("description") or _first_line(body)
                                 or "Imported skill.").split())[:300],
        version=str(data.get("version", "0.1.0")),
        body=body,
        tags=list(data.get("tags") or []),
        allowed_tools=list(data.get("allowed_tools") or data.get("allowed-tools") or []),
        source_format=str(data.get("source_format", data.get("format", "markus"))),
    )


def _load_yaml_named(root: Path, source: str) -> Skill:
    manifest = None
    for candidate in ("skill.yaml", f"{source}.yaml", "skill.json", "config.json"):
        path = root / candidate
        if path.is_file():
            manifest = _read_yaml(path) if path.suffix == ".yaml" else _read_json(path)
            break
    manifest = manifest or {}

    body = ""
    for candidate in ("SKILL.md", "SOUL.md", "README.md"):
        path = root / candidate
        if path.is_file():
            metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if candidate == "SKILL.md" and metadata:
                break
    name = str(manifest.get("name") or _name_from_readme(root, body) or root.name)
    return Skill(
        name=skill_name(name),
        description=" ".join(str(manifest.get("description") or _first_line(body)
                                 or f"Imported from {source}.").split())[:300],
        version=str(manifest.get("version", "0.1.0")),
        body=body,
        tags=list(manifest.get("tags") or []),
        allowed_tools=list(manifest.get("allowed_tools") or []),
        source_format=source,
    )


def _load_mcp(root: Path) -> Skill:
    for candidate in ("mcp.json", "server.json"):
        path = root / candidate
        if path.is_file():
            data = _read_json(path)
            break
    else:
        data = {}
    servers = data.get("mcpServers") or {}
    name = next(iter(servers), root.name) if isinstance(servers, dict) else root.name
    server = servers.get(name, {}) if isinstance(servers, dict) else {}
    return Skill(
        name=skill_name(str(name)),
        description=" ".join(str(server.get("description") or
                                 f"MCP server imported from {root.name}").split())[:300],
        body=(root / "README.md").read_text(encoding="utf-8")
        if (root / "README.md").is_file() else f"# {name}\n",
        source_format="mcp-server",
    )


def _load_generic(root: Path) -> Skill:
    body = ""
    for candidate in ("SKILL.md", "README.md"):
        path = root / candidate
        if path.is_file():
            body = split_frontmatter(path.read_text(encoding="utf-8"))[1]
            break
    return Skill(
        name=skill_name(_name_from_readme(root, body) or root.name),
        description=" ".join(_first_line(body).split())[:300] or "Imported skill.",
        body=body,
        source_format="generic",
    )


# --------------------------------------------------------------------------
# exporters
# --------------------------------------------------------------------------

def _export_markus(skill: Skill, out: Path, extras: dict) -> Path:
    target = out
    target.mkdir(parents=True, exist_ok=True)
    (target / "skill.yaml").write_text(skill.as_yaml_doc(), encoding="utf-8")
    (target / "SKILL.md").write_text(skill.as_markdown(), encoding="utf-8")
    _copy_extras(skill, target)
    return target


def _export_yaml_bundle(skill: Skill, out: Path, manifest_name: str, extras: dict,
                        markdown_name: str = "SKILL.md") -> Path:
    target = _export_markdown_bundle(skill, out, extras)
    (target / markdown_name).write_text(skill.as_markdown(), encoding="utf-8")
    (target / manifest_name).write_text(skill.as_yaml_doc(), encoding="utf-8")
    return target


def _export_mcp(skill: Skill, out: Path, extras: dict) -> Path:
    target = out
    target.mkdir(parents=True, exist_ok=True)
    scripts = sorted(rel for rel in skill.files
                     if rel.startswith("scripts/") or rel.endswith((".py", ".js", ".sh")))
    descriptor = {
        "mcpServers": {
            skill.name: {
                "command": "python3",
                "args": ["-m", f"{skill.name}_mcp"],
                "description": skill.description,
                "tools": [
                    {"name": Path(script).stem, "script": script,
                     "description": f"Runs {script} from the {skill.name} skill pack."}
                    for script in scripts
                ] or [{"name": skill.name, "script": None,
                       "description": "No scripts in this pack — instructions only."}],
            }
        }
    }
    (target / "mcp.json").write_text(json.dumps(descriptor, indent=2) + "\n",
                                     encoding="utf-8")
    _copy_extras(skill, target)
    _write_notes(target, {
        **extras,
        "notes": "mcp.json describes a server whose tools are this pack's scripts. The "
                 "server wrapper itself is host-specific and is NOT generated — point "
                 "the command at your own MCP SDK entry point.",
    })
    return target


# --------------------------------------------------------------------------
# public operations
# --------------------------------------------------------------------------

def detect_format(source: Path) -> str:
    """Return the format name for a directory, or raise ``UnknownFormat``."""
    for spec in FORMATS:
        try:
            if spec.detect(source):
                return spec.name
        except (OSError, SkillError):
            continue
    raise UnknownFormat(
        f"could not detect a skill format in {source} — expected one of: "
        + ", ".join(spec.name for spec in FORMATS)
    )


def open_source(source: Path | str) -> tuple[Path, TemporaryDirectory | None]:
    """Accept a directory or a zip; return ``(path, tempdir_to_clean)``."""
    source = Path(source).expanduser()
    if source.is_dir():
        return source, None
    if zipfile.is_zipfile(source):
        temp = TemporaryDirectory(prefix="hoolulu-skill-")
        with zipfile.ZipFile(source) as archive:
            archive.extractall(temp.name)
        extracted = Path(temp.name)
        entries = [p for p in extracted.iterdir() if p.is_dir()]
        # a zip that wraps everything in one folder should behave like that folder
        if len(entries) == 1 and not (extracted / "SKILL.md").exists():
            return entries[0], temp
        return extracted, temp
    raise SkillError(f"{source} is neither a directory nor a zip file")


def import_skill(source: Path | str, *, name: str | None = None,
                 dest_root: Path | str | None = None, force: bool = False) -> dict:
    """Detect, normalize and install a skill. Returns a report dict."""
    root = Path(dest_root or config.SKILLS_DIR).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path, temp = open_source(source)
    try:
        source_format = detect_format(path)
        skill = FORMATS_BY_NAME[source_format].load(path)
        if name:
            skill.name = skill_name(name)

        # descriptor files are superseded by skill.yaml in the normal form;
        # only the skill's own scripts and references travel with it
        files = _collect_files(path, skip=DESCRIPTOR_FILES)
        skill.files = {rel: text for rel, text in files.items()}
        skill.source_format = source_format

        target = root / skill.name
        if target.exists() and not force:
            raise SkillError(
                f"{target} already exists — pass --force to replace it"
            )
        if target.exists():
            shutil.rmtree(target)
        written = _export_markus(skill, target, {"source_format": source_format})
        return {
            "ok": True,
            "name": skill.name,
            "source_format": source_format,
            "path": str(written),
            "description": skill.description,
            "files": 2 + len(skill.files),
        }
    finally:
        if temp is not None:
            temp.cleanup()


def export_skill(name: str, fmt: str, *, out: Path | str | None = None,
                 src_root: Path | str | None = None) -> dict:
    """Write an installed skill out in another ecosystem's format."""
    spec = FORMATS_BY_NAME.get(fmt)
    if spec is None:
        raise SkillError(f"unknown format '{fmt}' — known: "
                         + ", ".join(FORMATS_BY_NAME))
    root = Path(src_root or config.SKILLS_DIR).expanduser()
    source = root / skill_name(name)
    if not source.is_dir():
        raise SkillError(f"no skill '{name}' in {root}")

    skill = _load_markus(source)
    files = _collect_files(source, skip={"skill.yaml", "SKILL.md"})
    skill.files = files

    # `markus skill export <name> --format <fmt>` writes ./<name>-<fmt>/;
    # with --out it writes <out>/<name>/ so several skills can share a folder.
    if out:
        base = Path(out).expanduser()
        base.mkdir(parents=True, exist_ok=True)
        target = base / (f"{skill.name}-mcp" if fmt == "mcp-server" else skill.name)
    else:
        target = Path.cwd() / f"{skill.name}-{fmt}"

    written = spec.export(skill, target, {
        "source_format": skill.source_format,
        "exporter": "hoolulu hub",
        "scripts": [rel for rel in files if rel.startswith("scripts/")],
    })
    return {"ok": True, "name": skill.name, "format": fmt, "path": str(written)}


def list_skills(root: Path | str | None = None) -> list[dict]:
    """Every installed skill with its format and description."""
    directory = Path(root or config.SKILLS_DIR).expanduser()
    if not directory.is_dir():
        return []
    skills = []
    for path in sorted(directory.iterdir()):
        if not path.is_dir() or not (path / "skill.yaml").is_file():
            continue  # not a skill pack (an export folder, a stray directory)
        try:
            skill = _load_markus(path)
        except SkillError:
            continue
        skills.append({
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "source_format": skill.source_format,
            "tags": skill.tags,
            "scripts": sorted(rel for rel in _collect_files(path)
                              if rel.startswith("scripts/")),
            "path": str(path),
        })
    return skills


def remove_skill(name: str, *, root: Path | str | None = None) -> bool:
    directory = Path(root or config.SKILLS_DIR).expanduser()
    target = directory / skill_name(name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def formats_table() -> list[dict]:
    return [{"name": spec.name, "description": spec.description,
             "signature": spec.signature,
             "detect": "detect rule: " + spec.signature} for spec in FORMATS]
