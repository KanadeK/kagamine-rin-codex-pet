from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

CHROMA_KEY = (255, 0, 255)
CHROMA_DISTANCE_MAX = 96


def scrub(source: Path, png_output: Path, webp_output: Path) -> dict[str, object]:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    pixels = list(image.getdata())
    changed = 0
    cleaned: list[tuple[int, int, int, int]] = []
    for red, green, blue, alpha in pixels:
        distance_squared = (
            (red - CHROMA_KEY[0]) ** 2
            + (green - CHROMA_KEY[1]) ** 2
            + (blue - CHROMA_KEY[2]) ** 2
        )
        if alpha > 0 and distance_squared <= CHROMA_DISTANCE_MAX**2:
            cleaned.append((0, 0, 0, 0))
            changed += 1
        else:
            cleaned.append((red, green, blue, alpha))
    image.putdata(cleaned)

    png_output.parent.mkdir(parents=True, exist_ok=True)
    webp_output.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_output, format="PNG", optimize=False)
    image.save(
        webp_output,
        format="WEBP",
        lossless=True,
        quality=100,
        method=6,
        exact=True,
    )
    return {
        "ok": changed > 0,
        "algorithm": "project-chroma-residue-to-transparent",
        "threshold": {
            "key": list(CHROMA_KEY),
            "euclideanDistanceMax": CHROMA_DISTANCE_MAX,
        },
        "changedPixels": changed,
        "hiddenRgbReplacement": [0, 0, 0, 0],
        "png": png_output.name,
        "webp": webp_output.name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove exact project color-key residue after edge despill."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--png-output", type=Path, required=True)
    parser.add_argument("--webp-output", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    result = scrub(
        args.source.resolve(),
        args.png_output.resolve(),
        args.webp_output.resolve(),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
