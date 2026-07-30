from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PET = ROOT / "pet"


def require_pet(testcase: object) -> None:
    if not (PET / "spritesheet.webp").is_file():
        testcase.skipTest("final pet atlas has not been assembled yet")


def copy_pet(destination: Path) -> Path:
    shutil.copytree(PET, destination)
    return destination
