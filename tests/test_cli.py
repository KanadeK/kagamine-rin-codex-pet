from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from rin_pet.cli import _emit, _repository_root, _run, main
from tests.helpers import PET, ROOT, require_pet


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def _run(self, *args: str) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(list(args))
        return code, json.loads(output.getvalue())

    def test_validate_json_success(self) -> None:
        code, value = self._run("validate", str(PET), "--strict", "--json")
        self.assertEqual(code, 0)
        self.assertTrue(value["ok"])

    def test_trace_failure_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "bad.jsonl"
            source.write_text("not json", encoding="utf-8")
            code, value = self._run("trace", str(source), "--json")
            self.assertEqual(code, 2)
            self.assertFalse(value["ok"])
            self.assertEqual(value["error"], "TimelineError")

    def test_verify_mismatch_returns_one(self) -> None:
        code, value = self._run(
            "verify-package",
            str(PET / "spritesheet.webp"),
            "--sha256",
            "0" * 64,
            "--json",
        )
        self.assertEqual(code, 1)
        self.assertFalse(value["ok"])

    def test_trace_success_with_and_without_output(self) -> None:
        fixture = ROOT / "examples" / "sanitized-session.jsonl"
        code, timeline = self._run("trace", str(fixture), "--json")
        self.assertEqual(code, 0)
        self.assertTrue(timeline["events"])
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "timeline.json"
            code, result = self._run(
                "trace", str(fixture), "--output", str(target), "--json"
            )
            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertTrue(target.is_file())

    def test_command_adapters_cover_stage_install_repair_and_uninstall(self) -> None:
        fake_install = MagicMock()
        fake_install.to_dict.return_value = {"ok": True, "action": "install"}
        fake_repair = MagicMock()
        fake_repair.to_dict.return_value = {"ok": True, "action": "repair"}
        fake_uninstall = MagicMock()
        fake_uninstall.to_dict.return_value = {"ok": True, "action": "uninstall"}
        with (
            patch("rin_pet.cli.build_stage", return_value={"ok": True}) as stage,
            patch("rin_pet.cli.install_pet", return_value=fake_install) as install,
            patch("rin_pet.cli.repair_pet", return_value=fake_repair) as repair,
            patch(
                "rin_pet.cli.uninstall_pet", return_value=fake_uninstall
            ) as uninstall,
        ):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                code, value = self._run(
                    "--repository-root",
                    str(ROOT),
                    "stage",
                    "--timeline",
                    str(root / "timeline.json"),
                    "--output",
                    str(root / "site"),
                    "--json",
                )
                self.assertEqual((code, value["ok"]), (0, True))
                stage.assert_called_once()

                code, value = self._run(
                    "install",
                    "--source",
                    str(PET),
                    "--codex-home",
                    str(root / "codex"),
                    "--dry-run",
                    "--json",
                )
                self.assertEqual((code, value["action"]), (0, "install"))
                install.assert_called_once()

                code, value = self._run(
                    "repair",
                    "--source",
                    str(PET),
                    "--codex-home",
                    str(root / "codex"),
                    "--dry-run",
                    "--json",
                )
                self.assertEqual((code, value["action"]), (0, "repair"))
                repair.assert_called_once()

                code, value = self._run(
                    "uninstall",
                    "--codex-home",
                    str(root / "codex"),
                    "--dry-run",
                    "--json",
                )
                self.assertEqual((code, value["action"]), (0, "uninstall"))
                uninstall.assert_called_once()

    def test_command_adapters_cover_doctor_pack_pet_pack_and_demo(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "project.zip"
            pet_package = root / "rin.codex-pet"
            with (
                patch(
                    "rin_pet.cli.doctor_pet",
                    return_value={"ok": False, "status": "missing"},
                ),
                patch(
                    "rin_pet.cli.build_package",
                    return_value={"ok": True, "archive": {"path": package.name}},
                ) as pack,
                patch(
                    "rin_pet.cli.build_pet_archive",
                    return_value={"ok": True, "archive": {"path": pet_package.name}},
                ) as pack_pet,
                patch("rin_pet.cli.parse_trace_file", return_value={"events": []}),
                patch(
                    "rin_pet.cli.build_stage",
                    return_value={"ok": True, "timelineEvents": 0},
                ),
            ):
                code, value = self._run(
                    "doctor",
                    "--codex-home",
                    str(root / "codex"),
                    "--source",
                    str(PET),
                    "--json",
                )
                self.assertEqual((code, value["status"]), (1, "missing"))

                prefix = ("--repository-root", str(ROOT))
                code, value = self._run(
                    *prefix,
                    "pack",
                    "--output",
                    str(package),
                    "--manifest",
                    str(root / "manifest.json"),
                    "--checksums",
                    str(root / "SHA256SUMS"),
                    "--json",
                )
                self.assertEqual((code, value["ok"]), (0, True))
                pack.assert_called_once()

                code, value = self._run(
                    *prefix,
                    "pack-pet",
                    "--output",
                    str(pet_package),
                    "--json",
                )
                self.assertEqual((code, value["ok"]), (0, True))
                pack_pet.assert_called_once()

                code, value = self._run(
                    *prefix,
                    "demo",
                    "--output",
                    str(root / "demo"),
                    "--json",
                )
                self.assertEqual((code, value["ok"]), (0, True))
                self.assertIn("timeline", value)

    def test_text_emitter_repository_lookup_and_unhandled_command(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _emit({"nested": [1], "scalar": 2}, as_json=False)
            _emit("done", as_json=False)
        rendered = output.getvalue()
        self.assertIn("nested: [1]", rendered)
        self.assertIn("scalar: 2", rendered)
        self.assertTrue(rendered.rstrip().endswith("done"))
        self.assertEqual(_repository_root(ROOT), ROOT.resolve())

        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "missing"
            with (
                patch("rin_pet.cli.Path.cwd", return_value=missing),
                patch(
                    "rin_pet.cli.__file__",
                    str(missing / "rin_pet" / "cli.py"),
                ),
            ):
                with self.assertRaises(FileNotFoundError):
                    _repository_root(missing)

        args = MagicMock(command="not-a-command")
        with self.assertRaises(AssertionError):
            _run(args)


if __name__ == "__main__":
    unittest.main()
