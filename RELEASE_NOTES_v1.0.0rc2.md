# pypdfbox 1.0.0rc2 — Release Notes

Second release candidate for the 1.0 cut. Delta over
[1.0.0rc1](RELEASE_NOTES_v1.0.0rc1.md):

## Fixed

- **`PDDocument.save()` now compresses by default** (upstream PDFBox
  3.0 parity). The `compress_parameters` argument was previously
  accepted but ignored, so every save produced an uncompressed
  classic-xref file. `save()` now defaults to
  `CompressParameters.DEFAULT_COMPRESSION`: non-stream objects are
  packed into `/Type /ObjStm` object streams addressed by a
  compressed cross-reference stream, exactly like Java PDFBox.
  Pass `CompressParameters.NO_COMPRESSION` for the traditional
  layout. Encrypted documents round-trip through the compressed
  path (verified against the Java PDFBox 3.0.7 oracle).
- **`COSWriter`** gained an `object_stream_size` constructor
  parameter so the `CompressParameters` value is honoured end to end.
- **`writedecodedstream`** (the `WriteDecodedDoc` port) now saves
  with `NO_COMPRESSION`, mirroring upstream — a decoded-streams
  debugging artifact must not be re-compressed on the way out.
- **ObjStm packing excludes the `/Encrypt` subtree.** The R4/AES-128
  handler writes `/CF` as an indirect object; packing it into an
  (encrypted) object stream made the file undecryptable — the reader
  needs the complete encryption dictionary before it can open any
  object stream. Found by the encryption round-trip matrix once
  compression became the default.
- **Degenerate incremental xref stream fixed.** An incremental save
  with zero rewritten objects over an xref-stream base emitted an
  unparseable `/W [0 0 0]`; the mandatory object-0 row now always
  gets nonzero column widths.

## Changed (deliberate divergence from upstream — see CHANGES.md)

- **`Splitter` prunes unused page resources.** Each split chunk
  page's `/Resources` is rebuilt to contain only the `/Font`,
  `/XObject`, `/ExtGState`, `/ColorSpace`, `/Pattern`, `/Shading`,
  and `/Properties` entries its content actually references
  (recursing through form XObjects, tiling patterns, Type 3 char
  procs, and appearance streams that fall back to page resources).
  Upstream copies the page's — possibly inherited, document-wide —
  resource dictionary wholesale, so splitting one page out of a
  document whose pages share a page-tree-level `/Resources`
  produced a chunk as large as the whole source. `/ProcSet` and
  unrecognized categories are kept as-is, and any content-stream
  tokenization failure conservatively keeps the full dictionary.

Together these fix the reported `pypdfbox split` behaviour where a
small page-range split emitted an uncompressed file carrying the
entire document's resource tree: on a 3-page 181 KB shared-resources
document, a 1-page split now weighs 61 KB instead of 181 KB, and the
compressed writer brings a 2-page split of the PDFBOX-5762 fixture
from 20.5 KB down to 13.0 KB.
