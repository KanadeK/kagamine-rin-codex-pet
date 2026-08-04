from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rin_pet.atlas import validate_pet_directory  # noqa: E402
from rin_pet.safeio import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_json,
    sha256_file,
)

_CANONICAL_TEXT_SUFFIXES = {".json", ".md"}


def _provenance_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in _CANONICAL_TEXT_SUFFIXES:
        # Git publishes these files with LF via .gitattributes. Hash that
        # canonical representation even when a Windows worktree uses CRLF.
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def _generation_inputs() -> list[dict[str, object]]:
    source_root = ROOT / "artwork" / "source"
    if not source_root.is_dir():
        raise FileNotFoundError(
            "artwork/source is missing; retain the approved prompts and job "
            "manifest before building pet provenance"
        )
    values = []
    source_files = (item for item in source_root.rglob("*") if item.is_file())
    for path in sorted(
        source_files,
        key=lambda item: item.relative_to(ROOT).as_posix().casefold(),
    ):
        data = _provenance_bytes(path)
        values.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    if not values:
        raise ValueError("artwork/source contains no provenance inputs")
    return values


def _write_checksums(pet_dir: Path) -> None:
    lines = "".join(
        f"{sha256_file(pet_dir / name)}  {name}\n"
        for name in ("pet.json", "provenance.json", "spritesheet.webp")
    )
    atomic_write_bytes(pet_dir / "SHA256SUMS", lines.encode())


def build_pet(source: Path) -> dict[str, object]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"final WebP atlas not found: {source}")
    with Image.open(source) as opened:
        image_format = opened.format
        size = opened.size
    if image_format != "WEBP" or size != (1536, 2288):
        raise ValueError(
            f"final atlas must be a 1536x2288 WebP, got {image_format} {size}"
        )

    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="pet-build-", dir=tmp_root))
    target = ROOT / "pet"
    backup: Path | None = None
    try:
        shutil.copyfile(source, staging / "spritesheet.webp")
        atomic_write_json(
            staging / "pet.json",
            {
                "id": "kagamine-rin",
                "displayName": "Kagamine Rin / 鏡音リン",
                "description": (
                    "Unofficial non-commercial Kagamine Rin Codex v2 pet "
                    "with nine animations and sixteen look directions."
                ),
                "spriteVersionNumber": 2,
                "spritesheetPath": "spritesheet.webp",
            },
        )
        atomic_write_json(
            staging / "provenance.json",
            {
                "schemaVersion": 1,
                "petId": "kagamine-rin",
                "createdAt": "2026-07-30",
                "character": "Kagamine Rin / 鏡音リン",
                "characterManager": "Crypton Future Media, Inc.",
                "assetLicense": "Piapro Character License (PCL)",
                "assetLicenseUrl": "https://piapro.jp/license/pcl",
                "characterGuidelineUrl": (
                    "https://piapro.jp/license/character_guideline"
                ),
                "officialAssetsIncluded": False,
                "thirdPartyFanArtIncluded": False,
                "artworkMethod": (
                    "New fan depiction generated with OpenAI built-in image "
                    "generation and assembled with the deterministic Hatch Pet "
                    "v2 pipeline."
                ),
                "spriteContract": {
                    "version": 2,
                    "cellWidth": 192,
                    "cellHeight": 208,
                    "columns": 8,
                    "rows": 11,
                    "usedCells": 74,
                    "transparentPaddingCells": 14,
                    "neutralLookFrame": {"row": 0, "column": 6},
                    "lookDirections": 16,
                },
                "qualityEvidence": [
                    "artwork/qa/atlas-validation.json",
                    "artwork/qa/direction-semantics.json",
                    "artwork/qa/direction-blind-validation.json",
                    "artwork/qa/look-continuity.json",
                    "artwork/qa/final-visual-qa.json",
                ],
                "generationInputs": _generation_inputs(),
            },
        )
        _write_checksums(staging)
        report = validate_pet_directory(staging, strict=True)
        if not report.is_ok(strict=True):
            details = "; ".join(
                f"{issue.code}: {issue.message}" for issue in report.issues
            )
            raise ValueError(f"staged pet failed strict validation: {details}")

        if target.exists():
            manifest = target / "pet.json"
            if not manifest.is_file() or '"kagamine-rin"' not in manifest.read_text(
                encoding="utf-8"
            ):
                raise ValueError(
                    f"refusing to replace an unrecognized pet directory: {target}"
                )
            backup = tmp_root / "previous-pet"
            if backup.exists():
                raise ValueError(
                    f"refusing to overwrite existing build backup: {backup}"
                )
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except Exception:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return report.to_dict(strict=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the validated pet directory from the cleaned v2 WebP."
    )
    parser.add_argument(
        "--spritesheet",
        type=Path,
        default=(
            ROOT / "artwork" / "hatch-run" / "final" / "spritesheet-extended-clean.webp"
        ),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_pet(args.spritesheet)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Built validated pet directory: {ROOT / 'pet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
