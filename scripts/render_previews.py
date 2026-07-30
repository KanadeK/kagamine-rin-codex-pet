from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rin_pet.constants import (  # noqa: E402
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    FRAME_COUNTS,
    STATE_ROWS,
)

FRAME_DURATIONS = {
    "idle": [280, 110, 110, 140, 140, 320],
    "running-right": [120, 120, 120, 120, 120, 120, 120, 220],
    "running-left": [120, 120, 120, 120, 120, 120, 120, 220],
    "waving": [140, 140, 140, 280],
    "jumping": [140, 140, 140, 140, 280],
    "failed": [140, 140, 140, 140, 140, 140, 140, 240],
    "waiting": [150, 150, 150, 150, 150, 260],
    "running": [120, 120, 120, 120, 120, 220],
    "review": [150, 150, 150, 150, 150, 280],
}


def render_previews(atlas_path: Path, output_dir: Path) -> dict[str, object]:
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
    if atlas.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise ValueError(
            f"expected {ATLAS_WIDTH}x{ATLAS_HEIGHT} v2 atlas, got "
            f"{atlas.width}x{atlas.height}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    previews: list[dict[str, object]] = []
    for state, durations in FRAME_DURATIONS.items():
        count = FRAME_COUNTS[state]
        if len(durations) != count:
            raise ValueError(f"{state} duration count does not match atlas contract")
        row = STATE_ROWS[state]
        frames = [
            atlas.crop(
                (
                    column * CELL_WIDTH,
                    row * CELL_HEIGHT,
                    (column + 1) * CELL_WIDTH,
                    (row + 1) * CELL_HEIGHT,
                )
            )
            for column in range(count)
        ]
        output = output_dir / f"{state}.gif"
        frames[0].save(
            output,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
            optimize=False,
        )
        previews.append(
            {
                "state": state,
                "path": output.name,
                "frames": count,
                "bytes": output.stat().st_size,
            }
        )
    return {"ok": True, "atlas": str(atlas_path), "previews": previews}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render clean animation GIFs directly from the final v2 atlas."
    )
    parser.add_argument(
        "--atlas",
        type=Path,
        default=ROOT / "pet" / "spritesheet.webp",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "media" / "animations",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = render_previews(args.atlas.resolve(), args.output.resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Rendered {len(result['previews'])} previews to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
