from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
            or "/" in name
            or "\\" in name
        ):
            raise ValueError(f"invalid checksum line: {line!r}")
        if name in values:
            raise ValueError(f"duplicate checksum entry: {name}")
        values[name] = digest.lower()
    return values


def verify_archive(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as bundle:
        infos = bundle.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate ZIP member in {path.name}")
        for info in infos:
            if "\\" in info.filename:
                raise ValueError(f"ZIP member uses a backslash: {info.filename!r}")
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if (
                info.filename.startswith("/")
                or ".." in member.parts
                or (member.parts and ":" in member.parts[0])
            ):
                raise ValueError(f"unsafe ZIP member: {info.filename!r}")
            if info.date_time != FIXED_DATE:
                raise ValueError(f"nondeterministic ZIP timestamp in {info.filename!r}")
            mode = (info.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
                raise ValueError(f"ZIP member is not a regular file: {info.filename!r}")

        manifest_names = [
            name for name in names if name.endswith("/PACKAGE-MANIFEST.json")
        ]
        if "PACKAGE-MANIFEST.json" in names:
            manifest_names.append("PACKAGE-MANIFEST.json")
        if len(manifest_names) != 1:
            raise ValueError(f"expected one package manifest in {path.name}")
        manifest_name = manifest_names[0]
        manifest = json.loads(bundle.read(manifest_name).decode("utf-8"))
        prefix = manifest_name[: -len("PACKAGE-MANIFEST.json")]
        listed_names: set[str] = set()
        for item in manifest["files"]:
            relative = str(item["path"])
            member = PurePosixPath(relative)
            if (
                relative.startswith(("/", "\\"))
                or "\\" in relative
                or ".." in member.parts
                or (member.parts and ":" in member.parts[0])
            ):
                raise ValueError(f"unsafe internal manifest path: {relative!r}")
            name = prefix + relative
            listed_names.add(name)
            data = bundle.read(name)
            if sha256_bytes(data) != item["sha256"]:
                raise ValueError(f"internal hash mismatch: {name}")
            if len(data) != item["bytes"]:
                raise ValueError(f"internal size mismatch: {name}")
        if set(names) != listed_names | {manifest_name}:
            raise ValueError(f"archive member set differs from manifest in {path.name}")
        return {
            "path": path.name,
            "members": len(infos),
            "manifest": manifest_name,
        }


def verify_release(
    artifacts: Path, manifest_path: Path, checksums_path: Path
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = parse_checksums(checksums_path)
    verified: list[dict[str, Any]] = []
    expected_names = set()
    for item in manifest["artifacts"]:
        name = item["path"]
        expected_names.add(name)
        path = artifacts / name
        actual = sha256_file(path)
        if actual != item["sha256"]:
            raise ValueError(f"release manifest hash mismatch: {name}")
        if checksums.get(name) != actual:
            raise ValueError(f"SHA256SUMS mismatch: {name}")
        if path.stat().st_size != item["bytes"]:
            raise ValueError(f"release manifest size mismatch: {name}")
        verified.append(verify_archive(path))
    if set(checksums) != expected_names:
        raise ValueError("SHA256SUMS artifact set differs from release manifest")
    return {"ok": True, "artifacts": verified}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all GitHub Release assets.")
    parser.add_argument("--artifacts", type=Path, default=Path("dist"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("dist/release-manifest.json")
    )
    parser.add_argument("--checksums", type=Path, default=Path("dist/SHA256SUMS"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_release(args.artifacts, args.manifest, args.checksums)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        result = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
