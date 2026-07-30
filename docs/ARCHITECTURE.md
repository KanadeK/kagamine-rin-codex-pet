# Architecture

The repository has three independently testable layers.

## Pet package

`pet/pet.json` and `pet/spritesheet.webp` implement the Codex v2 atlas contract:
8 columns, 11 rows, 192×208 cells, nine status animation rows, and sixteen
clockwise look directions. Pixel validation treats used, unused, edge-clipped,
hidden-RGB, and chroma-residue cells separately.

## RinTrace

`rin_pet.timeline` accepts JSONL records from a local Codex session or a
compatible synthetic fixture. It classifies lifecycle metadata into pet states
and deliberately discards every free-form value. The output schema retains:

- an input SHA-256;
- source line number;
- a normalized allow-listed event kind;
- pet state;
- relative offset and bounded duration.

No prompt, message, tool argument, tool output, path, email, or account value is
copied. Unknown records become the generic `activity` kind.

## Offline stage and operations

The static stage uses the shipped atlas and a sanitized timeline. It has no
analytics, CDN, font, network, or framework dependency. The Python CLI also
provides:

- strict validation;
- deterministic ZIP packaging;
- validate-before-write installation;
- backup-first replacement and rollback;
- installed-package diagnosis and repair;
- recoverable uninstall.

All paths are resolved before mutation. ZIP members containing absolute paths,
parent traversal, drive prefixes, or symlink metadata are rejected.
