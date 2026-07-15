# pypdfbox 1.0.0rc4 — Release Notes

Fourth release candidate. Delta over
[1.0.0rc3](RELEASE_NOTES_v1.0.0rc3.md) — a PDF-processing performance
overhaul. Every change in this release is **behavior-preserving**:
parsed object graphs, saved bytes, extracted text (and glyph
positions), decoded filter output, and rendered pixels are all
byte-for-byte identical to rc3. No public API changed; there are no
behavioral divergences from upstream to record. The work removes a
family of accidental quadratics and replaces per-byte/per-pixel Python
loops on hot paths with bulk operations.

## Fixed — algorithmic (quadratic → linear)

- **Splitting a PDF no longer deep-copies the whole document per
  page.** `PDDocument.import_page` skipped `/Parent` *after* a deep
  copy that had already walked the page tree (and thus every page) —
  making `Splitter.split` O(n²). The CLI `split` of an 800-page
  document drops from ~22 s to ~0.7 s.
- **`PDPageTree` indexed access is O(1)-per-descent, not O(n).**
  `get_page(i)` no longer materializes the entire `/Kids` array on
  every call; a `get_page(i)` loop over 2000 pages goes 1.4 s → 0.007 s.
- **Object-stream member resolution is linear in the stream's `/N`.**
  The owning `ObjStm` is decoded once and members are found by number
  and parsed from a shared buffer instead of re-decoding and
  re-scanning per member (8000-member stream 2.0 s → 0.37 s). Since
  object streams back most modern PDFs, this speeds up plain opening.
- **`PDFMergerUtility` AcroForm merge is O(F), not O(F²).** Field-name
  collision detection uses an incrementally grown name set instead of
  re-walking the destination field tree per source field (800+800
  fields 2.6 s → 0.04 s). The destination `/ParentTree` is cached
  across successive appends, and shared resources are hashed once.
- **`import_page` AcroForm widget re-attachment** keeps incremental
  collision state instead of rescanning `/Fields` per page (importing
  1600 widget pages 1.6 s → 0.05 s).
- **Tagged-PDF split** flattens the source `/ParentTree` once per run
  and tests page membership via an id-map instead of a per-element
  page-tree walk.
- **The writer's object queue** uses an id-set membership test instead
  of an O(queue) scan per enqueued object (uncompressed save of 4000
  pages 1.4 s → 0.47 s).
- **`ScratchFile`** MIXED-mode allocation and free-page reuse are O(1)
  (an in-memory page counter and a membership set replace per-op
  scans); the duplicate-text suppression pass in `PDFTextStripper`
  uses a spatial grid instead of an O(n²) scan (16k identical runs
  1.5 s → 0.04 s).

## Fixed — constant-factor (hot loops)

- **PNG/TIFF predictor decode** (used by nearly every cross-reference
  stream and predictor-compressed image) has numpy fast paths for the
  PNG Up/Sub and TIFF Predictor 2 cases at byte-aligned depths — PNG-Up
  on a 10 MB stream 321 ms → 13 ms. Average/Paeth and sub-byte depths
  keep the exact scalar path.
- **Text extraction** memoizes per-font glyph lists and per-code
  Unicode (mirroring the existing width cache) and reuses text-render
  matrix scale factors, cutting a 400-page extraction ~40 %.
- **`COSStream`** caches decoded bytes, so repeated reads of the same
  stream (e.g. a form XObject stamped many times) decode once instead
  of re-running the filter chain each time.
- **LZW / ASCII85 decoders** tokenize over a local buffer instead of
  per-byte stream reads (ASCII85 7.6 → 17.4 MB/s).
- **The parser** uses frozenset byte classifiers, avoids re-scanning
  number tokens, and validates `N G obj` xref headers with a single
  bulk read (whole-document load ~26 % faster); brute-force recovery
  scans on malformed files are cached instead of re-run per lookup.
- **The renderer** vectorizes the ARGB white→transparent pass, the
  separable blend modes, soft-mask application, colour-key masking and
  matte un-premultiplication with numpy (white→transparent pass on a
  300 DPI page 1.8 s → 0.03 s). The non-separable HSL blend keeps the
  exact scalar path.

## Verified

- Full non-oracle test suite: **57,749 passed, 0 failed**. Each change
  was gated by capture-before / compare-after harnesses asserting
  byte-identical (and, for text, glyph-position-identical) output;
  ~20 new regression tests accompany the fixes. Optimizations that
  could not be proven output-identical were deliberately not taken.
