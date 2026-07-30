from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .constants import (
    ATLAS_COLUMNS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    FRAME_COUNTS,
    NEUTRAL_LOOK_FRAME,
    PET_ID,
    SPRITE_VERSION,
    STATE_ROWS,
)
from .models import ValidationReport
from .safeio import sha256_file


def locate_pet_dir(source: Path) -> Path:
    source = source.resolve()
    candidates = (source, source / "pet")
    for candidate in candidates:
        if (candidate / "pet.json").is_file():
            return candidate
    matches = list(source.glob("*/pet/pet.json")) if source.is_dir() else []
    if len(matches) == 1:
        return matches[0].parent
    raise FileNotFoundError(
        f"could not find pet.json in {source}, {source / 'pet'}, "
        "or one package-root/pet directory"
    )


def _read_manifest(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.add("error", "manifest-missing", "pet.json is missing", "pet.json")
        return None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.add(
            "error", "manifest-invalid", f"pet.json is not valid UTF-8 JSON: {exc}"
        )
        return None
    if not isinstance(value, dict):
        report.add("error", "manifest-shape", "pet.json must contain an object")
        return None
    return value


def _validate_manifest(
    manifest: dict[str, Any], report: ValidationReport
) -> Path | None:
    expected = {
        "id": PET_ID,
        "spriteVersionNumber": SPRITE_VERSION,
        "spritesheetPath": "spritesheet.webp",
    }
    for field, wanted in expected.items():
        actual = manifest.get(field)
        if actual != wanted:
            report.add(
                "error",
                f"manifest-{field}",
                f"{field} must be {wanted!r}, got {actual!r}",
                f"pet.json:{field}",
            )
    for field in ("displayName", "description"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            report.add(
                "error",
                f"manifest-{field}",
                f"{field} must be a non-empty string",
                f"pet.json:{field}",
            )
    path = manifest.get("spritesheetPath")
    if isinstance(path, str) and path == Path(path).name:
        return report.source / path
    report.add(
        "error",
        "manifest-spritesheet-path",
        "spritesheetPath must be a plain filename inside the pet directory",
    )
    return None


def _alpha_bbox(cell: Image.Image) -> tuple[int, int, int, int] | None:
    return cell.getchannel("A").getbbox()


def _validate_cells(image: Image.Image, report: ValidationReport) -> None:
    used_cells = 0
    unused_cells = 0
    near_edge: list[str] = []
    low_coverage: list[str] = []
    for state, row in STATE_ROWS.items():
        used = FRAME_COUNTS[state]
        for column in range(ATLAS_COLUMNS):
            box = (
                column * CELL_WIDTH,
                row * CELL_HEIGHT,
                (column + 1) * CELL_WIDTH,
                (row + 1) * CELL_HEIGHT,
            )
            cell = image.crop(box)
            bbox = _alpha_bbox(cell)
            label = f"{state}[{column}]"
            required = column < used or (row, column) == NEUTRAL_LOOK_FRAME
            if required:
                used_cells += 1
                if bbox is None:
                    report.add(
                        "error", "used-cell-empty", "required cell is empty", label
                    )
                    continue
                alpha = cell.getchannel("A")
                opaque_area = sum(1 for value in alpha.tobytes() if value > 0)
                if opaque_area < int(CELL_WIDTH * CELL_HEIGHT * 0.015):
                    low_coverage.append(label)
                left, top, right, bottom = bbox
                if (
                    left <= 1
                    or top <= 1
                    or right >= CELL_WIDTH - 1
                    or bottom >= CELL_HEIGHT - 1
                ):
                    near_edge.append(label)
            else:
                unused_cells += 1
                if bbox is not None:
                    report.add(
                        "error",
                        "unused-cell-populated",
                        "unused cell must be fully transparent",
                        label,
                    )
    if near_edge:
        report.add(
            "error",
            "cell-edge-clipping",
            "visible pixels touch the two-pixel cell safety edge",
            ", ".join(near_edge),
        )
    if low_coverage:
        report.add(
            "error",
            "cell-low-coverage",
            "required cells contain too little visible sprite content",
            ", ".join(low_coverage),
        )
    report.metadata["usedCells"] = used_cells
    report.metadata["unusedCells"] = unused_cells


def _validate_pixels(image: Image.Image, report: ValidationReport) -> None:
    hidden_rgb = 0
    opaque_magenta = 0
    pixels = image.tobytes()
    for offset in range(0, len(pixels), 4):
        red, green, blue, alpha = pixels[offset : offset + 4]
        if alpha == 0 and (red or green or blue):
            hidden_rgb += 1
        if alpha > 0 and red >= 245 and green <= 12 and blue >= 245:
            opaque_magenta += 1
    if hidden_rgb:
        report.add(
            "error",
            "hidden-rgb",
            f"{hidden_rgb} fully transparent pixels retain non-zero RGB",
        )
    if opaque_magenta:
        report.add(
            "error",
            "chroma-residue",
            f"{opaque_magenta} visible pixels still match the magenta key",
        )
    report.metadata["hiddenRgbPixels"] = hidden_rgb
    report.metadata["opaqueChromaPixels"] = opaque_magenta


def validate_pet_directory(source: Path, *, strict: bool = False) -> ValidationReport:
    pet_dir = locate_pet_dir(source)
    report = ValidationReport(source=pet_dir)
    manifest = _read_manifest(pet_dir / "pet.json", report)
    sheet_path = _validate_manifest(manifest, report) if manifest else None

    if sheet_path is not None:
        try:
            with Image.open(sheet_path) as opened:
                image_format = opened.format
                image = opened.convert("RGBA")
        except FileNotFoundError:
            report.add("error", "spritesheet-missing", "spritesheet.webp is missing")
        except UnidentifiedImageError as exc:
            report.add(
                "error", "spritesheet-invalid", f"spritesheet cannot be decoded: {exc}"
            )
        else:
            report.metadata.update(
                {
                    "format": image_format,
                    "mode": image.mode,
                    "width": image.width,
                    "height": image.height,
                    "sha256": sha256_file(sheet_path),
                    "bytes": sheet_path.stat().st_size,
                }
            )
            if image_format != "WEBP":
                report.add("error", "spritesheet-format", "spritesheet must be WebP")
            if image.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
                report.add(
                    "error",
                    "spritesheet-size",
                    f"expected {ATLAS_WIDTH}x{ATLAS_HEIGHT}, got "
                    f"{image.width}x{image.height}",
                )
            else:
                _validate_cells(image, report)
                _validate_pixels(image, report)

    required_repo_files = (
        pet_dir / "provenance.json",
        pet_dir / "SHA256SUMS",
    )
    for required in required_repo_files:
        if not required.is_file():
            report.add(
                "warning",
                "provenance-file-missing",
                f"required release/provenance file is missing: {required.name}",
                str(required),
            )
    provenance_path = pet_dir / "provenance.json"
    if provenance_path.is_file():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            report.add(
                "error",
                "provenance-invalid",
                f"provenance.json is not valid UTF-8 JSON: {exc}",
            )
        else:
            if not isinstance(provenance, dict) or provenance.get("petId") != PET_ID:
                report.add(
                    "error",
                    "provenance-shape",
                    f"provenance.json petId must be {PET_ID!r}",
                )
            if isinstance(provenance, dict):
                if provenance.get("schemaVersion") != 1:
                    report.add(
                        "error",
                        "provenance-version",
                        "provenance.json schemaVersion must be 1",
                    )
                if provenance.get("officialAssetsIncluded") is not False:
                    report.add(
                        "error",
                        "official-assets",
                        "provenance must explicitly state that no official "
                        "assets are included",
                    )
                if provenance.get("thirdPartyFanArtIncluded") is not False:
                    report.add(
                        "error",
                        "third-party-art",
                        "provenance must explicitly state that no third-party "
                        "fan art is included",
                    )
                asset_license = provenance.get("assetLicense")
                if (
                    not isinstance(asset_license, str)
                    or "Piapro Character License" not in asset_license
                ):
                    report.add(
                        "error",
                        "provenance-license",
                        "provenance assetLicense must identify the Piapro "
                        "Character License",
                    )
    checksums_path = pet_dir / "SHA256SUMS"
    if checksums_path.is_file():
        try:
            lines = checksums_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            report.add("error", "checksums-invalid", f"SHA256SUMS is not UTF-8: {exc}")
        else:
            entries: dict[str, str] = {}
            for line in lines:
                digest, separator, name = line.partition("  ")
                if (
                    separator != "  "
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest.lower())
                    or "/" in name
                    or "\\" in name
                ):
                    report.add(
                        "error",
                        "checksums-line",
                        f"invalid SHA256SUMS entry: {line!r}",
                    )
                    continue
                if name in entries:
                    report.add(
                        "error",
                        "checksums-duplicate-entry",
                        f"SHA256SUMS contains duplicate entry for {name}",
                    )
                entries[name] = digest.lower()
            for name in ("pet.json", "spritesheet.webp", "provenance.json"):
                file = pet_dir / name
                if name not in entries:
                    report.add(
                        "error",
                        "checksums-missing-entry",
                        f"SHA256SUMS has no entry for {name}",
                    )
                elif file.is_file() and sha256_file(file) != entries[name]:
                    report.add(
                        "error",
                        "checksums-mismatch",
                        f"SHA-256 mismatch for {name}",
                    )

    report.metadata["atlasColumns"] = ATLAS_COLUMNS
    report.metadata["atlasRows"] = len(STATE_ROWS)
    report.metadata["spriteVersionNumber"] = SPRITE_VERSION
    report.metadata["strictOk"] = report.is_ok(strict=True)
    return report
