# Artwork and atlas pipeline

The shipped character depiction is a newly generated, unofficial
non-commercial fan work. No official illustration, logo, game asset, voice,
song, lyric, or third-party fan-art pixel is included.

## Identity brief

The canonical brief uses only recognizable design traits from the official
profile: blonde bob, oversized white bow, cyan eyes, white sailor-inspired
top with a yellow neckerchief, black shorts, and dark arm/leg warmers. The
rendering is a compact sticker-like chibi designed to stay readable inside a
192×208 cell.

## Required v2 topology

- 8 columns × 11 rows
- 192×208 pixels per cell
- 1536×2288 final WebP
- 9 standard state rows
- 16 clockwise look directions across rows 9 and 10
- 74 required cells (including the neutral look frame) and 14 fully
  transparent padding cells

Every standard row was generated from both the canonical base and a
state-specific slot guide. `running-left` was generated independently rather
than mirrored because the belt pouch and smaller design details are
asymmetric.

## Quality gates

Each generated row is immediately split into cells and checked for:

- exact frame count;
- empty or clipped required cells;
- populated unused cells;
- edge contact;
- component extraction fallback;
- scale outliers;
- residual chroma pixels;
- hidden RGB in transparent pixels.

The nine standard rows are reviewed together on a labeled contact sheet. Look
directions use an explicit pet-specific mechanics note, approved cardinal
anchors, coherent half-circle strips, direction sheets, continuity checks, and
three independent blind direction reviews. A separate reviewer performs the
final package-level visual decision.

Retained evidence is under `artwork/qa/`. Exact prompts, the generation job
manifest, and the input brief are under `artwork/source/`. Intermediate
generator caches and discarded attempts are intentionally not distributed.

## License boundary

Software and original documentation are MIT licensed. Character-depicting
visual files are governed separately by the Piapro Character License and
current character guidelines; see `ASSET_LICENSE.md` and `NOTICE.md`.
