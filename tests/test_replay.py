from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rin_pet.replay import build_stage
from rin_pet.safeio import SafetyError
from rin_pet.timeline import parse_trace_file
from tests.helpers import ROOT, require_pet


class ReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def _timeline(self, root: Path) -> Path:
        output = root / "timeline.json"
        parse_trace_file(ROOT / "examples" / "sanitized-session.jsonl", output)
        return output

    def test_builds_complete_offline_stage_and_replaces_own_stage(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            timeline = self._timeline(root)
            output = root / "site"
            first = build_stage(ROOT, output, timeline_path=timeline)
            second = build_stage(ROOT, output, timeline_path=timeline)
            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertTrue((output / ".rin-pet-stage").is_file())
            self.assertTrue((output / "pet" / "spritesheet.webp").is_file())
            manifest = json.loads(
                (output / "site-manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(manifest["offline"])
            self.assertFalse(manifest["analytics"])
            self.assertIn("timeline.json", manifest["files"])

    def test_refuses_to_replace_unowned_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "site"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(SafetyError, "not created"):
                build_stage(ROOT, output, timeline_path=self._timeline(root))
            self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_invalid_timeline_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            timeline = root / "timeline.json"
            timeline.write_text('{"schemaVersion":1,"events":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid timeline"):
                build_stage(ROOT, root / "site", timeline_path=timeline)

    def test_default_timeline_and_unsafe_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "site"
            result = build_stage(ROOT, output)
            self.assertTrue(result["ok"])
            with self.assertRaisesRegex(SafetyError, "unsafe stage output"):
                build_stage(ROOT, ROOT)

    def test_unreadable_timeline_and_failed_copy_leave_no_stage(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "site"
            with self.assertRaisesRegex(ValueError, "cannot read timeline"):
                build_stage(ROOT, output, timeline_path=root / "missing.json")
            self.assertFalse(output.exists())

            broken_root = root / "repository"
            (broken_root / "pet").mkdir(parents=True)
            for file in (ROOT / "pet").iterdir():
                if file.is_file():
                    (broken_root / "pet" / file.name).write_bytes(file.read_bytes())
            (broken_root / "web").mkdir()
            (broken_root / "examples").mkdir()
            timeline = self._timeline(root)
            with self.assertRaises(FileNotFoundError):
                build_stage(broken_root, output, timeline_path=timeline)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
