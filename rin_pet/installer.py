from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atlas import locate_pet_dir, validate_pet_directory
from .constants import PET_ID
from .models import InstallResult
from .safeio import (
    SafetyError,
    ensure_within,
    exclusive_lock,
    extract_zip_safely,
    sha256_file,
)


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


@contextmanager
def _resolved_source(source: Path) -> Iterator[Path]:
    source = source.expanduser().resolve()
    if source.is_dir():
        yield locate_pet_dir(source)
        return
    if not source.is_file() or source.suffix.lower() not in {".zip", ".codex-pet"}:
        raise FileNotFoundError(
            f"source must be a pet directory or ZIP archive: {source}"
        )
    with tempfile.TemporaryDirectory(prefix="rin-pet-source-") as raw:
        extracted = Path(raw)
        extract_zip_safely(source, extracted)
        yield locate_pet_dir(extracted)


def _validate_source(pet_dir: Path) -> str:
    report = validate_pet_directory(pet_dir, strict=True)
    if not report.is_ok(strict=True):
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in report.issues)
        raise ValueError(f"source pet did not pass strict validation: {summary}")
    return str(report.metadata["sha256"])


def _backup_path(codex_home: Path, source_hash: str) -> Path:
    # Microseconds avoid collisions when install/repair/uninstall operations happen
    # in the same second (common in automated recovery tests).
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return codex_home / "pet-backups" / PET_ID / f"{stamp}-{source_hash[:8]}"


def install_pet(
    source: Path,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
    action: str = "install",
) -> InstallResult:
    codex_home = (codex_home or default_codex_home()).expanduser().resolve()
    target_root = codex_home / "pets"
    target = target_root / PET_ID
    ensure_within(target, codex_home)

    with _resolved_source(source) as pet_dir:
        source_hash = _validate_source(pet_dir)
        if dry_run:
            return InstallResult(action, target, None, True, source_hash)

        codex_home.mkdir(parents=True, exist_ok=True)
        target_root.mkdir(parents=True, exist_ok=True)
        lock = codex_home / ".kagamine-rin-pet.lock"
        with exclusive_lock(lock):
            staging = Path(
                tempfile.mkdtemp(prefix=f".{PET_ID}.staging-", dir=target_root)
            )
            backup: Path | None = None
            try:
                for name in (
                    "pet.json",
                    "spritesheet.webp",
                    "provenance.json",
                    "SHA256SUMS",
                ):
                    shutil.copy2(pet_dir / name, staging / name)
                staged_hash = _validate_source(staging)
                if staged_hash != source_hash:
                    raise ValueError("staging hash differs from validated source")
                if target.exists():
                    backup = _backup_path(codex_home, source_hash)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    if backup.exists():
                        raise SafetyError(f"backup collision: {backup}")
                    shutil.move(str(target), str(backup))
                try:
                    os.replace(staging, target)
                except Exception:
                    if backup is not None and backup.exists() and not target.exists():
                        shutil.move(str(backup), str(target))
                    raise
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
        return InstallResult(action, target, backup, False, source_hash)


def doctor_pet(
    *,
    codex_home: Path | None = None,
    source: Path | None = None,
) -> dict[str, Any]:
    codex_home = (codex_home or default_codex_home()).expanduser().resolve()
    target = codex_home / "pets" / PET_ID
    if not target.is_dir():
        return {
            "ok": False,
            "status": "missing",
            "target": str(target),
            "repair": "rin-pet repair --source pet",
        }
    report = validate_pet_directory(target, strict=True)
    result = report.to_dict(strict=True)
    result["status"] = "healthy" if result["ok"] else "invalid"
    result["target"] = str(target)
    if source is not None:
        with _resolved_source(source) as source_dir:
            expected = _validate_source(source_dir)
        installed = report.metadata.get("sha256")
        result["expectedSha256"] = expected
        result["matchesSource"] = bool(expected and installed == expected)
        if result["ok"] and not result["matchesSource"]:
            result["ok"] = False
            result["status"] = "modified"
    return result


def repair_pet(
    source: Path,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    return install_pet(source, codex_home=codex_home, dry_run=dry_run, action="repair")


def uninstall_pet(
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    codex_home = (codex_home or default_codex_home()).expanduser().resolve()
    target = codex_home / "pets" / PET_ID
    ensure_within(target, codex_home)
    if not target.is_dir():
        raise FileNotFoundError(f"installed pet not found: {target}")
    source_hash = sha256_file(target / "spritesheet.webp")
    backup = _backup_path(codex_home, source_hash)
    if dry_run:
        return InstallResult("uninstall", target, backup, True, source_hash)
    with exclusive_lock(codex_home / ".kagamine-rin-pet.lock"):
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            raise SafetyError(f"backup collision: {backup}")
        shutil.move(str(target), str(backup))
    return InstallResult("uninstall", target, backup, False, source_hash)


def read_checksums(pet_dir: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (pet_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if separator != "  " or len(digest) != 64:
            raise ValueError(f"invalid checksum line: {line!r}")
        values[name] = digest
    return values


def verify_provenance(pet_dir: Path) -> dict[str, Any]:
    value = json.loads((pet_dir / "provenance.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("petId") != PET_ID:
        raise ValueError("provenance.json has an invalid petId")
    return value
