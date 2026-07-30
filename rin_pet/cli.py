from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .atlas import validate_pet_directory
from .installer import doctor_pet, install_pet, repair_pet, uninstall_pet
from .packaging import build_package, build_pet_archive, verify_package
from .replay import build_stage
from .timeline import parse_trace_file


def _repository_root(explicit: Path | None = None) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit.expanduser().resolve())
    candidates.extend((Path.cwd().resolve(), Path(__file__).resolve().parent.parent))
    for candidate in candidates:
        if (
            (candidate / "pet" / "pet.json").is_file()
            and (candidate / "web" / "index.html").is_file()
            and (candidate / "examples" / "sanitized-session.jsonl").is_file()
        ):
            return candidate
    locations = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        "could not locate the extracted project root; run from the repository "
        "or pass --repository-root before the command. Checked: "
        f"{locations}"
    )


def _emit(value: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}: {json.dumps(item, ensure_ascii=False, sort_keys=True)}")
            else:
                print(f"{key}: {item}")
        return
    print(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rin-pet",
        description=(
            "Validate, replay, package, install, diagnose, and repair the "
            "Kagamine Rin Codex pet."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        help="extracted project root for stage, pack, pack-pet, and demo",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a pet directory")
    validate.add_argument("source", nargs="?", type=Path, default=Path("pet"))
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")

    trace = commands.add_parser(
        "trace", help="redact a Codex JSONL trace into a pet timeline"
    )
    trace.add_argument("input", type=Path)
    trace.add_argument("--output", type=Path)
    trace.add_argument("--json", action="store_true")

    stage = commands.add_parser("stage", help="build the offline replay stage")
    stage.add_argument("--timeline", type=Path)
    stage.add_argument("--output", type=Path, default=Path("dist/site"))
    stage.add_argument("--json", action="store_true")

    install = commands.add_parser("install", help="validate and install the pet")
    install.add_argument("--source", type=Path, default=Path("pet"))
    install.add_argument("--codex-home", type=Path)
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true")

    doctor = commands.add_parser("doctor", help="diagnose an installed pet")
    doctor.add_argument("--source", type=Path)
    doctor.add_argument("--codex-home", type=Path)
    doctor.add_argument("--json", action="store_true")

    repair = commands.add_parser("repair", help="repair via validated replacement")
    repair.add_argument("--source", type=Path, default=Path("pet"))
    repair.add_argument("--codex-home", type=Path)
    repair.add_argument("--dry-run", action="store_true")
    repair.add_argument("--json", action="store_true")

    uninstall = commands.add_parser(
        "uninstall", help="move the installed pet into the backup store"
    )
    uninstall.add_argument("--codex-home", type=Path)
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")

    package = commands.add_parser("pack", help="build a deterministic release ZIP")
    package.add_argument("--version", default=__version__)
    package.add_argument("--output", type=Path)
    package.add_argument("--manifest", type=Path)
    package.add_argument("--checksums", type=Path)
    package.add_argument("--json", action="store_true")

    pet_package = commands.add_parser(
        "pack-pet", help="build a standalone deterministic .codex-pet archive"
    )
    pet_package.add_argument("--version", default=__version__)
    pet_package.add_argument("--output", type=Path)
    pet_package.add_argument("--json", action="store_true")

    verify = commands.add_parser("verify-package", help="verify a release SHA-256")
    verify.add_argument("archive", type=Path)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--json", action="store_true")

    demo = commands.add_parser(
        "demo", help="parse the safe fixture and build a complete offline stage"
    )
    demo.add_argument("--output", type=Path, default=Path("dist/demo"))
    demo.add_argument("--json", action="store_true")
    return parser


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.command == "validate":
        report = validate_pet_directory(args.source, strict=args.strict)
        value = report.to_dict(strict=args.strict)
        return value, 0 if value["ok"] else 1
    if args.command == "trace":
        timeline = parse_trace_file(args.input, args.output)
        if args.output is None:
            return timeline, 0
        return {
            "ok": True,
            "output": str(args.output),
            "events": len(timeline["events"]),
            "inputSha256": timeline["source"]["sha256"],
        }, 0
    if args.command == "stage":
        root = _repository_root(args.repository_root)
        return (
            build_stage(root, args.output, timeline_path=args.timeline),
            0,
        )
    if args.command == "install":
        result = install_pet(
            args.source,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
        return result.to_dict(), 0
    if args.command == "doctor":
        result = doctor_pet(codex_home=args.codex_home, source=args.source)
        return result, 0 if result["ok"] else 1
    if args.command == "repair":
        result = repair_pet(
            args.source,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
        return result.to_dict(), 0
    if args.command == "uninstall":
        result = uninstall_pet(
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
        return result.to_dict(), 0
    if args.command == "pack":
        root = _repository_root(args.repository_root)
        output = args.output or (
            root / "dist" / f"kagamine-rin-codex-pet-v{args.version}.zip"
        )
        manifest = args.manifest or root / "dist" / "release-manifest.json"
        checksums = args.checksums or root / "dist" / "SHA256SUMS"
        return (
            build_package(
                root,
                output,
                version=args.version,
                manifest_output=manifest,
                checksums_output=checksums,
            ),
            0,
        )
    if args.command == "pack-pet":
        root = _repository_root(args.repository_root)
        output = args.output or (
            root / "dist" / f"kagamine-rin-v{args.version}.codex-pet"
        )
        return (
            build_pet_archive(
                root,
                output,
                version=args.version,
            ),
            0,
        )
    if args.command == "verify-package":
        result = verify_package(args.archive, args.sha256)
        return result, 0 if result["ok"] else 1
    if args.command == "demo":
        root = _repository_root(args.repository_root)
        timeline = args.output / "sanitized-timeline.json"
        parse_trace_file(root / "examples" / "sanitized-session.jsonl", timeline)
        result = build_stage(root, args.output / "site", timeline_path=timeline)
        result["timeline"] = str(timeline)
        return result, 0
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    as_json = bool(getattr(args, "json", False))
    try:
        result, exit_code = _run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        error = {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }
        _emit(error, as_json=as_json)
        return 2
    _emit(result, as_json=as_json)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
