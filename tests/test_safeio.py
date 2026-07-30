from __future__ import annotations

import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from rin_pet.safeio import (
    SafetyError,
    ensure_within,
    exclusive_lock,
    extract_zip_safely,
)


class SafeIoTests(unittest.TestCase):
    def _archive(self, root: Path, name: str, member: str) -> Path:
        archive = root / name
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(member, b"payload")
        return archive

    def test_safe_archive_extracts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = self._archive(root, "safe.zip", "nested/file.txt")
            destination = root / "out"
            extract_zip_safely(archive, destination)
            self.assertEqual(
                (destination / "nested" / "file.txt").read_bytes(), b"payload"
            )

    def test_archive_traversal_absolute_and_drive_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for index, member in enumerate(
                (
                    "../escape.txt",
                    "/absolute.txt",
                    "C:/drive.txt",
                    "a/../b.txt",
                    "a//double.txt",
                )
            ):
                with self.subTest(member=member):
                    archive = self._archive(root, f"unsafe-{index}.zip", member)
                    with self.assertRaises(SafetyError):
                        extract_zip_safely(archive, root / f"out-{index}")

    def test_zip_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "symlink.zip"
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(info, "target")
            with self.assertRaisesRegex(SafetyError, "symlink"):
                extract_zip_safely(archive, root / "out")

    def test_archive_member_and_expansion_limits_are_enforced_before_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = self._archive(root, "large.zip", "payload.bin")
            destination = root / "out"
            with patch("rin_pet.safeio.MAX_ZIP_TOTAL_BYTES", 1):
                with self.assertRaisesRegex(SafetyError, "expands"):
                    extract_zip_safely(archive, destination)
            self.assertFalse(destination.exists())

            with patch("rin_pet.safeio.MAX_ZIP_MEMBERS", 0):
                with self.assertRaisesRegex(SafetyError, "members"):
                    extract_zip_safely(archive, destination)
            self.assertFalse(destination.exists())

    def test_case_colliding_archive_members_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "collision.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("Pet.json", b"one")
                bundle.writestr("pet.json", b"two")
            with self.assertRaisesRegex(SafetyError, "case-colliding"):
                extract_zip_safely(archive, root / "out")

    def test_ensure_within_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertEqual(ensure_within(root / "a", root), (root / "a").resolve())
            with self.assertRaisesRegex(SafetyError, "escapes"):
                ensure_within(root.parent / "escape", root)

    def test_exclusive_lock_rejects_concurrent_owner_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            lock = Path(raw) / "lock"
            with exclusive_lock(lock):
                self.assertTrue(lock.is_file())
                with self.assertRaisesRegex(SafetyError, "already exists"):
                    with exclusive_lock(lock):
                        pass
            self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
