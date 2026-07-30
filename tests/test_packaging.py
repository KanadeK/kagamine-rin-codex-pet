from __future__ import annotations

import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from rin_pet.packaging import (
    _release_files,
    build_package,
    build_pet_archive,
    verify_package,
)
from rin_pet.safeio import sha256_file
from tests.helpers import ROOT, require_pet


class PackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def test_project_package_is_deterministic_across_wall_clock_time(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = root / "first.zip"
            second = root / "second.zip"
            build_package(ROOT, first, version="0.1.0")
            time.sleep(1.05)
            build_package(ROOT, second, version="0.1.0")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as bundle:
                self.assertTrue(bundle.namelist())
                self.assertTrue(
                    all(
                        info.date_time == (2026, 1, 1, 0, 0, 0)
                        for info in bundle.infolist()
                    )
                )
                self.assertEqual(len(bundle.namelist()), len(set(bundle.namelist())))

    def test_pet_archive_is_deterministic_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = root / "first.codex-pet"
            second = root / "second.codex-pet"
            build_pet_archive(ROOT, first, version="0.1.0")
            time.sleep(1.05)
            build_pet_archive(ROOT, second, version="0.1.0")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            digest = sha256_file(first)
            self.assertTrue(verify_package(first, digest)["ok"])
            self.assertFalse(verify_package(first, "0" * 64)["ok"])

    def test_bad_versions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "bad.zip"
            with self.assertRaisesRegex(ValueError, "digits and dots"):
                build_package(ROOT, output, version="../1")
            with self.assertRaisesRegex(ValueError, "digits and dots"):
                build_pet_archive(ROOT, output, version="v1")

    def test_release_file_iterator_skips_cache_and_missing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "README.md").write_text("readme", encoding="utf-8")
            package = root / "rin_pet"
            cache = package / "__pycache__"
            cache.mkdir(parents=True)
            (package / "included.py").write_text("pass", encoding="utf-8")
            (package / "excluded.pyc").write_bytes(b"cache")
            (cache / "also-excluded.py").write_text("pass", encoding="utf-8")
            relative = {
                path.relative_to(root).as_posix() for path in _release_files(root)
            }
            self.assertEqual(relative, {"README.md", "rin_pet/included.py"})

    def test_invalid_pet_is_rejected_before_both_package_formats(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "pet").mkdir()
            (root / "pet" / "pet.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "validation failed"):
                build_package(root, root / "bad.zip", version="0.1.0")
            with self.assertRaisesRegex(ValueError, "validation failed"):
                build_pet_archive(root, root / "bad.codex-pet", version="0.1.0")


if __name__ == "__main__":
    unittest.main()
