from __future__ import annotations

import json
import os
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .atlas import validate_pet_directory
from .constants import FIXED_ZIP_DATETIME
from .safeio import atomic_write_bytes, atomic_write_json, sha256_file

_ROOT_FILES = (
    ".gitattributes",
    ".gitignore",
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "LICENSE",
    "ASSET_LICENSE.md",
    "NOTICE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
)


def _release_files(root: Path) -> Iterable[Path]:
    for name in _ROOT_FILES:
        path = root / name
        if path.is_file():
            yield path
    for directory in (
        ".github",
        "pet",
        "rin_pet",
        "scripts",
        "web",
        "examples",
        "docs",
        "media",
        "tests",
        "artwork/qa",
        "artwork/source",
    ):
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            if "__pycache__" not in path.parts and path.suffix != ".pyc":
                yield path


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATETIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def _write_deterministic_zip(
    output: Path,
    entries: Iterable[tuple[str, bytes]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_tmp = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(descriptor)
    tmp = Path(raw_tmp)
    try:
        with zipfile.ZipFile(
            tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for name, data in entries:
                bundle.writestr(_zip_info(name), data)
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)


def build_package(
    repository_root: Path,
    output: Path,
    *,
    version: str,
    manifest_output: Path | None = None,
    checksums_output: Path | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    report = validate_pet_directory(repository_root, strict=True)
    if not report.is_ok(strict=True):
        details = "; ".join(issue.code for issue in report.issues)
        raise ValueError(f"pet validation failed before packaging: {details}")
    if not version or any(char not in "0123456789." for char in version):
        raise ValueError("version must contain only digits and dots")

    files = sorted(set(_release_files(repository_root)))
    relative_manifest: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(repository_root).as_posix()
        relative_manifest.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    internal_manifest = {
        "schemaVersion": 1,
        "project": "kagamine-rin-codex-pet",
        "version": version,
        "files": relative_manifest,
    }
    internal_bytes = (
        json.dumps(
            internal_manifest, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        + b"\n"
    )

    prefix = f"kagamine-rin-codex-pet-v{version}"
    entries = [
        (
            f"{prefix}/{path.relative_to(repository_root).as_posix()}",
            path.read_bytes(),
        )
        for path in files
    ]
    entries.append((f"{prefix}/PACKAGE-MANIFEST.json", internal_bytes))
    _write_deterministic_zip(output, entries)

    archive_hash = sha256_file(output)
    result = {
        "ok": True,
        "schemaVersion": 1,
        "project": "kagamine-rin-codex-pet",
        "version": version,
        "archive": {
            "path": output.name,
            "sha256": archive_hash,
            "bytes": output.stat().st_size,
        },
        "files": relative_manifest,
    }
    if manifest_output is not None:
        atomic_write_json(manifest_output, result)
    if checksums_output is not None:
        line = f"{archive_hash}  {output.name}\n".encode()
        atomic_write_bytes(checksums_output, line)
    return result


def build_pet_archive(
    repository_root: Path,
    output: Path,
    *,
    version: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    report = validate_pet_directory(repository_root, strict=True)
    if not report.is_ok(strict=True):
        details = "; ".join(issue.code for issue in report.issues)
        raise ValueError(f"pet validation failed before packaging: {details}")
    if not version or any(char not in "0123456789." for char in version):
        raise ValueError("version must contain only digits and dots")

    pet_dir = repository_root / "pet"
    names = ("pet.json", "spritesheet.webp", "provenance.json", "SHA256SUMS")
    metadata = {
        "schemaVersion": 1,
        "project": "kagamine-rin-codex-pet",
        "version": version,
        "format": "codex-pet",
        "files": [
            {
                "path": name,
                "sha256": sha256_file(pet_dir / name),
                "bytes": (pet_dir / name).stat().st_size,
            }
            for name in names
        ],
    }
    metadata_bytes = (
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True).encode(
            "utf-8"
        )
        + b"\n"
    )
    entries = [(name, (pet_dir / name).read_bytes()) for name in names]
    entries.append(("PACKAGE-MANIFEST.json", metadata_bytes))
    _write_deterministic_zip(output, entries)
    return {
        "ok": True,
        "project": "kagamine-rin-codex-pet",
        "version": version,
        "archive": {
            "path": output.name,
            "sha256": sha256_file(output),
            "bytes": output.stat().st_size,
        },
        "files": metadata["files"],
    }


def verify_package(archive: Path, expected_sha256: str) -> dict[str, Any]:
    actual = sha256_file(archive)
    return {
        "ok": actual.lower() == expected_sha256.lower(),
        "archive": str(archive),
        "expected": expected_sha256.lower(),
        "actual": actual,
    }
