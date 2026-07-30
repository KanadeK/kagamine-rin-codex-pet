from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rin_pet import __version__  # noqa: E402
from rin_pet.atlas import validate_pet_directory  # noqa: E402
from rin_pet.packaging import build_package, build_pet_archive  # noqa: E402
from rin_pet.replay import build_stage  # noqa: E402
from rin_pet.timeline import parse_trace_file  # noqa: E402


class GateFailure(RuntimeError):
    pass


def configure_utf8_output(*streams: Any) -> None:
    """Use deterministic UTF-8 output even on legacy Windows code pages."""
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def run_command(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    record = {
        "name": name,
        "command": command,
        "exitCode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }
    if result.returncode != 0:
        raise GateFailure(
            f"{name} failed with exit code {result.returncode}\n"
            f"{record['stdout']}\n{record['stderr']}"
        )
    return record


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise GateFailure(f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout


def run_gate(*, allow_dirty: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(
        run_command(
            "compile",
            [sys.executable, "-m", "compileall", "-q", "rin_pet", "scripts", "tests"],
        )
    )
    checks.append(run_command("ruff", [sys.executable, "-m", "ruff", "check", "."]))
    checks.append(
        run_command(
            "ruff-format",
            [sys.executable, "-m", "ruff", "format", "--check", "."],
        )
    )
    checks.append(
        run_command(
            "python-tests",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        )
    )
    node = shutil.which("node")
    if node is None:
        raise GateFailure("node is required for JavaScript runtime tests")
    checks.append(
        run_command(
            "javascript-tests",
            [node, "--test", "tests/js/runtime.test.mjs"],
        )
    )
    checks.append(
        run_command(
            "secret-scan",
            [sys.executable, "scripts/secret_scan.py", "--json"],
        )
    )
    checks.append(run_command("git-diff-check", ["git", "diff", "--check"]))

    report = validate_pet_directory(ROOT, strict=True)
    if not report.is_ok(strict=True):
        raise GateFailure(
            "strict pet validation failed: "
            + "; ".join(f"{issue.code}: {issue.message}" for issue in report.issues)
        )

    dirty = git_output("status", "--porcelain=v1")
    if dirty and not allow_dirty:
        raise GateFailure(
            "worktree is dirty; commit intended files or use --allow-dirty"
        )

    has_head = (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if has_head:
        log = git_output("log", "--format=%B")
        if "Co-authored-by:" in log:
            raise GateFailure("commit history contains a Co-authored-by trailer")

    with tempfile.TemporaryDirectory(prefix="rin-pet-release-gate-") as raw:
        temp = Path(raw)
        generated_timeline = temp / "timeline.json"
        parse_trace_file(
            ROOT / "examples" / "sanitized-session.jsonl", generated_timeline
        )
        golden = ROOT / "examples" / "sanitized-timeline.json"
        if generated_timeline.read_bytes() != golden.read_bytes():
            raise GateFailure(
                "examples/sanitized-timeline.json is stale; regenerate it with "
                "`rin-pet trace examples/sanitized-session.jsonl "
                "--output examples/sanitized-timeline.json`"
            )
        build_stage(ROOT, temp / "site", timeline_path=generated_timeline)

        first_project = temp / "project-a.zip"
        second_project = temp / "project-b.zip"
        first_pet = temp / "pet-a.codex-pet"
        second_pet = temp / "pet-b.codex-pet"
        build_package(ROOT, first_project, version=__version__)
        build_pet_archive(ROOT, first_pet, version=__version__)
        time.sleep(1.1)
        build_package(ROOT, second_project, version=__version__)
        build_pet_archive(ROOT, second_pet, version=__version__)
        if first_project.read_bytes() != second_project.read_bytes():
            raise GateFailure("full-project ZIP is not deterministic across time")
        if first_pet.read_bytes() != second_pet.read_bytes():
            raise GateFailure(".codex-pet archive is not deterministic across time")

    return {
        "ok": True,
        "strictPet": report.to_dict(strict=True),
        "dirtyAllowed": allow_dirty,
        "checks": checks,
        "deterministicArtifacts": 2,
        "timeSeparatedBuilds": True,
    }


def main() -> int:
    configure_utf8_output(sys.stdout, sys.stderr)
    parser = argparse.ArgumentParser(description="Run every pre-release gate.")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_gate(allow_dirty=args.allow_dirty)
    except (GateFailure, OSError, ValueError) as exc:
        result = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif result["ok"]:
        print("Release gate passed.")
    else:
        print(f"Release gate failed: {result['message']}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
