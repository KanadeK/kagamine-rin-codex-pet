from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rin_pet import __version__
from scripts.build_release import build_release
from scripts.verify_release import verify_release
from tests.helpers import require_pet


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        require_pet(self)

    def test_complete_release_build_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            manifest = build_release(__version__, output)
            self.assertTrue(manifest["ok"])
            self.assertEqual(len(manifest["artifacts"]), 2)
            verified = verify_release(
                output,
                output / "release-manifest.json",
                output / "SHA256SUMS",
            )
            self.assertTrue(verified["ok"])
            self.assertEqual(len(verified["artifacts"]), 2)

    def test_release_verification_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            manifest = build_release(__version__, output)
            archive = output / str(manifest["artifacts"][0]["path"])
            with archive.open("ab") as handle:
                handle.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_release(
                    output,
                    output / "release-manifest.json",
                    output / "SHA256SUMS",
                )

    def test_release_version_must_match_project(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(ValueError, "does not match"):
                build_release("9.9.9", Path(raw))


if __name__ == "__main__":
    unittest.main()
