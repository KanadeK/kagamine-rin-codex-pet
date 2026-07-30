from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any


class SafetyError(RuntimeError):
    """Raised when a path or archive violates a safety boundary."""


MAX_ZIP_MEMBERS = 512
MAX_ZIP_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 128 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    atomic_write_bytes(path, payload)


def ensure_within(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    root = parent.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SafetyError(f"path escapes allowed root: {resolved}") from exc
    return resolved


def _validated_member_path(name: str) -> PurePosixPath:
    if "\\" in name:
        raise SafetyError(f"ZIP member must use forward slashes: {name!r}")
    normalized = name[:-1] if name.endswith("/") else name
    if not normalized or normalized.startswith("/"):
        raise SafetyError(f"unsafe absolute ZIP member: {name!r}")
    raw_parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise SafetyError(f"unsafe ZIP member traversal: {name!r}")
    member = PurePosixPath(normalized)
    if member.parts and ":" in member.parts[0]:
        raise SafetyError(f"unsafe drive-qualified ZIP member: {name!r}")
    return member


def extract_zip_safely(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise SafetyError(
                f"ZIP has {len(infos)} members; limit is {MAX_ZIP_MEMBERS}"
            )
        total_bytes = sum(info.file_size for info in infos)
        if total_bytes > MAX_ZIP_TOTAL_BYTES:
            raise SafetyError(
                f"ZIP expands to {total_bytes} bytes; limit is {MAX_ZIP_TOTAL_BYTES}"
            )

        validated: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        seen: set[str] = set()
        for info in infos:
            member = _validated_member_path(info.filename)
            normalized = member.as_posix().casefold()
            if normalized in seen:
                raise SafetyError(
                    f"duplicate or case-colliding ZIP member: {info.filename!r}"
                )
            seen.add(normalized)
            if info.flag_bits & 0x1:
                raise SafetyError(
                    f"encrypted ZIP member is not allowed: {info.filename!r}"
                )
            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                raise SafetyError(
                    f"ZIP member exceeds {MAX_ZIP_MEMBER_BYTES} bytes: "
                    f"{info.filename!r}"
                )
            mode = (info.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode):
                raise SafetyError(f"ZIP symlink is not allowed: {info.filename!r}")
            if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise SafetyError(f"ZIP special file is not allowed: {info.filename!r}")
            validated.append((info, member))

        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for info, member in validated:
            output = ensure_within(destination.joinpath(*member.parts), root)
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info, "r") as source, output.open("wb") as target:
                shutil.copyfileobj(source, target)


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SafetyError(
            f"operation lock already exists: {path}; remove it only after "
            "confirming no rin-pet process is running"
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)
