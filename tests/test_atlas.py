from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rin_pet.atlas import (
    _read_manifest,
    _validate_cells,
    _validate_manifest,
    _validate_pixels,
    locate_pet_dir,
    validate_pet_directory,
)
from rin_pet.constants import CELL_HEIGHT, CELL_WIDTH
from rin_pet.models import ValidationReport
from tests.helpers import PET, ROOT, copy_pet, require_pet


class AtlasTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def test_repository_pet_passes_strict_validation(self) -> None:
        report = validate_pet_directory(ROOT, strict=True)
        self.assertTrue(report.is_ok(strict=True), report.to_dict(strict=True))
        self.assertEqual(report.metadata["width"], 1536)
        self.assertEqual(report.metadata["height"], 2288)
        self.assertEqual(report.metadata["usedCells"], 74)
        self.assertEqual(report.metadata["unusedCells"], 14)

    def test_locate_pet_directory_from_repository_and_package_root(self) -> None:
        self.assertEqual(locate_pet_dir(ROOT), PET.resolve())
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw) / "bundle" / "pet"
            copy_pet(package)
            self.assertEqual(locate_pet_dir(Path(raw)), package.resolve())

    def test_tampered_manifest_and_checksum_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pet = copy_pet(Path(raw) / "pet")
            manifest = json.loads((pet / "pet.json").read_text(encoding="utf-8"))
            manifest["id"] = "impostor"
            (pet / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = validate_pet_directory(pet, strict=True)
            codes = {issue.code for issue in report.issues}
            self.assertIn("manifest-id", codes)
            self.assertIn("checksums-mismatch", codes)
            self.assertFalse(report.is_ok(strict=True))

    def test_missing_provenance_is_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pet = copy_pet(Path(raw) / "pet")
            (pet / "provenance.json").unlink()
            (pet / "SHA256SUMS").unlink()
            report = validate_pet_directory(pet, strict=True)
            self.assertFalse(report.is_ok(strict=True))
            self.assertGreaterEqual(len(report.warnings), 2)

    def test_locator_rejects_missing_and_ambiguous_packages(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with self.assertRaises(FileNotFoundError):
                locate_pet_dir(root)
            for name in ("first", "second"):
                pet = root / name / "pet"
                pet.mkdir(parents=True)
                (pet / "pet.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                locate_pet_dir(root)

    def test_manifest_reader_and_schema_errors_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            report = ValidationReport(source=root)
            self.assertIsNone(_read_manifest(root / "missing.json", report))

            invalid = root / "invalid.json"
            invalid.write_bytes(b"\xff")
            self.assertIsNone(_read_manifest(invalid, report))

            invalid.write_text("[]", encoding="utf-8")
            self.assertIsNone(_read_manifest(invalid, report))

            manifest = {
                "id": "wrong",
                "spriteVersionNumber": 1,
                "spritesheetPath": "nested/sheet.webp",
                "displayName": " ",
                "description": None,
            }
            self.assertIsNone(_validate_manifest(manifest, report))
            codes = {issue.code for issue in report.issues}
            self.assertIn("manifest-missing", codes)
            self.assertIn("manifest-invalid", codes)
            self.assertIn("manifest-shape", codes)
            self.assertIn("manifest-id", codes)
            self.assertIn("manifest-displayName", codes)
            self.assertIn("manifest-spritesheet-path", codes)

    def test_cell_and_pixel_corruption_is_detected(self) -> None:
        with Image.open(PET / "spritesheet.webp") as opened:
            image = opened.convert("RGBA")
        transparent = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        image.paste(transparent, (0, 0))
        image.paste(transparent, (CELL_WIDTH, 0))
        image.putpixel((CELL_WIDTH, 0), (20, 20, 20, 255))
        image.putpixel((7 * CELL_WIDTH + 20, 20), (20, 20, 20, 255))

        report = ValidationReport(source=PET)
        _validate_cells(image, report)
        codes = {issue.code for issue in report.issues}
        self.assertIn("used-cell-empty", codes)
        self.assertIn("unused-cell-populated", codes)
        self.assertIn("cell-edge-clipping", codes)
        self.assertIn("cell-low-coverage", codes)

        pixels = Image.new("RGBA", (2, 1))
        pixels.putdata(((1, 2, 3, 0), (255, 0, 255, 255)))
        pixel_report = ValidationReport(source=PET)
        _validate_pixels(pixels, pixel_report)
        pixel_codes = {issue.code for issue in pixel_report.issues}
        self.assertEqual(pixel_codes, {"hidden-rgb", "chroma-residue"})
        self.assertEqual(pixel_report.metadata["hiddenRgbPixels"], 1)
        self.assertEqual(pixel_report.metadata["opaqueChromaPixels"], 1)

    def test_bad_image_provenance_and_checksums_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pet = Path(raw) / "pet"
            pet.mkdir()
            manifest = {
                "id": "kagamine-rin",
                "displayName": "Kagamine Rin",
                "description": "test",
                "spriteVersionNumber": 2,
                "spritesheetPath": "spritesheet.webp",
            }
            (pet / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(
                pet / "spritesheet.webp", format="PNG"
            )
            (pet / "provenance.json").write_text(
                json.dumps(
                    {
                        "petId": "wrong",
                        "schemaVersion": 2,
                        "officialAssetsIncluded": True,
                        "thirdPartyFanArtIncluded": True,
                        "assetLicense": "unknown",
                    }
                ),
                encoding="utf-8",
            )
            digest = "0" * 64
            (pet / "SHA256SUMS").write_text(
                "\n".join(
                    (
                        "not-a-checksum",
                        f"{digest}  pet.json",
                        f"{digest}  pet.json",
                        f"{digest}  spritesheet.webp",
                    )
                ),
                encoding="utf-8",
            )
            report = validate_pet_directory(pet, strict=True)
            codes = {issue.code for issue in report.issues}
            expected = {
                "spritesheet-format",
                "spritesheet-size",
                "provenance-shape",
                "provenance-version",
                "official-assets",
                "third-party-art",
                "provenance-license",
                "checksums-line",
                "checksums-duplicate-entry",
                "checksums-missing-entry",
                "checksums-mismatch",
            }
            self.assertTrue(expected.issubset(codes), sorted(codes))

    def test_missing_invalid_image_and_non_utf8_metadata_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            pet = Path(raw) / "pet"
            pet.mkdir()
            manifest = {
                "id": "kagamine-rin",
                "displayName": "Kagamine Rin",
                "description": "test",
                "spriteVersionNumber": 2,
                "spritesheetPath": "spritesheet.webp",
            }
            (pet / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
            missing = validate_pet_directory(pet)
            self.assertIn("spritesheet-missing", {i.code for i in missing.issues})

            (pet / "spritesheet.webp").write_bytes(b"not-an-image")
            (pet / "provenance.json").write_bytes(b"\xff")
            (pet / "SHA256SUMS").write_bytes(b"\xff")
            invalid = validate_pet_directory(pet)
            codes = {issue.code for issue in invalid.issues}
            self.assertIn("spritesheet-invalid", codes)
            self.assertIn("provenance-invalid", codes)
            self.assertIn("checksums-invalid", codes)


if __name__ == "__main__":
    unittest.main()
