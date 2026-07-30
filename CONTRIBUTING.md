# Contributing

Contributions to the MIT-licensed tooling are welcome. By contributing code or
documentation, you agree that your contribution is available under `LICENSE`.

Do not submit:

- official Kagamine Rin artwork, logos, audio, voicebanks, songs, or game
  assets;
- third-party fan art without explicit redistribution permission;
- real Codex session logs or screenshots containing private content;
- generated sprite replacements that have not passed the complete v2 visual
  and deterministic QA gates documented in `docs/REPAIR.md`.

Run before opening a pull request:

```bash
python scripts/release_check.py --allow-dirty
```

Keep commits attributable to their actual author. Do not add generated
`Co-authored-by` trailers.
