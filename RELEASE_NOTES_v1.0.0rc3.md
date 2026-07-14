# pypdfbox 1.0.0rc3 — Release Notes

Third release candidate. Delta over
[1.0.0rc2](RELEASE_NOTES_v1.0.0rc2.md) — completes the save-path
compression audit started in rc2:

## Fixed

- **`PDPageContentStream` compresses page content by default**
  (upstream parity). The 2-arg constructor previously wrote plaintext
  operator streams; upstream Java delegates with `compress=true`. All
  content-authoring surfaces (`texttopdf`, `imagetopdf`, user code)
  now emit Flate-encoded content streams. Appearance/form-XObject
  targets keep upstream's bare (uncompressed) output stream, and
  `compress=False` opts out per stream.
- **`decompress_objectstreams` and `write_decoded_doc` save with
  `NO_COMPRESSION`** — after rc2's compressed-save default, both tools
  were re-packing the very streams they had just expanded. Matches
  upstream, which passes `CompressParameters.NO_COMPRESSION` in both
  tools.

## Verified clean (no change needed)

- Full save (compressed and classic) writes only objects reachable
  from the trailer — orphan objects in the source are dropped,
  byte-for-byte consistent with Java PDFBox 3.0.7 on the probe file.
- `PageExtractor` delegates to `Splitter` and inherits rc2's resource
  pruning; merger/overlay/encrypt/decrypt inherit the compressed
  default through `PDDocument.save()`; FDF output stays classic-xref
  like upstream; incremental saves are append-only by design.

## Changed

- README now carries PyPI version, monthly-downloads, and license
  badges (download counts are not shown natively by PyPI; the badge
  reads pypistats.org).
