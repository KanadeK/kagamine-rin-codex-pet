from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .atlas import locate_pet_dir, validate_pet_directory
from .safeio import SafetyError, atomic_write_json, ensure_within, sha256_file
from .timeline import validate_timeline

_STAGE_MARKER = ".rin-pet-stage"


def _load_timeline(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read timeline {path}: {exc}") from exc
    errors = validate_timeline(value)
    if errors:
        raise ValueError("invalid timeline: " + "; ".join(errors))
    return value


def _safe_output(output: Path, repository_root: Path) -> Path:
    resolved = output.resolve()
    forbidden = {
        Path(resolved.anchor).resolve(),
        Path.home().resolve(),
        repository_root.resolve(),
        repository_root.parent.resolve(),
    }
    if resolved in forbidden:
        raise SafetyError(f"refusing unsafe stage output directory: {resolved}")
    ensure_within(resolved, output.parent.resolve())
    return resolved


def build_stage(
    repository_root: Path,
    output: Path,
    *,
    timeline_path: Path | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output = _safe_output(output, repository_root)
    pet_dir = locate_pet_dir(repository_root)
    report = validate_pet_directory(pet_dir, strict=True)
    if not report.is_ok(strict=True):
        codes = ", ".join(issue.code for issue in report.issues)
        raise ValueError(f"pet validation failed before stage build: {codes}")

    if timeline_path is None:
        timeline_path = repository_root / "examples" / "sanitized-timeline.json"
    timeline = _load_timeline(timeline_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not (output / _STAGE_MARKER).is_file():
        raise SafetyError(
            "refusing to replace an existing directory that was not created "
            f"by rin-pet: {output}"
        )
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        for name in ("index.html", "styles.css", "app.mjs", "runtime.mjs"):
            shutil.copy2(repository_root / "web" / name, staging / name)
        target_pet = staging / "pet"
        target_pet.mkdir()
        for name in ("pet.json", "spritesheet.webp", "provenance.json", "SHA256SUMS"):
            shutil.copy2(pet_dir / name, target_pet / name)
        atomic_write_json(staging / "timeline.json", timeline)
        manifest_files: dict[str, dict[str, Any]] = {}
        for file in sorted(path for path in staging.rglob("*") if path.is_file()):
            relative = file.relative_to(staging).as_posix()
            manifest_files[relative] = {
                "sha256": sha256_file(file),
                "bytes": file.stat().st_size,
            }
        manifest = {
            "schemaVersion": 1,
            "offline": True,
            "analytics": False,
            "files": manifest_files,
        }
        atomic_write_json(staging / "site-manifest.json", manifest)
        (staging / _STAGE_MARKER).write_text(
            "Kagamine Rin offline replay stage\n", encoding="utf-8"
        )
        if output.exists():
            shutil.rmtree(output)
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "ok": True,
        "output": str(output),
        "timelineEvents": len(timeline["events"]),
        "files": len(manifest["files"]) + 1,
    }
