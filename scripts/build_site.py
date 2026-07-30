from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rin_pet.replay import build_stage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the offline RinTrace site.")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "site")
    parser.add_argument(
        "--timeline",
        type=Path,
        default=ROOT / "examples" / "sanitized-timeline.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_stage(ROOT, args.output, timeline_path=args.timeline)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Built offline stage: {result['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
