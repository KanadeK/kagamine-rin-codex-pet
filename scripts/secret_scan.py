from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "artwork",
    "build",
    "dist",
    "node_modules",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}


def candidate_files(root: Path) -> Iterable[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            path = root / line
            if path.is_file():
                yield path
        return
    yield from (path for path in root.rglob("*") if path.is_file())


def scan(root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in sorted(set(candidate_files(root))):
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "rule": name,
                            "path": relative.as_posix(),
                            "line": line_number,
                        }
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-confidence repository secret scan."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = scan(ROOT)
    result = {"ok": not findings, "findingCount": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif findings:
        for finding in findings:
            print(f"{finding['rule']}: {finding['path']}:{finding['line']}")
    else:
        print("Secret scan passed.")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
