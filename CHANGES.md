# CHANGES

Substantive behavioral deviations of pypdfbox vs upstream Apache PDFBox.
Per-release notes go here; trivial naming changes (camelCase → snake_case) are not listed.

## Format

```
- pypdfbox/<path>: <one-line description of deviation>
  upstream: PDFBox <version> <java path>
  reason: <why we deviate>
```

## Project-wide deviations vs upstream

- **No `preflight` module.** Apache PDFBox 4.0 removes Preflight; we follow that decision. PDF/A and PDF/UA validation is performed via external veraPDF / PAC.
- **No commons-logging / log4j.** Python `logging` (stdlib) is used throughout.
- **Method naming.** Java camelCase → Python snake_case across the entire API surface. Semantics unchanged.

## Per-file deviations

- `pypdfbox/io/random_access_read_buffer.py`: wraps `io.BytesIO` instead of reimplementing PDFBox's chunked-list storage. Observable behavior is identical; implementation is C-backed and ~25 lines instead of ~120. Justification: PRD §3.7 (stdlib-first for generic infrastructure).
- `pypdfbox/io/random_access_read_buffered_file.py`: wraps `io.BufferedReader` over a raw file fd. Stdlib provides the read-ahead buffering that upstream's `RandomAccessReadBufferedFile` implements manually. Justification: PRD §3.7.
- `pypdfbox/io/random_access_read_memory_mapped.py`: net-new optional implementation backed by `mmap.mmap`. No upstream counterpart; offered as opt-in for very large files where kernel paging beats userspace buffering. Justification: PRD §3.7 — use stdlib affordances when they fit.
- `pypdfbox/io/random_access_read_view.py`: original slice-view implementation. Mirrors the upstream `RandomAccessReadView` API; storage strategy is direct seek-on-parent rather than upstream's bounded-stream wrapper.
- `pypdfbox/io/scratch_file.py`: backed by `tempfile.SpooledTemporaryFile` (mixed mode), `tempfile.TemporaryFile` (temp-file-only), or `io.BytesIO` (memory-only). Upstream uses page-based scratch storage; we delegate spill-to-disk policy to stdlib. Behavior visible to callers (read/write/seek/clear) is identical. Justification: PRD §3.7. Default spill threshold in MIXED mode without an explicit cap is 16 MiB.

## Backfill — aligned with upstream test expectations

Driven by porting upstream JUnit tests (PRD §12.1):

