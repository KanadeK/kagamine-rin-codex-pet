# Diagnosis and repair

All mutating operations validate before writing, use a per-pet lock, stage
files beside the destination, and move the previous installation into a
recoverable backup. Do not delete backups or lock files until you understand
the failure.

## Start with a dry run

```bash
python -m rin_pet validate pet --strict --json
python -m rin_pet install --source pet --dry-run --json
python -m rin_pet doctor --source pet --json
```

An exit code of `0` means the requested check passed. `validate` and `doctor`
return `1` for a valid command whose subject is unhealthy. Input, I/O, or
safety errors return `2`.

## Strict validation fails

Run:

```bash
python -m rin_pet validate pet --strict --json
```

Common codes:

| Code | Meaning | Repair |
| --- | --- | --- |
| `manifest-*` | `pet.json` does not match the shipped v2 contract | Restore `pet/pet.json` from the release archive |
| `spritesheet-size` | Atlas is not exactly 1536×2288 | Restore the published `spritesheet.webp`; do not resize it |
| `used-cell-empty` | A required animation cell is transparent | Restore the atlas or rerun the full artwork pipeline |
| `unused-cell-populated` | Padding cells contain pixels | Restore the atlas; hand-erasing can leave hidden RGB |
| `cell-edge-clipping` | Visible pixels touch a cell safety edge | Repair at frame source, then rebuild the atlas |
| `hidden-rgb` / `chroma-residue` | Transparency cleanup is incomplete | Rerun the documented despill/assembly pipeline |
| `checksums-mismatch` | A shipped file changed | Restore all four pet files from one matching release |

Do not silence strict warnings. `provenance.json` and `SHA256SUMS` are part of
the installable unit.

## Installed pet is missing or modified

```bash
python -m rin_pet doctor --source pet --json
python -m rin_pet repair --source pet --dry-run --json
python -m rin_pet repair --source pet --json
python -m rin_pet doctor --source pet --json
```

Repair validates the source twice, moves the current directory to:

```text
~/.codex/pet-backups/kagamine-rin/<UTC timestamp>-<hash prefix>/
```

and atomically promotes the staged replacement. If promotion fails, the
previous installation is moved back automatically.

## A lock already exists

The lock is `~/.codex/.kagamine-rin-pet.lock`. First confirm that no
`rin-pet`, `python -m rin_pet`, install, repair, or uninstall process is still
running. If a process is active, let it finish. Only after confirming the
recorded PID is stale should you remove that one lock file and retry.

Never recursively delete `~/.codex`.

## Installation from an archive is rejected

The extractor rejects absolute paths, `..` traversal, drive-qualified names,
and ZIP symlinks before copying any pet file. Download the asset again and
verify it:

```bash
python -m rin_pet verify-package kagamine-rin-v0.1.0.codex-pet \
  --sha256 <value-from-SHA256SUMS> --json
```

If the hash differs, do not install the archive.

## Offline stage refuses an output directory

The builder replaces only a directory containing its own
`.rin-pet-stage` marker. Choose an empty output path:

```bash
python -m rin_pet stage --output tmp/rin-stage --json
```

If an existing directory contains important files, keep it and use another
path. Do not add the marker by hand to bypass this safeguard.

## Trace parsing fails

Confirm that the input is UTF-8 JSONL with one object per non-empty line and
is below the documented size/record limits:

```bash
python -m rin_pet trace session.jsonl \
  --output tmp/timeline.json --json
```

Never paste a real session log into a public issue. Reduce a problem to a
synthetic fixture containing no message, account, path, or tool payload data.

## Release package is not deterministic

Run the full gate:

```bash
python scripts/release_check.py --json
```

The gate builds both archives twice with more than one second between builds
and compares bytes. If it fails:

1. inspect ZIP member timestamps with `python scripts/verify_release.py`;
2. check for generated files containing wall-clock timestamps;
3. ensure file enumeration is sorted;
4. rebuild from a clean checkout;
5. do not publish until both separated builds are byte-identical.

## CI failure reproduction

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
node --test tests/js/runtime.test.mjs
python scripts/secret_scan.py --json
python scripts/release_check.py --json
```

The final command is the authoritative pre-release gate. Its JSON identifies
the failed subcheck and preserves the last portion of stdout/stderr.
