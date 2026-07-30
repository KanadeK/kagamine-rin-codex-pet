from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rin_pet.installer import (
    _resolved_source,
    default_codex_home,
    doctor_pet,
    install_pet,
    read_checksums,
    repair_pet,
    uninstall_pet,
    verify_provenance,
)
from rin_pet.packaging import build_pet_archive
from rin_pet.safeio import SafetyError
from tests.helpers import PET, ROOT, require_pet


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def test_install_doctor_repair_and_recoverable_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw) / "codex"
            installed = install_pet(PET, codex_home=codex_home)
            self.assertTrue(installed.target.is_dir())
            self.assertIsNone(installed.backup)
            self.assertTrue(doctor_pet(codex_home=codex_home, source=PET)["ok"])

            (installed.target / "pet.json").write_text("{}", encoding="utf-8")
            unhealthy = doctor_pet(codex_home=codex_home, source=PET)
            self.assertFalse(unhealthy["ok"])
            self.assertEqual(unhealthy["status"], "invalid")

            repaired = repair_pet(PET, codex_home=codex_home)
            self.assertIsNotNone(repaired.backup)
            self.assertTrue(repaired.backup.is_dir())
            self.assertTrue(doctor_pet(codex_home=codex_home, source=PET)["ok"])

            removed = uninstall_pet(codex_home=codex_home)
            self.assertFalse(removed.target.exists())
            self.assertTrue(removed.backup.is_dir())
            self.assertEqual(doctor_pet(codex_home=codex_home)["status"], "missing")

    def test_dry_run_does_not_create_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw) / "does-not-exist"
            result = install_pet(PET, codex_home=codex_home, dry_run=True)
            self.assertTrue(result.dry_run)
            self.assertFalse(codex_home.exists())

    def test_invalid_source_is_rejected_before_target_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "pet.json").write_text("{}", encoding="utf-8")
            codex_home = root / "codex"
            with self.assertRaises((FileNotFoundError, ValueError)):
                install_pet(source, codex_home=codex_home)
            self.assertFalse((codex_home / "pets").exists())

    def test_doctor_rejects_an_invalid_comparison_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex_home = root / "codex"
            install_pet(PET, codex_home=codex_home)
            source = root / "source"
            source.mkdir()
            (source / "pet.json").write_text("{}", encoding="utf-8")
            with self.assertRaises((FileNotFoundError, ValueError)):
                doctor_pet(codex_home=codex_home, source=source)

    def test_standalone_codex_pet_archive_installs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "rin.codex-pet"
            build_pet_archive(ROOT, archive, version="0.1.0")
            result = install_pet(archive, codex_home=root / "codex")
            self.assertTrue(result.target.is_dir())
            self.assertTrue(doctor_pet(codex_home=root / "codex")["ok"])

    def test_defaults_checksum_reader_and_provenance_reader(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            configured = Path(raw) / "configured"
            with patch(
                "rin_pet.installer.os.environ.get",
                return_value=str(configured),
            ):
                self.assertEqual(default_codex_home(), configured)
            with patch("rin_pet.installer.os.environ.get", return_value=None):
                self.assertEqual(default_codex_home(), Path.home() / ".codex")

            checksums = read_checksums(PET)
            self.assertIn("spritesheet.webp", checksums)
            provenance = verify_provenance(PET)
            self.assertEqual(provenance["petId"], "kagamine-rin")

            broken = Path(raw) / "broken"
            broken.mkdir()
            (broken / "SHA256SUMS").write_text(
                "\ninvalid\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid checksum"):
                read_checksums(broken)
            (broken / "provenance.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid petId"):
                verify_provenance(broken)

    def test_invalid_archive_source_and_missing_uninstall_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "pet.txt"
            source.write_text("not an archive", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                with _resolved_source(source):
                    self.fail("invalid source must not yield")
            with self.assertRaises(FileNotFoundError):
                uninstall_pet(codex_home=root / "codex")

    def test_doctor_marks_a_valid_install_that_differs_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw) / "codex"
            install_pet(PET, codex_home=codex_home)
            with patch("rin_pet.installer._validate_source", return_value="0" * 64):
                result = doctor_pet(codex_home=codex_home, source=PET)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "modified")
            self.assertFalse(result["matchesSource"])

    def test_staging_mismatch_is_rejected_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw) / "codex"
            with patch(
                "rin_pet.installer._validate_source",
                side_effect=("a" * 64, "b" * 64),
            ):
                with self.assertRaisesRegex(ValueError, "staging hash differs"):
                    install_pet(PET, codex_home=codex_home)
            self.assertFalse((codex_home / "pets" / "kagamine-rin").exists())

    def test_failed_promotion_restores_previous_install(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex_home = Path(raw) / "codex"
            first = install_pet(PET, codex_home=codex_home)
            original = (first.target / "spritesheet.webp").read_bytes()
            with patch(
                "rin_pet.installer.os.replace",
                side_effect=PermissionError("promotion blocked"),
            ):
                with self.assertRaisesRegex(PermissionError, "promotion blocked"):
                    repair_pet(PET, codex_home=codex_home)
            self.assertTrue(first.target.is_dir())
            self.assertEqual(
                (first.target / "spritesheet.webp").read_bytes(),
                original,
            )

    def test_backup_collision_and_dry_run_uninstall_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex_home = root / "codex"
            installed = install_pet(PET, codex_home=codex_home)
            dry_run = uninstall_pet(codex_home=codex_home, dry_run=True)
            self.assertTrue(dry_run.dry_run)
            self.assertTrue(installed.target.is_dir())

            collision = root / "collision"
            collision.mkdir()
            with patch("rin_pet.installer._backup_path", return_value=collision):
                with self.assertRaisesRegex(SafetyError, "backup collision"):
                    repair_pet(PET, codex_home=codex_home)
                self.assertTrue(installed.target.is_dir())
                with self.assertRaisesRegex(SafetyError, "backup collision"):
                    uninstall_pet(codex_home=codex_home)
                self.assertTrue(installed.target.is_dir())


if __name__ == "__main__":
    unittest.main()