- `pypdfbox/io/random_access_read.py`: added `read_fully(buf, offset, length)` (raises `EOFError` on premature EOF) and `skip(n)` (clamps to length). Mirrors upstream `RandomAccessRead.readFully` / `skip`.
- `pypdfbox/io/random_access_read_buffer.py`, `_buffered_file.py`, `_memory_mapped.py`, `_view.py`: `seek(negative)` now raises `OSError` (was `ValueError`), `seek(past_end)` clamps to length and leaves the stream at EOF (was: raised `ValueError`). Matches upstream PDFBox semantics; required by ported `seek*` tests.
- `pypdfbox/io/random_access_read_view.py`: removed `start_position + length > parent_length` validation (upstream allows logical views past parent end; reads simply stop at parent EOF). `create_view()` on a view raises `OSError` (upstream forbids).
- `pypdfbox/io/scratch_file.py::ScratchFileBuffer.create_view()` raises `NotImplementedError` (upstream's `UnsupportedOperationException`).
- `pypdfbox/cos/cos_number.py`: new abstract base `COSNumber` (parses string → `COSInteger`/`COSFloat`, handling exponential notation and Java-Long-out-of-range markers). `COSInteger`/`COSFloat` now extend `COSNumber`.
- `pypdfbox/cos/cos_float.py`: values are now clamped to **IEEE-754 single precision** (`float32`) on both `__init__` paths to match Java `float` semantics — required for upstream parity tests on `equals()`/`hashCode()`. `_normalize_negatives` recovers from PDFBOX-2990 / -3369 / -3500 / -4289 misplaced-`-` cases (`--16.33` → `-16.33`, `0.-262` → `-0.262`, `0.00000-33917698` → `-0.0000033917698`); raises `OSError` on unrecoverable double-`-`.
- `pypdfbox/cos/cos_integer.py`: added `is_valid()` / `set_valid()` for PDFBOX-5176 large-integer-out-of-Long-range marking.
- `pypdfbox/cos/cos_string.py`: `parse_hex` raises `OSError` (was `ValueError`) to mirror upstream `IOException`. Added `to_hex_string()`.
- `pypdfbox/cos/cos_stream.py`: `create_raw_input_stream()` raises `OSError` when no body. Added `create_input_stream()` and `create_output_stream(filters=None)` stubs that raise `NotImplementedError` when filters are requested (filter encoding lives in `filter` module).
- `pypdfbox/cos/cos_array.py`: added `remove_object`, `remove_all`, `retain_all`, `grow_to_size`, typed `set_name`/`get_name`/`set_int`/`get_int`/`set_string`/`get_string`, `set_float_array`/`to_float_array`, `to_cos_*_list` converters, factory classmethods `of_cos_names`/`of_cos_strings`/`of_cos_integers`/`of_cos_floats`. All match upstream signatures.
- `pypdfbox/cos/cos_document.py`: added `add_xref_table`, `get_objects_by_type`, `get_linearized_dictionary` (placeholder returning `None` until linearization-hint parsing lands).
- `pypdfbox/cos/cos_name.py`: added single-letter and short-name constants (`A`, `B`, `C`, `D`, `T`, `BE`, `PARAMS`, `FLATE_DECODE`, `ASCII85_DECODE`, `STANDARD_ENCODING`) referenced by ported tests.
- `pypdfbox/pdfparser/base_parser.py::read_name`: a `#` not followed by two hex digits is now kept literally rather than raising `PDFParseError`. Matches upstream `TestBaseParser.testInvalidHexSequence`.

## Filter module + Loader (parallel wave)

- `pypdfbox/filter/ascii85_decode.py`: encode/decode delegate to stdlib `base64.a85encode` / `a85decode` (which already implements PDF's base-85 + `z` shortcut + adobe `<~ ... ~>` framing). Original wrapper handles whitespace pre-cleaning, `~>` terminator stripping, and per-spec error reporting (`OSError`).
- `pypdfbox/filter/flate_decode.py`: `zlib` wrapper. PNG predictors 10-15 + TIFF predictor 2 supported on decode; encode-side predictor raises `NotImplementedError` (matches upstream).
- `pypdfbox/filter/ascii_hex_decode.py`: `binascii` wrapper. Whitespace ignored, odd-digit pad with `0`, terminates on `>`.
- `pypdfbox/filter/run_length_decode.py`: ported line-for-line so encoded bytes match upstream byte-identical.
- `pypdfbox/filter/lzw_decode.py`: PDF-flavored LZW (9-12 bit codes, MSB-first, EarlyChange honored on decode; encoder always emits EarlyChange=1 with the PDFBOX-1977 final-EOD-width fix).
- **Predictor logic duplication**: `flate_decode.py` and `lzw_decode.py` each carry an inline copy of the PNG/TIFF predictor inverse. Marked TODO for a shared `pypdfbox/filter/_predictor.py` extraction.
- `pypdfbox/cos/cos_document.py`: optional `source: RandomAccessRead | None` parameter / instance attribute so `Loader` can attach the file handle it created and have `doc.close()` close it. Caller-supplied sources stay caller-owned.
- `pypdfbox/loader.py`: top-level `Loader.load_pdf()` accepts path / `bytes` / `bytearray` / `memoryview` / `BinaryIO` / `RandomAccessRead`. Mirrors `org.apache.pdfbox.Loader.loadPDF()`. Encryption / password / `MemoryUsageSetting` parameters deferred until those features ship.
- `pypdfbox/__init__.py`: exports `Loader` so `from pypdfbox import Loader` works (matches PRD §7).
- `pypdfbox/pdfparser/pdf_stream_parser.py`: extends `COSParser`. Surfaces an `Operator` value type carrying the operator name plus optional `image_parameters` / `image_data` for inline-image (`BI` ... `ID` ... `EI`) sequences. Lenient PDFBox quirks preserved: stray `]` returns `COSNull`, isolated `+` returns `COSNull`, internal `-` in numbers dropped (PDFBOX-4064), Type-3 `d0`/`d1` operator suffix accepted.

## pdfwriter cluster #1 (full-save, traditional xref)

- `pypdfbox/pdfwriter/cos_writer.py`: cluster #1 covers full-save mode only. The following upstream paths are stubbed and raise `NotImplementedError` until later clusters land:
  - `incremental=True` constructor flag → cluster #2 (incremental save).
  - Xref-stream output (`writeXrefStream` and friends) → cluster #3.
  - Object-stream packing (`COSWriterObjectStream`) → cluster #3.
  - Encrypted documents (`is_encrypted()` → `True`) → security cluster.
  - Signatures (`SignatureInterface`, `/ByteRange` ranges) → cluster #2.
- `pypdfbox/pdfwriter/cos_writer.py`: `write(document)` accepts a `COSDocument` directly. Upstream's overloads also take `PDDocument` / `FDFDocument`; those wrappers are not yet ported (`PDDocument` → PRD §6.6 cluster).
- `pypdfbox/pdfwriter/cos_writer.py`: `/ID` synthesis uses `hashlib.sha256(time_ns + secrets.token_bytes(16))[:16]` instead of upstream's `Long.toString(idTime) + info-dict-values` digest. Same shape (two 16-byte hex strings) and same purpose; we don't have a `PDDocument.getDocumentId()` to thread in yet.

## pdfwriter cluster #2 (incremental save)

- `pypdfbox/pdfwriter/cos_writer.py`: `COSWriter(..., incremental=True, incremental_input=...)` now ships. The writer copies the source bytes to the output verbatim and appends only objects whose resolved value (or its `COSObject` wrapper) carries `is_needs_to_be_updated()=True`. The appended xref section lists only the changed/new objects, the trailer carries `/Prev = old_startxref`, `/Size = max_obj_num + 1`, and preserves `/ID` exactly as the source had it. Mirrors upstream `doWriteIncrement` + `prepareIncrement` + `doWriteXRefInc`.
- `pypdfbox/pdfwriter/cos_writer.py`: digital-signature re-signing is **not** implemented. When a source signature dict (`/Type /Sig` or `/DocTimeStamp`) contains a `/ByteRange [0 0 0 0]` placeholder (or any byterange whose third entry doesn't extend past the original file end), `save_incremental` raises `NotImplementedError` rather than silently corrupt the signature. The actual digest pipeline lands with the security cluster.
- `pypdfbox/pdfwriter/cos_writer.py`: `save_incremental` on a document with **no** dirty objects produces an output **byte-for-byte identical to the source**. Upstream's behaviour matches: nothing extra is appended. Unlike full-save mode, no `/ID` synthesis happens in incremental mode — the source's `/ID` array (if any) stays exactly as it was.
- `pypdfbox/pdfwriter/cos_writer.py`: an in-memory `BytesIO` increment buffer accumulates the appended objects + xref + trailer; the real output sink only sees source-bytes followed by buffer-contents at the very end. Mirrors upstream's `ByteArrayOutputStream` → `incrementalOutput` pipeline. The buffer is initialised with `position=0`; absolute byte offsets in the new xref are computed as `source_length + buffer_offset` at emit time (upstream cheats by seeding `position` with `inputData.length()` on the `COSStandardOutputStream`; functionally identical, easier to test in isolation).
- `pypdfbox/pdfwriter/cos_writer.py`: a CRLF separator is emitted at the very start of the increment buffer when there is at least one dirty object. This matches upstream's `getStandardOutput().writeCRLF()` at the top of `visitFromDocument` in incremental mode and guarantees an unambiguous boundary between the source's trailing `%%EOF` and the appended block. When nothing is dirty the separator is **not** emitted (preserving the byte-for-byte-identical contract).
- `pypdfbox/cos/cos_document.py`: added `get_source()` (read-only accessor for the parser-attached `RandomAccessRead`), `get_start_xref()` / `set_start_xref(offset)` (the offset of the trailing xref section, used by the incremental writer for `/Prev`).
- `pypdfbox/pdfparser/pdf_parser.py`: after parsing the trailing `startxref` value, calls `document.set_start_xref(...)` so the incremental writer can find it later.

## contentstream cluster #1 (Operator + OperatorName + PDContentStream)

- `pypdfbox/contentstream/operator.py`: operands list is stored on the `Operator` instance (`get_operands()` / `set_operands()`). Upstream keeps the operand stack on `PDFStreamEngine` / `PDFStreamParser`; pypdfbox attaches operands directly to the `Operator` returned by the parser as a convenience for token consumers (the parser already does this — see `pdf_stream_parser.py`). The cached singletons returned by `Operator.get_operator(name)` for ordinary operators must therefore be treated as flyweights — do not mutate operands on a cached instance you did not just receive from the parser.
- `pypdfbox/contentstream/operator.py`: cache uses a plain `dict` plus a `threading.Lock` instead of upstream `ConcurrentHashMap.putIfAbsent`. Functionally identical under the GIL.
- `pypdfbox/contentstream/pd_content_stream.py`: `get_matrix()` is typed `Any` rather than `Matrix` because `pypdfbox.util.Matrix` is not yet ported (it lands with the rendering cluster). Subclasses may return a `COSArray` (the on-disk form) until then.

## pdmodel cluster #3 (PDStream + XObject family)

- `pypdfbox/pdmodel/common/pd_stream.py`: stream construction/output with `filters` records the `/Filter` chain but stores caller-supplied bytes as-is. Upstream writes through `COSStream.createOutputStream(filters)` and therefore encodes on write; pypdfbox defers encode-on-write until the filter encoding surface is widened. Decoding existing filtered bytes is supported through `FilterFactory`.
- `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py`: image decoding, color-space wrapping, array color spaces, and rendered image conversion are deferred to rendering / graphics-color clusters. Cluster #3 exposes image metadata, raw `/ColorSpace` names, filter access, and decoded byte streams only.
- `pypdfbox/pdmodel/graphics/form/pd_form_x_object.py`: `get_matrix()` returns a plain six-float list until `pypdfbox.util.Matrix` lands with the rendering cluster.

## pdmodel cluster #5 lite (annotations)

- `pypdfbox/pdmodel/interactive/annotation/pd_annotation.py`: factory dispatch is intentionally truncated to Link/Text/Square/Circle plus `PDAnnotationUnknown`; Widget, Markup, and heavier annotation subclasses are deferred to forms/rendering clusters.
- `pypdfbox/pdmodel/interactive/annotation/pd_annotation_link.py`: action and destination accessors return raw COS objects until `PDAction` and the full `PDDestination` family land in pdmodel cluster #7.
- `pypdfbox/pdmodel/interactive/annotation/pd_annotation_square_circle.py`: inherits directly from `PDAnnotation` instead of upstream `PDAnnotationMarkup`; border style, border effect, and interior color use raw COS containers until their typed wrappers land.

## pdmodel cluster #7 partial (outlines / destinations / actions)

- `pypdfbox/pdmodel/interactive/documentnavigation/outline/*`: outline tree/list mechanics are present, with typed destination/action accessors for the common action and destination wrappers in this cluster.
- `pypdfbox/pdmodel/interactive/documentnavigation/destination/*`: ships named, Fit/FitB, FitH/FitBH, FitV/FitBV, and XYZ destinations. FitR and richer page-object resolution/index lookup are deferred.
- `pypdfbox/pdmodel/interactive/action/*`: ships base/factory plus GoTo, URI, Named, Launch, RemoteGoTo, JavaScript, and Unknown wrappers. Richer actions (SubmitForm, ResetForm, ImportData, Hide, Thread, Sound, Movie, Rendition, Trans, GoToE) are deferred and currently preserve as `PDActionUnknown`.
- `pypdfbox/pdmodel/pd_document_catalog.py`: `get_dests()` returns the raw `/Dests` dictionary until the name-tree node classes are ported.

## fontbox CMap cluster

- `pypdfbox/fontbox/cmap/cmap_parser.py`: predefined CMap loading currently supports only programmatic `Identity-H` and `Identity-V`; file-backed predefined CMaps such as `Adobe-Japan1-UCS2` are deferred.

## tools cluster #1

- `pypdfbox/tools/merge.py`: cluster #1 performs naive page-list concatenation and does not remap cross-document references such as links, named destinations, structure-tree owners, or form resources. This is replaced by `PDFMergerUtility` semantics when the multipdf cluster lands.
- `pypdfbox/tools/split.py`: cluster #1 copies page COS dictionaries into fresh documents without remapping references to sibling pages or document-level structures.
- `pypdfbox/tools/decrypt.py`: cluster #1 is pass-through for unencrypted PDFs and returns non-zero for encrypted inputs; real security removal depends on pdmodel cluster #10.
- `pypdfbox/tools/version.py`: prints Python/runtime package metadata in addition to the upstream-style version string.
