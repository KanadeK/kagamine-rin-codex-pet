# Kagamine Rin Codex Pet v0.1.0

First public release.

## Included

- complete Codex v2 Kagamine Rin pet with nine standard animation rows and
  sixteen clockwise look directions;
- standalone `kagamine-rin-v0.1.0.codex-pet` installer archive;
- RinTrace content-free Codex JSONL timeline parser;
- network-independent interactive replay stage;
- strict atlas/provenance/hash validator;
- transactional install, doctor, repair, and recoverable uninstall commands;
- deterministic project and pet packages with SHA-256 manifest;
- Python/JavaScript tests, secret scanning, CI, Pages, and CodeQL.

## Verify before installing

Download `SHA256SUMS` and compare the selected artifact:

```bash
python -m rin_pet verify-package kagamine-rin-v0.1.0.codex-pet \
  --sha256 <value-from-SHA256SUMS> --json
```

This is an unofficial non-commercial fan work. Software is MIT licensed;
character-depicting visual assets are separately governed by the Piapro
Character License and current character guidelines.
