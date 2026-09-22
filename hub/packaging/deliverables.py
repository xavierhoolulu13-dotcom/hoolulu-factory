"""Zip a build, record what is in it, and checksum the result."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .. import config

MANIFEST_NAME = "manifest.json"


class PackageError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def package_path(slug: str, version: str = "1.0.0") -> Path:
    return config.PACKAGE_ROOT / f"{slug}-{version}.zip"


def manifest_for(slug: str, *, version: str = "1.0.0",
                 qa: dict | None = None) -> dict:
    """Describe a build: what is in it, what it scored, where it came from."""
    build_dir = config.BUILD_ROOT / slug
    if not build_dir.is_dir():
        raise PackageError(f"nothing built at {build_dir} — run the build stage first")

    spec = {}
    spec_path = build_dir / "product.json"
    if spec_path.is_file():
        spec = json.loads(spec_path.read_text())

    artifacts = []
    for path in sorted(build_dir.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            artifacts.append({
                "path": str(path.relative_to(build_dir)),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })

    return {
        "slug": slug,
        "name": spec.get("name", slug),
        "template": spec.get("template", "?"),
        "version": version,
        "created_at": _now(),
        "entry": "index.html",
        "artifacts": artifacts,
        "total_bytes": sum(a["bytes"] for a in artifacts),
        "qa_score": (qa or {}).get("score"),
        "provenance": spec.get("provenance", {}),
        "monetization": spec.get("monetization", {}),
    }


def package(slug: str, *, version: str = "1.0.0", qa: dict | None = None) -> dict:
    """Write ``packages/<slug>-<version>.zip`` plus a manifest beside the build."""
    config.ensure_dirs()
    manifest = manifest_for(slug, version=version, qa=qa)
    build_dir = config.BUILD_ROOT / slug
    zip_path = package_path(slug, version)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(build_dir.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(build_dir))
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    data = zip_path.read_bytes()
    manifest["package"] = config.rel(zip_path)
    manifest["package_bytes"] = len(data)
    manifest["package_sha256"] = hashlib.sha256(data).hexdigest()

    manifest_path = build_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def format_package(manifest: dict) -> str:
    lines = [
        f"{manifest['name']} v{manifest['version']} packaged",
        f"  zip      : {manifest.get('package')} "
        f"({manifest.get('package_bytes', 0):,} bytes)",
        f"  sha256   : {(manifest.get('package_sha256') or '')[:16]}…",
        f"  files    : {len(manifest['artifacts'])} "
        f"({manifest['total_bytes']:,} bytes unpacked)",
    ]
    if manifest.get("qa_score") is not None:
        lines.append(f"  qa score : {manifest['qa_score']}/100")
    return "\n".join(lines)
