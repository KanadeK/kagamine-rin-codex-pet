from __future__ import annotations

import json
import tomllib
import unittest

from rin_pet import __version__
from scripts.build_pet import _generation_inputs
from tests.helpers import PET, ROOT


class MetadataTests(unittest.TestCase):
    def test_python_and_project_versions_match(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], __version__)

    def test_pet_id_and_version_match_when_atlas_is_present(self) -> None:
        manifest_path = PET / "pet.json"
        if not manifest_path.is_file():
            self.skipTest("final pet manifest has not been assembled yet")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "kagamine-rin")
        self.assertEqual(manifest["spriteVersionNumber"], 2)

    def test_required_pcl_notice_is_present_in_asset_documents(self) -> None:
        phrase = "この作品はピアプロ・キャラクター・ライセンスに基づいて"
        for name in ("ASSET_LICENSE.md", "NOTICE.md", "README.md", "README.zh-CN.md"):
            with self.subTest(name=name):
                self.assertIn(
                    phrase,
                    (ROOT / name).read_text(encoding="utf-8"),
                )

    def test_artwork_provenance_matches_canonical_published_sources(self) -> None:
        provenance = json.loads((PET / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["generationInputs"], _generation_inputs())


if __name__ == "__main__":
    unittest.main()
