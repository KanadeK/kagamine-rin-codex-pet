# Selection research

Research snapshot: **2026-07-30**.

## Why Kagamine Rin

The target had to be a real, recognizable character, absent from existing
Codex pet work, suitable for a public non-commercial fan release, and visually
readable at 192×208 pixels.

Kagamine Rin met all four constraints:

- Crypton Future Media's official profile identifies her as a virtual singer
  with a blonde bob, large bow, and orange image color.
- The PCL explicitly lists Kagamine Rin, permits creators to make and publicly
  distribute their own derivative works, and provides a required attribution
  line.
- Piapro's live character page listed more than 67,000 Rin illustrations at
  the time of research, a durable first-party demand signal rather than an
  invented popularity claim.
- Her bow, yellow neckerchief, blonde bob, and black/white/yellow silhouette
  remain identifiable at pet scale without text or a logo.

Sources:

- https://piapro.jp/characters/rin
- https://piapro.jp/license/pcl/summary
- https://piapro.jp/license/pcl
- https://piapro.jp/license/character_guideline
- https://piapro.net/pages/character

## Novelty checks

The following were checked before repository initialization:

1. Local repositories under the workspace root, including existing Baiyan,
   Feibi/Jiubi, Kiki, Pepper, and Miaocui Jiao cat projects.
2. `legeling/awesome-codex-pet` at its then-current `pets.json`: 171 total
   entries and 87 anime/game-character entries. Kagamine Rin was absent.
3. GitHub repository searches for:
   - `"Kagamine Rin" "Codex pet"`
   - `kagamine-rin-codex-pet`
   - `"鏡音リン" codex pet`
4. GitHub code searches for:
   - `"Kagamine Rin" "spriteVersionNumber"`
   - `"鏡音リン" "spriteVersionNumber"`
   - `"Kagamine Rin" "codex://pets/install"`

Those repository and code queries returned no matching Kagamine Rin Codex pet
at the time of research. Absence is a dated search result, not a permanent
claim; rerun the queries before a future major release.

## Rejected candidates

- Hatsune Miku: existing dedicated Codex pet/theme repositories and a gallery
  entry.
- Reimu Hakurei: already present in `awesome-codex-pet`.
- Frieren and Anya Forger: existing dedicated repositories and gallery entries.
- Kasane Teto: an existing `teto-codex-pet` repository and another nested pet
  package were found.

## Functional gap

Existing local v2 pet projects already cover validation, deterministic
packaging, preview pages, and transactional installation. This repository
therefore adds a different working capability: a privacy-preserving parser
that converts real Codex JSONL activity into a content-free animation timeline
and a static offline replay stage. The parser never copies prompt or tool
payload text into its output.
