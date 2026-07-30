from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rin_pet import __version__  # noqa: E402
from rin_pet.atlas import validate_pet_directory  # noqa: E402
from rin_pet.packaging import build_package, build_pet_archive  # noqa: E402
from rin_pet.replay import build_stage  # noqa: E402
from rin_pet.safeio import atomic_write_bytes, atomic_write_json  # noqa: E402
from rin_pet.timeline import parse_trace_file  # noqa: E402


def build_release(version: str, output: Path) -> dict[str, object]:
    if version != __version__:
        raise ValueError(
            f"release version {version!r} does not match project version "
            f"{__version__!r}"
        )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / ".rin-pet-release").write_text(
        "Kagamine Rin release output\n", encoding="utf-8"
    )

    timeline = output / "sanitized-timeline.json"
    parsed = parse_trace_file(ROOT / "examples" / "sanitized-session.jsonl", timeline)
    build_stage(ROOT, output / "site", timeline_path=timeline)

    project_archive = output / f"kagamine-rin-codex-pet-v{version}.zip"
    pet_archive = output / f"kagamine-rin-v{version}.codex-pet"
    project = build_package(ROOT, project_archive, version=version)
    pet = build_pet_archive(ROOT, pet_archive, version=version)

    artifacts = [project["archive"], pet["archive"]]
    manifest = {
        "ok": True,
        "schemaVersion": 1,
        "project": "kagamine-rin-codex-pet",
        "version": version,
        "timeline": {
            "sha256": parsed["source"]["sha256"],
            "events": len(parsed["events"]),
        },
        "petValidation": validate_pet_directory(ROOT, strict=True).to_dict(strict=True),
        "artifacts": artifacts,
    }
    atomic_write_json(output / "release-manifest.json", manifest)
    checksum_lines = "".join(
        f"{item['sha256']}  {item['path']}\n"
        for item in sorted(artifacts, key=lambda value: str(value["path"]))
    )
    atomic_write_bytes(output / "SHA256SUMS", checksum_lines.encode("utf-8"))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic GitHub Release assets."
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_release(args.version, args.output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for artifact in result["artifacts"]:
            print(f"{artifact['sha256']}  {artifact['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
