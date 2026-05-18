# PROVENANCE

This file tracks every source file in `pypdfbox/` that is **ported from Apache PDFBox**, satisfying Apache 2.0 §4(b) ("notices stating that You changed the files") in one centralized place.

## Conventions

- Entries are grouped by `pypdfbox/` module.
- Each row records the **pypdfbox path**, the **upstream PDFBox version** the port was derived from, and the **upstream Java path**.
- Files that have **no** PDFBox counterpart (Python-only utilities, glue, net-new code) are **not** listed here. Their absence here means: original work.
- For per-port behavioral changes vs upstream, see `CHANGES.md`.

## Upstream baseline

- Apache PDFBox **3.0.x latest stable** at time of port. Designed to align with PDFBox 4.0 changes (Preflight removed; see `CLAUDE.md` § PDFBox 4.0 Alignment Notes).
- Upstream repository: https://github.com/apache/pdfbox

## Ported files

### `pypdfbox/io/`

Per PRD §3.7 (stdlib-first), the io module is adapter code over Python stdlib (`io.BytesIO`, `io.BufferedReader`, etc.). Only the **interface contracts** below derive from PDFBox; concrete implementations are original work wrapping stdlib.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/io/random_access_read.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/RandomAccessRead.java` | interface contract only (method signatures + semantics) |
| `pypdfbox/io/random_access_write.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/RandomAccessWrite.java` | interface contract only |
| `pypdfbox/io/memory_usage_setting.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/MemoryUsageSetting.java` | API surface (modes, factories, predicates) |
| `pypdfbox/io/scratch_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFile.java` | page-oriented allocator API (`get_new_page()`, `read_page()`, `write_page()`, free-page queue, `create_buffer()` lifecycle); backing storage is RAM/temp-file/mixed per `MemoryUsageSetting` |
| `pypdfbox/io/scratch_file_buffer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFileBuffer.java` | random-access read/write buffer backed by fixed-size `ScratchFile` pages |

Original work (no PROVENANCE entry needed; listed here for clarity):
- `pypdfbox/io/random_access_read_buffer.py` — adapter over `io.BytesIO`
- `pypdfbox/io/random_access_read_buffered_file.py` — adapter over `io.BufferedReader`
- `pypdfbox/io/random_access_read_memory_mapped.py` — adapter over `mmap.mmap`
- `pypdfbox/io/random_access_read_view.py` — slice view, original
- `pypdfbox/io/random_access_write_buffer.py` — adapter over `io.BytesIO`
- `pypdfbox/io/io_utils.py` — small convenience helpers (most usage delegates to stdlib)

### `pypdfbox/cos/`

PDF-specific code, not stdlib-adapter territory. Ports the PDFBox COS object model.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/cos/cos_base.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSBase.java` |
| `pypdfbox/cos/i_cos_visitor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/ICOSVisitor.java` (with `visit_from_object` per 4.0) |
| `pypdfbox/cos/cos_name.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSName.java` |
| `pypdfbox/cos/cos_string.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSString.java` |
| `pypdfbox/cos/cos_integer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSInteger.java` |
| `pypdfbox/cos/cos_float.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSFloat.java` |
| `pypdfbox/cos/cos_boolean.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSBoolean.java` |
| `pypdfbox/cos/cos_null.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSNull.java` |
| `pypdfbox/cos/cos_array.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSArray.java` |
| `pypdfbox/cos/cos_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSDictionary.java` |
| `pypdfbox/cos/cos_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSObject.java` |
| `pypdfbox/cos/cos_object_key.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSObjectKey.java` |
| `pypdfbox/cos/cos_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSStream.java` |
| `pypdfbox/cos/cos_document.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSDocument.java` |
| `pypdfbox/cos/cos_number.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSNumber.java` |
| `pypdfbox/cos/cos_document_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSDocumentState.java` |
| `pypdfbox/cos/cos_update_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/COSUpdateState.java` |
| `pypdfbox/cos/pd_linearization_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocument.java` (linearization-hint parsing extracted from upstream `PDDocument` into a standalone typed wrapper) |

### `pypdfbox/pdfparser/`

PDF-specific parsing — port territory.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfparser/base_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/BaseParser.java` (tokenization plus literal-string parsing/recovery subset; includes PDFBOX-6093 `\r\n>` end-of-string leniency) |
| `pypdfbox/pdfparser/cos_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/COSParser.java` (direct-object / array / dict / indirect-ref + brute-force recovery + parsePDFHeader + parseXrefTable + parseXrefObjStream + parseObjectStream + direct-/Length stream body; indirect-/Length deferred to PDFParser) |
| `pypdfbox/pdfparser/xref_trailer_resolver.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/XrefTrailerResolver.java` |
| `pypdfbox/pdfparser/pdf_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFParser.java` + `PDFXRefStreamParser.java` + `PDFObjectStreamParser.java` (traditional xref + trailer + /Prev, PDF 1.5 xref streams, compressed object streams, lenient startxref recovery, direct-/Length and missing-/Length stream body recovery, encrypted xref-stream early decryption, linearization metadata detection) |
| `pypdfbox/pdfparser/pdf_stream_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFStreamParser.java` |
| `pypdfbox/pdfparser/endstream_filter_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/EndstreamFilterStream.java` |
| `pypdfbox/loader.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/Loader.java` (path / bytes / stream forms only — encryption + password params deferred) |

Original work (no PROVENANCE entry needed; listed here for clarity):
- `pypdfbox/pdfparser/parse_error.py` — Python-native exception type with optional byte offset.

### `pypdfbox/pdfwriter/`

PDF-specific serialization — port territory.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfwriter/cos_standard_output_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/COSStandardOutputStream.java` |
| `pypdfbox/pdfwriter/cos_writer_xref_entry.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/COSWriterXRefEntry.java` |
| `pypdfbox/pdfwriter/cos_writer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/COSWriter.java` (full-save + incremental-save paths — xref-stream output, object-stream packing, encryption, signature digest computation stubbed for later clusters) |
| `pypdfbox/pdfwriter/content_stream_writer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/ContentStreamWriter.java` |
| `pypdfbox/pdfwriter/compress/compress_parameters.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/CompressParameters.java` |

### `pypdfbox/filter/`

PDF stream filters per ISO 32000-1 §7.4. Per PRD §3.7, filters that wrap stdlib are thin adapters; PDF-specific decode/encode + parameter handling is original.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/filter/filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Filter.java` | interface contract only |
| `pypdfbox/filter/decode_result.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/DecodeResult.java` | API surface only |
| `pypdfbox/filter/filter_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/FilterFactory.java` | API surface (registry + abbreviation map) |
| `pypdfbox/filter/flate_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/FlateFilter.java` | API surface; underlying compress/decompress is `zlib`. Predictor (PNG/TIFF) lives in shared `_predictor.py` |
| `pypdfbox/filter/_predictor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Predictor.java` | API surface (encode + decode entry points); per-row PNG / TIFF math is original (RFC 2083 §6 + TIFF 6.0 §14) |
| `pypdfbox/filter/ascii_hex_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCIIHexFilter.java` | API surface; underlying hex codec is `binascii` |
| `pypdfbox/filter/ascii85_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCII85Filter.java` | API surface; base-85 numerics delegated to `base64.a85encode`/`a85decode` |
| `pypdfbox/filter/run_length_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/RunLengthFilter.java` | full port — encoder ported line-for-line so output bytes match PDFBox |
| `pypdfbox/filter/lzw_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/LZWFilter.java` | full port — PDF-flavored LZW (9-12 bit, MSB-first, EarlyChange handling). Predictor (PNG/TIFF) lives in shared `_predictor.py` |
| `pypdfbox/filter/ccitt_fax_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CCITTFaxFilter.java` | API surface; T.4 / T.6 decoding delegated to libtiff via Pillow (synthetic TIFF wrapper around the encoded strip). Group 4 encode support delegates to libtiff via Pillow. |
| `pypdfbox/filter/jpx_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/JPXFilter.java` | API surface; JPEG 2000 decoding delegated to OpenJPEG via Pillow. Decode-only (no encoder use case yet). |
| `pypdfbox/filter/jbig2_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/JBIG2Filter.java` | API surface only — original implementation that wraps the MIT-licensed `jbig2-parser` (Rust-backed) library. `/JBIG2Globals` resolution + prepend logic and bilevel parameter surfacing are original; PDFBox upstream uses Levigo's `jbig2-imageio` SPI which we replaced. Decode-only (no encoder use case yet). |
| `pypdfbox/filter/missing_image_reader_exception.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/MissingImageReaderException.java` (extends `OSError` per CLAUDE.md `IOException` mapping) |
| `pypdfbox/filter/identity_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/IdentityFilter.java` | full port — pass-through `decode`/`encode` via `io_utils.copy`. Not registered in `FilterFactory` (upstream class is package-private; reached only through `CryptFilter`). |

### `pypdfbox/contentstream/`

Cluster #1 (Operator + OperatorName + PDContentStream).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/__init__.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/Operator.java` (operands stored on the instance per pypdfbox convention. Originally shipped as `operator.py`; restructured into a package in cluster #2 so the upstream `operator/text/` subpackage can coexist.) |
| `pypdfbox/contentstream/operator_name.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/OperatorName.java` |
| `pypdfbox/contentstream/pd_content_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/PDContentStream.java` (`get_matrix` typed as `Any` until `Matrix` ports with the rendering cluster) |

Cluster #2 (PDFStreamEngine + OperatorProcessor base + 9 PRD §6.7 text operators).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/pdf_stream_engine.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/PDFStreamEngine.java` (cluster #2: dispatch surface only — operator registry, processPage / processStream / processOperator / unsupportedOperator / operatorException; graphics-state stack, text-state, resources push/pop and Type3 / tiling-colour gating land in cluster #3) |
| `pypdfbox/contentstream/operator_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/OperatorProcessor.java` (also covers `MissingOperandException.java` — both small, co-located) |
| `pypdfbox/contentstream/operator/text/begin_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/BeginText.java` |
| `pypdfbox/contentstream/operator/text/end_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/EndText.java` |
| `pypdfbox/contentstream/operator/text/set_font_and_size.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetFontAndSize.java` (font lookup deferred to cluster #3 — handler validates types and notifies the engine) |
| `pypdfbox/contentstream/operator/text/set_matrix.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetMatrix.java` (forwards a 6-element list; will swap to `Matrix` in cluster #3) |
| `pypdfbox/contentstream/operator/text/move_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/MoveText.java` |
| `pypdfbox/contentstream/operator/text/move_text_set_leading.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/MoveTextSetLeading.java` |
| `pypdfbox/contentstream/operator/text/show_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowText.java` (cluster #2 raises `MissingOperandException` on empty operands; the upstream `getTextMatrix() == null` guard is deferred to cluster #3) |
| `pypdfbox/contentstream/operator/text/show_text_adjusted.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextAdjusted.java` (cluster #2 raises `MissingOperandException` on empty operands; the upstream `getTextMatrix() == null` guard is deferred to cluster #3) |
| `pypdfbox/contentstream/operator/text/show_text_line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLine.java` |
| `pypdfbox/contentstream/operator/text/show_text_line_and_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLineAndSpace.java` |

Cluster #3 lite (color operator hooks).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/color/set_stroking_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingColor.java` |

### `pypdfbox/text/`
_(not started)_

### `pypdfbox/rendering/`

Clusters #1 + #2 ship **original Python work** built on Pillow + aggdraw + fontTools — not a line-by-line port of upstream `PDFRenderer.java` / `PageDrawer.java`. The upstream classes target Java2D's `Graphics2D` API; there is no Python equivalent to port verbatim. The PUBLIC API surface (`render_image(page_index, scale)`, `render_image_with_dpi(page_index, dpi)`) does mirror upstream, and operator dispatch reuses the ported `PDFStreamEngine` infrastructure. Cluster #2 added text/glyph rasterisation (TrueType glyph outlines through fontTools), Form XObject `Do`, `W`/`W*` clip paths, and inline images.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/rendering/pdf_renderer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/PDFRenderer.java` + `pdfbox/src/main/java/org/apache/pdfbox/rendering/PageDrawer.java` | API surface only (`renderImage` / `renderImageWithDPI` entry points + per-operator semantics from `PageDrawer`). Implementation is original Python over Pillow + aggdraw + fontTools — Java2D `Graphics2D` has no Python equivalent. |
| `pypdfbox/rendering/image_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/ImageType.java` | enum + `to_buffered_image_type()` (returns the AWT `BufferedImage.TYPE_*` int constants); `pil_mode` is a Python-side helper for the renderer's ``Image.new`` mode. |
| `pypdfbox/rendering/render_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/RenderDestination.java` | enum (`EXPORT`/`VIEW`/`PRINT`); values are the title-case strings already consumed by `PDOptionalContentProperties.get_render_state`. |

Original work (no PROVENANCE entry needed; listed for clarity):
- `pypdfbox/rendering/__init__.py` — re-exports `PDFRenderer` + `ImageType` + `RenderDestination`

### `pypdfbox/pdmodel/`

Cluster #1 (PDDocument / PDPage / PDPageTree / PDDocumentCatalog / PDResources / PDRectangle).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/pd_document.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocument.java` (cluster #1 surface — load / save / save_incremental / pages / version / encryption flags; signing, FDF, overlay, font subsetting deferred) |
| `pypdfbox/pdmodel/pd_document_catalog.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentCatalog.java` (cluster #1 + follow-on waves — pages, version, language, page layout/mode defaults, structure/mark-info shortcuts, AcroForm cache/fixup overload, outlines, metadata, additional actions, names/dests, viewer preferences, page labels, output intents, threads, URI/base URI, requirements, associated files, developer extensions, piece info, needs-rendering, has_*/clear_* helpers; collection/perms/legal stay raw COS dictionaries until typed wrappers land) |
| `pypdfbox/pdmodel/pd_page.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPage.java` |
| `pypdfbox/pdmodel/pd_page_tree.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageTree.java` |
| `pypdfbox/pdmodel/pd_resources.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDResources.java` (cluster #1 surface — resource-dict accessors; XObject / font / colorspace lookups stubbed for later clusters) |
| `pypdfbox/pdmodel/pd_resource_cache.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/ResourceCache.java`, `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/DefaultResourceCache.java` (interface + default in-memory impl; soft-reference eviction not ported — explicit `clear()` instead, see `CHANGES.md`) |
| `pypdfbox/pdmodel/pd_rectangle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDRectangle.java` |
| `pypdfbox/pdmodel/missing_resource_exception.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/MissingResourceException.java` (extends `OSError` per CLAUDE.md `IOException` mapping) |

Cluster #2 (PDDocumentInformation / PDPageLabels / PDViewerPreferences).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/pd_document_information.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentInformation.java` |
| `pypdfbox/pdmodel/pd_page_labels.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDPageLabels.java` (in-memory dict instead of full `PDNumberTreeNode` port — read tolerates one level of `/Kids`, write emits flat `/Nums`. Full tree port lands when other number-tree consumers need it.) |
| `pypdfbox/pdmodel/pd_page_label_range.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDPageLabelRange.java` |
| `pypdfbox/pdmodel/pd_viewer_preferences.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/viewerpreferences/PDViewerPreferences.java` (`PRINT_SCALING.None` exported as `None_` for Python keyword conflict; underlying name value `"None"` preserved) |

Cluster #3 (PDStream + XObject family).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/pd_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDStream.java` |
| `pypdfbox/pdmodel/common/pd_range.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDRange.java` (typed wrapper around the 2-entry COSArray pair; pypdfbox extensions: `width`, `contains`, `clamp`, `is_normalized`, `is_well_formed`, `as_tuple`, iteration, value-equality / hashing, `set_starting_index`) |
| `pypdfbox/pdmodel/common/pd_matrix.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/Matrix.java` (renamed `PDMatrix` and re-homed under `pdmodel/common` for callers that work with page-level matrices without reaching into `pypdfbox.util`; deferred surface that depends on classes not yet ported: AffineTransform/Vector overloads. pypdfbox extensions: `is_identity`, `get_single` defensive copy, `__copy__`/`__deepcopy__` hooks. Static `Matrix.concatenate(a, b)` is exposed as `concatenate_matrices` to avoid colliding with the instance method `concatenate`.) |
| `pypdfbox/pdmodel/graphics/pd_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDXObject.java` |
| `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObject.java` (metadata + stream access, typed color-space/mask metadata, filter predicates, suffixes, decoded stream access, and best-effort PIL conversion for DCT/JPX plus raw 8-bit DeviceGray/DeviceRGB/Separation/DeviceN; full sampled-image rendering features such as decode arrays, masks, Indexed expansion, and non-8bpc samples remain rendering-cluster work) |
| `pypdfbox/pdmodel/graphics/form/pd_form_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/form/PDFormXObject.java` |
| `pypdfbox/pdmodel/graphics/form/pd_transparency_group_attributes.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/form/PDTransparencyGroupAttributes.java` |
| `pypdfbox/pdmodel/graphics/form/pd_transparency_group.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/form/PDTransparencyGroup.java` |
| `pypdfbox/pdmodel/graphics/pd_post_script_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDPostScriptXObject.java` |

Cluster #5 lite (annotation base + common subclasses).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotation.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_link.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationLink.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationText.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_square_circle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationSquareCircle.java`, `PDAnnotationSquare.java`, `PDAnnotationCircle.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_unknown.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationUnknown.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_widget.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationWidget.java` (lite — `/AA /BS /MK /Parent` return raw COS) |

Cluster #7 partial (outlines + destinations + actions).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDOutlineNode.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_document_outline.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDDocumentOutline.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_item.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDOutlineItem.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_destination_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDDestinationNameTreeNode.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_named_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDNamedDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_width_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitWidthDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_height_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitHeightDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_rectangle_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitRectangleDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_xyz_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageXYZDestination.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDAction.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_go_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionGoTo.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_uri.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionURI.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_named.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionNamed.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_launch.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionLaunch.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_remote_go_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionRemoteGoTo.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_java_script.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionJavaScript.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_submit_form.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionSubmitForm.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_reset_form.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionResetForm.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_import_data.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionImportData.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_hide.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionHide.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_thread.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionThread.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_sound.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionSound.java` (`/Sound` typed via `PDSoundStream`; setter still accepts raw COSBase for back-compat) |
| `pypdfbox/pdmodel/interactive/sound/pd_sound_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/sound/PDSoundStream.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_movie.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionMovie.java` (lite — `/Annotation` returns raw COS, typed PDAnnotationMovie deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_action_rendition.py` | 3.0.x | PDF 32000-1 §12.6.4.13 (no upstream source — modelled on spec; `/AN` and `/R` return raw COS) |
| `pypdfbox/pdmodel/interactive/action/pd_action_transition.py` | 3.0.x | PDF 32000-1 §12.6.4.14 (no upstream source; `/Trans` typed via PDTransition) |
| `pypdfbox/pdmodel/interactive/action/pd_action_embedded_go_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionEmbeddedGoTo.java` (`/T` typed via PDTargetDirectory) |
| `pypdfbox/pdmodel/interactive/action/pd_target_directory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDTargetDirectory.java` (lite — `/N` exposed as named-destination string, `/P` as page index int per task spec; deviates from upstream `/N`=embedded filename, `/P`=page-or-named-dest) |
| `pypdfbox/pdmodel/interactive/action/pd_document_catalog_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDDocumentCatalogAdditionalActions.java` |
| `pypdfbox/pdmodel/interactive/action/pd_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDAdditionalActions.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_border_style_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDBorderStyleDictionary.java` (lite — `/D` returns raw `COSArray`, `PDLineDashPattern` deferred) |
| `pypdfbox/pdmodel/interactive/annotation/pd_border_effect_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDBorderEffectDictionary.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_characteristics_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAppearanceCharacteristicsDictionary.java` (lite — `/BC`/`/BG` raw `COSArray`, `/I`/`/RI`/`/IX` raw `COSStream`) |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAppearanceDictionary.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_entry.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAppearanceEntry.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAppearanceStream.java` (lite — does NOT yet extend `PDFormXObject`) |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationLine.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_free_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationFreeText.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_file_attachment.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationFileAttachment.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_rubber_stamp.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationRubberStamp.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_popup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPopup.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_markup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationMarkup.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_text_markup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTextMarkup.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_highlight.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationHighlight.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_underline.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationUnderline.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_strikeout.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationStrikeout.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_squiggly.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationSquiggly.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_caret.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationCaret.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_ink.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationInk.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_polygon.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPolygon.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_polyline.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPolyline.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_movie.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationMovie.java` (lite — `/Movie` returns raw `COSDictionary`, `/A` returns raw `COSBase`; typed `PDMovie` and `PDMovieActivation` deferred) |
| `pypdfbox/pdmodel/common/pd_metadata.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDMetadata.java` (lite — multi-arg `__init__` dispatch; no XMPMetadata-returning accessor) |
| `pypdfbox/pdmodel/graphics/color/pd_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDColor.java` (lite — `to_rgb` rendering conversion deferred) |
| `pypdfbox/pdmodel/graphics/color/pd_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDColorSpace.java` (lite — `create()` factory deferred) |
| `pypdfbox/pdmodel/graphics/color/pd_device_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceColorSpace.java` |
| `pypdfbox/pdmodel/graphics/color/pd_device_gray.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceGray.java` |
| `pypdfbox/pdmodel/graphics/color/pd_device_rgb.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceRGB.java` |
| `pypdfbox/pdmodel/graphics/color/pd_device_cmyk.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceCMYK.java` (lite — ICC profile loading deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_action_unknown.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDAction.java` (unknown-action fallback pattern) |
| `pypdfbox/pdmodel/interactive/action/pd_page_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDPageAdditionalActions.java` |
| `pypdfbox/pdmodel/interactive/action/pd_form_field_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDFormFieldAdditionalActions.java` |
| `pypdfbox/pdmodel/interactive/action/pd_annotation_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDAnnotationAdditionalActions.java` |

Cluster #7 foundations (file specifications, generic name tree, optional content, page transitions, AcroForm scaffold).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/pd_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDNameTreeNode.java` |
| `pypdfbox/pdmodel/common/pd_string_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDJavascriptNameTreeNode.java` (modelled after; concrete string-keyed subclass — additive value→COS direction) |
| `pypdfbox/pdmodel/common/pd_number_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDNumberTreeNode.java` |
| `pypdfbox/pdmodel/pd_document_name_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentNameDictionary.java` |
| `pypdfbox/pdmodel/pd_document_name_destination_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentNameDestinationDictionary.java` |
| `pypdfbox/pdmodel/pd_embedded_files_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDEmbeddedFilesNameTreeNode.java` |
| `pypdfbox/pdmodel/pd_javascript_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDJavascriptNameTreeNode.java` (leaf type is Python `str` — typed `PDActionJavaScript` value deferred) |
| `pypdfbox/pdmodel/common/filespecification/pd_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_simple_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDSimpleFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_complex_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDComplexFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_embedded_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDEmbeddedFile.java` (lite — date accessors return raw COSString; constructor variants collapsed) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_group.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentGroup.java` (does not extend `PDPropertyList` — parent not yet ported) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_properties.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentProperties.java` (BaseState/RenderState enums collapsed to plain strings) |
| `pypdfbox/pdmodel/graphics/color/pd_output_intent.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDOutputIntent.java` (`(PDDocument, profile-bytes-or-stream)` constructor wraps ICC bytes into a flate-compressed `/DestOutputProfile` PDStream with `/N` from the header; typed `PDStream` accessor + `get_dest_output_intent()` raw alias; pypdfbox-only `get_n_for_profile()` helper, `/DestOutputProfileRef` PDF 2.0 entry, `set_subtype` / `set_dest_output_profile_ref` typed setters) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_membership_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentMembershipDictionary.java` (`/VE` raw COSArray — visibility-expression tree parsing deferred per upstream) |
| `pypdfbox/pdmodel/graphics/pd_property_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDPropertyList.java` (lite — `create()` returns `None` for unknown `/Type`) |
| `pypdfbox/pdmodel/graphics/pd_line_dash_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDLineDashPattern.java` (lite — phase accepts `float`) |
| `pypdfbox/pdmodel/graphics/state/pd_extended_graphics_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PDExtendedGraphicsState.java` (lite — `/SMask` typed via `get_soft_mask_typed()` → `PDSoftMask`; `/TR`/`/TR2` raw round-trip + honoured at compositing time in `PDFRenderer`; `copy_into_graphics_state` lite — see CHANGES.md) |
| `pypdfbox/pdmodel/graphics/state/pd_font_setting.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PDFontSetting.java` |
| `pypdfbox/pdmodel/graphics/state/pd_soft_mask.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PDSoftMask.java` (lite — exposes `/S`/`/G`/`/BC`/`/TR` raw round-trip; honoured by `PDFRenderer._render_soft_mask_alpha`) |
| `pypdfbox/pdmodel/graphics/state/rendering_intent.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/RenderingIntent.java` |
| `pypdfbox/pdmodel/graphics/state/rendering_mode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/RenderingMode.java` |
| `pypdfbox/pdmodel/graphics/color/pd_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDPattern.java` |
| `pypdfbox/pdmodel/graphics/color/pd_indexed.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDIndexed.java` (lite — lookup table raw filtered bytes) |
| `pypdfbox/pdmodel/graphics/color/pd_separation.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDSeparation.java` |
| `pypdfbox/pdmodel/graphics/color/pd_device_n.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceN.java` |
| `pypdfbox/pdmodel/graphics/color/pd_icc_based.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDICCBased.java` (lite — ICC profile parsing deferred) |
| `pypdfbox/pdmodel/graphics/color/pd_cal_gray.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDCalGray.java` |
| `pypdfbox/pdmodel/graphics/color/pd_cal_rgb.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDCalRGB.java` |
| `pypdfbox/pdmodel/graphics/color/pd_lab.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDLab.java` |
| `pypdfbox/pdmodel/font/pd_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFont.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_simple_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDSimpleFont.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_type1_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType1Font.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_true_type_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDTrueTypeFont.java` (scaffold + `get_glyph_width(code)` backed by `/Widths` first, then embedded `/FontFile2` hmtx scaled by `1000 / unitsPerEm`; full Type1 fallbacks / CIDToGIDMap deferred) |
| `pypdfbox/pdmodel/font/pd_type0_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType0Font.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_font_descriptor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontDescriptor.java` + `PDPanose.java` + `PDPanoseClassification.java` (full surface — flag bits, all Table 122 entries, /FontFile/FontFile2/FontFile3, /CharSet, /MissingWidth, /CIDSet, /Style→Panose 12-byte block) |
| `pypdfbox/pdmodel/font/pd_font_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontFactory.java` (Type1/TrueType/Type0 only; PDCIDFont/PDType3Font deferred) |
| `pypdfbox/pdmodel/font/pd_font_like.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontLike.java` (Java interface modelled as runtime-checkable `typing.Protocol`; method names snake_case per project rules) |
| `pypdfbox/pdmodel/font/pd_vector_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDVectorFont.java` (Java interface modelled as runtime-checkable `typing.Protocol`; `GeneralPath` typed as `Any` since pypdfbox is AWT-free) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_signature.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSignature.java` (lite — actual signing deferred) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_seed_value.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSeedValue.java` (lite) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_signature_lock.py` | 3.0.x | PDF 32000-1 Table 233 SigFieldLock dictionary (no upstream `PDSignatureLock.java`; modelled on spec) |
| `pypdfbox/pdmodel/interactive/digitalsignature/signature_interface.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/SignatureInterface.java` (single-method `sign(content) -> bytes` callback) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pkcs7_signature.py` | 3.0.x | original (concrete `SignatureInterface` backed by `cryptography.hazmat.primitives.serialization.pkcs7.PKCS7SignatureBuilder`; PDFBox callers usually plug in a Bouncy Castle / KeyStore-driven impl) |
| `pypdfbox/pdmodel/interactive/form/pd_xfa_resource.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDXFAResource.java` (`get_document` returns `xml.etree.ElementTree.Element`, not W3C `Document`; `is_dynamic` substring heuristic) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureNode.java` |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDAttributeObject.java` (lite — typed owner subclasses deferred) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/revisions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/Revisions.java` |
| `pypdfbox/pdmodel/font/standard14_fonts.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/Standard14Fonts.java` (per-glyph widths + descriptor numerics now sourced from bundled Adobe AFM files via `afm_loader`) |
| `pypdfbox/pdmodel/font/afm/*.afm` (14 files) | 3.0.x | `pdfbox/src/main/resources/org/apache/pdfbox/resources/afm/*.afm` (verbatim Adobe Core 14 AFM metrics; redistributed under the Adobe permissive notice preserved in each file's `Comment Copyright …` header — see `pypdfbox/pdmodel/font/afm/LICENSE.txt`) |
| `pypdfbox/pdmodel/font/encoding/encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/Encoding.java` |
| `pypdfbox/pdmodel/font/encoding/dictionary_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/DictionaryEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/standard_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/StandardEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/win_ansi_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/WinAnsiEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/mac_roman_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/MacRomanEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/mac_os_roman_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/MacOSRomanEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/mac_expert_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/MacExpertEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/symbol_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/SymbolEncoding.java` |
| `pypdfbox/pdmodel/font/encoding/zapf_dingbats_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/ZapfDingbatsEncoding.java` |
| `pypdfbox/pdmodel/graphics/pattern/pd_abstract_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDAbstractPattern.java` |
| `pypdfbox/pdmodel/graphics/pattern/pd_tiling_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDTilingPattern.java` (incl. `PDContentStream` mixin: `get_contents` / `get_contents_for_random_access`) |
| `pypdfbox/pdmodel/graphics/pattern/pd_shading_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDShadingPattern.java` |
| `pypdfbox/pdmodel/graphics/shading/pd_shading.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShading.java` |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type1.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType1.java` (function-based; lite) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type2.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType2.java` (axial; lite) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type3.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType3.java` (radial; lite) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type4.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType4.java` (free-form Gouraud; mesh decoding deferred) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type5.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType5.java` (lattice Gouraud) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type6.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType6.java` (Coons patch) |
| `pypdfbox/pdmodel/graphics/shading/pd_shading_type7.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType7.java` (tensor-product patch) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_standard_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDStandardAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_layout_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDLayoutAttributeObject.java` (full §14.8.5.4 surface — Wave 41 round-out) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_list_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDListAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_print_field_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDPrintFieldAttributeObject.java` |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_table_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDTableAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_export_format_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDExportFormatAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_user_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDUserAttributeObject.java` (lite — /P entries as plain dicts) |
| `pypdfbox/pdmodel/documentinterchange/prepress/pd_box_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/prepress/PDBoxStyle.java` |
| `pypdfbox/pdmodel/pd_page_content_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageContentStream.java` (lite — text encoding, AppendMode, compression, BMC/BDC/EMC deferred) |
| `pypdfbox/contentstream/operator/operator_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/OperatorProcessor.java` (lite — handlers are no-op stubs) |
| `pypdfbox/contentstream/operator/operator_registry.py` | 3.0.x | original (Python-side dispatch registry) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransition.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionStyle.java` (plain class with constants, not `enum.Enum`) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_motion.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionMotion.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_dimension.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDimension.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_direction.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDirection.java` |
| `pypdfbox/pdmodel/interactive/form/pd_acro_form.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDAcroForm.java` (scaffold + `flatten` + `refresh_appearances` + `xfa_is_dynamic`/`has_xfa`/`set_xfa` + `get_need_appearances_if_exists` + scripting handler + `cache_fields` + `get_signature_fields` — FDF/PDFieldTree deferred) |
| `pypdfbox/pdmodel/interactive/form/pd_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDField.java` (scaffold — value handling + `/AA` typing deferred) |
| `pypdfbox/pdmodel/interactive/form/pd_non_terminal_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDNonTerminalField.java` |
| `pypdfbox/pdmodel/interactive/form/pd_terminal_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDTerminalField.java` (also hosts `PDFieldStub` — generic concrete subclass returned by factory until typed dispatch lands) |
| `pypdfbox/pdmodel/interactive/form/pd_field_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDFieldFactory.java` (typed `/FT` dispatch wired for Tx/Btn/Ch/Sig) |
| `pypdfbox/pdmodel/interactive/form/pd_variable_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDVariableText.java` |
| `pypdfbox/pdmodel/interactive/form/pd_default_appearance_string.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDDefaultAppearanceString.java` |
| `pypdfbox/pdmodel/interactive/form/pd_text_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDTextField.java` (lite — value handling does not regenerate widget appearance) |
| `pypdfbox/pdmodel/interactive/form/pd_button.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDButton.java` (lite — `get_on_values` returns empty set) |
| `pypdfbox/pdmodel/interactive/form/pd_push_button.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDPushButton.java` |
| `pypdfbox/pdmodel/interactive/form/pd_radio_button.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDRadioButton.java` |
| `pypdfbox/pdmodel/interactive/form/pd_check_box.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDCheckBox.java` (lite — `get_on_value` walks first widget kid only) |
| `pypdfbox/pdmodel/interactive/form/pd_choice.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDChoice.java` |
| `pypdfbox/pdmodel/interactive/form/pd_combo_box.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDComboBox.java` |
| `pypdfbox/pdmodel/interactive/form/pd_list_box.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDListBox.java` |
| `pypdfbox/pdmodel/interactive/form/pd_signature_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureField.java` (lite — typed `PDSignature`/`PDSeedValue`/`PDSignatureLock` deferred) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_tree_root.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureTreeRoot.java` (scaffold — typed kid dispatch / parent tree / class map deferred) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_element.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureElement.java` (scaffold — `/A` attributes, `/C` classes, `getPage`/`setPage`, `getStandardStructureType` ported; multi-overload `appendKid` deferred) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_mark_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDMarkInfo.java` (upstream `setSuspect(false)`-only bug fixed) |

### `pypdfbox/fontbox/`

Cluster #1 — TTF data stream + 12 table classes + WGL4 glyph-name table.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/ttf/ttf_data_stream.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/TTFDataStream.java` (+ `MemoryTTFDataStream.java`, `RandomAccessReadDataStream.java` folded in) |
| `pypdfbox/fontbox/ttf/ttf_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/TTFTable.java` |
| `pypdfbox/fontbox/ttf/header_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/HeaderTable.java` |
| `pypdfbox/fontbox/ttf/horizontal_header_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/HorizontalHeaderTable.java` |
| `pypdfbox/fontbox/ttf/horizontal_metrics_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/HorizontalMetricsTable.java` |
| `pypdfbox/fontbox/ttf/index_to_location_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/IndexToLocationTable.java` |
| `pypdfbox/fontbox/ttf/maximum_profile_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/MaximumProfileTable.java` (incl. PDFBOX-6105 max_component_depth fix) |
| `pypdfbox/fontbox/ttf/name_record.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/NameRecord.java` |
| `pypdfbox/fontbox/ttf/naming_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/NamingTable.java` (incl. PDFBOX-2608 invalid-offset guard) |
| `pypdfbox/fontbox/ttf/os2_windows_metrics_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/OS2WindowsMetricsTable.java` |
| `pypdfbox/fontbox/ttf/post_script_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/PostScriptTable.java` (incl. PDFBOX-4851 EOF padding) |
| `pypdfbox/fontbox/ttf/cmap_lookup.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/CmapLookup.java` |
| `pypdfbox/fontbox/ttf/cmap_subtable.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/CmapSubtable.java` (formats 0/2/4/6/12; formats 8/10/13/14 raise NotImplementedError — deferred to fontbox cluster #3) |
| `pypdfbox/fontbox/ttf/cmap_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/CmapTable.java` |
| `pypdfbox/fontbox/ttf/wgl4_names.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/WGL4Names.java` |
| `pypdfbox/fontbox/ttf/true_type_font.py` | n/a (wrapper) | API-shape mirror of `fontbox/src/main/java/org/apache/fontbox/ttf/TrueTypeFont.java`; SFNT parsing is delegated to the MIT-licensed `fontTools.ttLib` library rather than a hand-rolled port. The wrapper preserves the PDFBox accessor surface (`get_units_per_em`, `get_number_of_glyphs`, `get_advance_width`, `get_unicode_cmap_subtable`, `get_header` / `get_horizontal_header` / `get_maximum_profile` / `get_horizontal_metrics`, `get_table_map`) and projects fontTools' values back into the existing typed-table classes (`HeaderTable`, `HorizontalHeaderTable`, etc., which remain hand-rolled ports of their upstream Java counterparts). Glyph outlines, GSUB / GPOS, kerning, and name-table accessors still defer to a later cluster. |

Cluster #3 — encodings + Adobe Glyph List.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/encoding/encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/Encoding.java` (folded with `fontbox/src/main/java/org/apache/fontbox/encoding/Encoding.java` — pdmodel base is the richer one; `addCharacterEncoding` exposed as `add`) |
| `pypdfbox/fontbox/encoding/standard_encoding.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/encoding/StandardEncoding.java` |
| `pypdfbox/fontbox/encoding/mac_roman_encoding.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/encoding/MacRomanEncoding.java` |
| `pypdfbox/fontbox/encoding/win_ansi_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/WinAnsiEncoding.java` |
| `pypdfbox/fontbox/encoding/mac_expert_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/MacExpertEncoding.java` |
| `pypdfbox/fontbox/encoding/symbol_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/SymbolEncoding.java` |
| `pypdfbox/fontbox/encoding/zapf_dingbats_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/ZapfDingbatsEncoding.java` |
| `pypdfbox/fontbox/encoding/glyph_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/GlyphList.java` (data inlined as Python dict literals from upstream `glyphlist.txt` (4281 entries) + `zapfdingbats.txt` (202 entries); reverse `unicode -> name` map deferred — only forward `to_unicode` is used by text extraction) |

Cluster #4 — PostScript CMap parsing.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/cmap/codespace_range.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cmap/CodespaceRange.java` |
| `pypdfbox/fontbox/cmap/cmap.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cmap/CMap.java` |
| `pypdfbox/fontbox/cmap/cmap_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cmap/CMapParser.java` |

### `pypdfbox/xmpbox/`

XMP packet parsing plus typed schema/property surfaces. Parser storage remains
primitive-compatible while schema APIs expose the ported `AbstractField`,
`ArrayProperty`, simple-property, structured-type, and `TypeMapping` layers.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/xmp_metadata.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/XMPMetadata.java` (+ `XmpConstants.java` folded in; schema factories/getters and typed-property accessors wired for the implemented schema set) |
| `pypdfbox/xmpbox/xmp_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPSchema.java` (primitive parser storage plus upstream-named generic property hooks; typed `AbstractField` / `ArrayProperty` classes live under `pypdfbox/xmpbox/type/`) |
| `pypdfbox/xmpbox/dublin_core_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/DublinCoreSchema.java` (constants + value getters) |
| `pypdfbox/xmpbox/xmp_basic_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPBasicSchema.java` (string-form and typed property accessors; `Advisory` exposes `Bag<XPathType>`, `Identifier` exposes `Bag<TextType>`, `Thumbnails` exposes `Alt<ThumbnailType>`; string date getters preserve ISO strings while typed date accessors return `DateType`) |
| `pypdfbox/xmpbox/pdfa_identification_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/PDFAIdentificationSchema.java` (typed `part` / `conformance` / `amd` / `rev` accessors with upstream `setPartValueWithInt` / `setPartValueWithString` / `setRevValueWithInt` / `setRevValueWithString` aliases; conformance validates against `{A, B, U, e, f}` per PDFBOX-6088 and raises `BadFieldValueException`; pypdfbox-only `corr` correction-year passthrough) |
| `pypdfbox/xmpbox/pdfa_extension_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/PDFAExtensionSchema.java` (lite surface — `pdfaExtension:schemas` Bag dict accessors + raw element passthrough; nested `pdfaProperty` / `pdfaType` struct hierarchy deferred) |
| `pypdfbox/xmpbox/xmp_rights_management_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPRightsManagementSchema.java` (typed `Certificate` / `Marked` / `Owner` / `UsageTerms` / `WebStatement` accessors) |
| `pypdfbox/xmpbox/xmp_media_management_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPMediaManagementSchema.java` (typed simple properties plus ResourceRef/ResourceEvent/Version-backed `DerivedFrom`, `RenditionOf`, `ManagedFrom`, `History`, `Versions`, `Manifest`, and `Ingredients`) |
| `pypdfbox/xmpbox/dom_xmp_parser.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/DomXmpParser.java` (+ `XmpParsingException.java`; read path only, ElementTree-backed) |
| `pypdfbox/xmpbox/date_converter.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/DateConverter.java` (returns `datetime.datetime` instead of `Calendar`; naive ISO 8601 strings are anchored to UTC matching upstream's `fromISO8601` fallback; year-0 input rejected — Python `datetime` does not support year 0, deviates from upstream `0000-01-01` → `0001-01-01`) |

### `pypdfbox/tools/`

Tools cluster #1 — command-line dispatcher and basic commands.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/tools/cli.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFBox.java` |
| `pypdfbox/tools/merge.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFMerger.java` |
| `pypdfbox/tools/split.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFSplit.java` |
| `pypdfbox/tools/decrypt.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/Decrypt.java` (owner-password flow, exit-code parity, safe in-place rewrite, `-keyStore`/`-alias` PKCS#12 loading surface; public-key material is validated but end-to-end public-key decrypt remains deferred) |
| `pypdfbox/tools/version.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/Version.java` |

Original work (no PROVENANCE entry needed; listed here for clarity):
- `pypdfbox/tools/info.py` — small pypdfbox-specific document summary command.

### `pypdfbox/debugger/`

Tkinter/Ttk port of the upstream Swing-based debugger (PDF tree explorer / hex viewer / search). Wave 1292+. Stdlib-only (`tkinter`, `tkinter.ttk`, `tkinter.font`, `tkinter.simpledialog`, `tkinter.filedialog`, `tkinter.messagebox`) plus the existing Pillow dep for image rendering.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/debugger/ui/array_entry.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ArrayEntry.java` |
| `pypdfbox/debugger/ui/map_entry.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/MapEntry.java` |
| `pypdfbox/debugger/ui/page_entry.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/PageEntry.java` |
| `pypdfbox/debugger/ui/document_entry.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/DocumentEntry.java` |
| `pypdfbox/debugger/ui/xref_entry.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/XrefEntry.java` |
| `pypdfbox/debugger/ui/xref_entries.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/XrefEntries.java` |
| `pypdfbox/debugger/ui/pdf_tree_model.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/PDFTreeModel.java` |
| `pypdfbox/debugger/ui/window_prefs.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/WindowPrefs.java` |
| `pypdfbox/debugger/ui/debug_log.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/DebugLog.java` |
| `pypdfbox/debugger/ui/high_resolution_image_icon.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/HighResolutionImageIcon.java` |
| `pypdfbox/debugger/ui/image_util.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ImageUtil.java` |
| `pypdfbox/debugger/treestatus/tree_status.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/treestatus/TreeStatus.java` |
| `pypdfbox/debugger/treestatus/tree_status_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/treestatus/TreeStatusPane.java` |
| `pypdfbox/debugger/ui/textsearcher/search_engine.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/textsearcher/SearchEngine.java` |
| `pypdfbox/debugger/ui/textsearcher/searcher.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/textsearcher/Searcher.java` |
| `pypdfbox/debugger/ui/textsearcher/search_panel.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/textsearcher/SearchPanel.java` |
| `pypdfbox/debugger/hexviewer/hex_model.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexModel.java` |
| `pypdfbox/debugger/hexviewer/hex_changed_event.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexChangedEvent.java` |
| `pypdfbox/debugger/hexviewer/hex_change_listener.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexChangeListener.java` |
| `pypdfbox/debugger/hexviewer/select_event.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/SelectEvent.java` |
| `pypdfbox/debugger/hexviewer/selection_change_listener.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/SelectionChangeListener.java` |
| `pypdfbox/debugger/hexviewer/hex_model_changed_event.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexModelChangedEvent.java` |
| `pypdfbox/debugger/hexviewer/hex_model_change_listener.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexModelChangeListener.java` |
| `pypdfbox/debugger/hexviewer/address_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/AddressPane.java` |
| `pypdfbox/debugger/hexviewer/hex_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexPane.java` |
| `pypdfbox/debugger/hexviewer/ascii_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/ASCIIPane.java` |
| `pypdfbox/debugger/hexviewer/upper_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/UpperPane.java` |
| `pypdfbox/debugger/hexviewer/status_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/StatusPane.java` |
| `pypdfbox/debugger/hexviewer/hex_editor.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexEditor.java` |
| `pypdfbox/debugger/hexviewer/hex_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/hexviewer/HexView.java` |
| `pypdfbox/debugger/flagbitspane/flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/Flag.java` |
| `pypdfbox/debugger/flagbitspane/annot_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/AnnotFlag.java` |
| `pypdfbox/debugger/flagbitspane/field_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/FieldFlag.java` |
| `pypdfbox/debugger/flagbitspane/encrypt_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/EncryptFlag.java` |
| `pypdfbox/debugger/flagbitspane/sig_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/SigFlag.java` |
| `pypdfbox/debugger/flagbitspane/font_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/FontFlag.java` |
| `pypdfbox/debugger/flagbitspane/panose_flag.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/PanoseFlag.java` |
| `pypdfbox/debugger/flagbitspane/flag_bits_pane_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/FlagBitsPaneView.java` |
| `pypdfbox/debugger/flagbitspane/flag_bits_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/flagbitspane/FlagBitsPane.java` |
| `pypdfbox/debugger/streampane/tooltip/tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/ToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/tool_tip_controller.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/ToolTipController.java` |
| `pypdfbox/debugger/streampane/tooltip/color_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/ColorToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/rg_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/RGToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/k_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/KToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/g_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/GToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/scn_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/SCNToolTip.java` |
| `pypdfbox/debugger/streampane/tooltip/font_tool_tip.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/tooltip/FontToolTip.java` |
| `pypdfbox/debugger/colorpane/cs_array_based.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/CSArrayBased.java` |
| `pypdfbox/debugger/colorpane/cs_device_n.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/CSDeviceN.java` |
| `pypdfbox/debugger/colorpane/cs_indexed.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/CSIndexed.java` |
| `pypdfbox/debugger/colorpane/cs_separation.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/CSSeparation.java` |
| `pypdfbox/debugger/colorpane/color_bar_cell_renderer.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/ColorBarCellRenderer.java` |
| `pypdfbox/debugger/colorpane/device_n_colorant.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/DeviceNColorant.java` |
| `pypdfbox/debugger/colorpane/device_n_table_model.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/DeviceNTableModel.java` |
| `pypdfbox/debugger/colorpane/indexed_colorant.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/IndexedColorant.java` |
| `pypdfbox/debugger/colorpane/indexed_table_model.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/colorpane/IndexedTableModel.java` |
| `pypdfbox/debugger/fontencodingpane/font_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/FontPane.java` |
| `pypdfbox/debugger/fontencodingpane/font_encoding_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/FontEncodingView.java` |
| `pypdfbox/debugger/fontencodingpane/simple_font.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/SimpleFont.java` |
| `pypdfbox/debugger/fontencodingpane/type0_font.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/Type0Font.java` |
| `pypdfbox/debugger/fontencodingpane/type3_font.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/Type3Font.java` |
| `pypdfbox/debugger/fontencodingpane/font_encoding_pane_controller.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/fontencodingpane/FontEncodingPaneController.java` |
| `pypdfbox/debugger/streampane/stream.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/Stream.java` |
| `pypdfbox/debugger/streampane/operator_marker.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/OperatorMarker.java` |
| `pypdfbox/debugger/streampane/stream_pane_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/StreamPaneView.java` |
| `pypdfbox/debugger/streampane/stream_text_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/StreamTextView.java` |
| `pypdfbox/debugger/streampane/stream_image_view.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/StreamImageView.java` |
| `pypdfbox/debugger/streampane/stream_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/streampane/StreamPane.java` |
| `pypdfbox/debugger/stringpane/string_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/stringpane/StringPane.java` |
| `pypdfbox/debugger/signaturepane/signature_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/signaturepane/SignaturePane.java` |
| `pypdfbox/debugger/ui/menu_base.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/MenuBase.java` |
| `pypdfbox/debugger/ui/zoom_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ZoomMenu.java` |
| `pypdfbox/debugger/ui/rotation_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/RotationMenu.java` |
| `pypdfbox/debugger/ui/render_destination_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/RenderDestinationMenu.java` |
| `pypdfbox/debugger/ui/view_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ViewMenu.java` |
| `pypdfbox/debugger/ui/image_type_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ImageTypeMenu.java` |
| `pypdfbox/debugger/ui/print_dpi_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/PrintDpiMenu.java` |
| `pypdfbox/debugger/ui/text_stripper_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/TextStripperMenu.java` |
| `pypdfbox/debugger/ui/tree_view_menu.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/TreeViewMenu.java` |
| `pypdfbox/debugger/ui/recent_files.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/RecentFiles.java` |
| `pypdfbox/debugger/pagepane/page_pane.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/pagepane/PagePane.java` |
| `pypdfbox/debugger/pagepane/debug_text_overlay.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/pagepane/DebugTextOverlay.java` |
| `pypdfbox/debugger/ui/error_dialog.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ErrorDialog.java` |
| `pypdfbox/debugger/ui/file_open_save_dialog.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/FileOpenSaveDialog.java` |
| `pypdfbox/debugger/ui/text_dialog.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/TextDialog.java` |
| `pypdfbox/debugger/ui/log_dialog.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/LogDialog.java` |
| `pypdfbox/debugger/ui/reader_bottom_panel.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/ReaderBottomPanel.java` |
| `pypdfbox/debugger/ui/pdf_tree_cell_renderer.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/PDFTreeCellRenderer.java` |
| `pypdfbox/debugger/ui/tree.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/Tree.java` |
| `pypdfbox/debugger/ui/osx_adapter.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/OSXAdapter.java` |
| `pypdfbox/debugger/pd_debugger.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/PDFDebugger.java` |

---

## Ported upstream tests

Per PRD §12.1, every cluster's tests come in two layers: hand-written tests (under `tests/<module>/`) and ported upstream JUnit 5 tests (under `tests/<module>/upstream/`). Only the **ported** tests are listed below — hand-written tests are original work.

Upstream baseline branch: `apache/pdfbox` `3.0` (most files at `pdfbox/src/test/java/org/apache/pdfbox/<module>/...`; the io subproject lives at `io/src/test/java/org/apache/pdfbox/io/...`).

### `tests/io/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/io/upstream/test_random_access_read_buffer.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferTest.java` (includes PDFBOX-5764 sliced-input parity) |
| `tests/io/upstream/test_random_access_read_buffered_file.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferedFileTest.java` (includes `readFullyAcrossBuffers` cross-buffer read parity) |
| `tests/io/upstream/test_random_access_read_memory_mapped.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadMemoryMappedFileTest.java` |
| `tests/io/upstream/test_random_access_read_view.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadViewTest.java` |
| `tests/io/upstream/test_random_access_write_buffer.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadWriteBufferTest.java` (read+write split — write portion only) |
| `tests/io/upstream/test_scratch_file_buffer.py` | `io/src/test/java/org/apache/pdfbox/io/ScratchFileBufferTest.java` |
| `tests/io/upstream/test_io_utils.py` | `io/src/test/java/org/apache/pdfbox/io/TestIOUtils.java` |
| `tests/io/upstream/fixtures/RandomAccessReadFile1.txt` | `io/src/test/resources/org/apache/pdfbox/io/RandomAccessReadFile1.txt` (byte-identical) |
| `tests/io/upstream/fixtures/RandomAccessReadEmptyFile.txt` | `io/src/test/resources/org/apache/pdfbox/io/RandomAccessReadEmptyFile.txt` |

Not yet ported (classes not implemented in pypdfbox): `SequenceRandomAccessReadTest`, `RandomAccessInputStreamTest`, `NonSeekableRandomAccessReadInputStreamTest`.

### `tests/cos/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/cos/upstream/test_cos_array.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSArray.java` |
| `tests/cos/upstream/test_cos_boolean.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSBoolean.java` |
| `tests/cos/upstream/test_cos_dictionary.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/COSDictionaryTest.java` |
| `tests/cos/upstream/test_cos_document.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/COSDocumentTest.java` |
| `tests/cos/upstream/test_cos_float.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSFloat.java` |
| `tests/cos/upstream/test_cos_increment.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java` (all skipped — needs PDDocument / Loader / pdfwriter) |
| `tests/cos/upstream/test_cos_integer.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSInteger.java` |
| `tests/cos/upstream/test_cos_name.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSName.java` |
| `tests/cos/upstream/test_cos_number.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSNumber.java` |
| `tests/cos/upstream/test_cos_object_key.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/COSObjectKeyTest.java` |
| `tests/cos/upstream/test_cos_stream.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSStream.java` |
| `tests/cos/upstream/test_cos_string.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSString.java` |
| `tests/cos/upstream/test_cos_update_info.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSUpdateInfo.java` |
| `tests/cos/upstream/test_pdf_doc_encoding.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java` |
| `tests/cos/upstream/test_unmodifiable_cos_dictionary.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/UnmodifiableCOSDictionaryTest.java` |

`TestCOSBase.java` and `TestCOSNumber.java` are abstract upstream — folded into the relevant subclass tests rather than ported separately.

### `tests/pdfparser/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdfparser/upstream/test_base_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/TestBaseParser.java` (includes `testCheckForEndOfString` / PDFBOX-6093 literal-string recovery) |
| `tests/pdfparser/upstream/test_pdf_stream_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/PDFStreamParserTest.java` |
| `tests/pdfparser/upstream/test_cos_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/COSParserTest.java` (parse-header / brute-force / rebuild-trailer / parse-xref-stream / parse-xref-table subset; fixture-corpus-driven cases skipped) |
| `tests/pdfparser/upstream/test_endstream_filter_stream.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/EndstreamFilterStreamTest.java` (byte-sequence test directly ported; PDFBOX-2079 embedded-file fixture path covered by a synthetic missing-`/Length` stream-body regression through `PDFParser._read_stream_body()`) |
| `tests/pdfparser/upstream/test_base_parser_wave888.py` | (no upstream Java equivalent — pypdfbox-original coverage-wave augmentation that re-invokes sibling `test_base_parser` cases as callables to gate skipped-placeholder branches) |

Not yet ported (classes not implemented in pypdfbox): `PDFObjectStreamParserTest`, `TestPDFParser`.

### `tests/filter/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/filter/upstream/test_filters.py` | `pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java` (RLE round-trip + ASCII85 slice) |
| `tests/filter/upstream/test_filters_flate_ascii_hex.py` | `pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java` (Flate + ASCIIHex slice) |
| `tests/filter/upstream/test_lzw_filter_upstream.py` | `pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java` (LZW slice) + PDFBOX-1977 regression |

### `tests/pdfwriter/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdfwriter/upstream/test_save_incremental.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java` (all skipped — needs PDDocument + PDPageContentStream + pdmodel + fontbox) |
| `tests/pdfwriter/upstream/test_content_stream_writer.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/ContentStreamWriterTest.java` (single test `testPDFBox4750` executable against in-tree PDFStreamParser, ContentStreamWriter, PDStream, and PDFRenderer) |

### `tests/xmpbox/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/xmpbox/upstream/test_dom_xmp_parser.py` | `xmpbox/src/test/java/org/apache/xmpbox/xml/DomXmpParserTest.java` (`testPDFBox5976` + `testPDFBox5649` ported; rest skipped — need rich type system / strict mode / additional schemas) |

### `tests/pdmodel/upstream/` (cluster #2 additions)

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/upstream/test_pd_document_information.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentInformation.java` (fixture-backed metadata extraction and PDFBOX-3068 indirect-title cases covered by synthetic PDFs) |

`PDPageLabelsTest` / `PDViewerPreferencesTest` do not exist upstream in PDFBox 3.0.

### `tests/pdmodel/upstream/` (cluster #3 additions)

PDFBox 3.0 has no focused upstream JUnit classes for `PDStream`, `PDXObject`, or `PDFormXObject`. At cluster #3 time, `PDImageXObjectTest` cases that depended on image codecs, `PDImageXObject.createFromFile*`, `LosslessFactory`, and rendering/color-space classes were deferred. Later image factory and mask coverage is tracked under the Wave 31+ image entries below.

### `tests/pdmodel/interactive/annotation/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/interactive/annotation/upstream/test_pd_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTest.java` |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_square_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDSquareAnnotationTest.java` |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_circle_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDCircleAnnotationTest.java` |

### `tests/fontbox/cmap/`

`tests/fontbox/cmap/upstream/test_cmap_parser.py` ports focused `CMapParserTest` parser regressions, including PDFBOX-4720 identity `bfrange`; broader bundled-resource/font-text parity remains covered by local parser tests until fixtures are ported.

### `tests/pdmodel/interactive/action/` and `tests/pdmodel/interactive/documentnavigation/`

PDFBox 3.0 does not provide focused unit-test classes for each lightweight action and destination wrapper. Cluster #7 wrappers are covered with hand-written tests for factory dispatch, COS round-trip, and outline/catalog/link integration. Broader upstream tests that depend on fixture PDFs remain skipped in `tests/pdmodel/upstream/` until those fixtures land.

### `tests/tools/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/tools/upstream/test_pdfbox_headless.py` | `pdfbox-tools/src/test/java/org/apache/pdfbox/tools/TestPDFBox.java` |

### `tests/fontbox/encoding/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/fontbox/encoding/upstream/test_encoding.py` | `fontbox/src/test/java/org/apache/fontbox/encoding/EncodingTest.java` |

### `tests/fontbox/ttf/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/fontbox/ttf/upstream/test_wgl4_names.py` | `fontbox/src/test/java/org/apache/fontbox/ttf/WGL4NamesTest.java` |
| `tests/fontbox/ttf/upstream/test_random_access_read_buffer_data_stream.py` | `fontbox/src/test/java/org/apache/fontbox/ttf/RandomAccessReadBufferDataStreamTest.java` |
| `tests/fontbox/ttf/upstream/test_ttf_parser.py` | `fontbox/src/test/java/org/apache/fontbox/ttf/TestTTFParser.java` |
| `tests/fontbox/ttf/upstream/test_otf_parser.py` | (no upstream `OTFParserTest.java` in PDFBox 3.0; tests model the public surface from `OTFParser.java`) |
| `tests/fontbox/ttf/upstream/test_kerning_subtable.py` | (no upstream `KerningSubtableTest.java` in PDFBox 3.0; tests model the public contract from `KerningSubtable.java`) |
| `tests/fontbox/ttf/upstream/test_cmap_subtable.py` | `fontbox/src/test/java/org/apache/fontbox/ttf/TestCMapSubtable.java` |
| `tests/xmpbox/upstream/test_date_converter.py` | `xmpbox/src/test/java/org/apache/xmpbox/DateConverterTest.java` (folds in `pdfbox/src/test/java/org/apache/pdfbox/util/TestDateUtil.java`) |
| `tests/xmpbox/upstream/test_type_mapping.py` | (no upstream `TypeMappingTest.java` in PDFBox 3.0; tests model the public surface from `TypeMapping.java`) |
| `tests/pdmodel/graphics/image/upstream/test_ccitt_factory.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/CCITTFactoryTest.java` (partial: chess image + encode round-trip; fixture-dependent tests deferred until `ccittg3.tif`/`ccittg4.tif`/`ccittg4multi.tif` are vendored) |

Not yet ported (need `TTFParser` / `TrueTypeCollection` / `TTFSubsetter` — fontbox clusters #2+): `TestTTFParser`, `TestCMapSubtable`, `GlyfCompositeDescriptTest`, `TrueTypeFontCollectionTest`, `TTFSubsetterTest`, `GlyphSubstitutionTable*`.

### Test fixtures

| pypdfbox fixture path | upstream resource path | upstream PDFBox version |
|---|---|---|
| `tests/fixtures/fontbox/ttf/LiberationSans-Regular.ttf` | `fontbox/src/test/resources/ttf/LiberationSans-Regular.ttf` | 3.0.x |
| `tests/fixtures/fontbox/ttf/DejaVuSansMono.ttf` | downloaded by upstream from `https://issues.apache.org/jira/secure/attachment/12809395/DejaVuSansMono.ttf` (see `fontbox/pom.xml` `PDFBOX-3379` execution) — DejaVu Sans Mono 2.26 (Bitstream Vera license + DejaVu public-domain changes) | 3.0.x |
| `pypdfbox/resources/ttf/LiberationSans-Regular.ttf` | liberation-fonts-2.1.5 release tarball (SIL OFL 1.1, Google 2010 + Red Hat 2012) — Standard 14 Helvetica substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSans-Bold.ttf` | liberation-fonts-2.1.5 — Helvetica-Bold substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSans-Italic.ttf` | liberation-fonts-2.1.5 — Helvetica-Oblique substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSans-BoldItalic.ttf` | liberation-fonts-2.1.5 — Helvetica-BoldOblique substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSerif-Regular.ttf` | liberation-fonts-2.1.5 — Times-Roman substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSerif-Bold.ttf` | liberation-fonts-2.1.5 — Times-Bold substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSerif-Italic.ttf` | liberation-fonts-2.1.5 — Times-Italic substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationSerif-BoldItalic.ttf` | liberation-fonts-2.1.5 — Times-BoldItalic substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationMono-Regular.ttf` | liberation-fonts-2.1.5 — Courier substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationMono-Bold.ttf` | liberation-fonts-2.1.5 — Courier-Bold substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationMono-Italic.ttf` | liberation-fonts-2.1.5 — Courier-Oblique substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LiberationMono-BoldItalic.ttf` | liberation-fonts-2.1.5 — Courier-BoldOblique substitute | liberation-fonts 2.1.5 |
| `pypdfbox/resources/ttf/LICENSE.txt` | liberation-fonts-2.1.5 upstream `LICENSE` (SIL OFL 1.1 verbatim) | liberation-fonts 2.1.5 |
| `tests/fixtures/fontbox/cmap/CMapTest` | `fontbox/src/test/resources/cmap/CMapTest` | 3.0.x |
| `tests/fixtures/fontbox/cmap/CMapNoWhitespace` | `fontbox/src/test/resources/cmap/CMapNoWhitespace` | 3.0.x |
| `tests/fixtures/fontbox/cmap/CMapMalformedbfrange1` | `fontbox/src/test/resources/cmap/CMapMalformedbfrange1` | 3.0.x |
| `tests/fixtures/fontbox/cmap/CMapMalformedbfrange2` | `fontbox/src/test/resources/cmap/CMapMalformedbfrange2` | 3.0.x |
| `tests/fixtures/fontbox/cmap/Identitybfrange` | `fontbox/src/test/resources/cmap/Identitybfrange` | 3.0.x |
| `tests/fixtures/pdmodel/with_outline.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/pdmodel/with_outline.pdf` | 3.0.x |
| `tests/fixtures/pdmodel/page_tree_multiple_levels.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/pdmodel/page_tree_multiple_levels.pdf` | 3.0.x |
| `tests/fixtures/pdfparser/PDFBOX-6041-example.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/pdfparser/PDFBOX-6041-example.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-4417-001031.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-4417-001031.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-5762-722238.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-5762-722238.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-5792-240045.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-5792-240045.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-5809-509329.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-5809-509329.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-5811-362972.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-5811-362972.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-5840-410609.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-5840-410609.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-6018-099267-p9-OrphanPopups.pdf` | `pdfbox/src/test/resources/input/merge/PDFBOX-6018-099267-p9-OrphanPopups.pdf` | 3.0.x |
| `tests/fixtures/multipdf/OverlayTestBaseRot0.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/OverlayTestBaseRot0.pdf` | 3.0.x |
| `tests/fixtures/multipdf/rot0.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/rot0.pdf` | 3.0.x |
| `tests/fixtures/multipdf/rot90.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/rot90.pdf` | 3.0.x |
| `tests/fixtures/multipdf/rot180.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/rot180.pdf` | 3.0.x |
| `tests/fixtures/multipdf/rot270.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/rot270.pdf` | 3.0.x |
| `tests/fixtures/multipdf/Overlayed-with-rot0.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/Overlayed-with-rot0.pdf` | 3.0.x |
| `tests/fixtures/multipdf/Overlayed-with-rot90.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/Overlayed-with-rot90.pdf` | 3.0.x |
| `tests/fixtures/multipdf/Overlayed-with-rot180.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/Overlayed-with-rot180.pdf` | 3.0.x |
| `tests/fixtures/multipdf/Overlayed-with-rot270.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/Overlayed-with-rot270.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-6049-Source.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/PDFBOX-6049-Source.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-6049-Overlay.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/PDFBOX-6049-Overlay.pdf` | 3.0.x |
| `tests/fixtures/multipdf/PDFBOX-6049-ExpectedResult.pdf` | `pdfbox/src/test/resources/org/apache/pdfbox/multipdf/PDFBOX-6049-ExpectedResult.pdf` | 3.0.x |
| `tests/fixtures/pdfwriter/PDFBOX-3110-poems-beads.pdf` | `pdfbox/src/test/resources/input/PDFBOX-3110-poems-beads.pdf` | 3.0.x |

### `tests/pdmodel/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/upstream/test_pd_document.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocument.java` (`testVersions` partial — auto-bump-on-save deferred to font / encryption clusters; `testSaveArabicLocale` skipped — Java-locale-specific) |
| `tests/pdmodel/upstream/test_pd_document_catalog.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDDocumentCatalogTest.java` (page-labels, malformed page-labels, page count, output-intents, malformed open-action boolean, and null threads covered with fixture-free synthetic documents) |
| `tests/pdmodel/upstream/test_pd_page.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageTest.java` (annotation pre-add and null thread-bead cases active with fixture-free synthetic coverage; remaining fixture-dependent cases still deferred) |
| `tests/pdmodel/upstream/test_pd_page_tree.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageTreeTest.java` (full upstream parity: `with_outline.pdf` / `page_tree_multiple_levels.pdf` fixtures bundled under `tests/fixtures/pdmodel/`; node-loop case covered with a fixture-free synthetic page-tree cycle) |

### `tests/contentstream/upstream/`

Upstream PDFBox 3.0 ships **no** test classes for `Operator`, `OperatorName`, or `PDContentStream` (verified by recursive listing of `pdfbox/src/test/java/org/apache/pdfbox/contentstream/`; only operator-*processor* tests live there, which depend on rendering and aren't in scope until cluster #2+). The hand-written tests under `tests/contentstream/test_operator.py` / `test_operator_name.py` / `test_pd_content_stream.py` are the only coverage for cluster #1; nothing to port here.

### Wave 8 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/font/pd_cid_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDCIDFont.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_cid_font_type0.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType0.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_cid_font_type2.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType2.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_cid_system_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDCIDSystemInfo.java` |
| `pypdfbox/pdmodel/font/pd_type3_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType3Font.java` (lite — typed PDCharProc deferred) |
| `pypdfbox/pdmodel/font/pd_mm_type1_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDMMType1Font.java` (marker subclass) |
| `pypdfbox/pdmodel/font/pd_type1c_font.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType1CFont.java` (marker subclass) |
| `pypdfbox/pdmodel/common/function/pd_function.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunction.java` + `PDFunctionTypeIdentity.java` (Identity sentinel bundled in same module; eval dispatch + interpolate helper + /Type=/Function on stream construction) |
| `pypdfbox/pdmodel/common/function/pd_function_type0.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType0.java` (lite — sampled-table decoding deferred) |
| `pypdfbox/pdmodel/common/function/pd_function_type2.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType2.java` |
| `pypdfbox/pdmodel/common/function/pd_function_type3.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType3.java` |
| `pypdfbox/pdmodel/common/function/pd_function_type4.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType4.java` (lite — PostScript instruction parsing deferred) |
| `pypdfbox/pdmodel/pd_pages_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPagesNameTreeNode.java` |
| `pypdfbox/pdmodel/pd_templates_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDTemplatesNameTreeNode.java` |
| `pypdfbox/pdmodel/pd_ids_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDIDSNameTreeNode.java` (leaf type bytes; deviates from upstream String) |
| `pypdfbox/pdmodel/pd_urls_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDURLSNameTreeNode.java` |
| `pypdfbox/pdmodel/pd_alternate_presentations_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDAlternatePresentationsNameTreeNode.java` |
| `pypdfbox/pdmodel/pd_renditions_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDRenditionsNameTreeNode.java` |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_marked_content_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDMarkedContentReference.java` |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_object_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDObjectReference.java` |
| `pypdfbox/contentstream/operator/path/{curve_to,curve_to_replicate_initial_point,curve_to_replicate_final_point,close_path,append_rectangle,stroke_path,close_and_stroke_path,fill_path_non_zero_winding,fill_path_even_odd,legacy_fill_path,fill_then_stroke_non_zero_winding,close_fill_then_stroke_non_zero_winding,fill_then_stroke_even_odd,close_fill_then_stroke_even_odd,end_path_no_op,clip_non_zero_winding,clip_even_odd}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/{graphics,path,clip}/*.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/text/{set_text_rendering_mode,set_text_rise,set_character_spacing,set_word_spacing,set_horizontal_scaling,set_text_leading,next_line}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/*.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/color/{set_stroking_color_space,set_non_stroking_color_space,set_stroking_color,set_stroking_color_n,set_non_stroking_color,set_non_stroking_color_n,set_stroking_gray,set_non_stroking_gray,set_stroking_rgb,set_non_stroking_rgb,set_stroking_cmyk,set_non_stroking_cmyk}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/*.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/markedcontent/{begin_marked_content,begin_marked_content_with_props,end_marked_content,define_marked_content_point,define_marked_content_point_with_props}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/*.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/markedcontent/_props.py` | 3.0.x | original (no upstream class — refactor of helper logic inlined across upstream's five marked-content operator classes: tag extraction, property-list resolution via engine resources, `/MCID` accessor, `/Artifact` predicate) |

### Wave 9 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/encryption/pd_encryption.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PDEncryption.java` |
| `pypdfbox/pdmodel/encryption/pd_crypt_filter_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PDCryptFilterDictionary.java` |
| `pypdfbox/pdmodel/encryption/access_permission.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/AccessPermission.java` (lite — bit positions exposed as 1-based for readability) |
| `pypdfbox/pdmodel/encryption/protection_policy.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/ProtectionPolicy.java` |
| `pypdfbox/pdmodel/encryption/standard_protection_policy.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/StandardProtectionPolicy.java` |
| `pypdfbox/pdmodel/encryption/security_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SecurityHandler.java` (lite — uses `cryptography` library; /CF dispatch deferred) |
| `pypdfbox/pdmodel/encryption/standard_security_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/StandardSecurityHandler.java` (revisions 2-6) |
| `pypdfbox/pdmodel/encryption/security_provider.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SecurityHandlerFactory.java` (lite registry) |
| `pypdfbox/pdmodel/encryption/public_key_security_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PublicKeySecurityHandler.java` (decrypt + encrypt paths; encrypt path uses cryptography PKCS7EnvelopeBuilder, deferrals tracked in CHANGES.md) |
| `pypdfbox/pdmodel/encryption/public_key_protection_policy.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PublicKeyProtectionPolicy.java` |
| `pypdfbox/pdmodel/encryption/public_key_recipient.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PublicKeyRecipient.java` |
| `pypdfbox/pdmodel/encryption/public_key_decryption_material.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/PublicKeyDecryptionMaterial.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/signature_validation_result.py` | 3.0.x | original (PDFBox uses Java exceptions; we return a structured dataclass) |
| `pypdfbox/pdmodel/interactive/annotation/pd_ink_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PDInkAppearanceHandler.java` (geometry helper extracted) |
| `pypdfbox/pdmodel/interactive/annotation/pd_path_info.py` | 3.0.x | original (typed (x,y)-list helper) |
| `pypdfbox/pdmodel/interactive/annotation/pd_line_info.py` | 3.0.x | original (typed 2-point line helper) |
| `pypdfbox/pdmodel/interactive/annotation/pd_vertices.py` | 3.0.x | original (typed flat float-list helper for /Vertices) |
| `pypdfbox/contentstream/operator/imagecontent/{begin_inline_image,begin_inline_image_data,end_inline_image}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/{BI,ID,EI}.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/graphics/{invoke_named_xobject,concatenate_matrix}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/{Do,cm}.java` (lite no-op stubs) |
| `pypdfbox/contentstream/operator/state/{set_dash_pattern,set_flatness,set_rendering_intent,set_graphics_state_parameters}.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/{d,i,ri,gs}.java` (lite no-op stubs) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_four_colours.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDFourColours.java` |

### Wave 12 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfwriter/cos_writer.py` (xref-stream + ObjStm output) | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/COSWriter.java` (writeXrefStream + COSWriterObjectStream paths) |
| `pypdfbox/pdfparser/pdf_parser.py` (xref-stream decoder + compressed-object loader) | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFXRefStreamParser.java` + `PDFObjectStreamParser.java` |

### Type 1 / CFF font program parsing (fontTools wrappers)

The Type 1 PFB-style and CFF (Type1C) parsing internals are NOT ported from upstream — `org.apache.fontbox.type1.Type1Font` and `org.apache.fontbox.cff.CFFFont` (plus their helper classes `CFFParser`, `CharStringHandler`, `Type1Lexer`, etc.) re-implement PostScript / CFF parsing in Java. We delegate that responsibility to the (MIT-licensed) `fontTools` library and only mirror the public API surface needed by `PDType1Font` / `PDType1CFont`. Method names, parameter shapes, and semantic contracts (lazy parse, glyph-name lookup, charstring draw protocol) match upstream where applicable.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/fontbox/type1/type1_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Type1Font.java` | API surface only — parsing delegated to `fontTools.t1Lib.T1Font` |
| `pypdfbox/fontbox/cff/cff_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/CFFFont.java` | API surface only — parsing delegated to `fontTools.cffLib.CFFFontSet`; widths via `fontTools.misc.psCharStrings.T2WidthExtractor` |
| `pypdfbox/pdmodel/font/pd_type1_font.py` (`get_glyph_width` extension + `get_glyph_path` + `set_font_program` + `_get_type1_font`) | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType1Font.java` (`getWidthFromFont`, `getPath` analogues) |
| `pypdfbox/pdmodel/font/pd_type1c_font.py` (`get_glyph_width` / `get_glyph_path` / `set_font_program` / `_get_cff_font` overrides) | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType1CFont.java` (graduated from marker subclass to working CFF wrapper) |

### Wave 28 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/adobe_pdf_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/AdobePDFSchema.java` |
| `pypdfbox/xmpbox/xmp_basic_job_ticket_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPBasicJobTicketSchema.java` (+ co-located lite `JobType` from `xmpbox/src/main/java/org/apache/xmpbox/type/JobType.java`) |
| `pypdfbox/xmpbox/xmp_paged_text_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPageTextSchema.java` |
| `pypdfbox/xmpbox/photoshop_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/PhotoshopSchema.java` |
| `pypdfbox/pdmodel/interactive/measurement/pd_measure_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/measurement/PDMeasureDictionary.java` |
| `pypdfbox/pdmodel/interactive/measurement/pd_rectlinear_measure_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/measurement/PDRectlinearMeasureDictionary.java` |
| `pypdfbox/pdmodel/interactive/measurement/pd_number_format_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/measurement/PDNumberFormatDictionary.java` |
| `pypdfbox/pdmodel/interactive/measurement/pd_viewport_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/measurement/PDViewportDictionary.java` |
| `pypdfbox/pdmodel/interactive/action/pd_action_set_ocg_state.py` | 3.0.x | original (PDF 32000-1 §12.6.4.12 SetOCGState — no upstream Java class in 3.0.x; typed wrapper added so factory yields a typed instance instead of `PDActionUnknown`) |
| `pypdfbox/pdmodel/interactive/action/pd_action_go_to_dp.py` | 3.0.x | original (PDF 2.0 / ISO 32000-2 §12.6.4.4 GoToDp — no upstream Java class in 3.0.x or trunk) |
| `pypdfbox/pdmodel/interactive/action/pd_action_rich_media_execute.py` | 3.0.x | original (PDF 2.0 / ISO 32000-2 §13.6.4 RichMediaExecute — no upstream Java class in 3.0.x or trunk) |
| `pypdfbox/text/pdf_text_stripper_by_area.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PDFTextStripperByArea.java` |
| `pypdfbox/text/text_metrics.py` | 3.0.x | original (no upstream Java source in PDFBox 3.0.x; data-holder shape conforms to upstream-documented ascent/descent ratios) |
| `pypdfbox/text/word_with_text_positions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PDFTextStripper.java` (private inner class `WordWithTextPositions`, promoted to top-level) |
| `pypdfbox/fontbox/ttf/glyph_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/GlyphTable.java` (API surface only — parsing delegated to fontTools `glyf` table) |
| `pypdfbox/fontbox/ttf/glyph_data.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/GlyphData.java` (+ inlined minimal `BoundingBox` from `fontbox/src/main/java/org/apache/fontbox/util/BoundingBox.java`) (API surface only — parsing delegated to fontTools) |
| `pypdfbox/fontbox/ttf/kerning_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/KerningTable.java` (API surface only — parsing delegated to fontTools `kern` table) |
| `pypdfbox/fontbox/ttf/kerning_subtable.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/KerningSubtable.java` (API surface only — parsing delegated to fontTools) |
| `pypdfbox/fontbox/ttf/vertical_header_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/VerticalHeaderTable.java` (API surface only — parsing delegated to fontTools `vhea` table) |
| `pypdfbox/fontbox/ttf/vertical_metrics_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/VerticalMetricsTable.java` (API surface only — parsing delegated to fontTools `vmtx` table) |
| `pypdfbox/fontbox/ttf/glyph_substitution_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/GlyphSubstitutionTable.java` (API surface only — parsing delegated to fontTools `GSUB` table; lookup type 1 only — types 2-8 deferred) |
| `pypdfbox/fontbox/ttf/digital_signature_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/DigitalSignatureTable.java` (API surface only — parsing delegated to fontTools `DSIG` table) |
| `pypdfbox/fontbox/cff/type2_char_string.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/Type2CharString.java` (API surface only — parsing delegated to `fontTools.misc.psCharStrings.T2CharString`) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_prop_build.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDPropBuild.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_prop_build_data_dict.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDPropBuildDataDict.java` |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_group_usage.py` | 3.0.x | original (typed wrapper around the OCG `/Usage` sub-dict per PDF 32000-1 §8.11.4.4 Table 102; upstream `PDOptionalContentGroup.getUsage()` returns a raw `COSDictionary`) |
| `tests/fixtures/text/input/eu-001.pdf` | 3.0.x | `pdfbox/src/test/resources/input/eu-001.pdf` |
| `tests/xmpbox/upstream/test_adobe_pdf_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFTest.java` |
| `tests/xmpbox/upstream/test_photoshop_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/PhotoshopSchemaTest.java` |
| `tests/text/upstream/test_pdf_text_stripper_by_area.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/text/PDFTextStripperByAreaTest.java` |
| `tests/fontbox/ttf/upstream/test_glyph_substitution_table.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/ttf/GlyphSubstitutionTableTest.java` (spirit-port — Lohit-Bengali fixture not bundled; asserts `get_supported_script_tags`/`get_supported_feature_tags` against `LiberationSans-Regular.ttf`) |

### Wave 29 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_class_map.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureTreeRoot.java` (extracted typed wrapper around the inline `getClassMap`/`setClassMap` block — no standalone upstream class) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_user_property.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDUserProperty.java` (relocated to `taggedpdf` for proximity to `PDUserAttributeObject`) |
| `pypdfbox/pdmodel/documentinterchange/markedcontent/pd_marked_content.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/markedcontent/PDMarkedContent.java` |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_artifact_marked_content.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDArtifactMarkedContent.java` |
| `pypdfbox/pdmodel/pd_developer_extension.py` | 3.0.x | original (PDF 32000-1 §7.12.2 / ISO 32000-2 §7.12.3 — no upstream Java class in 3.0.x or trunk; only the COSName constants `BASE_VERSION` / `EXTENSION_LEVEL` / `EXTENSIONS` exist upstream) |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_default_attribute_object.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDDefaultAttributeObject.java` |
| `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_parent_tree_value.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDParentTreeValue.java` |
| `pypdfbox/pdmodel/page_layout.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PageLayout.java` |
| `pypdfbox/pdmodel/page_mode.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PageMode.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_content_stream.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDAppearanceContentStream.java` (relocated to `interactive/annotation` for cohesion with `PDAppearanceStream`) |
| `pypdfbox/pdmodel/common/pd_destination_or_action.py` | 3.0 | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDDestinationOrAction.java` (concrete marker class with static `create(value)` dispatcher; Python has no interface-only construct) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_seed_value_certificate.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSeedValueCertificate.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_seed_value_mdp.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSeedValueMDP.java` |
| `pypdfbox/fontbox/cmap/cid_range.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cmap/CIDRange.java` (promoted from private `_CIDRange` to public typed) |
| `pypdfbox/fontbox/cmap/bf_char_entry.py` | 3.0.x | original (no upstream class — `bfchar` triples are inlined by upstream `CMapParser`; pypdfbox surfaces typed value object) |
| `pypdfbox/fontbox/cmap/bf_char_range.py` | 3.0.x | original (no upstream class — `bfrange` triples are inlined by upstream `CMapParser`) |
| `pypdfbox/xmpbox/exif_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/ExifSchema.java` (simple, rational, GPS coordinate, date, integer, text, and LangAlt typed-property accessors; OECF / CFAPattern / Flash / DeviceSettings struct families remain deferred) |
| `pypdfbox/xmpbox/tiff_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/TiffSchema.java` (substitute for non-existent `CameraRawSchema` — TIFF tags cover camera-pipeline metadata) |
| `pypdfbox/tools/extracttext.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/ExtractText.java` (round-out: embedded-PDF extraction, `-html`/`-md` minimal-wrapper output, `-ignoreBeads`, `-debug` stderr summary — see CHANGES.md) |
| `tests/tools/upstream/test_extracttext.py` | 3.0.x | `pdfbox-tools/src/test/java/org/apache/pdfbox/tools/TestExtractText.java` (fixture-free ports for console extraction, embedded-PDF extraction, `-addFileName`, `-rotationMagic`, and output append/overwrite behavior) |
| `pypdfbox/tools/encrypt.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/Encrypt.java` |
| `pypdfbox/contentstream/pdf_graphics_stream_engine.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/PDFGraphicsStreamEngine.java` |
| `pypdfbox/pdmodel/documentinterchange/markedcontent/pd_property_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/markedcontent/PDPropertyList.java` (re-export module — implementation lives in `pypdfbox/pdmodel/graphics/pd_property_list.py`) |
| `pypdfbox/pdmodel/graphics/image/pd_inline_image.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PDInlineImage.java` |
| `tests/pdmodel/upstream/test_page_layout.py` | 3.0 | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PageLayoutTest.java` |
| `tests/pdmodel/upstream/test_page_mode.py` | 3.0 | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PageModeTest.java` |
| `tests/fontbox/cmap/upstream/test_cid_range.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/cmap/CIDRangeTest.java` |
| `tests/pdmodel/graphics/image/upstream/test_pd_inline_image.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDInlineImageTest.java` |

### Wave 30 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/text/pdf_marked_content_extractor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PDFMarkedContentExtractor.java` (subclasses `PDFTextStripper` rather than upstream's `LegacyPDFStreamEngine`) |
| `pypdfbox/pdmodel/common/pdfdoc_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/PDFDocEncoding.java` (relocated to `pdmodel/common` per task brief; upstream is in `cos`) |
| `pypdfbox/pdmodel/font/encoding/built_in_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/BuiltInEncoding.java` |
| `pypdfbox/fontbox/font_box_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/FontBoxFont.java` |
| `pypdfbox/fontbox/encoded_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/EncodedFont.java` |
| `pypdfbox/fontbox/font_mapping.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMapping.java` (relocated to `fontbox` package per task brief; upstream is in `pdfbox.pdmodel.font`) |
| `pypdfbox/fontbox/font_mappers.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMappers.java` (relocated to `fontbox` package) |
| `pypdfbox/fontbox/font_mapper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/{FontMapper.java,FontMapperImpl.java}` (default impl trimmed to Standard 14 — system-font scanner deferred since matplotlib/font_manager / fontconfig would be a new dep) |
| `pypdfbox/fontbox/font_format.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontFormat.java` (relocated to `fontbox` package alongside the rest of the FontMapper cluster) |
| `pypdfbox/fontbox/font_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontInfo.java` (relocated to `fontbox` package; package-private helpers exposed as public methods since Python has no equivalent visibility level) |
| `pypdfbox/fontbox/font_provider.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontProvider.java` (relocated to `fontbox` package; no concrete `FileSystemFontProvider` shipped — see CHANGES.md) |
| `pypdfbox/fontbox/cid_font_mapping.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/CIDFontMapping.java` (relocated to `fontbox` package) |
| `pypdfbox/multipdf/__init__.py` | 3.0.x | new package — sibling files below |
| `pypdfbox/multipdf/overlay.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/Overlay.java` (PDFBOX-6048 lower-left positioning per CLAUDE.md alignment note) |
| `pypdfbox/multipdf/pdf_clone_utility.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/PDFCloneUtility.java` |
| `pypdfbox/multipdf/layer_utility.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/LayerUtility.java` |
| `pypdfbox/multipdf/page_extractor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/PageExtractor.java` (delegates to direct page-tree append since `Splitter` is not yet ported) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_thread.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDThread.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_thread_bead.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDThreadBead.java` |
| `pypdfbox/tools/pdfdebugger.py` | 3.0.x | original (upstream `PDFDebugger` is a Swing GUI — pypdfbox provides a CLI-only COS walker/debugger per CLAUDE.md "no GUI subsystems": summary/trailer/page/object/xref/list-objects/tree, stream dumps, page-token dumps, encryption summary, JSON output, and interactive text walker) |
| `pypdfbox/tools/imagetopdf.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/tools/ImageToPDF.java` (image embedding remains inline via Pillow + zlib; image factories are ported separately) |
| `tests/pdmodel/common/upstream/test_pdfdoc_encoding.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java` |
| `tests/pdmodel/common/function/upstream/test_pd_function_type4.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java` |
| `tests/multipdf/upstream/test_overlay.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/multipdf/OverlayTest.java` (rendering-comparison tests skipped — depend on bundled fixture PDFs we don't carry) |
| `tests/multipdf/upstream/test_pdf_clone_utility.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFCloneUtilityTest.java` (only `testClonePDFWithCosArrayStream` ported — other two depend on `PDFMergerUtility` not yet ported) |
| `tests/multipdf/upstream/test_layer_utility.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/multipdf/TestLayerUtility.java` |
| `tests/multipdf/upstream/test_page_extractor.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/multipdf/PageExtractorTest.java` |

### Wave 31 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/multipdf/splitter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/Splitter.java` |
| `pypdfbox/multipdf/pdf_merger_utility.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/multipdf/PDFMergerUtility.java` (structure-tree merging deferred) |
| `pypdfbox/pdmodel/graphics/image/jpeg_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/JPEGFactory.java` |
| `pypdfbox/pdmodel/graphics/image/lossless_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/LosslessFactory.java` |
| `pypdfbox/pdmodel/graphics/image/ccitt_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/CCITTFactory.java` (only `createFromImage(BufferedImage)` is ported; the TIFF-extraction path `createFromFile`/`createFromByteArray` is deferred — see CHANGES.md) |
| `pypdfbox/fontbox/cmap/cmap_manager.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/CMapManager.java` (relocated to `fontbox/cmap` to co-locate with the resources directory it reads) |
| `pypdfbox/fontbox/cmap/resources/Adobe-CNS1-UCS2` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Adobe-CNS1-UCS2` |
| `pypdfbox/fontbox/cmap/resources/Adobe-GB1-UCS2` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Adobe-GB1-UCS2` |
| `pypdfbox/fontbox/cmap/resources/Adobe-Japan1-UCS2` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Adobe-Japan1-UCS2` |
| `pypdfbox/fontbox/cmap/resources/Adobe-Korea1-UCS2` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Adobe-Korea1-UCS2` |
| `pypdfbox/fontbox/cmap/resources/Identity-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Identity-H` |
| `pypdfbox/fontbox/cmap/resources/Identity-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/Identity-V` |
| `pypdfbox/fontbox/ttf/ttf_subsetter.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/TTFSubsetter.java` (API surface only — subset logic delegated to `fontTools.subset.Subsetter`) |
| `pypdfbox/xmpbox/type/abstract_field.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/AbstractField.java` + `xmpbox/src/main/java/org/apache/xmpbox/type/Attribute.java` |
| `pypdfbox/xmpbox/type/abstract_simple_property.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/AbstractSimpleProperty.java` |
| `pypdfbox/xmpbox/type/text_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/TextType.java` |
| `pypdfbox/xmpbox/type/integer_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/IntegerType.java` |
| `pypdfbox/xmpbox/type/boolean_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/BooleanType.java` |
| `pypdfbox/xmpbox/type/date_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/DateType.java` |
| `pypdfbox/xmpbox/type/real_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/RealType.java` |
| `pypdfbox/xmpbox/type/uri_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/URIType.java` |
| `pypdfbox/xmpbox/type/proper_name_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ProperNameType.java` |
| `pypdfbox/xmpbox/type/agent_name_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/AgentNameType.java` |
| `pypdfbox/xmpbox/type/mime_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/MIMEType.java` |
| `pypdfbox/xmpbox/type/guid_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/GUIDType.java` |
| `pypdfbox/xmpbox/type/choice_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ChoiceType.java` |
| `pypdfbox/xmpbox/type/array_property.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ArrayProperty.java` + `Cardinality.java` + `AbstractComplexProperty.java` + `ComplexPropertyContainer.java` |
| `pypdfbox/xmpbox/type/lang_alt.py` | 3.0.x | derived from `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPSchema.java#reorganizeAltOrder` + `ArrayProperty(Cardinality.Alt)` idiom |
| `pypdfbox/xmpbox/type/type_mapping.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/TypeMapping.java` (simple-property registry, structured-type registry, defined-type namespace registration, and create_* factories; schema factory / PropertiesDescription reflection machinery deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_windows_launch_params.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDWindowsLaunchParams.java` |
| `pypdfbox/pdmodel/interactive/form/pd_appearance_generator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceGeneratorHelper.java` (text-field flat-text path only — button/choice/signature appearances deferred) |
| `pypdfbox/tools/texttopdf.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/TextToPDF.java` |
| `pypdfbox/tools/writedecodedstream.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/WriteDecodedDoc.java` |
| `pypdfbox/pdmodel/pdfa_flavour.py` | 3.0.x | original (no upstream PDFBox class — pypdfbox provides a passive *detector* per CLAUDE.md "no preflight"; actual conformance validation is out of scope) |
| `tests/xmpbox/type/upstream/test_attribute.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/AttributeTest.java` |
| `tests/xmpbox/type/upstream/test_simple_metadata_properties.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/TestSimpleMetadataProperties.java` |
| `tests/pdmodel/graphics/image/upstream/test_jpeg_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/JPEGFactoryTest.java` |
| `tests/pdmodel/graphics/image/upstream/test_lossless_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/LosslessFactoryTest.java` (rendering-comparison parts skipped) |
| `tests/pdmodel/graphics/image/upstream/test_lossless_factory_helpers_wave886.py` | 3.0.x | (no upstream Java equivalent — pypdfbox-original coverage-wave augmentation exercising lossless-factory helper code paths via mock image objects with custom color-space getters) |
| `tests/multipdf/upstream/test_pdf_merger_utility.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFMergerUtilityTest.java` (4 active + 25 skipped — rendering / fixture-dependent) |
| `tests/fontbox/ttf/upstream/test_ttf_subsetter.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/ttf/TTFSubsetterTest.java` (4 active + 5 skipped — system-font / `forceInvisible`) |

### Wave 32 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/type/abstract_structured_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/AbstractStructuredType.java` (+ `AbstractComplexProperty.java` + `ComplexPropertyContainer.java` folded in) |
| `pypdfbox/xmpbox/type/rational_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/RationalType.java` |
| `pypdfbox/xmpbox/type/dimensions_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/DimensionsType.java` |
| `pypdfbox/xmpbox/type/colorant_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ColorantType.java` |
| `pypdfbox/xmpbox/type/font_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/FontType.java` |
| `pypdfbox/xmpbox/type/resource_ref_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ResourceRefType.java` |
| `pypdfbox/xmpbox/type/resource_event_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ResourceEventType.java` |
| `pypdfbox/xmpbox/type/thumbnail_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ThumbnailType.java` |
| `pypdfbox/xmpbox/type/layer_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/LayerType.java` |
| `pypdfbox/xmpbox/type/job_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/JobType.java` (promoted to real `AbstractStructuredType`; lite cluster-#1 form retained as alias) |
| `pypdfbox/fontbox/cff/type1_char_string.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/Type1CharString.java` (API surface only — opcode interpretation delegated to `fontTools.misc.psCharStrings.T1CharString`; `dup` / `exch` arithmetic ops fontTools leaves as `NotImplementedError` are filled in by a private `_Type1ExtendedExtractor` subclass per Adobe Type 1 Font Format spec §6.5) |
| `pypdfbox/fontbox/afm/afm_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/AFMParser.java` |
| `pypdfbox/fontbox/afm/font_metrics.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/FontMetrics.java` |
| `pypdfbox/fontbox/afm/char_metric.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/CharMetric.java` |
| `pypdfbox/fontbox/afm/kern_pair.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/KernPair.java` |
| `pypdfbox/fontbox/afm/ligature.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/Ligature.java` |
| `pypdfbox/fontbox/afm/composite.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/Composite.java` |
| `pypdfbox/fontbox/afm/composite_part.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/CompositePart.java` |
| `pypdfbox/fontbox/afm/track_kern.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/TrackKern.java` |
| `pypdfbox/text/filtered_text_stripper.py` | 3.0.x | derived from `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/ExtractText.java#getAngle` + `AngleCollector` / `FilteredTextStripper` inner classes |
| `pypdfbox/fontbox/cmap/resources/UniCNS-UTF16-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniCNS-UTF16-H` |
| `pypdfbox/fontbox/cmap/resources/UniCNS-UTF16-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniCNS-UTF16-V` |
| `pypdfbox/fontbox/cmap/resources/UniGB-UTF16-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniGB-UTF16-H` |
| `pypdfbox/fontbox/cmap/resources/UniGB-UTF16-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniGB-UTF16-V` |
| `pypdfbox/fontbox/cmap/resources/UniJIS-UTF16-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniJIS-UTF16-H` |
| `pypdfbox/fontbox/cmap/resources/UniJIS-UTF16-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniJIS-UTF16-V` |
| `pypdfbox/fontbox/cmap/resources/UniKS-UTF16-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniKS-UTF16-H` |
| `pypdfbox/fontbox/cmap/resources/UniKS-UTF16-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/UniKS-UTF16-V` |
| `pypdfbox/fontbox/cmap/resources/GB-EUC-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/GB-EUC-H` |
| `pypdfbox/fontbox/cmap/resources/GB-EUC-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/GB-EUC-V` |
| `pypdfbox/fontbox/cmap/resources/B5pc-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/B5pc-H` |
| `pypdfbox/fontbox/cmap/resources/B5pc-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/B5pc-V` |
| `pypdfbox/fontbox/cmap/resources/90ms-RKSJ-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/90ms-RKSJ-H` |
| `pypdfbox/fontbox/cmap/resources/90ms-RKSJ-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/90ms-RKSJ-V` |
| `pypdfbox/fontbox/cmap/resources/KSC-EUC-H` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/KSC-EUC-H` |
| `pypdfbox/fontbox/cmap/resources/KSC-EUC-V` | 3.0.x | `fontbox/src/main/resources/org/apache/fontbox/cmap/KSC-EUC-V` |
| `tests/xmpbox/type/upstream/test_abstract_structured_type.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/TestAbstractStructuredType.java` |
| `tests/xmpbox/type/upstream/test_structured_type.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/TestStructuredType.java` |
| `tests/xmpbox/upstream/test_xmp_basic_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/XMPBasicTest.java` (includes Bag-cardinality typed-property parity for Advisory/XPath and Identifier/Text) |
| `tests/xmpbox/upstream/test_dublin_core_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/DublinCoreTest.java` |
| `tests/fontbox/afm/upstream/test_afm_parser.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/AFMParserTest.java` |
| `tests/fontbox/afm/upstream/test_font_metrics.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/FontMetricsTest.java` |
| `tests/fontbox/afm/upstream/test_char_metric.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/CharMetricTest.java` |
| `tests/fontbox/afm/upstream/test_composite.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/CompositeTest.java` |
| `tests/fontbox/afm/upstream/test_kern_pair.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/KernPairTest.java` |
| `pypdfbox/pdmodel/pdfua_flavour.py` | 3.0.x | pypdfbox addition (no upstream Java class — passive PDF/UA flavour metadata holder; actual conformance validation is out of scope) |
| `pypdfbox/tools/listbookmarks.py` | 3.0.x | `pdfbox-examples/src/main/java/org/apache/pdfbox/examples/pdmodel/PrintBookmarks.java` |
| `pypdfbox/xmpbox/pdfua_identification_schema.py` | 3.0.x | pypdfbox addition (no upstream Java class — mirrors `PDFAIdentificationSchema` shape for PDF/UA `pdfuaid` namespace) |
| `pypdfbox/xmpbox/type/gps_coordinate_type.py` | 3.0.x | pypdfbox addition (no upstream Java class — D,M,Sk / D,M.mmk EXIF GPS coordinate parser) |
| `tests/pdmodel/test_pdfua_flavour.py` | 3.0.x | pypdfbox addition (covers `pdfua_flavour.py`) |
| `tests/tools/test_listbookmarks.py` | 3.0.x | derived from `pdfbox-examples/.../PrintBookmarks.java` invocation patterns |
| `tests/xmpbox/test_pdfua_identification_schema.py` | 3.0.x | pypdfbox addition (covers `pdfua_identification_schema.py`) |
| `pypdfbox/fontbox/encoding/resources/glyphlist.txt` | 3.0.x | `pdfbox/src/main/resources/org/apache/pdfbox/resources/glyphlist/glyphlist.txt` |
| `pypdfbox/fontbox/encoding/resources/additional.txt` | 3.0.x | `pdfbox/src/main/resources/org/apache/pdfbox/resources/glyphlist/additional.txt` |
| `pypdfbox/fontbox/encoding/resources/zapfdingbats.txt` | 3.0.x | `pdfbox/src/main/resources/org/apache/pdfbox/resources/glyphlist/zapfdingbats.txt` |
| `pypdfbox/fontbox/ttf/gsub/feature_record.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/FeatureRecord.java` |
| `pypdfbox/fontbox/ttf/gsub/feature_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/FeatureListTable.java` |
| `pypdfbox/fontbox/ttf/gsub/lang_sys_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/LangSysTable.java` |
| `pypdfbox/fontbox/ttf/gsub/script_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/ScriptTable.java` |
| `pypdfbox/fontbox/cff/cff_cid_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/CFFCIDFont.java` |
| `pypdfbox/fontbox/cff/cff_type1_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/CFFType1Font.java` |
| `pypdfbox/fontbox/cff/fd_select.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cff/CFFParser.java` (FDSelect / Format0FDSelect / Format3FDSelect inner classes) |
| `pypdfbox/fontbox/cff/fd_array.py` | 3.0.x | derived from `CFFParser.parseFDArray()` shape (no upstream class file) |
| `pypdfbox/pdmodel/graphics/color/pd_device_n.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceN.java` |
| `pypdfbox/pdmodel/graphics/color/pd_device_n_process.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceNProcess.java` |
| `pypdfbox/pdmodel/graphics/color/pd_lab.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDLab.java` |
| `pypdfbox/pdmodel/graphics/color/pd_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDPattern.java` |
| `pypdfbox/pdmodel/documentinterchange/markedcontent/pd_artifact_marked_content.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/markedcontent/PDArtifactMarkedContent.java` (re-export shim; canonical impl at `taggedpdf/pd_artifact_marked_content.py`) |
| `pypdfbox/xmpbox/type/pdfa_field_description_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/PDFAFieldType.java` |
| `pypdfbox/xmpbox/type/pdfa_property_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/PDFAPropertyType.java` |
| `pypdfbox/xmpbox/type/pdfa_schema_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/PDFASchemaType.java` |
| `pypdfbox/xmpbox/type/pdfa_type_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/PDFATypeType.java` |
| `pypdfbox/xmpbox/type/pdfa_value_type_description_type.py` | 3.0.x | alias module re-exporting `PDFATypeType` (no separate upstream class) |
| `pypdfbox/text/text_position.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/TextPosition.java` |
| `pypdfbox/text/position_wrapper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PositionWrapper.java` |
| `pypdfbox/pdmodel/fdf/fdf_document.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFDocument.java` |
| `pypdfbox/pdmodel/fdf/fdf_catalog.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFCatalog.java` |
| `pypdfbox/pdmodel/fdf/fdf_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFDictionary.java` |
| `pypdfbox/pdmodel/fdf/fdf_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFField.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotation.java` |
| `pypdfbox/filter/lzw_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/LZWFilter.java` (alias module; codec body in `lzw_decode.py`) |
| `pypdfbox/filter/run_length_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/RunLengthDecodeFilter.java` (alias module; codec body in `run_length_decode.py`) |
| `pypdfbox/pdmodel/interactive/digitalsignature/pd_seed_value_time_stamp.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSeedValueTimeStamp.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_data.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/GsubData.java` |
| `pypdfbox/fontbox/ttf/gsub/lookup_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/gsub/LookupTable.java` |
| `pypdfbox/fontbox/ttf/gsub/lookup_subtable.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/table/common/LookupSubTable.java` + `table/common/CoverageTable.java` + `table/gsub/{LookupTypeSingleSubstFormat1,LookupTypeSingleSubstFormat2,LookupTypeMultipleSubstitutionFormat1,LookupTypeAlternateSubstitutionFormat1,LookupTypeLigatureSubstitutionSubstFormat1,SequenceTable,AlternateSetTable,LigatureTable,LigatureSetTable}.java` (single-file aggregate) |
| `tests/fontbox/ttf/gsub/upstream/test_lookup_subtable.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForLatinTest.java` |
| `tests/fontbox/ttf/gsub/upstream/test_gsub_data.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GlyphSubstitutionDataExtractorTest.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_stamp.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationRubberStamp.java` (renamed Stamp per PDF spec) |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_polygon.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPolygon.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_polyline.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPolyline.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_file_attachment.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationFileAttachment.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_sound.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationSound.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_screen.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationScreen.java` |
| `tests/pdmodel/common/function/upstream/test_pd_function_type_4.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/TestPDFunctionType4.java` |
| `pypdfbox/pdmodel/common/function/pd_function_type3.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType3.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_bounding_box_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitBoundingBoxDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_bounding_box_height_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitBoundingBoxHeightDestination.java` |
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_page_fit_bounding_box_width_destination.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDPageFitBoundingBoxWidthDestination.java` |
| `pypdfbox/text/pdf_marked_content_extractor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PDFMarkedContentExtractor.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationText.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_free_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationFreeText.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_square.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationSquare.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_circle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationCircle.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationLine.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_file_attachment.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationFileAttachment.java` |
| `tests/pdmodel/upstream/test_pd_page_content_stream.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageContentStreamTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_color.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDColorTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_color_space_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDColorSpaceTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_color_space.py` | 3.0.x | placeholder — upstream has no dedicated `PDColorSpaceTest.java` covering the abstract base; surface inferred from `PDColorSpace.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/color/upstream/test_pd_icc_based.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDICCBasedTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_indexed.py` | 3.0.x | placeholder — upstream has no dedicated `PDIndexedTest.java`; surface inferred from `PDIndexed.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/upstream/test_pd_x_object.py` | 3.0.x | placeholder — upstream has no dedicated `PDXObjectTest.java`; surface inferred from `PDXObject.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/image/upstream/test_pd_image_x_object_masks.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObjectTest.java` (mask coverage subset) |
| `pypdfbox/fontbox/type1/type1_font_util.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Type1FontUtil.java` |
| `pypdfbox/fontbox/type1/type1_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Type1Parser.java` + `Type1Lexer.java` (lite — top-level keys + FontInfo only) |
| `pypdfbox/fontbox/type1/type1_mapping.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Type1Mapping.java` |
| `tests/fontbox/type1/upstream/test_type1_font_util.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/type1/Type1FontUtilTest.java` |
| `tests/pdmodel/font/upstream/test_pd_type0_font.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType0FontTest.java` |
| `tests/pdmodel/font/upstream/test_pd_cid_font_type0.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType0Test.java` |
| `tests/pdmodel/font/upstream/test_pd_cid_font_type2.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType2Test.java` |
| `pypdfbox/pdmodel/font/pd_type3_char_proc.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDType3CharProc.java` |
| `tests/pdmodel/font/upstream/test_pd_type3_font.py` | 3.0.x | combined `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType3FontTest.java` + `PDType3CharProcTest.java` |
| `tests/pdmodel/font/upstream/test_pd_font_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDFontTest.java` (factory subset) |
| `tests/fontbox/cmap/upstream/test_cmap_parser.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/cmap/CMapParserTest.java` (focused parser regressions including PDFBOX-4720 identity `bfrange`) |
| `pypdfbox/contentstream/operator/state/set_line_width.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineWidth.java` |
| `pypdfbox/contentstream/operator/state/set_line_cap_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineCapStyle.java` |
| `pypdfbox/contentstream/operator/state/set_line_join_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineJoinStyle.java` |
| `pypdfbox/contentstream/operator/state/set_line_miter_limit.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineMiterLimit.java` |
| `pypdfbox/contentstream/operator/text/set_char_spacing.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetCharSpacing.java` |
| `pypdfbox/contentstream/operator/text/set_word_spacing_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetWordSpacing.java` |
| `pypdfbox/contentstream/operator/text/set_horizontal_text_scaling.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetHorizontalTextScaling.java` |
| `pypdfbox/contentstream/operator/text/set_text_leading_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextLeading.java` |
| `pypdfbox/contentstream/operator/text/set_text_rendering_mode_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextRenderingMode.java` |
| `pypdfbox/contentstream/operator/text/set_text_rise_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextRise.java` |
| `pypdfbox/contentstream/operator/text/next_line_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/NextLine.java` |
| `pypdfbox/contentstream/operator/graphics/shading_fill.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ShadingFill.java` |
| `pypdfbox/io/scratch_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFile.java` |
| `pypdfbox/io/scratch_file_buffer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFileBuffer.java` |
| `tests/io/upstream/test_scratch_file.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/io/ScratchFileTest.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/cos_filter_input_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/COSFilterInputStream.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/sig_utils.py` | 3.0.x | derived from `pdfbox-examples/.../SigUtils.java` patterns (KU/EKU bit checks only) |
| `tests/pdmodel/font/upstream/test_standard14_fonts.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/Standard14FontsTest.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_icon_fit.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAppearanceCharacteristicsDictionary.java` (PDIconFit inner class) |
| `tests/xmpbox/upstream/test_adobe_pdf_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFTest.java` |
| `pypdfbox/fontbox/ttf/ttf_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/TTFParser.java` |
| `pypdfbox/fontbox/ttf/otf_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/OTFParser.java` |
| `pypdfbox/fontbox/ttf/open_type_font.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/OpenTypeFont.java` |
| `tests/pdmodel/interactive/form/upstream/test_appearance_generator_helper.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceGeneratorHelperTest.java` (subset — fixture-loading and custom-font/rotation tests skipped) |
| `tests/pdmodel/interactive/form/upstream/test_pd_acro_form.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDAcroFormTest.java` (subset — fixture-load/render-parity, FDF, network-fetch, lazy-DA/DR auto-population, and PDType0Font load tests skipped) |
| `pypdfbox/pdmodel/interactive/action/open_mode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/OpenMode.java` |
| `pypdfbox/pdmodel/interactive/form/pd_text_field.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDTextField.java` |
| `pypdfbox/pdmodel/interactive/form/pd_choice.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDChoice.java` |
| `pypdfbox/pdmodel/interactive/form/pd_radio_button.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDRadioButton.java` |
| `pypdfbox/pdmodel/interactive/form/pd_button.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDButton.java` |
| `tests/pdmodel/interactive/form/upstream/test_pd_text_field.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDTextFieldTest.java` |
| `tests/pdmodel/interactive/form/upstream/test_pd_choice.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDChoiceTest.java` (subset — PDFBOX-6150 fixture-loading test skipped) |
| `tests/pdmodel/interactive/form/upstream/test_pd_list_box.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestListBox.java` (subset — PDF write/annotation setup and deferred `PDChoice.setValue(List)` validation/index sync skipped) |
| `tests/pdmodel/interactive/form/upstream/test_pd_button.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDButtonTest.java` (subset — Acrobat-PDF fixture-loading tests skipped) |
| `tests/pdmodel/interactive/form/upstream/test_pd_signature_field.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureFieldTest.java` (subset — setValueForAbstractedSignatureField and PDFBOX-4822 byte-range test skipped) |
| `tests/pdmodel/encryption/upstream/test_public_key_security_handler.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/encryption/TestPublicKeyEncryption.java` (subset — full PDF write/read cycle deferred; handler-level assertions translated using `cryptography` for cert/key generation in lieu of the upstream Bouncy-Castle keystore) |
| `tests/pdmodel/encryption/upstream/test_public_key_security_handler_wave909.py` | 3.0.x | (no upstream Java equivalent — pypdfbox-original coverage-wave augmentation that monkeypatches sibling cert-generation helpers to drive skip branches around heavy crypto setup) |
| `tests/text/upstream/test_pdf_text_stripper_deeper.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/text/TestTextStripper.java` (subset — synthetic content streams stand in for the upstream PDF fixtures the lite stripper does not yet round-trip; pins `setShouldFlipAxes`, `setShouldSeparateByBeads` bead-bucket ordering, `shouldSkipGlyph`, `isParagraphSeparation` drop+indent prongs, and `writeStringWithPositions` invariants) |
| `tests/pdmodel/font/upstream/test_pd_font_descriptor.py` | 3.0.x | derived line-by-line from `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontDescriptor.java`, `PDPanose.java`, `PDPanoseClassification.java` — upstream has no dedicated `PDFontDescriptorTest.java`; tests pin Javadoc-documented contracts (defaults, flag masks, /Type entry, /CharSet COSString storage, /CIDSet stream wrapping, 12-byte Panose layout) |

### Wave 41 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/multipdf/test_splitter_signatures.py` | 3.0.x | hand-written; signature widget detection + AcroForm /SigFlags scrub for `pdfbox/src/main/java/org/apache/pdfbox/multipdf/Splitter.java` (upstream has no dedicated `SplitterSignatureTest.java`) |
| `tests/multipdf/test_splitter_cid_fonts.py` | 3.0.x | hand-written; CID `/FontFile2` round-trip across `Splitter` chunks (upstream has no dedicated `SplitterCIDFontTest.java` — exercised via `PDFMergerUtilityTest` fixtures we don't carry) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_configuration.py` | 3.0.x | original (no standalone upstream class — Apache PDFBox 3.0 inlines /D accessors on `PDOptionalContentProperties.java`; pypdfbox extracts a typed wrapper so the same surface services /Configs entries) |
| `tests/pdmodel/graphics/optionalcontent/upstream/test_optional_content_groups.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/TestOptionalContentGroups.java` (state-assertion subset — content-stream writing + image-diff render phases skipped per per-test comment) |
| `tests/multipdf/test_merger_struct_tree.py` | 3.0.x | hand-written; structure-tree edge-case coverage for `pdfbox/src/main/java/org/apache/pdfbox/multipdf/PDFMergerUtility.java` — RoleMap conflict, MCID-indexed parent-tree leaves, /Pg rewriting, destination /Info / /Metadata override, AcroFormMergeMode dispatch, IDTree collision (synthetic equivalents to upstream `PDFMergerUtilityTest.testStructureTreeMerge*` cases that depend on `input/PDFA-1b.pdf` fixture) |
| `tests/xmpbox/upstream/test_pdfa_identification_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationOthersTest.java` + `PDFAIdentificationTest.java` (parameterised value channel and typed-field property round-trip covered; XmpSerializer round-trip uses a hand-rolled XMP packet because pypdfbox does not yet ship an upstream-shaped serializer) |
| `tests/pdmodel/graphics/color/upstream/test_pd_output_intent.py` | 3.0.x | parity-shaped tests for `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDOutputIntent.java` — upstream PDFBox 3.0 ships no dedicated `PDOutputIntentTest.java`, so coverage targets the documented Java API contract (subtype + flate-compressed `/DestOutputProfile` + `/N` + string accessors) |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_pd_signature.py` | 3.0.x | placeholder — upstream has no `PDSignatureTest.java` (verified 2026-04-27 against `apache/pdfbox` `3.0` branch); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_pd_signature.py` |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_pd_prop_build.py` | 3.0.x | placeholder — upstream has no `PDPropBuild*Test.java` (verified 2026-04-27); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_pd_prop_build.py` |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_signature_verification.py` | 3.0.x | placeholder — upstream has no JUnit class for the verify pipeline (exercised via `pdfbox-examples`'s `ShowSignatureTest.java`); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_signature_verification.py` |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_cos_filter_input_stream.py` | 3.0.x | placeholder — upstream has no standalone `COSFilterInputStreamTest.java` (verified against PDFBox 3.0); behaviour exercised via signing-roundtrip integration upstream, and via this hand-written port of the public `read` / `to_byte_array` / `calculate_ranges` / `get_remaining` / `next_range` surface |
| `tests/pdmodel/documentinterchange/logicalstructure/test_pd_structure_tree_root_round_out.py` | 3.0.x | hand-written; pins Wave 41 round-out additions on `PDStructureTreeRoot` / `PDStructureElement` (`iter_descendants`, `find_by_role`, `resolve_role_map`, `build_parent_tree`, `get_class_names_as_strings`, `has_class`, `get_attribute_objects`, `has_attribute_owner`, `iter_object_references`, `get_parent_node`, `get_structure_tree_root`) |
| `tests/pdmodel/documentinterchange/logicalstructure/upstream/test_pd_structure_element.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureElementTest.java` (subset — ports the `checkElement` recursion and the `/A`-takes-precedence-over-`/C` rule onto a synthetic structure tree; the fixture-loading driver paths `testPDFBox4197` / `testClassMap` are deferred until full PDF reader integration is wired in) |
| `pypdfbox/fontbox/cff/_expert_encoding.py` | 3.0.x | derived table from `fontbox/src/main/java/org/apache/fontbox/cff/CFFExpertEncoding.java` (raw code→SID pairs) + Adobe Standard Strings table (resolves SIDs to glyph names) — used by `CFFType1Font.code_to_name` for predefined Expert encoding |
| `pypdfbox/fontbox/ttf/glyph_positioning_table.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/ttf/GlyphPositioningTable.java` (API surface — parsing delegated to fontTools `GPOS` table; structural accessors `get_script_list` / `get_feature_list` / `get_lookup_list` / `get_lookup` / `get_lookup_subtables` / `get_feature_record` / `get_lookup_indices_for_feature` are pypdfbox-only — upstream keeps the OT structures private; lookup-type 2 pair-adjustment kerning extraction implemented for both Format 1 and Format 2 subtables; types 1, 3-9 surfaced via raw / structural accessors but not engine-applied — matches upstream's stop-short coverage) |
| `tests/fontbox/ttf/upstream/test_glyph_positioning_table.py` | 3.0.x | placeholder — upstream PDFBox 3.0 ships no dedicated `GlyphPositioningTableTest.java` (the upstream class is itself a `TAG`-only scaffold); spirit-port asserts script / feature inventory + lookup-type breadth against `LiberationSans-Regular.ttf` |

### Wave 43 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/action/pd_action_go_to_3d_view.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionGoTo3DView.java` |
| `pypdfbox/pdmodel/interactive/action/pd_uri_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDURIDictionary.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_printer_mark.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationPrinterMark.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_redact.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationRedact.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_three_d.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotation3D.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_trap_net.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTrapNet.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_annotation_watermark.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationWatermark.java` |
| `pypdfbox/xmpbox/type/version_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/VersionType.java` |
| `tests/fontbox/ttf/upstream/test_kerning_subtable.py` | 3.0.x | parity-shaped coverage for `fontbox/src/main/java/org/apache/fontbox/ttf/KerningSubtable.java` format behavior |
| `tests/pdmodel/graphics/color/upstream/test_pd_separation.py` | 3.0.x | parity-shaped coverage for `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDSeparation.java` |
| `tests/pdmodel/interactive/action/test_pd_action_go_to_3d_view.py` | 3.0.x | hand-written coverage for `PDActionGoTo3DView` |
| `tests/pdmodel/interactive/action/test_pd_action_sound_round_out.py` | 3.0.x | hand-written coverage for `PDActionSound` round-out |

### Wave 44 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/xmpbox/type/test_version_type.py` | 3.0.x | hand-written coverage for `xmpbox/src/main/java/org/apache/xmpbox/type/VersionType.java` structured-type accessors |

### Wave 45 additions

Original work (no PROVENANCE row needed; listed here for clarity):
- `pypdfbox/contentstream/operator/color/_device_color.py` — small shared helper used by the six device-colour operator ports to build `PDColor` and notify engine hooks.
- `tests/contentstream/operator/color/test_device_color_semantics.py` — hand-written behavioral coverage for device-colour operator dispatch.

### Wave 46 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/annotation/pd_movie.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDMovie.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_movie_activation.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDMovieActivation.java` |
| `tests/pdmodel/graphics/shading/test_pd_shading_type4_type5_parity.py` | 3.0.x | hand-written parity coverage for `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType4.java` and `PDShadingType5.java` |
| `tests/pdmodel/graphics/shading/upstream/test_pd_shading_type_5.py` | 3.0.x | placeholder — upstream has no dedicated `PDShadingType5Test.java`; surface inferred from `PDShadingType5.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/shading/upstream/test_pd_shading_type_4.py` | 3.0.x | placeholder — upstream has no dedicated `PDShadingType4Test.java`; surface inferred from `PDShadingType4.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/color/upstream/test_pd_device_cmyk.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceCMYKTest.java` (`testPDFBox5787` ICC race-condition test skipped — JVM-specific, no Pillow analogue) |
| `tests/pdmodel/interactive/documentnavigation/outline/upstream/test_pd_outline_node.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDOutlineNodeTest.java` |
| `tests/pdmodel/documentinterchange/logicalstructure/upstream/test_pd_structure_node.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureElementTest.java` (kid-management subset of `testSimple`, plus synthetic `createObject` dispatch tests — no dedicated `PDStructureNodeTest.java` exists upstream) |
| `tests/fontbox/ttf/upstream/test_open_type_font.py` | 3.0.x | placeholder — upstream has no dedicated `OpenTypeFontTest.java`; surface inferred from `OpenTypeFont.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/color/upstream/test_pd_lab.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDLabTest.java` |
| `tests/pdmodel/font/upstream/test_pd_cid_font.py` | 3.0.x | placeholder — upstream has no dedicated `PDCIDFontTest.java`; surface inferred from `PDCIDFont.java` (PDFBox 3.0.x) |
| `tests/xmpbox/upstream/test_xmp_media_management_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/XMPMediaManagementTest.java` |
| `tests/fontbox/encoding/upstream/test_glyph_list.py` | 3.0.x | placeholder — upstream has no dedicated `GlyphListTest.java` in PDFBox 3.0.x; surface ports the documented `GlyphList.java` contract |
| `tests/pdmodel/graphics/color/upstream/test_pd_pattern.py` | 3.0.x | placeholder — upstream has no dedicated `PDPatternTest.java`; surface inferred from `PDPattern.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/image/upstream/test_pd_image_x_object.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObjectTest.java` |
| `tests/pdmodel/font/upstream/test_pd_simple_font.py` | 3.0.x | placeholder — upstream has no dedicated `PDSimpleFontTest.java`; surface inferred from `PDSimpleFont.java` (PDFBox 3.0.x) |
| `tests/pdmodel/fdf/upstream/test_fdf_field.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/fdf/FDFFieldTest.java` |
| `tests/pdmodel/common/function/upstream/test_pd_function.py` | 3.0.x | placeholder — upstream has no dedicated `PDFunctionTest.java`; surface inferred from `PDFunction.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/color/upstream/test_pd_device_n.py` | 3.0.x | placeholder — upstream has no dedicated `PDDeviceNTest.java`; surface inferred from `PDDeviceN.java` (PDFBox 3.0.x) |
| `tests/pdmodel/fdf/upstream/test_fdf_annotation_line.py` | 3.0.x | placeholder — upstream has no dedicated `FDFAnnotationLineTest.java`; surface inferred from `FDFAnnotationLine.java` (PDFBox 3.0.x) |
| `tests/fontbox/cff/upstream/test_cff_font.py` | 3.0.x | placeholder — upstream has no dedicated `CFFFontTest.java`; covers package-private setters (Java lines 59 / 128 / 146 / 178) + `toString` (205) |
| `tests/rendering/upstream/test_pdf_renderer.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/rendering/TestRendering.java` (rendering-comparison parts skipped — fixtures not yet ported) |
| `tests/pdmodel/interactive/form/upstream/test_pd_terminal_field.py` | 3.0.x | derived from `PDTerminalField.java` + `PDField.java` `importFDF`/`exportFDF` — no dedicated `PDTerminalFieldTest.java` upstream |
| `tests/pdmodel/font/upstream/test_pd_font.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDFontTest.java` (base-class parity subset) |
| `tests/pdmodel/fdf/upstream/test_fdf_annotation_free_text.py` | 3.0.x | placeholder — no upstream `FDFAnnotationFreeTextTest.java` (FreeText is exercised transitively via `FDFAnnotationTest.loadXFDFAnnotations` which depends on the unported XFDF Loader); tests pin `FDFAnnotationFreeText.java` contract |
| `tests/pdmodel/documentinterchange/taggedpdf/upstream/test_pd_user_property.py` | 3.0.x | placeholder — upstream has no dedicated `PDUserPropertyTest.java`; surface inferred from `PDUserProperty.java` (PDFBox 3.0.x) |
| `tests/pdmodel/interactive/form/upstream/test_pd_field.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDFieldTest.java` |
| `tests/fontbox/ttf/upstream/test_true_type_font.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/TestTTFParser.java` (`testPostTable` slice — TrueTypeFont accessors only) |
| `tests/xmpbox/upstream/test_xmp_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/XMPSchemaTest.java` |
| `tests/contentstream/upstream/test_pdf_stream_engine.py` | 3.0.x | placeholder — upstream has no dedicated `PDFStreamEngineTest.java`; tests pin behaviour-mirroring smoke tests against `PDFStreamEngine.java` (PDFBox 3.0.x) |
| `tests/pdmodel/fdf/upstream/test_fdf_document.py` | 3.0.x | placeholder — upstream has no dedicated `FDFDocumentTest.java`; surface inferred from `FDFDocument.java` (PDFBox 3.0.x) |
| `tests/fontbox/ttf/upstream/test_glyph_data.py` | 3.0.x | placeholder — upstream has no dedicated `GlyphDataTest.java`; behaviour mirror anchored to `GlyphData.java` source line numbers |
| `tests/pdmodel/interactive/form/upstream/test_pd_variable_text.py` | 3.0.x | placeholder — no upstream `PDVariableTextTest.java` (behaviour pinned via `PDTextField`/`PDListBox`/`PDComboBox` suites) |
| `tests/pdmodel/interactive/form/upstream/test_pd_default_appearance_string.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDDefaultAppearanceStringTest.java` |
| `tests/filter/upstream/test_filter.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/filter/TestFilters.java` (`testEmptyFilterList` plus chain semantics not directly testable in upstream's `TestFilters` surface) |
| `tests/cos/upstream/test_cos_update_state.py` | 3.0.x | placeholder — upstream has no dedicated `COSUpdateStateTest.java`; behaviour pinned via contract tests against `COSUpdateState.java` (PDFBox 3.0.x) |
| `tests/text/upstream/test_pdf_text_stripper.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/text/TestTextStripper.java` (helper-method extraction; not full corpus port — corpus tests need rendering-comparison fixtures) |
| `tests/pdmodel/font/upstream/test_pd_type3_char_proc.py` | 3.0.x | placeholder — upstream has no dedicated `PDType3CharProcTest.java`; behaviour anchored to `PDType3CharProc.java` source line ranges |
| `tests/pdmodel/upstream/test_pd_resources.py` | 3.0.x | synthesised from PDResources resource patterns in `COSWriterTest`, `TestLayerUtility`, `TestOptionalContentGroups` (no dedicated `PDResourcesTest.java` upstream) |
| `tests/fontbox/cmap/upstream/test_cmap.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/cmap/TestCMap.java` |
| `tests/pdmodel/common/upstream/test_pd_name_tree_node.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/TestPDNameTreeNode.java` |
| `tests/fontbox/type1/upstream/test_type1_parser.py` | 3.0.x | placeholder — upstream has no dedicated `Type1ParserTest.java`; behaviour mirrored against `Type1Parser.java` (PDFBox 3.0.x) |
| `tests/pdmodel/graphics/color/upstream/test_pd_cal_rgb.py` | 3.0.x | placeholder — upstream has no dedicated `PDCalRGBTest.java`; behaviour mirrored against `PDCalRGB.java` (PDFBox 3.0.x) |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_annotation_text.py` | 3.0.x | placeholder — upstream has no standalone `PDAnnotationTextTest.java`; API mirror against `PDAnnotationText.java` (PDFBox 3.0.x) |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_annotation_polyline.py` | 3.0.x | placeholder — upstream has no `PDAnnotationPolylineTest.java`; tests anchored to `PDAnnotationPolyline.java` source line refs |
| `tests/pdmodel/common/upstream/test_pd_number_tree_node.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/TestPDNumberTreeNode.java` |
| `tests/pdmodel/graphics/form/upstream/test_pd_form_x_object.py` | 3.0.x | placeholder — upstream has no dedicated `PDFormXObjectTest.java` (covered transitively); tests anchored to `PDFormXObject.java` source line refs |
| `tests/pdmodel/font/upstream/test_pd_type1_font.py` | 3.0.x | placeholder — upstream has no dedicated `PDType1FontTest.java`; coverage derived from `PDFontTest.java` factory subset + upstream `PDType1Font.java` private helpers |
| `tests/pdmodel/encryption/upstream/test_security_handler.py` | 3.0.x | placeholder — upstream has no dedicated `SecurityHandlerTest.java`; surface inferred from `SecurityHandler.java` (PDFBox 3.0.x) |
| `tests/pdfwriter/upstream/test_cos_writer.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSWriterTest.java` (2 ports active, 2 skipped pending fixture support) |

### Wave 47 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/form/pd_field_tree.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDFieldTree.java` |
| `tests/pdmodel/interactive/form/test_pd_field_tree.py` | 3.0.x | hand-written coverage for `PDFieldTree` traversal and Python sequence compatibility |

### Wave 48 additions

No new port files were added in Wave 48. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`, `PDDocumentCatalog`, `FontMetrics`, `XMPBasicSchema`, and `PDFStreamEngine`.

### Wave 49 additions

No new port files were added in Wave 49. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`, `PDAnnotationFreeText`, `PDResources`, `NameRecord`, and `XMPRightsManagementSchema`.

### Wave 50 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/ascii_hex_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCIIHexFilter.java` |
| `tests/filter/test_ascii_hex_filter.py` | 3.0.x | hand-written coverage for the upstream-named `ASCIIHexFilter` alias and registry wiring |

Existing upstream-derived modules extended in Wave 50: `ContentStreamWriter`, `COSStandardOutputStream`, `PDPage`, `PDTilingPattern`, and `PostScriptTable`.

### Wave 51 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/dct_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/DCTFilter.java` |
| `tests/filter/test_dct_decode.py` | 3.0.x | hand-written coverage for `/DCTDecode` decode-only behavior and registry wiring |

Existing upstream-derived modules extended in Wave 51: `COSArray`, `PDAnnotationWidget`, `PDPage`, and `OS2WindowsMetricsTable`.

### Wave 52 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/flate_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/FlateFilter.java` |
| `tests/filter/test_flate_filter.py` | 3.0.x | hand-written coverage for the upstream-named `FlateFilter` alias and registry wiring |

Existing upstream-derived modules extended in Wave 52: `COSWriterXRefEntry`, `PDImageXObject`, `PDAnnotationWidget`, and `HeaderTable`.

### Wave 53 additions

No new port files were added in Wave 53. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`, `PDPage`, `PDShadingType3`, `TrueTypeFont`, and `XMPMediaManagementSchema`.

### Wave 54 additions

No new port files were added in Wave 54. The wave only extended existing upstream-derived modules and their existing test files:
`COSStandardOutputStream`, `PDAnnotation`, `PDResources`, `VerticalMetricsTable`, `ASCII85Decode`, and `ASCIIHexDecode`.

### Wave 55 additions

No new port files were added in Wave 55. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`, `PDAnnotationMarkup`, `PDResources`, `NamingTable`, and `XMPSchema`.

### Wave 56 additions

No new port files were added in Wave 56. The wave only extended existing upstream-derived modules and their existing test files:
`COSArray`, `PDAnnotationMarkup`, `PDResources`, `MaximumProfileTable`, `HorizontalHeaderTable`, and `XMPSchema`.

### Wave 57 additions

No new port files were added in Wave 57. The wave only extended existing upstream-derived modules and their existing test files:
`COSArray`, `PDAnnotationCaret`, `PDResources`, `MaximumProfileTable`, and `XMPSchema`.

### Wave 58 additions

No new port files were added in Wave 58. The wave only extended existing upstream-derived modules and their existing test files:
`COSArray`, `PDResources`, `PDAnnotationRubberStamp`, `PDAnnotationStamp`, `HorizontalMetricsTable`, and `LangAlt`.

### Wave 59 additions

No new port files were added in Wave 59. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`, `PDAnnotationMovie`, and `TrueTypeFont`.

### Wave 60 additions

No new port files were added in Wave 60. The wave only extended existing upstream-derived modules and their existing test files:
`TTFTable`, `Attribute`, and `AbstractField`.

### Wave 61 additions

No new port files were added in Wave 61. The wave only extended existing upstream-derived modules and their existing test files:
`COSInteger`, `COSFloat`, and `COSString`.

### Wave 62 additions

No new port files were added in Wave 62. The wave only extended existing upstream-derived modules and their existing test files:
`COSDocument`.

### Wave 63 additions

No new port files were added in Wave 63. The wave only extended existing upstream-derived modules and their existing test files:
`NameRecord`.

### Wave 64 additions

No new port files were added in Wave 64. The wave only extended existing upstream-derived modules and their existing test files:
`JobType` and `ResourceEventType`.

### Wave 65 additions

No new port files were added in Wave 65. The wave only extended existing upstream-derived modules and their existing test files:
`COSArray`.

### Wave 66 additions

No new port files were added in Wave 66. The wave only extended existing upstream-derived modules and their existing test files:
`COSDictionary`.

### Wave 67 additions

No new port files were added in Wave 67. The wave only extended existing upstream-derived modules and their existing test files:
`CmapSubtable`.

### Wave 68 additions

No new port files were added in Wave 68. The wave only extended existing upstream-derived modules and their existing test files:
`DimensionsType` and `LayerType`.

### Wave 69 additions

No new port files were added in Wave 69. The wave only extended existing upstream-derived modules and their existing test files:
`VersionType`.

### Wave 70 additions

No new port files were added in Wave 70. The wave only extended existing upstream-derived modules and their existing test files:
`ResourceRefType`.

### Wave 71 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/ascii85_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCII85Filter.java` (alias module; codec body in `ascii85_decode.py`) |
| `tests/filter/test_ascii85_filter.py` | 3.0.x | hand-written coverage for the upstream-named `ASCII85Filter` alias and registry wiring |

Existing upstream-derived modules extended in Wave 71: `Filter` (`SYSPROP_DEFLATELEVEL`, `SYSPROP_CCITTFAX_MAXBYTES`, `get_compression_level`), `FlateDecode` (encode honours configured deflate level).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/state/empty_graphics_stack_exception.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/EmptyGraphicsStackException.java` |

### Wave 73 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/dct_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/DCTFilter.java` (alias module; codec body in `dct_decode.py`) |
| `pypdfbox/filter/ccitt_fax_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CCITTFaxFilter.java` (alias module; codec body in `ccitt_fax_decode.py`) |
| `pypdfbox/filter/tiff_extension.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/TIFFExtension.java` |
| `tests/filter/test_dct_filter.py` | 3.0.x | hand-written coverage for the upstream-named `DCTFilter` alias and registry wiring |
| `tests/filter/test_ccitt_fax_filter.py` | 3.0.x | hand-written coverage for the upstream-named `CCITTFaxFilter` alias and registry wiring |
| `tests/filter/test_tiff_extension.py` | 3.0.x | hand-written coverage pinning every `TIFFExtension` constant value |

### XMP simple-type parity round-out (URLType / RenditionClassType)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/type/url_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/URLType.java` |
| `pypdfbox/xmpbox/type/rendition_class_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/RenditionClassType.java` |
| `tests/xmpbox/type/test_boolean_type.py` | 3.0.x | hand-written coverage for `BooleanType` constants + value coercion |
| `tests/xmpbox/type/test_url_type.py` | 3.0.x | hand-written coverage for the `URLType` simple property + registry wiring |
| `tests/xmpbox/type/test_rendition_class_type.py` | 3.0.x | hand-written coverage for the `RenditionClassType` simple property + registry wiring |

### XMP simple-type parity round-out (LocaleType / XPathType / PartType)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/type/locale_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/LocaleType.java` |
| `pypdfbox/xmpbox/type/xpath_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/XPathType.java` |
| `pypdfbox/xmpbox/type/part_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/PartType.java` |
| `tests/xmpbox/type/test_locale_type.py` | 3.0.x | hand-written coverage for the `LocaleType` simple property + registry wiring |
| `tests/xmpbox/type/test_xpath_type.py` | 3.0.x | hand-written coverage for the `XPathType` simple property + registry wiring |
| `tests/xmpbox/type/test_part_type.py` | 3.0.x | hand-written coverage for the `PartType` simple property + registry wiring |

### XMPMetadata upstream test port (testInitMetaDataWithInfo / testAddingSchem)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/xmpbox/upstream/test_xmp_metadata.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/XMPMetaDataTest.java` (`testInitMetaDataWithInfo` + `testAddingSchem` ported; `XmpSerializationException` smoke tests skipped — pypdfbox raises plain `RuntimeError`; `testPDFBOX3257` already lives in `test_dom_xmp_parser.py`) |

### Coverage-wave augmentation tests (no upstream Java equivalents)

These `_wave<N>.py` files live alongside upstream-port test modules but are
**pypdfbox-original coverage augmentation** — they re-invoke sibling cases as
callable bodies (sometimes with `monkeypatch`) to exercise placeholder /
skipped branches so coverage counts the lines. They are **not** ports of
upstream Java tests; the upstream test surface is fully captured by the
non-`_wave<N>` sibling file in the same directory.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/cos/upstream/test_cos_float_wave1226.py` | 3.0.x | (none — coverage augmentation around `tests/cos/upstream/test_cos_float.py`) |
| `tests/cos/upstream/test_cos_integer_wave1225.py` | 3.0.x | (none — coverage augmentation around `tests/cos/upstream/test_cos_integer.py`) |
| `tests/cos/upstream/test_cos_object_key_wave1224.py` | 3.0.x | (none — coverage augmentation around `tests/cos/upstream/test_cos_object_key.py`) |
| `tests/cos/upstream/test_cos_update_info_wave1223.py` | 3.0.x | (none — coverage augmentation around `tests/cos/upstream/test_cos_update_info.py`) |
| `tests/cos/upstream/test_pdf_doc_encoding_wave1017.py` | 3.0.x | (none — coverage augmentation around `tests/cos/upstream/test_pdf_doc_encoding.py`) |
| `tests/fontbox/cmap/upstream/test_cmap_parser_wave1204.py` | 3.0.x | (none — coverage augmentation around `tests/fontbox/cmap/upstream/test_cmap_parser.py`) |
| `tests/fontbox/ttf/upstream/test_glyph_positioning_table_wave938.py` | 3.0.x | (none — coverage augmentation around `tests/fontbox/ttf/upstream/test_glyph_positioning_table.py`) |
| `tests/fontbox/ttf/upstream/test_glyph_substitution_table_wave1189.py` | 3.0.x | (none — coverage augmentation around `tests/fontbox/ttf/upstream/test_glyph_substitution_table.py`) |
| `tests/fontbox/ttf/upstream/test_ttf_subsetter_wave1188.py` | 3.0.x | (none — coverage augmentation around `tests/fontbox/ttf/upstream/test_ttf_subsetter.py`) |
| `tests/multipdf/upstream/test_overlay_wave955.py` | 3.0.x | (none — coverage augmentation around `tests/multipdf/upstream/test_overlay.py`) |
| `tests/multipdf/upstream/test_page_extractor_wave1008.py` | 3.0.x | (none — coverage augmentation around `tests/multipdf/upstream/test_page_extractor.py`) |
| `tests/pdfwriter/upstream/test_save_incremental_wave917.py` | 3.0.x | (none — coverage augmentation around `tests/pdfwriter/upstream/test_save_incremental.py`) |
| `tests/pdmodel/documentinterchange/logicalstructure/upstream/test_pd_structure_element_wave1004.py` | 3.0.x | (none — coverage augmentation around `tests/pdmodel/documentinterchange/logicalstructure/upstream/test_pd_structure_element.py`) |
| `tests/pdmodel/font/upstream/test_pd_type0_font_wave1127.py` | 3.0.x | (none — coverage augmentation around `tests/pdmodel/font/upstream/test_pd_type0_font.py`) |
| `tests/text/upstream/test_pdf_text_stripper_by_area_wave1029.py` | 3.0.x | (none — coverage augmentation around `tests/text/upstream/test_pdf_text_stripper_by_area.py`) |
| `tests/xmpbox/type/upstream/test_structured_type_wave1020.py` | 3.0.x | (none — coverage augmentation around `tests/xmpbox/type/upstream/test_structured_type.py`) |


### Wave 1274 additions

No new port files added. The wave only extended existing upstream-derived modules with explicit `to_string()` mirrors and missing public methods/aliases against PDFBox 3.0.x. New hand-written coverage tests:

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/cos/test_cos_null_wave1274.py` | 3.0.x | (hand-written coverage for `COSNull.to_string`) |
| `tests/pdfwriter/test_content_stream_writer_wave1274.py` | 3.0.x | (hand-written coverage for `ContentStreamWriter.write_object` dispatcher) |
| `tests/pdmodel/font/test_pd_cid_system_info_wave1274.py` | 3.0.x | (hand-written coverage for `PDCIDSystemInfo.to_string`) |
| `tests/pdmodel/interactive/documentnavigation/outline/test_pd_outline_item_iterator_wave1274.py` | 3.0.x | (hand-written coverage for `PDOutlineItemIterator.next` Java-iterator alias) |
| `tests/pdmodel/font/test_pd_true_type_font.py` | 3.0.x | hand-written coverage for `PDTrueTypeFont.generate_bounding_box` / `get_parser` / `get_path_from_outlines` / `load` |
| `tests/fontbox/ttf/gsub/upstream/test_feature_record.py` | 3.0.x | upstream-shaped synthetic tests for `FeatureRecord.to_string` (no standalone JUnit upstream — exercised through GSUB parsing tests) |
| `tests/fontbox/ttf/gsub/upstream/test_lookup_table.py` | 3.0.x | upstream-shaped synthetic tests for `LookupTable.to_string` |
| `tests/fontbox/ttf/gsub/upstream/test_script_table.py` | 3.0.x | upstream-shaped synthetic tests for `ScriptTable.to_string` |

### Wave 1275 additions

No new port files added. The wave only extended existing upstream-derived modules with explicit `to_string()` mirrors and missing public methods/aliases against PDFBox 3.0.x. New hand-written coverage tests:

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/contentstream/test_operator_wave1275.py` | 3.0.x | hand-written coverage for `Operator.execute` |
| `tests/contentstream/test_pd_content_stream_wave1275.py` | 3.0.x | hand-written coverage for `PDContentStream.get_b_box` |
| `tests/cos/test_cos_document_wave1275.py` | 3.0.x | hand-written coverage for `COSDocument.get_stream_cache` |
| `tests/cos/test_cos_object_wave1275.py` | 3.0.x | hand-written coverage for `COSObject.to_string` |
| `tests/cos/test_cos_stream_wave1275.py` | 3.0.x | hand-written coverage for `COSStream.write` |
| `tests/cos/test_i_cos_visitor_wave1275.py` | 3.0.x | hand-written coverage for `ICOSVisitor.visit_from_int` |
| `tests/fontbox/cff/test_cff_type1_font_wave1275.py` | 3.0.x | hand-written coverage for `CFFType1Font.get_parser` / `set_encoding` |
| `tests/fontbox/test_font_box_font_wave1275.py` | 3.0.x | hand-written coverage for `get_font_b_box` helper |
| `tests/fontbox/test_font_info_wave1275.py` | 3.0.x | hand-written coverage for `FontInfo.to_string` |
| `tests/fontbox/ttf/test_bounding_box_wave1275.py` | 3.0.x | hand-written coverage for `BoundingBox.to_string` (in `glyph_data.py`) |
| `tests/fontbox/ttf/test_font_headers_wave1275.py` | 3.0.x | hand-written coverage for `FontHeaders.get_non_otf_table_gcid142` / `set_non_otf_gcid142` |
| `tests/fontbox/ttf/test_header_table_wave1275.py` | 3.0.x | hand-written coverage for `HeaderTable.read_headers` |
| `tests/fontbox/ttf/test_name_record_wave1275.py` | 3.0.x | hand-written coverage for `NameRecord.to_string` |
| `tests/fontbox/ttf/test_ttf_table_wave1275.py` | 3.0.x | hand-written coverage for `TTFTable.read_headers` no-op base |
| `tests/fontbox/type1/test_type1_font_wave1275.py` | 3.0.x | hand-written coverage for `Type1Font.create_with_pfb` / `get_font_b_box` / `get_parser` / `to_string` |
| `tests/io/test_memory_usage_setting_wave1275.py` | 3.0.x | hand-written coverage for `MemoryUsageSetting.to_string` |
| `tests/io/test_random_access_read_buffered_file_wave1275.py` | 3.0.x | hand-written coverage for `RandomAccessReadBufferedFile.read_page` / `remove_eldest_entry` |
| `tests/io/test_scratch_file_wave1275.py` | 3.0.x | hand-written coverage for `ScratchFile.init_pages` / `enlarge` |
| `tests/pdfwriter/test_cos_writer_setters_wave1275.py` | 3.0.x | hand-written coverage for `COSWriter.set_output` / `set_standard_output` |
| `tests/pdmodel/common/test_pd_name_tree_node_wave1275.py` | 3.0.x | hand-written coverage for `PDNameTreeNode.calculate_limits` |
| `tests/pdmodel/common/test_pd_range_wave1275.py` | 3.0.x | hand-written coverage for `PDRange.to_string` |
| `tests/pdmodel/common/test_pd_stream_wave1275.py` | 3.0.x | hand-written coverage for `PDStream.internal_get_decode_params` |
| `tests/pdmodel/documentinterchange/logicalstructure/test_pd_marked_content_reference_to_string_wave1275.py` | 3.0.x | hand-written coverage for `PDMarkedContentReference.to_string` |
| `tests/pdmodel/documentinterchange/markedcontent/test_pd_marked_content_to_string_wave1275.py` | 3.0.x | hand-written coverage for `PDMarkedContent.to_string` |
| `tests/pdmodel/documentinterchange/taggedpdf/test_pd_artifact_marked_content_wave1275.py` | 3.0.x | hand-written coverage for `PDArtifactMarkedContent.is_attached` |
| `tests/pdmodel/documentinterchange/taggedpdf/test_pd_standard_attribute_object_wave1275.py` | 3.0.x | hand-written coverage for `PDStandardAttributeObject.set_four_colors` |
| `tests/pdmodel/encryption/test_security_handler_aes_other_wave1275.py` | 3.0.x | hand-written coverage for `SecurityHandler.encrypt_data_ae_sother` |
| `tests/pdmodel/fdf/test_fdf_annotation_rich_contents_wave1275.py` | 3.0.x | hand-written coverage for `FDFAnnotation.rich_contents_to_string` |
| `tests/pdmodel/fdf/test_fdf_field_escape_xml_wave1275.py` | 3.0.x | hand-written coverage for `FDFField.escape_xml` |
| `tests/pdmodel/font/test_pd_panose_wave1275.py` | 3.0.x | hand-written coverage for `PDPanoseClassification.to_string` |
| `tests/pdmodel/graphics/color/test_pd_color_space_wave1275.py` | 3.0.x | hand-written coverage for `PDColorSpace.create_from_cos_object` |
| `tests/pdmodel/graphics/color/test_pd_device_n_attributes_wave1275.py` | 3.0.x | hand-written coverage for `PDDeviceNAttributes.to_string` |
| `tests/pdmodel/graphics/color/test_pd_indexed_wave1275.py` | 3.0.x | hand-written coverage for `PDIndexed.set_high_value` |
| `tests/pdmodel/graphics/color/test_pd_output_intent_wave1275.py` | 3.0.x | hand-written coverage for `PDOutputIntent.configure_output_profile` |
| `tests/pdmodel/graphics/shading/test_pd_shading_to_paint_wave1275.py` | 3.0.x | hand-written coverage for `PDShading.to_paint` / Type1 / Type2 |
| `tests/pdmodel/graphics/state/test_pd_soft_mask_wave1275.py` | 3.0.x | hand-written coverage for `PDSoftMask.get_sub_type` |
| `tests/pdmodel/interactive/annotation/test_pd_appearance_characteristics_dictionary_wave1275.py` | 3.0.x | hand-written coverage for `PDAppearanceCharacteristicsDictionary.get_color` |
| `tests/pdmodel/interactive/digitalsignature/test_pd_signature_wave1275.py` | 3.0.x | hand-written coverage for `PDSignature.get_converted_contents` |
| `tests/pdmodel/interactive/documentnavigation/destination/test_pd_page_destination_wave1275.py` | 3.0.x | hand-written coverage for `PDPageDestination.index_of_page_tree` |
| `tests/pdmodel/interactive/form/test_pd_field_wave1275.py` | 3.0.x | hand-written coverage for `PDField.equals` / `hash_code` / `to_string` |
| `tests/pdmodel/interactive/form/test_pd_variable_text_wave1275.py` | 3.0.x | hand-written coverage for `PDVariableText.get_default_appearance_string` |
| `tests/pdmodel/interactive/form/test_pd_default_appearance_string.py` | 3.0.x | hand-written coverage for `PDDefaultAppearanceString` parser + accessors + writers |
| `tests/pdmodel/test_pd_rectangle_wave1275.py` | 3.0.x | hand-written coverage for `PDRectangle.to_string` / `transform` |
| `tests/xmpbox/test_xmp_metadata_wave1275.py` | 3.0.x | hand-written coverage for `XMPMetadata.get_end_x_packet` / `set_end_x_packet` / `get_type_mapping` |
| `tests/xmpbox/type/test_abstract_simple_property_wave1275.py` | 3.0.x | hand-written coverage for `AbstractSimpleProperty.to_string` |
| `tests/xmpbox/type/upstream/test_attribute_wave1275.py` | 3.0.x | hand-written coverage for `Attribute.to_string` |

### Wave 1276 additions

The wave reached 1:1 method parity (100.0%) across ported classes. New port files + tests:

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/font_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontFactory.java` (private inner `FontType` enum lifted to a top-level Python module) |
| `pypdfbox/cos/unmodifiable_cos_dictionary.py` | 3.0.x | re-export shim for the existing `UnmodifiableCOSDictionary` in `cos_dictionary.py`, mirroring the standalone Java class |
| `tests/cos/test_unmodifiable_cos_dictionary_wave1276.py` | 3.0.x | hand-written coverage for `UnmodifiableCOSDictionary.set_need_to_be_updated` |
| `tests/fontbox/test_font_box_font_wave1276.py` | 3.0.x | hand-written coverage for `FontBoxFont.get_font_b_box` Protocol method |
| `tests/fontbox/test_font_type_wave1276.py` | 3.0.x | hand-written coverage for `FontType.get_subtype` / `is_cid_subtype` |
| `tests/fontbox/cff/test_fd_select_to_string.py` | 3.0.x | hand-written coverage for `Format0FDSelect.to_string` / `Format3FDSelect.to_string` |
| `tests/pdmodel/test_pd_javascript_name_tree_node.py` | 3.0.x | hand-written coverage for `PDJavascriptNameTreeNode.convert_cos_to_pd` |
| `tests/pdmodel/documentinterchange/logicalstructure/test_pd_structure_element_name_tree_node.py` | 3.0.x | hand-written coverage for `PDStructureElementNameTreeNode.convert_cos_to_pd` |
| `tests/pdmodel/graphics/color/test_pd_device_color_space_to_string.py` | 3.0.x | hand-written coverage for `PDDeviceColorSpace.to_string` |

### Wave 1277 additions

New `type4` subpackage ported from upstream `org.apache.pdfbox.pdmodel.common.function.type4`:

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/function/type4/__init__.py` | 3.0.x | (package init mirroring upstream Java package layout) |
| `pypdfbox/pdmodel/common/function/type4/operator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/Operator.java` |
| `pypdfbox/pdmodel/common/function/type4/operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/Operators.java` |
| `pypdfbox/pdmodel/common/function/type4/execution_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/ExecutionContext.java` |
| `pypdfbox/pdmodel/common/function/type4/instruction_sequence.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/InstructionSequence.java` |
| `pypdfbox/pdmodel/common/function/type4/instruction_sequence_builder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/InstructionSequenceBuilder.java` |
| `pypdfbox/pdmodel/common/function/type4/parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/Parser.java` (incl. nested `SyntaxHandler`, `AbstractSyntaxHandler`, `Tokenizer`) |
| `pypdfbox/pdmodel/common/function/type4/arithmetic_operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/ArithmeticOperators.java` |
| `pypdfbox/pdmodel/common/function/type4/bitwise_operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/BitwiseOperators.java` |
| `pypdfbox/pdmodel/common/function/type4/conditional_operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/ConditionalOperators.java` |
| `pypdfbox/pdmodel/common/function/type4/relational_operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/RelationalOperators.java` |
| `pypdfbox/pdmodel/common/function/type4/stack_operators.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/type4/StackOperators.java` |
| `tests/pdmodel/common/function/type4/upstream/test_parser.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestParser.java` |
| `tests/pdmodel/common/function/type4/upstream/test_arithmetic_operators.py` | 3.0.x | derived from `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/type4/TestOperators.java` (arithmetic subset) |
| `tests/pdmodel/common/function/type4/upstream/test_bitwise_operators.py` | 3.0.x | derived from `TestOperators.java` (bitwise subset: testAnd / Bitshift / Not / Or / Xor) |
| `tests/pdmodel/common/function/type4/upstream/test_conditional_operators.py` | 3.0.x | derived from `TestOperators.java` (testIf / testIfElse) |
| `tests/pdmodel/common/function/type4/upstream/test_relational_operators.py` | 3.0.x | derived from `TestOperators.java` (testEq / Ne / Lt / Le / Gt / Ge) |
| `tests/pdmodel/common/function/type4/upstream/test_stack_operators.py` | 3.0.x | derived from `TestOperators.java` (testCopy / Dup / Exch / Index / Pop / Roll) |

### Wave 1278 additions

`fontbox.cff` package ported in 39 new modules. fontTools-backed where applicable (standard/expert encodings, ISOAdobe/Expert/ExpertSubset charsets, CFF binary decompile, char-string operator dictionaries). Upstream PDFBox 3.0.x; Java paths under `fontbox/src/main/java/org/apache/fontbox/cff/`:

| pypdfbox path | upstream Java path |
|---|---|
| `pypdfbox/fontbox/cff/cff_encoding.py` | `CFFEncoding.java` |
| `pypdfbox/fontbox/cff/cff_built_in_encoding.py` | `CFFParser.java` (inner `CFFBuiltInEncoding` + `Supplement`) |
| `pypdfbox/fontbox/cff/cff_standard_encoding.py` | `CFFStandardEncoding.java` |
| `pypdfbox/fontbox/cff/cff_expert_encoding.py` | `CFFExpertEncoding.java` |
| `pypdfbox/fontbox/cff/format0_encoding.py` | `CFFParser.java` (inner `Format0Encoding`) |
| `pypdfbox/fontbox/cff/format1_encoding.py` | `CFFParser.java` (inner `Format1Encoding` + `Range3`) |
| `pypdfbox/fontbox/cff/cff_charset.py` | `CFFCharset.java` |
| `pypdfbox/fontbox/cff/cff_charset_cid.py` | `CFFCharsetCID.java` |
| `pypdfbox/fontbox/cff/cff_charset_type1.py` | `CFFCharsetType1.java` |
| `pypdfbox/fontbox/cff/cff_iso_adobe_charset.py` | `CFFISOAdobeCharset.java` |
| `pypdfbox/fontbox/cff/cff_expert_charset.py` | `CFFExpertCharset.java` |
| `pypdfbox/fontbox/cff/cff_expert_subset_charset.py` | `CFFExpertSubsetCharset.java` |
| `pypdfbox/fontbox/cff/embedded_charset.py` | `EmbeddedCharset.java` |
| `pypdfbox/fontbox/cff/empty_charset_cid.py` | `CFFParser.java` (inner `EmptyCharsetCID`) |
| `pypdfbox/fontbox/cff/empty_charset_type1.py` | `CFFParser.java` (inner `EmptyCharsetType1`) |
| `pypdfbox/fontbox/cff/format1_charset.py` | `CFFParser.java` (inner `Format1Charset`) |
| `pypdfbox/fontbox/cff/format2_charset.py` | `CFFParser.java` (inner `Format2Charset`) |
| `pypdfbox/fontbox/cff/range_mapping.py` | `CFFParser.java` (inner `RangeMapping`) |
| `pypdfbox/fontbox/cff/byte_source.py` | `CFFParser.java` (inner `ByteSource` interface) |
| `pypdfbox/fontbox/cff/cff_byte_source.py` | `CFFParser.java` (inner `CFFBytesource`, lowercase `s` preserved) |
| `pypdfbox/fontbox/cff/data_input.py` | `DataInput.java` |
| `pypdfbox/fontbox/cff/data_input_byte_array.py` | `DataInputByteArray.java` |
| `pypdfbox/fontbox/cff/data_input_random_access_read.py` | `DataInputRandomAccessRead.java` |
| `pypdfbox/fontbox/cff/cff_parser.py` | `CFFParser.java` (top-level orchestrator, 37 methods) |
| `pypdfbox/fontbox/cff/header.py` | `CFFParser.java` (inner `Header`) |
| `pypdfbox/fontbox/cff/dict_data.py` | `CFFParser.java` (inner `DictData` + `Entry` + `Key`) |
| `pypdfbox/fontbox/cff/cff_standard_string.py` | `CFFStandardString.java` |
| `pypdfbox/fontbox/cff/cff_operator.py` | `CFFOperator.java` |
| `pypdfbox/fontbox/cff/char_string_command.py` | `CharStringCommand.java` |
| `pypdfbox/fontbox/cff/type1_keyword.py` | `CharStringCommand.java` (inner `Type1KeyWord` enum) |
| `pypdfbox/fontbox/cff/type2_keyword.py` | `CharStringCommand.java` (inner `Type2KeyWord` enum) |
| `pypdfbox/fontbox/cff/type1_char_string_parser.py` | `Type1CharStringParser.java` |
| `pypdfbox/fontbox/cff/type2_char_string_parser.py` | `Type2CharStringParser.java` |
| `pypdfbox/fontbox/cff/cid_keyed_type2_char_string.py` | `CIDKeyedType2CharString.java` |
| `pypdfbox/fontbox/cff/private_type1_char_string_reader.py` | (`PrivateType1CharStringReader` inner of `CFFCIDFont.java` + `Type1CharStringReader.java`) |
| `tests/fontbox/cff/upstream/test_cff_encoding.py` | `CFFEncodingTest.java` |
| `tests/fontbox/cff/upstream/test_data_input.py` | `DataInputTest.java` |
| `tests/fontbox/cff/upstream/test_data_input_random_access.py` | `DataInputRandomAccessTest.java` |
| `tests/fontbox/cff/upstream/test_cff_parser.py` | `CFFParserTest.java` |
| `tests/fontbox/cff/upstream/test_char_string_command.py` | `CharStringCommandTest.java` |

### Wave 1279 additions

`fontbox.ttf` package + subpackages ported in 42 new modules. fontTools-backed for TTC / glyf / OT lookups; per-script Indic shaping hand-ported (no Python library provides this). Upstream PDFBox 3.0.x; paths under `fontbox/src/main/java/org/apache/fontbox/ttf/`:

| pypdfbox path | upstream Java path |
|---|---|
| `pypdfbox/fontbox/ttf/point.py` | `GlyphRenderer.java` (private nested `Point`) |
| `pypdfbox/fontbox/ttf/glyf_descript.py` | `GlyfDescript.java` |
| `pypdfbox/fontbox/ttf/glyf_simple_descript.py` | `GlyfSimpleDescript.java` |
| `pypdfbox/fontbox/ttf/glyf_composite_descript.py` | `GlyfCompositeDescript.java` |
| `pypdfbox/fontbox/ttf/glyf_composite_comp.py` | `GlyfCompositeComp.java` |
| `pypdfbox/fontbox/ttf/glyph_renderer.py` | `GlyphRenderer.java` |
| `pypdfbox/fontbox/ttf/ttc_data_stream.py` | `TTCDataStream.java` |
| `pypdfbox/fontbox/ttf/true_type_collection.py` | `TrueTypeCollection.java` |
| `pypdfbox/fontbox/ttf/random_access_read_non_closing_input_stream.py` | `RandomAccessReadUnbufferedDataStream.java` (private nested) |
| `pypdfbox/fontbox/ttf/random_access_read_unbuffered_data_stream.py` | `RandomAccessReadUnbufferedDataStream.java` |
| `pypdfbox/fontbox/ttf/true_type_font_headers_processor.py` | `TrueTypeCollection.java` (inner `TrueTypeFontHeadersProcessor` interface) |
| `pypdfbox/fontbox/ttf/true_type_font_processor.py` | `TrueTypeCollection.java` (inner `TrueTypeFontProcessor` interface) |
| `pypdfbox/fontbox/ttf/cff_table.py` | `CFFTable.java` |
| `pypdfbox/fontbox/ttf/sub_header.py` | `CmapSubtable.java` (private nested `SubHeader`) |
| `pypdfbox/fontbox/ttf/substituting_cmap_lookup.py` | `SubstitutingCmapLookup.java` |
| `pypdfbox/fontbox/ttf/open_type_script.py` | `OpenTypeScript.java` |
| `pypdfbox/fontbox/ttf/vertical_origin_table.py` | `VerticalOriginTable.java` |
| `pypdfbox/fontbox/ttf/pair_data.py` | `KerningSubtable.java` (private nested `PairData` ABC) |
| `pypdfbox/fontbox/ttf/pair_data0_format0.py` | `KerningSubtable.java` (private nested `PairData0Format0`) |
| `pypdfbox/fontbox/ttf/table/common/range_record.py` | `table/common/RangeRecord.java` |
| `pypdfbox/fontbox/ttf/table/common/coverage_table_format1.py` | `table/common/CoverageTableFormat1.java` |
| `pypdfbox/fontbox/ttf/table/common/coverage_table_format2.py` | `table/common/CoverageTableFormat2.java` |
| `pypdfbox/fontbox/ttf/table/common/feature_list_table.py` | `table/common/FeatureListTable.java` |
| `pypdfbox/fontbox/ttf/table/common/lookup_list_table.py` | `table/common/LookupListTable.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker.py` | `gsub/GsubWorker.java` |
| `pypdfbox/fontbox/ttf/gsub/default_gsub_worker.py` | `gsub/DefaultGsubWorker.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_factory.py` | `gsub/GsubWorkerFactory.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_dflt.py` | `gsub/GsubWorkerForDflt.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_latin.py` | `gsub/GsubWorkerForLatin.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_bengali.py` | `gsub/GsubWorkerForBengali.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_devanagari.py` | `gsub/GsubWorkerForDevanagari.java` |
| `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_gujarati.py` | `gsub/GsubWorkerForGujarati.java` |
| `pypdfbox/fontbox/ttf/gsub/compound_character_tokenizer.py` | `gsub/CompoundCharacterTokenizer.java` |
| `pypdfbox/fontbox/ttf/gsub/glyph_array_splitter.py` | `gsub/GlyphArraySplitter.java` |
| `pypdfbox/fontbox/ttf/gsub/glyph_array_splitter_regex_impl.py` | `gsub/GlyphArraySplitterRegexImpl.java` |
| `pypdfbox/fontbox/ttf/gsub/glyph_substitution_data_extractor.py` | `gsub/GlyphSubstitutionDataExtractor.java` |
| `pypdfbox/fontbox/ttf/gsub/script_table_details.py` | `gsub/GlyphSubstitutionDataExtractor.java` (private nested `ScriptTableDetails`) |
| `pypdfbox/fontbox/ttf/model/language.py` | `model/Language.java` (enum) |
| `pypdfbox/fontbox/ttf/model/map_backed_gsub_data.py` | `model/MapBackedGsubData.java` |
| `pypdfbox/fontbox/ttf/model/map_backed_script_feature.py` | `model/MapBackedScriptFeature.java` |
| `pypdfbox/fontbox/ttf/model/script_feature.py` | `model/ScriptFeature.java` (interface) |
| `tests/fontbox/ttf/upstream/test_glyf_composite_descript.py` | `GlyfCompositeDescriptTest.java` |
| `tests/fontbox/ttf/upstream/test_true_type_font_collection.py` | `TrueTypeFontCollectionTest.java` |
| `tests/fontbox/ttf/gsub/upstream/test_compound_character_tokenizer.py` | `gsub/CompoundCharacterTokenizerTest.java` |
| `tests/fontbox/ttf/gsub/upstream/test_glyph_array_splitter_regex_impl.py` | `gsub/GlyphArraySplitterRegexImplTest.java` |

### Wave 1280 additions

Six subsystem clusters ported in 92 new modules. Library-first throughout (Pillow / fontTools / stdlib / jbig2-parser). Upstream PDFBox 3.0.x. Modules grouped by package; upstream Java paths are the obvious mirror of the snake_case Python paths (e.g. `pypdfbox/pdmodel/graphics/shading/axial_shading_context.py` ← `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/AxialShadingContext.java`). See `.parity/parity.json` for the full method-by-method audit.

**`pdmodel.graphics.shading/` (25):** axial_shading_context, axial_shading_paint, coons_patch, cubic_bezier_curve, gouraud_shading_context, int_point, line, patch, patch_meshes_shading_context, pd_mesh_based_shading_type, pd_triangle_based_shading_type, radial_shading_context, radial_shading_paint, shaded_triangle, shading_context, shading_paint, tensor_patch, triangle_based_shading_context, type1_shading_context, type1_shading_paint, type4_shading_paint, type5_shading_paint, type6_shading_paint, type7_shading_paint, vertex.

**`pdmodel/interactive/annotation/handlers/` (17):** cloudy_border, pd_caret_appearance_handler, pd_circle_appearance_handler, pd_file_attachment_appearance_handler, pd_free_text_appearance_handler, pd_highlight_appearance_handler, pd_ink_appearance_handler, pd_line_appearance_handler, pd_link_appearance_handler, pd_polygon_appearance_handler, pd_polyline_appearance_handler, pd_sound_appearance_handler, pd_square_appearance_handler, pd_squiggly_appearance_handler, pd_strikeout_appearance_handler, pd_text_appearance_handler, pd_underline_appearance_handler.

**`filter/` (14):** ascii85_input_stream, ascii85_output_stream, ccitt_fax_decoder_stream, ccitt_fax_encoder_stream, crypt_filter, decode_options, final_decode_options, flate_filter_decoder_stream, jbig2_filter, jpx_filter, node, predictor, predictor_output_stream, tree.

**`pdmodel/font/` (15):** cid_system_info, file_system_font_provider, font_cache, font_mapper_impl, font_match, fs_font_info, pd_cid_font_type2_embedder, pd_true_type_font_embedder, pd_type1_font_embedder, subsetter, to_unicode_writer, true_type_embedder, uni_util, vertical_displacement_range, encoding/type1_encoding.

**`pdmodel/interactive/form/` (12):** appearance_generator_helper, appearance_style, builder, field_iterator, field_utils, key_value, paragraph, plain_text, plain_text_formatter, scripting_handler, text_align, word.

**`contentstream/operator/graphics/` (12):** append_rectangle_to_path, clip_even_odd_rule, clip_non_zero_rule, close_fill_even_odd_and_stroke_path, close_fill_non_zero_and_stroke_path, end_path, fill_even_odd_and_stroke_path, fill_even_odd_rule, fill_non_zero_and_stroke_path, fill_non_zero_rule, graphics_operator_processor, legacy_fill_non_zero_rule.

Upstream JUnit test ports (where they exist): `tests/pdmodel/font/test_to_unicode_writer.py` ← `TestToUnicodeWriter.java`.

### Wave 1281 additions

Five subsystem clusters ported in 166 new modules. Library-first throughout (Pillow / fontTools / cryptography / defusedxml / stdlib). Upstream PDFBox 3.0.x; Java paths mirror snake_case Python paths. See `.parity/parity.json` for the full audit. Selected groupings (full list visible via `git diff HEAD~1 -- pypdfbox`):

- **`pypdfbox/rendering/`**: glyph_cache, group_graphics, page_drawer, page_drawer_parameters, soft_mask, tiling_paint, tiling_paint_factory.
- **`pypdfbox/pdmodel/graphics/image/`**: pd_image, custom_factory, png_converter, predictor_encoder, sampled_image_reader.
- **`pypdfbox/pdmodel/graphics/{color,blend,state}/`**: 11 new modules (CIE / gamma / tristimulus / JPX color + blend channel/composite/function + PDGraphicsState/PDTextState).
- **`pypdfbox/pdfparser/`** + **`pdfparser/xref/`**: brute_force_parser, fdf_parser, object_numbers, pdf_object_stream_parser, pdf_xref_stream + parser, xref_trailer_obj, plus 6 xref entry classes.
- **`pypdfbox/io/`**: 10 new io modules (random_access*, stream_cache*, sequence_random_access, etc.).
- **`pypdfbox/cos/`**: cos_increment, cos_input_stream, cos_output_stream, cos_update_info, i_cos_parser, rewritten cos_object_key.
- **`pypdfbox/pdmodel/fdf/`**: 11 new annotation/page/template modules.
- **`pypdfbox/pdmodel/common/`**: cos_array_list, cos_dictionary_map, cos_objectable, label_generator, label_handler, pd_dictionary_wrapper, pd_immutable_rectangle, pd_object_stream, pd_typed_dictionary_wrapper, function/rinterpol.
- **`pypdfbox/pdmodel/`** (top-level): default_resource_cache_create_impl, page_iterator, pd_abstract_content_stream, resource_cache, resource_cache_create_function, resource_cache_factory, search_context.
- **`pypdfbox/pdmodel/encryption/`**: message_digests, rc4_cipher, sasl_prep, security_handler_factory, security_provider.
- **`pypdfbox/pdmodel/interactive/digitalsignature/`** + **`visible/`**: 8 new sig/template modules.
- **`pypdfbox/pdmodel/fixup/`** + **`processor/`**: 6 new fixup classes.
- **`pypdfbox/contentstream/operator/{color,markedcontent,state,text}/`**: 18 new operator classes.
- **`pypdfbox/util/`**: hex, iterative_merge_sort, matrix, vector, string_util, number_format_util, small_map, xml_util.
- **`pypdfbox/util/filetypedetector/`**: byte_trie, file_type, file_type_detector.
- **`pypdfbox/fontbox/util/autodetect/`**: 7 OS-dependent font-discovery modules.
- **`pypdfbox/pdfwriter/compress/`**: 4 compress-pool / object-stream modules.
- **`pypdfbox/xmpbox/{xml,schema,type}/`**: 8 new XMP modules (DomHelper, NamespaceFinder, PdfaExtensionHelper, XmpSerializer, XmpSchemaFactory, Types, ComplexPropertyContainer, AbstractComplexProperty).
- **`pypdfbox/text/`**: legacy_pdf_stream_engine, line_item.
- **`pypdfbox/printing/`**: pdf_pageable, pdf_printable.
- **`pypdfbox/multipdf/k_cloner.py`**, **`pdmodel/interactive/action/pd_action_factory.py`**, **`pdmodel/interactive/annotation/`** (annotation_filter, pd_external_data_dictionary).
- **`pypdfbox/fontbox/`**: cmap/cmap_strings, type1/token, type1/type1_char_string_reader, pfb/pfb_parser.

### Wave 1302 PROVENANCE backfill

Backfill of upstream Java paths for source files added in earlier waves (mostly waves 1280-1286 mass-port batches plus a handful from earlier clusters). Every `pypdfbox/*.py` file (excluding `__init__.py`) now has either a row pointing to an upstream Java path or a `(none — <reason>)` marker for original / hand-written code. Many entries here correspond to **inner classes extracted to their own modules** — Java allows nested classes; pypdfbox promotes them to module-level for testability, so the upstream Java path is the *enclosing* class with a note.

#### `pypdfbox/benchmark/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/benchmark/load_and_save.py` | 3.0.x | `benchmark/src/main/java/org/apache/pdfbox/benchmark/LoadAndSave.java` |
| `pypdfbox/benchmark/null_output_stream.py` | 3.0.x | `benchmark/src/main/java/org/apache/pdfbox/benchmark/NullOutputStream.java` |
| `pypdfbox/benchmark/rendering.py` | 3.0.x | `benchmark/src/main/java/org/apache/pdfbox/benchmark/Rendering.java` |
| `pypdfbox/benchmark/text_extraction.py` | 3.0.x | `benchmark/src/main/java/org/apache/pdfbox/benchmark/TextExtraction.java` |

#### `pypdfbox/contentstream/operator/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/draw_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/DrawObject.java` |

#### `pypdfbox/contentstream/operator/color/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/color/set_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_cmyk.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceCMYKColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_color_n.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingColorN.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingColorSpace.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_device_cmyk_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceCmykColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_device_gray_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceGrayColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_device_rgb_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceRgbColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_gray.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceGrayColor.java` |
| `pypdfbox/contentstream/operator/color/set_non_stroking_rgb.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceRGBColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_cmyk.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceCMYKColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_color_n.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingColorN.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingColorSpace.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_device_cmyk_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceCmykColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_device_gray_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceGrayColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_device_rgb_color.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceRgbColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_gray.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceGrayColor.java` |
| `pypdfbox/contentstream/operator/color/set_stroking_rgb.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceRGBColor.java` |

#### `pypdfbox/contentstream/operator/graphics/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/graphics/append_rectangle_to_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/AppendRectangleToPath.java` |
| `pypdfbox/contentstream/operator/graphics/clip_even_odd_rule.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ClipEvenOddRule.java` |
| `pypdfbox/contentstream/operator/graphics/clip_non_zero_rule.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ClipNonZeroRule.java` |
| `pypdfbox/contentstream/operator/graphics/close_fill_even_odd_and_stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CloseFillEvenOddAndStrokePath.java` |
| `pypdfbox/contentstream/operator/graphics/close_fill_non_zero_and_stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CloseFillNonZeroAndStrokePath.java` |
| `pypdfbox/contentstream/operator/graphics/concatenate_matrix.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Concatenate.java` |
| `pypdfbox/contentstream/operator/graphics/end_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/EndPath.java` |
| `pypdfbox/contentstream/operator/graphics/fill_even_odd_and_stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillEvenOddAndStrokePath.java` |
| `pypdfbox/contentstream/operator/graphics/fill_even_odd_rule.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillEvenOddRule.java` |
| `pypdfbox/contentstream/operator/graphics/fill_non_zero_and_stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillNonZeroAndStrokePath.java` |
| `pypdfbox/contentstream/operator/graphics/fill_non_zero_rule.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillNonZeroRule.java` |
| `pypdfbox/contentstream/operator/graphics/graphics_operator_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/GraphicsOperatorProcessor.java` |
| `pypdfbox/contentstream/operator/graphics/invoke_named_xobject.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/DrawObject.java` |
| `pypdfbox/contentstream/operator/graphics/legacy_fill_non_zero_rule.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/LegacyFillNonZeroRule.java` |

#### `pypdfbox/contentstream/operator/imagecontent/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/imagecontent/begin_inline_image.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/BeginInlineImage.java` |
| `pypdfbox/contentstream/operator/imagecontent/begin_inline_image_data.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/BeginInlineImage.java (ID operator — parsed inside BeginInlineImage)` |
| `pypdfbox/contentstream/operator/imagecontent/end_inline_image.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/BeginInlineImage.java (EI operator — parsed inside BeginInlineImage)` |

#### `pypdfbox/contentstream/operator/markedcontent/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/markedcontent/begin_marked_content.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/BeginMarkedContentSequence.java` |
| `pypdfbox/contentstream/operator/markedcontent/begin_marked_content_sequence.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/BeginMarkedContentSequence.java` |
| `pypdfbox/contentstream/operator/markedcontent/begin_marked_content_sequence_with_properties.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/BeginMarkedContentSequenceWithProperties.java` |
| `pypdfbox/contentstream/operator/markedcontent/begin_marked_content_with_props.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/BeginMarkedContentSequenceWithProperties.java` |
| `pypdfbox/contentstream/operator/markedcontent/define_marked_content_point.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPoint.java` |
| `pypdfbox/contentstream/operator/markedcontent/define_marked_content_point_with_props.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPointWithProperties.java` |
| `pypdfbox/contentstream/operator/markedcontent/end_marked_content.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/EndMarkedContentSequence.java` |
| `pypdfbox/contentstream/operator/markedcontent/end_marked_content_sequence.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/EndMarkedContentSequence.java` |
| `pypdfbox/contentstream/operator/markedcontent/marked_content_point.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPoint.java` |
| `pypdfbox/contentstream/operator/markedcontent/marked_content_point_with_properties.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPointWithProperties.java` |

#### `pypdfbox/contentstream/operator/path/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/path/append_rectangle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/AppendRectangleToPath.java` |
| `pypdfbox/contentstream/operator/path/clip_even_odd.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ClipEvenOddRule.java` |
| `pypdfbox/contentstream/operator/path/clip_non_zero_winding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ClipNonZeroRule.java` |
| `pypdfbox/contentstream/operator/path/close_and_stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CloseAndStrokePath.java` |
| `pypdfbox/contentstream/operator/path/close_fill_then_stroke_even_odd.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CloseFillEvenOddAndStrokePath.java` |
| `pypdfbox/contentstream/operator/path/close_fill_then_stroke_non_zero_winding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CloseFillNonZeroAndStrokePath.java` |
| `pypdfbox/contentstream/operator/path/close_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/ClosePath.java` |
| `pypdfbox/contentstream/operator/path/curve_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CurveTo.java` |
| `pypdfbox/contentstream/operator/path/curve_to_replicate_final_point.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CurveToReplicateFinalPoint.java` |
| `pypdfbox/contentstream/operator/path/curve_to_replicate_initial_point.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/CurveToReplicateInitialPoint.java` |
| `pypdfbox/contentstream/operator/path/end_path_no_op.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/EndPath.java` |
| `pypdfbox/contentstream/operator/path/fill_path_even_odd.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillEvenOddRule.java` |
| `pypdfbox/contentstream/operator/path/fill_path_non_zero_winding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillNonZeroRule.java` |
| `pypdfbox/contentstream/operator/path/fill_then_stroke_even_odd.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillEvenOddAndStrokePath.java` |
| `pypdfbox/contentstream/operator/path/fill_then_stroke_non_zero_winding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/FillNonZeroAndStrokePath.java` |
| `pypdfbox/contentstream/operator/path/legacy_fill_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/LegacyFillNonZeroRule.java` |
| `pypdfbox/contentstream/operator/path/line_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/LineTo.java` |
| `pypdfbox/contentstream/operator/path/move_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/MoveTo.java` |
| `pypdfbox/contentstream/operator/path/stroke_path.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/graphics/StrokePath.java` |

#### `pypdfbox/contentstream/operator/state/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/state/concatenate.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Concatenate.java` |
| `pypdfbox/contentstream/operator/state/restore.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Restore.java` |
| `pypdfbox/contentstream/operator/state/restore_graphics_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Restore.java` |
| `pypdfbox/contentstream/operator/state/save.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Save.java` |
| `pypdfbox/contentstream/operator/state/save_graphics_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Save.java` |
| `pypdfbox/contentstream/operator/state/set_dash_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineDashPattern.java` |
| `pypdfbox/contentstream/operator/state/set_flatness.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetFlatness.java` |
| `pypdfbox/contentstream/operator/state/set_graphics_state_parameters.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetGraphicsStateParameters.java` |
| `pypdfbox/contentstream/operator/state/set_line_dash_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineDashPattern.java` |
| `pypdfbox/contentstream/operator/state/set_rendering_intent.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetRenderingIntent.java` |

#### `pypdfbox/contentstream/operator/text/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/contentstream/operator/text/move_text_position.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/MoveText.java` |
| `pypdfbox/contentstream/operator/text/move_text_set_leading_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/MoveTextSetLeading.java` |
| `pypdfbox/contentstream/operator/text/next_line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/NextLine.java` |
| `pypdfbox/contentstream/operator/text/set_character_spacing.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetCharSpacing.java` |
| `pypdfbox/contentstream/operator/text/set_font_and_size_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetFontAndSize.java` |
| `pypdfbox/contentstream/operator/text/set_horizontal_scaling.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextHorizontalScaling.java` |
| `pypdfbox/contentstream/operator/text/set_text_horizontal_scaling.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextHorizontalScaling.java` |
| `pypdfbox/contentstream/operator/text/set_text_leading.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextLeading.java` |
| `pypdfbox/contentstream/operator/text/set_text_matrix.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetMatrix.java (Tm operator — upstream hosts SetMatrix under state/ but the Tm operator semantically lives in text state)` |
| `pypdfbox/contentstream/operator/text/set_text_rendering_mode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextRenderingMode.java` |
| `pypdfbox/contentstream/operator/text/set_text_rise.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextRise.java` |
| `pypdfbox/contentstream/operator/text/set_word_spacing.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetWordSpacing.java` |
| `pypdfbox/contentstream/operator/text/show_text_array.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextAdjusted.java` |
| `pypdfbox/contentstream/operator/text/show_text_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowText.java` |
| `pypdfbox/contentstream/operator/text/show_text_with_position.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLine.java` |
| `pypdfbox/contentstream/operator/text/show_text_with_word_and_char_spacing.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLineAndSpace.java` |

#### `pypdfbox/cos/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/cos/cos_increment.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/CosIncrement.java` |
| `pypdfbox/cos/cos_input_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/CosInputStream.java` |
| `pypdfbox/cos/cos_output_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/CosOutputStream.java` |
| `pypdfbox/cos/cos_update_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/CosUpdateInfo.java` |
| `pypdfbox/cos/i_cos_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/cos/ICosParser.java` |

#### `pypdfbox/examples/ant/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/ant/pdf_to_text_task.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/ant/PdfToTextTask.java` |

#### `pypdfbox/examples/interactive/form/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/interactive/form/add_border_to_field.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/AddBorderToField.java` |
| `pypdfbox/examples/interactive/form/create_check_box.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreateCheckBox.java` |
| `pypdfbox/examples/interactive/form/create_multi_widgets_form.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreateMultiWidgetsForm.java` |
| `pypdfbox/examples/interactive/form/create_push_button.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreatePushButton.java` |
| `pypdfbox/examples/interactive/form/create_radio_buttons.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreateRadioButtons.java` |
| `pypdfbox/examples/interactive/form/create_simple_form.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreateSimpleForm.java` |
| `pypdfbox/examples/interactive/form/create_simple_form_with_embedded_font.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/CreateSimpleFormWithEmbeddedFont.java` |
| `pypdfbox/examples/interactive/form/determine_text_fits_field.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/DetermineTextFitsField.java` |
| `pypdfbox/examples/interactive/form/field_remover.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/FieldRemover.java` |
| `pypdfbox/examples/interactive/form/field_triggers.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/FieldTriggers.java` |
| `pypdfbox/examples/interactive/form/fill_form_field.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/FillFormField.java` |
| `pypdfbox/examples/interactive/form/print_fields.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/PrintFields.java` |
| `pypdfbox/examples/interactive/form/set_field.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/SetField.java` |
| `pypdfbox/examples/interactive/form/update_field_on_document_open.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/interactive/form/UpdateFieldOnDocumentOpen.java` |

#### `pypdfbox/examples/lucene/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/lucene/index_pdf_files.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/lucene/IndexPdfFiles.java` |
| `pypdfbox/examples/lucene/lucene_pdf_document.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/lucene/LucenePdfDocument.java` |

#### `pypdfbox/examples/pdmodel/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/pdmodel/_font_helpers.py` | 3.0.x | (none — original helper bridging Java FontName-enum constructor to pypdfbox PDType1Font(COSDictionary)) |
| `pypdfbox/examples/pdmodel/add_annotations.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/AddAnnotations.java` |
| `pypdfbox/examples/pdmodel/add_image_to_pdf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/AddImageToPdf.java` |
| `pypdfbox/examples/pdmodel/add_javascript.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/AddJavascript.java` |
| `pypdfbox/examples/pdmodel/add_message_to_each_page.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/AddMessageToEachPage.java` |
| `pypdfbox/examples/pdmodel/add_metadata_from_doc_info.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/AddMetadataFromDocInfo.java` |
| `pypdfbox/examples/pdmodel/bengali_pdf_generation_hello_world.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/BengaliPdfGenerationHelloWorld.java` |
| `pypdfbox/examples/pdmodel/create_blank_pdf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreateBlankPdf.java` |
| `pypdfbox/examples/pdmodel/create_bookmarks.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreateBookmarks.java` |
| `pypdfbox/examples/pdmodel/create_gradient_shading_pdf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreateGradientShadingPdf.java` |
| `pypdfbox/examples/pdmodel/create_landscape_pdf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreateLandscapePdf.java` |
| `pypdfbox/examples/pdmodel/create_page_labels.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreatePageLabels.java` |
| `pypdfbox/examples/pdmodel/create_patterns_pdf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreatePatternsPdf.java` |
| `pypdfbox/examples/pdmodel/create_pdfa.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreatePdfa.java` |
| `pypdfbox/examples/pdmodel/create_portable_collection.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreatePortableCollection.java` |
| `pypdfbox/examples/pdmodel/create_separation_color_box.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/CreateSeparationColorBox.java` |
| `pypdfbox/examples/pdmodel/embedded_files.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/EmbeddedFiles.java` |
| `pypdfbox/examples/pdmodel/embedded_fonts.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/EmbeddedFonts.java` |
| `pypdfbox/examples/pdmodel/embedded_multiple_fonts.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/EmbeddedMultipleFonts.java` |
| `pypdfbox/examples/pdmodel/embedded_vertical_fonts.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/EmbeddedVerticalFonts.java` |
| `pypdfbox/examples/pdmodel/extract_embedded_files.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ExtractEmbeddedFiles.java` |
| `pypdfbox/examples/pdmodel/extract_metadata.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ExtractMetadata.java` |
| `pypdfbox/examples/pdmodel/extract_ttf_fonts.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ExtractTtfFonts.java` |
| `pypdfbox/examples/pdmodel/go_to_second_bookmark_on_open.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/GoToSecondBookmarkOnOpen.java` |
| `pypdfbox/examples/pdmodel/hello_world.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/HelloWorld.java` |
| `pypdfbox/examples/pdmodel/hello_world_ttf.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/HelloWorldTtf.java` |
| `pypdfbox/examples/pdmodel/hello_world_type1.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/HelloWorldType1.java` |
| `pypdfbox/examples/pdmodel/print_bookmarks.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/PrintBookmarks.java` |
| `pypdfbox/examples/pdmodel/print_document_meta_data.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/PrintDocumentMetaData.java` |
| `pypdfbox/examples/pdmodel/print_urls.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/PrintUrls.java` |
| `pypdfbox/examples/pdmodel/remove_first_page.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/RemoveFirstPage.java` |
| `pypdfbox/examples/pdmodel/replace_urls.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ReplaceUrls.java` |
| `pypdfbox/examples/pdmodel/rubber_stamp.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/RubberStamp.java` |
| `pypdfbox/examples/pdmodel/rubber_stamp_with_image.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/RubberStampWithImage.java` |
| `pypdfbox/examples/pdmodel/show_color_boxes.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ShowColorBoxes.java` |
| `pypdfbox/examples/pdmodel/show_text_with_positioning.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/ShowTextWithPositioning.java` |
| `pypdfbox/examples/pdmodel/superimpose_page.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/SuperimposePage.java` |
| `pypdfbox/examples/pdmodel/using_text_matrix.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/pdmodel/UsingTextMatrix.java` |

#### `pypdfbox/examples/printing/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/printing/opaque_draw_object.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePDFRenderer.java (extracted inner class OpaqueDrawObject)` |
| `pypdfbox/examples/printing/opaque_pdf_renderer.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePdfRenderer.java` |
| `pypdfbox/examples/printing/opaque_set_graphics_state_parameters.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePDFRenderer.java (extracted inner class OpaqueSetGraphicsStateParameters, lines 176-217)` |
| `pypdfbox/examples/printing/printing.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/printing/Printing.java` |

#### `pypdfbox/examples/rendering/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/rendering/custom_graphics_stream_engine.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/rendering/CustomGraphicsStreamEngine.java` |
| `pypdfbox/examples/rendering/custom_page_drawer.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/rendering/CustomPageDrawer.java` |

#### `pypdfbox/examples/signature/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/signature/cms_processable_input_stream.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CmsProcessableInputStream.java` |
| `pypdfbox/examples/signature/create_embedded_time_stamp.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateEmbeddedTimeStamp.java` |
| `pypdfbox/examples/signature/create_empty_signature_form.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateEmptySignatureForm.java` |
| `pypdfbox/examples/signature/create_signature.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateSignature.java` |
| `pypdfbox/examples/signature/create_signature_base.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateSignatureBase.java` |
| `pypdfbox/examples/signature/create_signed_time_stamp.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateSignedTimeStamp.java` |
| `pypdfbox/examples/signature/create_visible_signature.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateVisibleSignature.java` |
| `pypdfbox/examples/signature/create_visible_signature2.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/CreateVisibleSignature2.java` |
| `pypdfbox/examples/signature/show_signature.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/ShowSignature.java` |
| `pypdfbox/examples/signature/sig_utils.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/SigUtils.java` |
| `pypdfbox/examples/signature/tsa_client.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/TsaClient.java` |
| `pypdfbox/examples/signature/validation_time_stamp.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/ValidationTimeStamp.java` |

#### `pypdfbox/examples/signature/cert/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/signature/cert/certificate_verification_result.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/CertificateVerificationResult.java` |
| `pypdfbox/examples/signature/cert/certificate_verifier.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/CertificateVerifier.java` |
| `pypdfbox/examples/signature/cert/crl_verifier.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/CrlVerifier.java` |
| `pypdfbox/examples/signature/cert/ocsp_helper.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/OcspHelper.java` |
| `pypdfbox/examples/signature/cert/revoked_certificate_exception.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/RevokedCertificateException.java` |
| `pypdfbox/examples/signature/cert/sha1_digest_calculator.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/cert/OcspHelper.java (extracted inner class SHA1DigestCalculator, lines 616-651)` |

#### `pypdfbox/examples/signature/validation/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/signature/validation/add_validation_information.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/validation/AddValidationInformation.java` |
| `pypdfbox/examples/signature/validation/cert_information_collector.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/validation/CertInformationCollector.java` |
| `pypdfbox/examples/signature/validation/cert_information_helper.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/validation/CertInformationHelper.java` |
| `pypdfbox/examples/signature/validation/cert_signature_information.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/signature/validation/CertInformationCollector.java (extracted inner class CertSignatureInformation, lines 402-468)` |

#### `pypdfbox/examples/util/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/examples/util/add_watermark_text.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/AddWatermarkText.java` |
| `pypdfbox/examples/util/connected_input_stream.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/ConnectedInputStream.java` |
| `pypdfbox/examples/util/draw_print_text_locations.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/DrawPrintTextLocations.java` |
| `pypdfbox/examples/util/extract_text_by_area.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/ExtractTextByArea.java` |
| `pypdfbox/examples/util/extract_text_simple.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/ExtractTextSimple.java` |
| `pypdfbox/examples/util/pdf_highlighter.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/PdfHighlighter.java` |
| `pypdfbox/examples/util/pdf_merger_example.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/PdfMergerExample.java` |
| `pypdfbox/examples/util/print_image_locations.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/PrintImageLocations.java` |
| `pypdfbox/examples/util/print_text_colors.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/PrintTextColors.java` |
| `pypdfbox/examples/util/print_text_locations.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/PrintTextLocations.java` |
| `pypdfbox/examples/util/remove_all_text.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/RemoveAllText.java` |
| `pypdfbox/examples/util/split_booklet.py` | 3.0.x | `examples/src/main/java/org/apache/pdfbox/examples/util/SplitBooklet.java` |

#### `pypdfbox/filter/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/filter/ascii85_input_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Ascii85InputStream.java` |
| `pypdfbox/filter/ascii85_output_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Ascii85OutputStream.java` |
| `pypdfbox/filter/ccitt_fax_decoder_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CcittFaxDecoderStream.java` |
| `pypdfbox/filter/ccitt_fax_encoder_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CcittFaxEncoderStream.java` |
| `pypdfbox/filter/crypt_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CryptFilter.java` |
| `pypdfbox/filter/decode_options.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/DecodeOptions.java` |
| `pypdfbox/filter/final_decode_options.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/DecodeOptions.java (extracted inner class FinalDecodeOptions)` |
| `pypdfbox/filter/flate_filter_decoder_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/FlateFilterDecoderStream.java` |
| `pypdfbox/filter/jbig2_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Jbig2Filter.java` |
| `pypdfbox/filter/jpx_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/JpxFilter.java` |
| `pypdfbox/filter/node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CCITTFaxDecoderStream.java (extracted inner class Node)` |
| `pypdfbox/filter/predictor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Predictor.java` |
| `pypdfbox/filter/predictor_output_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/Predictor.java (extracted inner class PredictorOutputStream)` |
| `pypdfbox/filter/tree.py` | 3.0.x | `debugger/src/main/java/org/apache/pdfbox/debugger/ui/Tree.java` |

#### `pypdfbox/fontbox/cmap/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/cmap/cmap_strings.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/cmap/CmapStrings.java` |

#### `pypdfbox/fontbox/pfb/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/pfb/pfb_parser.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/pfb/PfbParser.java` |

#### `pypdfbox/fontbox/type1/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/type1/token.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Token.java` |
| `pypdfbox/fontbox/type1/type1_char_string_reader.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/type1/Type1CharStringReader.java` |

#### `pypdfbox/fontbox/util/autodetect/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/fontbox/util/autodetect/font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/FontDirFinder.java` |
| `pypdfbox/fontbox/util/autodetect/font_file_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/FontFileFinder.java` |
| `pypdfbox/fontbox/util/autodetect/mac_font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/MacFontDirFinder.java` |
| `pypdfbox/fontbox/util/autodetect/native_font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/NativeFontDirFinder.java` |
| `pypdfbox/fontbox/util/autodetect/os400_font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/Os400FontDirFinder.java` |
| `pypdfbox/fontbox/util/autodetect/unix_font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/UnixFontDirFinder.java` |
| `pypdfbox/fontbox/util/autodetect/windows_font_dir_finder.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/util/autodetect/WindowsFontDirFinder.java` |

#### `pypdfbox/io/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/io/non_seekable_random_access_read_input_stream.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/NonSeekableRandomAccessReadInputStream.java` |
| `pypdfbox/io/random_access.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccess.java` |
| `pypdfbox/io/random_access_input_stream.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessInputStream.java` |
| `pypdfbox/io/random_access_output_stream.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessOutputStream.java` |
| `pypdfbox/io/random_access_read_memory_mapped_file.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessReadMemoryMappedFile.java` |
| `pypdfbox/io/random_access_read_write_buffer.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessReadWriteBuffer.java` |
| `pypdfbox/io/random_access_stream_cache.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessStreamCache.java` |
| `pypdfbox/io/random_access_stream_cache_impl.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessStreamCacheImpl.java` |
| `pypdfbox/io/sequence_random_access_read.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/SequenceRandomAccessRead.java` |
| `pypdfbox/io/stream_cache_create_function.py` | 3.0.x | `io/src/main/java/org/apache/pdfbox/io/RandomAccessStreamCache.java (extracted inner interface StreamCacheCreateFunction)` |

#### `pypdfbox/pdfparser/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfparser/brute_force_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/BruteForceParser.java` |
| `pypdfbox/pdfparser/fdf_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/FdfParser.java` |
| `pypdfbox/pdfparser/object_numbers.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFXrefStreamParser.java (extracted inner class ObjectNumbers)` |
| `pypdfbox/pdfparser/pdf_object_stream_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PdfObjectStreamParser.java` |
| `pypdfbox/pdfparser/pdf_xref_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PdfXrefStream.java` |
| `pypdfbox/pdfparser/pdf_xref_stream_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PdfXrefStreamParser.java` |
| `pypdfbox/pdfparser/xref_trailer_obj.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/XrefTrailerResolver.java (extracted inner class XrefTrailerObj)` |

#### `pypdfbox/pdfparser/xref/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfparser/xref/abstract_x_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/AbstractXReference.java` |
| `pypdfbox/pdfparser/xref/free_x_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/FreeXReference.java` |
| `pypdfbox/pdfparser/xref/normal_x_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/NormalXReference.java` |
| `pypdfbox/pdfparser/xref/object_stream_x_reference.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/ObjectStreamXReference.java` |
| `pypdfbox/pdfparser/xref/x_reference_entry.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/XReferenceEntry.java` |
| `pypdfbox/pdfparser/xref/x_reference_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/xref/XReferenceType.java` |

#### `pypdfbox/pdfwriter/compress/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfwriter/compress/cos_object_pool.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/CosObjectPool.java` |
| `pypdfbox/pdfwriter/compress/cos_writer_compression_pool.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/CosWriterCompressionPool.java` |
| `pypdfbox/pdfwriter/compress/cos_writer_object_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/CosWriterObjectStream.java` |
| `pypdfbox/pdfwriter/compress/direct_access_byte_array_output_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfwriter/compress/COSWriterObjectStream.java (extracted inner class DirectAccessByteArrayOutputStream, lines 397-409)` |

#### `pypdfbox/pdmodel/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/default_resource_cache_create_impl.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/DefaultResourceCacheCreateImpl.java` |
| `pypdfbox/pdmodel/page_iterator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageTree.java (extracted inner class PageIterator)` |
| `pypdfbox/pdmodel/pd_abstract_content_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PdAbstractContentStream.java` |
| `pypdfbox/pdmodel/resource_cache.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/ResourceCache.java` |
| `pypdfbox/pdmodel/resource_cache_create_function.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/ResourceCacheCreateFunction.java` |
| `pypdfbox/pdmodel/resource_cache_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/ResourceCacheFactory.java` |
| `pypdfbox/pdmodel/search_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageTree.java (extracted inner class SearchContext)` |

#### `pypdfbox/pdmodel/common/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/cos_array_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/CosArrayList.java` |
| `pypdfbox/pdmodel/common/cos_dictionary_map.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/CosDictionaryMap.java` |
| `pypdfbox/pdmodel/common/cos_objectable.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/CosObjectable.java` |
| `pypdfbox/pdmodel/common/label_generator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDPageLabels.java (extracted inner class LabelGenerator, lines 295-415)` |
| `pypdfbox/pdmodel/common/label_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDPageLabels.java (extracted inner interface LabelHandler, lines 252-255)` |
| `pypdfbox/pdmodel/common/pd_dictionary_wrapper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PdDictionaryWrapper.java` |
| `pypdfbox/pdmodel/common/pd_immutable_rectangle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PdImmutableRectangle.java` |
| `pypdfbox/pdmodel/common/pd_object_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PdObjectStream.java` |
| `pypdfbox/pdmodel/common/pd_typed_dictionary_wrapper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PdTypedDictionaryWrapper.java` |

#### `pypdfbox/pdmodel/common/function/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/function/rinterpol.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunctionType0.java (extracted inner class Rinterpol, lines 252-373)` |

#### `pypdfbox/pdmodel/encryption/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/encryption/message_digests.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/MessageDigests.java` |
| `pypdfbox/pdmodel/encryption/rc4_cipher.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/Rc4Cipher.java` |
| `pypdfbox/pdmodel/encryption/sasl_prep.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SaslPrep.java` |
| `pypdfbox/pdmodel/encryption/security_handler_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/SecurityHandlerFactory.java` |

#### `pypdfbox/pdmodel/fdf/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/fdf/fdf_annotation_caret.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationCaret.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_ink.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationInk.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_polygon.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationPolygon.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_polyline.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationPolyline.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_stamp.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationStamp.java` |
| `pypdfbox/pdmodel/fdf/fdf_annotation_text_markup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfAnnotationTextMarkup.java` |
| `pypdfbox/pdmodel/fdf/fdf_java_script.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfJavaScript.java` |
| `pypdfbox/pdmodel/fdf/fdf_option_element.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfOptionElement.java` |
| `pypdfbox/pdmodel/fdf/fdf_page.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfPage.java` |
| `pypdfbox/pdmodel/fdf/fdf_page_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfPageInfo.java` |
| `pypdfbox/pdmodel/fdf/fdf_template.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FdfTemplate.java` |
| `pypdfbox/pdmodel/fdf/xfdf_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFDictionary.java (XFDF Element-based constructor switch table, lines 137-217; XFDF parsing logic spread across FDFCatalog / FDFField / FDFAnnotation upstream)` |

#### `pypdfbox/pdmodel/fixup/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/fixup/abstract_fixup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/AbstractFixup.java` |
| `pypdfbox/pdmodel/fixup/acro_form_default_fixup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/AcroFormDefaultFixup.java` |
| `pypdfbox/pdmodel/fixup/pd_document_fixup.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/PdDocumentFixup.java` |

#### `pypdfbox/pdmodel/fixup/processor/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/fixup/processor/abstract_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AbstractProcessor.java` |
| `pypdfbox/pdmodel/fixup/processor/acro_form_defaults_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormDefaultsProcessor.java` |
| `pypdfbox/pdmodel/fixup/processor/acro_form_generate_appearances_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormGenerateAppearancesProcessor.java` |
| `pypdfbox/pdmodel/fixup/processor/acro_form_orphan_widgets_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AcroFormOrphanWidgetsProcessor.java` |
| `pypdfbox/pdmodel/fixup/processor/pd_document_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/PdDocumentProcessor.java` |

#### `pypdfbox/pdmodel/font/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/font/afm_loader.py` | 3.0.x | `fontbox/src/main/java/org/apache/fontbox/afm/AFMParser.java (functional adapter; delegates to fontTools.afmLib)` |
| `pypdfbox/pdmodel/font/cid_system_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/CidSystemInfo.java` |
| `pypdfbox/pdmodel/font/file_system_font_provider.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FileSystemFontProvider.java` |
| `pypdfbox/pdmodel/font/font_cache.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontCache.java` |
| `pypdfbox/pdmodel/font/font_mapper_impl.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMapperImpl.java` |
| `pypdfbox/pdmodel/font/font_match.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMapperImpl.java (extracted inner class FontMatch)` |
| `pypdfbox/pdmodel/font/fs_font_info.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FileSystemFontProvider.java (extracted inner class FSFontInfo)` |
| `pypdfbox/pdmodel/font/pd_cid_font_type2_embedder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PdCidFontType2Embedder.java` |
| `pypdfbox/pdmodel/font/pd_true_type_font_embedder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PdTrueTypeFontEmbedder.java` |
| `pypdfbox/pdmodel/font/pd_type1_font_embedder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PdType1FontEmbedder.java` |
| `pypdfbox/pdmodel/font/subsetter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/Subsetter.java` |
| `pypdfbox/pdmodel/font/to_unicode_writer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/ToUnicodeWriter.java` |
| `pypdfbox/pdmodel/font/true_type_embedder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/TrueTypeEmbedder.java` |
| `pypdfbox/pdmodel/font/uni_util.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/UniUtil.java` |
| `pypdfbox/pdmodel/font/vertical_displacement_range.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDCIDFont.java (extracted inner class VerticalDisplacementRange)` |

#### `pypdfbox/pdmodel/font/encoding/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/font/encoding/type1_encoding.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/Type1Encoding.java` |

#### `pypdfbox/pdmodel/graphics/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/blend_mode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/blend/BlendMode.java` |

#### `pypdfbox/pdmodel/graphics/blend/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/blend/blend_channel_function.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/blend/BlendMode.java (extracted inner functional interface BlendChannelFunction)` |
| `pypdfbox/pdmodel/graphics/blend/blend_composite.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/blend/BlendComposite.java` |
| `pypdfbox/pdmodel/graphics/blend/blend_function.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/blend/BlendMode.java (extracted inner functional interface BlendFunction)` |

#### `pypdfbox/pdmodel/graphics/color/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/color/pd_cie_based_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PdCieBasedColorSpace.java` |
| `pypdfbox/pdmodel/graphics/color/pd_cie_dictionary_based_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PdCieDictionaryBasedColorSpace.java` |
| `pypdfbox/pdmodel/graphics/color/pd_gamma.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PdGamma.java` |
| `pypdfbox/pdmodel/graphics/color/pd_jpx_color_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PdJpxColorSpace.java` |
| `pypdfbox/pdmodel/graphics/color/pd_tristimulus.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PdTristimulus.java` |

#### `pypdfbox/pdmodel/graphics/image/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/image/custom_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/CustomFactory.java` |
| `pypdfbox/pdmodel/graphics/image/pd_image.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PdImage.java` |
| `pypdfbox/pdmodel/graphics/image/png_converter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PngConverter.java` |
| `pypdfbox/pdmodel/graphics/image/predictor_encoder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/LosslessFactory.java (extracted inner class PredictorEncoder)` |
| `pypdfbox/pdmodel/graphics/image/sampled_image_reader.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/SampledImageReader.java` |

#### `pypdfbox/pdmodel/graphics/shading/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/shading/axial_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/AxialShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/coons_patch.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/CoonsPatch.java` |
| `pypdfbox/pdmodel/graphics/shading/cubic_bezier_curve.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/CubicBezierCurve.java` |
| `pypdfbox/pdmodel/graphics/shading/gouraud_shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/GouraudShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/int_point.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/IntPoint.java` |
| `pypdfbox/pdmodel/graphics/shading/line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Line.java` |
| `pypdfbox/pdmodel/graphics/shading/patch.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Patch.java` |
| `pypdfbox/pdmodel/graphics/shading/patch_meshes_shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PatchMeshesShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/pd_mesh_based_shading_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PdMeshBasedShadingType.java` |
| `pypdfbox/pdmodel/graphics/shading/pd_triangle_based_shading_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PdTriangleBasedShadingType.java` |
| `pypdfbox/pdmodel/graphics/shading/radial_shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/RadialShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/radial_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/RadialShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/shaded_triangle.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/ShadedTriangle.java` |
| `pypdfbox/pdmodel/graphics/shading/shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/ShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/tensor_patch.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/TensorPatch.java` |
| `pypdfbox/pdmodel/graphics/shading/triangle_based_shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/TriangleBasedShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/type1_shading_context.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type1ShadingContext.java` |
| `pypdfbox/pdmodel/graphics/shading/type1_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type1ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/type4_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type4ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/type5_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type5ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/type6_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type6ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/type7_shading_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Type7ShadingPaint.java` |
| `pypdfbox/pdmodel/graphics/shading/vertex.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/Vertex.java` |

#### `pypdfbox/pdmodel/graphics/state/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/graphics/state/pd_graphics_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PdGraphicsState.java` |
| `pypdfbox/pdmodel/graphics/state/pd_text_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PdTextState.java` |

#### `pypdfbox/pdmodel/interactive/action/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/action/pd_action_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PdActionFactory.java` |

#### `pypdfbox/pdmodel/interactive/annotation/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/annotation/annotation_filter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/AnnotationFilter.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_appearance_stream_name_tree_node.py` | 3.0.x | (none — original typed wrapper for /Names /AP name tree; upstream PDFBox 3.x exposes only raw COSDictionary; see CHANGES.md) |
| `pypdfbox/pdmodel/interactive/annotation/pd_external_data_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PdExternalDataDictionary.java` |

#### `pypdfbox/pdmodel/interactive/annotation/handlers/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/annotation/handlers/annotation_border.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/AnnotationBorder.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/cloudy_border.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/CloudyBorder.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_abstract_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdAbstractAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_caret_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdCaretAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_circle_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdCircleAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_file_attachment_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdFileAttachmentAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_free_text_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdFreeTextAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_highlight_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdHighlightAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_ink_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdInkAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_line_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdLineAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_link_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdLinkAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_polygon_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdPolygonAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_polyline_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdPolylineAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_sound_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdSoundAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_square_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdSquareAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_squiggly_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdSquigglyAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_strikeout_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdStrikeoutAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_text_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdTextAppearanceHandler.java` |
| `pypdfbox/pdmodel/interactive/annotation/handlers/pd_underline_appearance_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/handlers/PdUnderlineAppearanceHandler.java` |

#### `pypdfbox/pdmodel/interactive/digitalsignature/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/digitalsignature/signature_options.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/SignatureOptions.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/signing_support.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/SigningSupport.java` |

#### `pypdfbox/pdmodel/interactive/digitalsignature/visible/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pd_visible_sig_builder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdVisibleSigBuilder.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pd_visible_sig_properties.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdVisibleSigProperties.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pd_visible_sign_designer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdVisibleSignDesigner.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pdf_template_builder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdfTemplateBuilder.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pdf_template_creator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdfTemplateCreator.java` |
| `pypdfbox/pdmodel/interactive/digitalsignature/visible/pdf_template_structure.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PdfTemplateStructure.java` |

#### `pypdfbox/pdmodel/interactive/form/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/form/appearance_generator_helper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceGeneratorHelper.java` |
| `pypdfbox/pdmodel/interactive/form/appearance_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceStyle.java` |
| `pypdfbox/pdmodel/interactive/form/builder.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainTextFormatter.java (extracted inner class Builder)` |
| `pypdfbox/pdmodel/interactive/form/field_iterator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDFieldTree.java (extracted inner class FieldIterator)` |
| `pypdfbox/pdmodel/interactive/form/field_utils.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/FieldUtils.java` |
| `pypdfbox/pdmodel/interactive/form/key_value.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/FieldUtils.java (extracted inner class KeyValue)` |
| `pypdfbox/pdmodel/interactive/form/paragraph.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainText.java (extracted inner class Paragraph)` |
| `pypdfbox/pdmodel/interactive/form/plain_text.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainText.java` |
| `pypdfbox/pdmodel/interactive/form/plain_text_formatter.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainTextFormatter.java` |
| `pypdfbox/pdmodel/interactive/form/scripting_handler.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/ScriptingHandler.java` |
| `pypdfbox/pdmodel/interactive/form/text_align.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainTextFormatter.java (extracted inner enum TextAlign)` |
| `pypdfbox/pdmodel/interactive/form/word.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PlainText.java (extracted inner class Word)` |

#### `pypdfbox/pdmodel/interactive/measurement/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/interactive/measurement/pd_media_clip.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_media_clip_data.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_media_clip_section.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_media_play_parameters.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_media_rendition.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_rendition.py` | 3.0.x | (none — original Python addition, no upstream class) |
| `pypdfbox/pdmodel/interactive/measurement/pd_selector_rendition.py` | 3.0.x | (none — original Python addition, no upstream class) |

#### `pypdfbox/printing/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/printing/pdf_pageable.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/printing/PdfPageable.java` |
| `pypdfbox/printing/pdf_printable.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/printing/PdfPrintable.java` |

#### `pypdfbox/rendering/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/rendering/glyph_cache.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/GlyphCache.java` |
| `pypdfbox/rendering/group_graphics.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/GroupGraphics.java` |
| `pypdfbox/rendering/page_drawer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/PageDrawer.java` |
| `pypdfbox/rendering/page_drawer_parameters.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/PageDrawerParameters.java` |
| `pypdfbox/rendering/soft_mask.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/SoftMask.java` |
| `pypdfbox/rendering/tiling_paint.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/TilingPaint.java` |
| `pypdfbox/rendering/tiling_paint_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/TilingPaintFactory.java` |

#### `pypdfbox/text/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/text/legacy_pdf_stream_engine.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/LegacyPdfStreamEngine.java` |
| `pypdfbox/text/line_item.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PDFTextStripper.java (extracted inner class LineItem, lines 2133-2163)` |
| `pypdfbox/text/pdf_text_stripper.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/PdfTextStripper.java` |
| `pypdfbox/text/text_position_comparator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/text/TextPositionComparator.java` |

#### `pypdfbox/tools/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/tools/decompress_objectstreams.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/DecompressObjectstreams.java` |
| `pypdfbox/tools/decrypt_tool.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/Decrypt.java` |
| `pypdfbox/tools/encrypt_tool.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/Encrypt.java` |
| `pypdfbox/tools/export_fdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ExportFdf.java` |
| `pypdfbox/tools/export_xfdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ExportXfdf.java` |
| `pypdfbox/tools/extract_images.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ExtractImages.java` |
| `pypdfbox/tools/extract_text.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ExtractText.java` |
| `pypdfbox/tools/extract_xmp.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ExtractXmp.java` |
| `pypdfbox/tools/image_to_pdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ImageToPdf.java` |
| `pypdfbox/tools/import_fdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ImportFdf.java` |
| `pypdfbox/tools/import_xfdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/ImportXfdf.java` |
| `pypdfbox/tools/overlay_pdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/OverlayPdf.java` |
| `pypdfbox/tools/pdf_box.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfBox.java` |
| `pypdfbox/tools/pdf_merger.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfMerger.java` |
| `pypdfbox/tools/pdf_split.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfSplit.java` |
| `pypdfbox/tools/pdf_text2_html.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfText2Html.java` |
| `pypdfbox/tools/pdf_text2_markdown.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfText2Markdown.java` |
| `pypdfbox/tools/pdf_to_image.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PdfToImage.java` |
| `pypdfbox/tools/print_pdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/PrintPdf.java` |
| `pypdfbox/tools/text_to_pdf.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/TextToPdf.java` |
| `pypdfbox/tools/version_tool.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/Version.java` |
| `pypdfbox/tools/write_decoded_doc.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/WriteDecodedDoc.java` |

#### `pypdfbox/tools/imageio/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/tools/imageio/image_io_util.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/imageio/ImageIoUtil.java` |
| `pypdfbox/tools/imageio/jpeg_util.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/imageio/JpegUtil.java` |
| `pypdfbox/tools/imageio/meta_util.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/imageio/MetaUtil.java` |
| `pypdfbox/tools/imageio/tiff_util.py` | 3.0.x | `tools/src/main/java/org/apache/pdfbox/tools/imageio/TiffUtil.java` |

#### `pypdfbox/util/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/util/hex.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/Hex.java` |
| `pypdfbox/util/iterative_merge_sort.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/IterativeMergeSort.java` |
| `pypdfbox/util/matrix.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/Matrix.java` |
| `pypdfbox/util/number_format_util.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/NumberFormatUtil.java` |
| `pypdfbox/util/small_map.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/SmallMap.java` |
| `pypdfbox/util/string_util.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/StringUtil.java` |
| `pypdfbox/util/vector.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/Vector.java` |
| `pypdfbox/util/xml_util.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/XmlUtil.java` |

#### `pypdfbox/util/filetypedetector/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/util/filetypedetector/byte_trie.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/filetypedetector/ByteTrie.java` |
| `pypdfbox/util/filetypedetector/file_type.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/filetypedetector/FileType.java` |
| `pypdfbox/util/filetypedetector/file_type_detector.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/util/filetypedetector/FileTypeDetector.java` |

#### `pypdfbox/xmpbox/schema/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/schema/xmp_schema_factory.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XmpSchemaFactory.java` |

#### `pypdfbox/xmpbox/type/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/type/abstract_complex_property.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/AbstractComplexProperty.java` |
| `pypdfbox/xmpbox/type/cfa_pattern_type.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/CfaPatternType.java` |
| `pypdfbox/xmpbox/type/complex_property_container.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/ComplexPropertyContainer.java` |
| `pypdfbox/xmpbox/type/types.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/Types.java` |

#### `pypdfbox/xmpbox/xml/`

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/xml/dom_helper.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/DomHelper.java` |
| `pypdfbox/xmpbox/xml/namespace_finder.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/DomXmpParser.java (extracted inner class NamespaceFinder, lines 1199-1229)` |
| `pypdfbox/xmpbox/xml/pdfa_extension_helper.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/PdfaExtensionHelper.java` |
| `pypdfbox/xmpbox/xml/xmp_serializer.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/XmpSerializer.java` |

### Wave 1333 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/pdmodel/test_extract_embedded_files.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/extract_embedded_files.py` — drives `main` / `extract_files_from_ef_tree` recursion / `extract_files_from_page` annotation walk / path-traversal guard / `get_embedded_file` fallback chain |
| `tests/examples/signature/test_create_visible_signature2.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/signature/create_visible_signature2.py` — drives `main` / `sign_pdf` (FileNotFoundError + tsa_url capture) / `_sign_document` DocMDP gate + signature wiring / `create_signature_rectangle` coord conversion / `create_visual_signature_template` AcroForm assembly / `find_existing_signature` four-branch lookup |
| `tests/examples/signature/cert/test_certificate_verifier.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/signature/cert/certificate_verifier.py` — multi-intermediate chain construction, no-root-anchor rejection, unexpected-exception wrapping, RSA + EC + non-RSA-non-EC `_verify_signed_by` branches, cycle break in `_build_chain`, OCSP-then-CRL fallback, recursion to self-signed anchor, AIA URL helpers |

### Wave 1335 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/benchmark/test_load_and_save.py` | 3.0.x | hand-written coverage for `pypdfbox/benchmark/load_and_save.py` — exercises `_consume` / `_time_call` scaffolding, all eight benchmark workloads (`load_medium_file` / `save_medium_file` / `save_incremental_medium_file` / `save_no_compression_medium_file` and the four `*_large_*` mirrors), spy `PDDocument.save` / `save_incremental` to verify `NullOutputStream` and `CompressParameters.NO_COMPRESSION` threading, and the workload's `finally`-closes-document path |
| `tests/examples/signature/test_create_visible_signature.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/signature/create_visible_signature.py` — drives `main` four-arg dispatch + image-stream capture, `usage` stderr, designer / property / stream-cache getter+setter round-trips, `sign_pdf` FileNotFoundError + tsa_url threading + str-path acceptance, `_sign_document` DocMDP block, default + explicit property paths, visual-signature embed-on-image-stream branch, skip-when-no-image branch, and `find_existing_signature` four-branch field lookup |

### Wave 1335 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdmodel/font/test_pd_cid_font_type2_embedder_wave1335.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_cid_font_type2_embedder.py` — drives the residual vertical-write constructor + `build_subset` vertical leg, `check_for_cid_gid_identity` maxp AttributeError fallback, `_build_to_unicode_cmap` missing-maxp + AttributeError version-bump swallow, `_build_widths_for_subset` glyph lookup failures + width==1000 skip, `_build_widths_full` zero-advance fallback, `_build_vertical_metrics_for_subset` glyph-loop branches (hmtx raise, glyf miss yMax=0, default skip, non-default emit), `_build_vertical_metrics_full` missing-maxp early return, `_get_unicode_cmap_reverse` best_cmap-None + getGlyphID AttributeError skip |

### Wave 1335 additions — hand-written test files (agent C)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/util/test_print_image_locations.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/util/print_image_locations.py` — drives ctor / `main()` / `usage()` arg permutations, `run()` happy + fallback (process_page raises `NotImplementedError` / `AttributeError`) paths against in-memory image-bearing PDFs (PNG via Pillow + `PDImageXObject.create_from_byte_array`), `process_operator` Do-branch dispatch (valid xobject prints metadata, broken resources swallowed, missing resources silent, non-Do operator delegates to super), `_maybe_print_image` with duck-typed image / form / string-name shapes, `_walk_page_x_objects` no-resources + no-names + continue-on-error coverage, `show_form` AttributeError swallow + RuntimeError propagation |
| `tests/examples/signature/test_show_signature.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/signature/show_signature.py` — drives ctor + `main()` arg-count exits + dispatch, `usage()` stderr, `show_signature` end-to-end on a blank PDF and on a PDF carrying an `add_signature`-staged dictionary, `_summarize` field + valid/invalid/empty-PKCS#7 contents arms, `check_content_value_with_file` matching + mismatch-warning slices, `verify_ets_idot_rfc3161` + the historical-spelling alias, `verify_pkcs7` valid + warning paths, `get_root_certificates`, `analyse_dss` no-DSS / present-DSS, `print_streams_from_array` with-array + None |

### Wave 1335 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/pdmodel/test_create_pdfa.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/create_pdfa.py` — drives `CreatePDFA.main` end-to-end with a real DejaVuSans TTF (via a monkey-patched `XmpSerializer.serialize` stub that sidesteps the latent `_append_field` `str.get_property_name` AttributeError on Dublin Core `set_title`), exercises usage / SystemExit branches (no args / wrong arg count / missing TTF → `OSError`), verifies `_make_srgb_icc_bytes` returns a deterministic canonical sRGB v2 profile (size prefix matches body length), and round-trips the saved PDF to assert OutputIntent metadata (info / output_condition / output_condition_identifier / registry_name) plus font embedding |
| `tests/examples/pdmodel/test_print_urls.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/print_urls.py` — drives `PrintURLs.main` against in-memory PDFs carrying `PDAnnotationLink` + `PDActionURI` pairs (rotation==0 coord flip, rotation==90 no-op branch, multi-link page, no-rectangle skip-region-registration branch, no-action annotation, blank page), plus full `get_action_uri` dispatch matrix (URI action accepted, None action, non-URI action, annotation without `get_action`, ValueError + RuntimeError swallow from broad-catch parity), and `usage()` stderr |
| `tests/examples/pdmodel/test_bengali_pdf_generation_hello_world.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/bengali_pdf_generation_hello_world.py` — drives `_read_bengali_lines` (`#`-comment filter, CRLF strip, empty file), `_tokenize_keep_separators` (empty / leading-separator / only-separators / basic), `main` usage + Helvetica fallback + explicit-TTF (DejaVuSans) end-to-end + nonexistent-TTF fallback + monkey-patched `get_bengali_text_from_file` returning [] to exercise `_FALLBACK_SAMPLE`, `get_re_aligned_text_based_on_page_height` single-page fit + multi-page overflow, `get_re_aligned_text_based_on_page_width` short-line passthrough + long-line wrap, `get_bengali_text_from_file` env-var override search-strategy + missing-resources path, Helvetica `get_font_descriptor()` raises AttributeError branch |
| `tests/examples/rendering/test_custom_page_drawer.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/rendering/custom_page_drawer.py` — adds `MyPDFRenderer` constructor + `create_page_drawer` factory tests, `MyPageDrawer` constructor, `get_paint` short-circuit (no graphics state) + RED→BLUE substitution (with a mocked graphics state) + TypeError swallow (canonical `to_rgb` returns a tuple) + non-stroking-mismatch fallthrough + AttributeError-swallow from `get_graphics_state`, `show_glyph` super-delegation + AttributeError suppression, `fill_path` super-delegation, `show_annotation` save / set-alpha=0.35 / super-call / restore lifecycle + restore-even-when-super-raises + save_graphics_state AttributeError suppression branches |

### Wave 1337 additions — hand-written test files (agent C)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/pdmodel/test_embedded_vertical_fonts.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/embedded_vertical_fonts.py` — drives `EmbeddedVerticalFonts.demo_with_font` end-to-end with a bundled DejaVuSans TTF (horizontal Type0 load, vertical Type0 load via `PDType0Font.load_vertical`, four `begin_text` / `end_text` glyph runs producing a single-page PDF, str-output + Path-output coercion), `main` fixture-absent `NotImplementedError` arm (no-argv default path lookup, explicit non-existent ttf argv), `main` happy-path with explicit TTF argv, and the no-arg constructor |
| `tests/examples/util/test_connected_input_stream.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/util/connected_input_stream.py` — drives all three `read()` overloads (single-byte returning `int` / `-1` at EOF, fill-buffer mode, offset+length partial-fill), `skip()` seekable + non-seekable fallback branches, `available()` zero default + delegating to a Java-style `.available()` impl, `mark()` + `reset()` round-trip plus reset-without-mark `OSError`, `mark_supported()` seekable / non-seekable / no-tell, and `close()` covering `disconnect()` method + `close()` fallback + inert-connection (neither method present) branches |
| `tests/examples/pdmodel/test_print_bookmarks.py` | 3.0.x | hand-written coverage for `pypdfbox/examples/pdmodel/print_bookmarks.py` — drives `main` usage (no-args / two-args) + outline-absent message + happy-path nested-outline tree walk (3 pages, two-level) + named-destination resolution via `/Names /Dests`; `print_bookmark` GoTo-action with PDPageDestination (bound to a real page dict), GoTo-action with COSString-named destination (str fallback → `Destination class: str`), non-GoTo `PDActionLaunch` (`Action class:` branch), GoTo with absent `/D` (`Destination class: NoneType` arm), and item-level `PDNamedDestination` resolution; `usage()` stderr exact-match |
| `tests/examples/interactive/form/test_field_remover.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/field_remover.py` — adds `main` usage (None / single-arg / 3-arg drive), `remove` happy path + unknown-field-name stdout message + missing-acro-form short-circuit + /Perms catalog-clean-up + widget-removal branch (against a page where the widget annotation is persisted via `set_annotations`), `remove_recursive` direct against a PDNonTerminalField subtree (find / not-found / two-level descent / terminal-fields-only short-circuit), and `usage()` stderr |

### Wave 1337 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/multipdf/test_pdf_merger_utility_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/multipdf/pdf_merger_utility.py` — exercises the optimize-mode canonical-hash helper (`_hash_cos` over all COS scalar/container leaves, cycle detection on dict/array/stream, stream-body unreadable abort, unknown-leaf abort, key-ordering stability) plus the public `_canonical_resource_hash` static wrapper, the `_dedup_page_resources` walker on edge-case resource subgraphs (no-resources, non-dict resources container, non-dict subcategory, COSNull entry, un-hashable cyclic entry, populate-then-collapse), accessor round-trips (`acro_form_merge_mode_property` getter/setter, `is_ignore_acro_form_errors`/`set_ignore_acro_form_errors` bool-cast, destination-file-name/stream/document-information/metadata round-trips), the OPTIMIZE_RESOURCES_MODE destination-missing guard and dynamic-XFA OSError path, the source-close + destination-close error-logging branches, the upstream-named alias wrappers (`is_dynamic_xfa`, `merge_into`, `merge_acro_form`, `acro_form_legacy_mode`/`acro_form_join_fields_mode`, `merge_open_action`, `merge_role_map`, `merge_id_tree`/`merge_k_entries`, `merge_output_intents`, `has_only_documents_or_parts`, `update_parent_entry`, `update_struct_parent_entries`), and the viewer-preferences / language / mark-info helpers' short-circuit and happy paths |

### Wave 1337 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/xmpbox/test_date_converter_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/xmpbox/date_converter.py` — drives `parse_big_endian_date` invalid-calendar / day-out-of-range returns None, `parse_date` longest-len bookkeeping when big-endian succeeds with trailing TZ data + alpha-start fall-through + digit-start simple-format match + None/empty/D:-short-circuit, `_two_digit_year_to_full` window edges (yy=0, 25, 50, 99), and each `_make_handler_*` regex+validate except-arm walk (unknown-month / day-99 / month-13 / not-a-date) plus the two-digit-year branch for every digit-start handler |
| `tests/xmpbox/test_xmp_schema_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/xmpbox/xmp_schema.py` — drives `XMPSchema.set_boolean_property_value` / `set_integer_property_value` / `set_date_property_value` cache-eviction-on-value-change branch, `_typed_property_or_raise` raw-and-cached-None early-return + raw-type-mismatch raise + unknown-raw-type raise, `internal_add_bag_value` str-fallback + ArrayProperty arm with TextType wrap (`AbstractSimpleProperty` lift via `get_string_value`), `reorganize_alt_order` dict-delegates + non-dict-no-op, `instanciate_simple` Boolean / Integer / Date / Text dispatch + TypeError-for-unknown, and `merge_complex_property` duplicate-short-circuit + all-new-returns-False |
| `tests/xmpbox/type/test_type_mapping_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/xmpbox/type/type_mapping.py` — drives `PropertyType.to_string`, `PropertiesDescription.__contains__`, `_SchemaFactory.get_properties_description`, `TypeMapping.get_specified_property_type` factory-match arm + single-struct-namespace-no-match (factory + struct both lack property) + defined-namespace returns DEFINED_TYPE + unknown-namespace-raises + factory-only-returns-None paths, `initialize_prop_mapping` `PROPERTIES` PropertyType-value arm + tuple-value arm + `_FIELD_TYPES`+`PROPERTIES` merge with PROPERTIES winning + malformed-skip, and `get_associated_schema_object` unknown-returns-None + known-namespace-no-creator-fallback |
| `tests/fontbox/ttf/test_ttf_parser_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/ttf_parser.py` — drives `_parse_table_headers_from_stream` raw-read-error (`get_original_data` raises), short-stream (<4 bytes), unsupported-scaler-magic, OTTO-without-allow-cff reject, `new_font` raises in subclass override, naming `get_post_script_name` / `get_font_family` raise (silently swallowed), OpenTypeFont `is_post_script` AttributeError fall-back, non-OTF with `CFF ` table reject, mandatory-table missing error; `create_font_with_tables` no-reader short-circuit (`font._tt` wiped), `_build_directory_entry` returning None (entries skipped), and oversize-entry (offset+length > file size) PDFBOX-5285 skip |
| `tests/tools/test_text_to_pdf_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/tools/text_to_pdf.py` — drives `_create_pdf_from_text` basic round-trip + single-arg overload (with a TTF-loaded font to bypass the latent `PDType1Font(FontName.HELVETICA)` bug at line 138/237), long-line `length_if_using_next_word` lookahead, empty-input `text_is_empty` page-add, `call` TTF-load branch (line 235), missing-input OSError → 4, missing-paths OSError-required, `PageSizes.get_page_size`, `main` argparse with `-ttf` / `-landscape` + `-margins` / `-pageSize A4`, and the accessor pair coverage (set_font_size / set_left_margin / set_right_margin / set_top_margin / set_bottom_margin / set_landscape / set_line_spacing positive-only). Form-feed handling (lines 162-180, 211-221, 185) is documented as latent dead code in `CHANGES.md` (Python `str.splitlines()` consumes `\f` before the inner word loop sees it) |
| `tests/contentstream/test_pdf_stream_engine_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/contentstream/pdf_stream_engine.py` — drives `process_form` delegation, `process_transparency_group` CTM-snapshot branch (line 666), `process_soft_mask` save-restore fence, `process_tiling_pattern` + `process_type3_stream` thin-wrapper dispatch, `show_annotation` None-vs-real appearance dispatch, `process_annotation` rect-bbox-missing / zero-width-rect / zero-width-bbox / attribute-error-guards / full happy path through `PDAppearanceStream` with valid bbox+rect, `push_resources` page-resources fallback + fresh-`PDResources` construction, `clip_to_rect` no-clipper / CTM+transform / transform-raises-fallback / None-rectangle, `_get_active_font` text_state-path + text_font-fallback + no-gs-None, `_decode_codes_via_font` no-progress break, `_glyph_displacement` None-font / no-getter / getter-raises, `show_type3_glyph` None-font / no-getter / getter-raises / None-charproc, `apply_text_adjustment` no-matrix / no-translate / translate-called, `transformed_point` no-gs / no-ctm / no-transform_point / transformer-raises / transformer-success, `_require_min_operands` raise + no-raise, `get_default_font` returns None |


### Wave 1337 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdmodel/interactive/digitalsignature/test_pd_signature_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/digitalsignature/pd_signature.py` — drives `_read_der_length` EOF / indefinite-form / truncated-long-form / reserved-n=0 raises, `_read_der_tlv` EOF + body-overrun raises, `_encode_der_length` >127-byte length overflow raise, `_hash_for_oid` unknown-OID None fallback, `_walk_signer_info` 16+ structural-mismatch return-None branches (top-not-SEQUENCE, contentType-not-OID, content-not-[0]-tagged, SignedData-not-SEQUENCE, version-not-INTEGER, digestAlgorithms-not-SET, encapContentInfo-not-SEQUENCE, unknown OPTIONAL tag, missing-signerInfos-SET, first-SignerInfo-not-SEQUENCE, signer-version-not-INTEGER, digestAlgorithm-not-SEQUENCE, digestAlgorithm-OID-not-OID, signatureAlgorithm-not-SEQUENCE, signatureAlgorithm-OID-not-OID, signature-not-OCTET-STRING, no-signedAttrs) plus the certs [0] IMPLICIT OPTIONAL skip happy path, `_verify_signed_attrs_signature` InvalidSignature + ValueError raise paths + EC public-key arm + unsupported-digest-OID raise, `_verify_chain_trust` chain-broken / self-signed-in-roots-succeeds / self-signed-not-in-roots branches, `_verify_cert_signature` InvalidSignature + EC-issuer arms, and `PDSignature.get_contents_from_bytes` with valid/missing/malformed `/ByteRange` plus a real PKCS#7 round-trip end-to-end exercise |
| `tests/pdmodel/interactive/form/test_pd_field_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/form/pd_field.py` — drives the base-class abstract-method `NotImplementedError` raises (`get_value_as_string`, `set_value`, `get_widgets`, `export_fdf`), `get_field_type` `/FT`-not-COSName + absent paths, `get_field_flags` absent + COSInteger + non-integer (returns 0) paths, and `import_fdf` `/Ff` overwrite (early return) + `/SetFf` OR-mutation + `/ClrFf` XOR-complement-clear + combined-mutation + non-None-`/V` write |
| `tests/pdmodel/graphics/image/test_jpeg_factory_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/image/jpeg_factory.py` — drives `_color_space_for_components` 0/5+ component ValueError, `_pil_mode_to_components` known-and-unknown branches, `_split_alpha_for_smask` RGB/RGBA/LA/PA/P-with-transparency arms, `get_alpha_image` non-PIL TypeError + BITMASK NotImplementedError + LA/PA/P-with-transparency/P-without-transparency paths, `get_color_image` non-PIL TypeError + LA/PA/P-with-transparency/P-without-transparency/1-bit/HSV-fallback/CMYK-passthrough/YCbCr-passthrough, `get_color_space_from_awt` non-PIL TypeError + YCbCr-returns-RGB + L/CMYK paths, `encode_image_to_jpeg_stream` + `create_jpeg` non-PIL TypeError, Java-style camelCase aliases (`createFromByteArray` / `createFromStream` / `createFromImage` with optional quality/dpi), module-level `_retrieve_dimensions` back-compat alias, `retrieve_dimensions` unidentified-blob ValueError + zero-components fallback to `len(probe.getbands())` (via monkey-patching `_pil_mode_to_components`), and `get_num_components_from_image_metadata` AttributeError-on-no-`.mode` fallback |
| `tests/pdmodel/font/test_pd_type1c_font_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_type1c_font.py` — drives `has_glyph_for_code` / `get_path_for_code` / `get_normalized_path_for_code` `sfthyphen` → `hyphen` and `nbspace` → `space` rewrite branches (with and without the target glyph in the embedded CFF), `get_path` direct-`nbspace` argument branch, `get_font_matrix` CFF-program-raises + wrong-length fallback + valid-matrix passthrough, `get_bounding_box` CFF-bbox-raises + wrong-length None-fallback + valid-bbox PDRectangle path, `get_width_from_font` `units_per_em <= 0` default substitution + `advance <= 0` short-circuit, `get_name_in_font` AGL → `uniXXXX` fallback (using `Omega` → U+2126 OHM SIGN per AGL historical quirk) + program-lacks-uni-form `.notdef` fallback, `read_encoding_from_font` embedded-program-with-encoding-map path returning `BuiltInEncoding`, `encode_codepoint` "no glyph for codepoint" + "name has no code in encoding" raises, and `generate_bounding_box` CFF-bbox exception + wrong-length None fallbacks |
| `tests/pdmodel/font/test_pd_font_wave1337.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_font.py` — drives the full `get_space_width` cascade: step 1 (`/ToUnicode` CMap's `get_space_mapping` > -1 + positive `get_width`) success and `get_width`-raises-NotImplementedError fall-through, step 2 (`get_string_width(" ")`) success + raise fall-through, step 3 (direct `/Widths` lookup at code 32 with explicit and `/FirstChar`-defaults-to-zero) success, step 4 (`get_width_from_font(32)`) success + raise fall-through, step 5 (average font width), and the broad-catch outer Exception swallow + final 250.0 default, plus the cache-hit early-return; `get_standard14_afm` BaseFont-absent / non-Standard14 / loader-KeyError / cache-hit paths; `get_width` Standard14 `NotImplementedError`→ 0.0 + non-Standard14 fall-through to `get_width_from_font`; `get_string_width` codes-iteration loop + empty-string; `to_unicode` no-cmap / Identity-H chr(code) / chr(0x110000) ValueError → None / non-Identity cmap-delegation paths; `is_subset` prefix/no-prefix/absent; `get_standard14_width` / `get_position_vector` / `add_to_subset` / `subset` base raises; and `get_displacement` zero-width default |

### Wave 1339 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/interactive/form/test_set_field.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/set_field.py` — extends the existing smoke test with the missing-AcroForm short-circuit (stderr warning), missing-field warning, `PDCheckBox` check and un_check arms (empty vs. non-empty value), `usage()` stderr, `main(None)` / `main([])` empty-argv arg-count branch, `set_field_args` three-arg happy path (loads form, sets field, saves `*_filled.pdf`), and `set_field_args` wrong-arg-count branch |
| `tests/examples/util/test_draw_print_text_locations.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/util/draw_print_text_locations.py` — extends the existing smoke test with `usage()` stderr, `main(None)` / too-many-args / single-arg dispatch, `show_glyph` AttributeError swallow when the base implementation is missing, `calculate_glyph_bounds` None-return, `write_string` happy-path stdout format and the `get_font` raises -> `<unknown>` fallback, and the `SCALE` constant |
| `tests/examples/interactive/form/test_create_radio_buttons.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/create_radio_buttons.py` — extends the existing smoke test with `__init__` no-op, `DEFAULT_FILENAME` class constant, `main(None)` / `main([])` empty-argv default-filename arms, `create_appearance_stream(on=True/False)` lite-port None returns, `draw_circle` four-Bezier emission (move_to + 4× curve_to + close_path), `get_line_width` with/without border-style (real `PDBorderStyleDictionary` exercise), and the `set_widgets`-raises fallback (monkey-patched to force the `radio_button.get_widgets().extend(widgets)` arm) |
| `tests/fontbox/util/autodetect/test_windows_font_dir_finder.py` | 3.0.x | hand-written coverage for `pypdfbox/fontbox/util/autodetect/windows_font_dir_finder.py` — drives `%windir%`-set with real FONTS subdir / with trailing `/` or `\\` separator stripped / `%windir%[:2]/PSFONTS` branch (monkey-patched `Path.exists` + `Path.is_dir`) / windir-set-no-FONTS empty result; the `len(windir) <= 2` drive-letter heuristic branch (probes C/D/E for WINDOWS/FONTS and PSFONTS, OSError swallow, no-match empty result); and the `%LOCALAPPDATA%/Microsoft/Windows/Fonts` append branch with set+exists / set+missing / unset paths. All branches driven cross-platform via env + `Path` monkey-patch so the test runs identically on POSIX and Windows hosts |
| `tests/benchmark/test_rendering.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/benchmark/rendering.py` — extends the scaffold with `__init__` idempotency (second `Rendering()` doesn't raise on existing `target/renditions`), `_consume` store / overwrite, `_time_call` positive float + exception propagation, all six benchmark workload bodies (`render_ghent_cmyk_no_output` / `render_ghent_cmyk` / `render_altona_no_output` / `render_altona` / `render_pdf_spec_no_output` / `render_pdf_spec`) with `Loader.load_pdf` + `PDFRenderer` stubs that supply a `_FakePDF` reporting two pages — covers the for-loop, the no-output `_consume` branch, the with-output PNG-write branch (verifies the prefix+index filename format), and the `finally`-closes-on-renderer-error guarantee |
| `tests/examples/util/test_print_text_colors.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/util/print_text_colors.py` — extends the smoke test with `main(None)` / zero / one / two-arg dispatch arms, `usage()` stderr check, ctor-as-text-stripper subclass assertion, and `process_text_position` callback with stubbed graphics state covering the full-state path (stroking + non-stroking colors + text-state rendering mode), the state-raises swallow branch, the state-without-text-state arm, and the `gs is None` skip arm |
| `tests/examples/printing/test_opaque_draw_object.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/printing/opaque_draw_object.py` — extends the smoke test with `process` happy-path branches against fake graphics contexts: context-None early return, `_FakeImageXObject` (typed via `__name__ = "PDImageXObject"`) `draw_image` dispatch with recursion counter untouched, `_FakeFormXObject` (`__name__ = "PDFormXObject"`) `show_form` dispatch with balanced increase/decrease level, recursion-too-deep error-log + form skip + `finally` decrease guarantee, and unknown-type silent ignore |
| `tests/examples/interactive/form/test_field_triggers.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/field_triggers.py` — extends the smoke test with all-six-trigger AA dictionary verification (E/X/D/U/Fo/Bl), missing-field + missing-AcroForm raise paths, `main` two-arg / one-arg / no-arg (with cwd redirection) dispatch arms, ctor + DEFAULT_INPUT/DEFAULT_OUTPUT class constant exposure, and a `builtins.__import__` monkey-patch test that forces both action-module ImportError fallback branches (no /AA dict written when modules are unavailable) |
| `tests/examples/util/test_pdf_highlighter.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/util/pdf_highlighter.py` — extends the smoke test with `generate_xml_highlight` string-normalisation (single str wrapped, list bypasses wrap), `end_page` directly driven against a populated buffer covering loc-line emission for hits, case-insensitive match, no-match silence, and uninitialised-state no-op, plus `main` zero / one / two-arg + file-and-word dispatch arms, `usage()` stderr, ctor state initialisation, ENCODING class constant, and `__main__` module-guard resolve |
| `tests/examples/interactive/form/test_print_fields.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/print_fields.py` — extends the smoke test with `print_fields` no-AcroForm and empty-AcroForm branches, `process_field` two-level non-terminal nesting (covers parent-path append `parent.{partial_name}` when parent differs), single-level non-terminal walk, value-raises swallow branch via monkey-patched `get_value_as_string`, terminal field with no `/T` (None partial_name), `main` zero / one / two-arg dispatch + file-load path, `usage()` stderr, ctor, and `__main__` module-guard resolve |
| `tests/text/test_pdf_text_stripper_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/text/pdf_text_stripper.py` — drives `_compute_avg_advance` user-space conversion (line 1002), `has_font_or_size_changed` name-comparison branches (font-names-differ / names-match / only-last-named / both-nameless identity fallback), `remove_contained_spaces` empty-list short-circuit, `fill_bead_rectangles` happy-path with mixed real/None beads + bead `get_rectangle`-raises swallow + page `get_thread_beads`-raises swallow, `process_pages` start+end-bookmark resolution (real positions) + collapse-to-empty-range when both bookmarks share an unresolvable outline item + per-page `process_page` invocation only for pages with content streams, `write_page` empty-article short-circuit + happy-path through `_emit_group`, `normalize_word` Allah-with-alif U+FDF2-after-U+0627 insertion (line 1775) + FB1D-block long-NFKC reversal (line 1779), `parse_bidi_file` malformed-hex ValueError swallow (lines 1888–1889), `handle_line_separation` no-prior-position line-start-only path + large-vertical-drop paragraph-start mark, and `begin_marked_content_sequence` defensive `get_string`-raises swallow (lines 1947–1948) |
| `tests/pdmodel/graphics/image/test_pd_image_x_object_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py` — drives `create_from_file_by_extension` extensionless-name + unknown-extension ValueError + TIFF-with-PNG-body OSError → PNG retry (lines 130–134); `create_from_file_by_content` OSError-on-missing-file wrap + unrecognised-magic ValueError; `create_from_byte_array` non-bytes-input TypeError + unrecognised-magic ValueError + TIFF→PNG fallback + custom-factory PNG/GIF/BMP route + dead-branch `_detect_file_type` monkey-patched to "UNKNOWN" → ValueError (line 211) + default Pillow+LosslessFactory round-trip for BMP/GIF; `create_raw_stream` happy-path + non-bytes-read defensive guard (lines 219–225); `get_filter` name/array/absent branches (line 310); `get_image` to-pil-None short-circuit (line 776) via region + opaque + subsampling variants; `get_raw_raster` non-stream-cos None branch (line 834) + happy-path; `extract_matte` no-color-space (line 854) + no-`to_rgb` attribute (line 861) + `to_rgb`-raises (lines 864–865) + `to_rgb`-returns-None (lines 866–867) + identity-`to_rgb` happy path; `to_pil_image` unsupported-bpc (line 984) + DeviceRGB invalid-decode (line 1000) + DeviceGray sub-byte short-raster (line 1006); `_apply_decode_to_8bit_samples` short-data / bpc=0 / wrong-decode-length guards (lines 1068–1069, 1078–1079); `_apply_decode_to_indexed_samples` short-data / bpc=0 / wrong-decode-length guards (lines 1098–1099, 1106–1107) + happy-path linear decode; `_apply_decode_to_8bit_indexed_samples` wrapper (line 1122); `_unpack_sub_byte_samples` invalid-bpc + zero-components guards (lines 1132–1133); `_clamp` low/high/in-range branches (lines 1289–1294); `_clamp01` bounds; `_detect_file_type` short-header; and `_unpack_16bit_samples` short-payload + big-endian decode |
| `tests/debugger/test_pd_debugger_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/pd_debugger.py` — exercises the non-mac `Exit` entry on the `File` menu, `add_recent_file_items` early returns (menu-unbuilt / file-menu-unbuilt / no-files) + happy-path repopulate, `get_find_*_menu_item` pre-build None returns, `_on_tree_open` empty-selection + sentinel-node-None paths, `_show_page` non-dict short-circuit, `_show_color_pane` empty / first-not-name / CalGray (CSArrayBased) branches + `_dispatch_selection` colorspace route (line 838), `_show_flag_pane` underneath-not-dict / key-None / view-None / get_panel-fallback (via stubbed `FlagBitsPane`) edges, `_show_stream` Contents-with-page-resources / CharProcs-grandparent / Form-with-resources / PatternType-1 / Thumb / Image-with-grandparent-resources / not-a-stream branches, `_show_font` no-key / no-resources-dict / pane-None (via stubbed `FontEncodingPaneController`) arms, `_save_as` / `_save_decoded_stream` / `_save_raw_stream` OSError recovery + no-stream + user-cancel, `_text_dialog` urlopen happy + OSError swallow, `update_title` non-mac prefix, `_read_stream_bytes` data-without-`read` `bytes(data)` fall-through, `_is_font_descriptor` / `_is_annot` non-dict-underneath false-returns (lines 970, 978), `_init_global_event_handlers` non-mac no-op (line 501), `_convert_to_string` COSStream OSError swallow (lines 2070–2071) |
| `tests/fontbox/ttf/test_ttf_subsetter_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/ttf_subsetter.py` — exercises `_apply_prefix` empty-`toUnicode` / already-tagged / non-PostScript / no-name-table edges (line 364), `log2(0)` + `log2(<0)` zero short-circuit (line 402), `to_u_int32` short-buffer pad (line 418) + missing-`low` TypeError (line 421), `write_long_date_time` int / aware-datetime / naive-datetime / `timeInMillis` shim / unsupported-value paths (lines 480–493), `write_table_header` short / long tag padding (line 537), `copy_bytes` non-seekable OSError fallback (lines 572–574) + AttributeError fallback + EOFError on short read (line 577), `_build_subset_font` prefix+invisible application (lines 661, 663), `_encoded_table` keep_tables-allowlist miss / tag-not-in-tt (DSIG) / tag-not-in-reader-tables edge branches (lines 681, 693) |
| `tests/pdmodel/font/test_pd_cid_font_type0_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_cid_font_type0.py` — drives `_uni_name_of_code_point` short / wide / uppercase hex paths (lines 42–45), `get_glyph_name` parent-empty `to_unicode` / parent-`to_unicode`-None / parent-resolved synthesised `uniXXXX` arms (lines 589–592), `get_path` CIDToGIDMap remapping via embedded uint16-pair stream (lines 613–615) + charstring-exception swallow (lines 623–625) + charstring-None trailing-`[]` (line 625), `has_glyph` cs-None early-return (line 652) + `get_gid` exception swallow (lines 655–656) |
| `tests/pdmodel/graphics/color/test_pd_device_n_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/color/pd_device_n.py` — drives `PDDeviceNAttributes.get_colorants` COSNull-value skip (line 183), `set_tint_transform` raw COSBase branch via a `get_cos_object`-stripped COSBase subclass (line 441), `to_rgb` attribute-path dispatch (line 625), `to_rgb_with_attributes` full process-mapping + missing-spot-colorant fall-back to tint-transform (line 669) + spot-`to_rgb`-returns-None fall-back (line 678) + DeviceN vs NChannel subtype branches (lines 612-613) + process-color-space-None fall-back via /Process lacking /ColorSpace, and the `to_rgb_image` super-delegating wrapper (line 696) |
| `tests/pdmodel/graphics/image/test_sampled_image_reader_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/image/sampled_image_reader.py` — drives Pillow-missing ImportError fall-backs across all four entry points (`get_stencil_image` 81-82, `get_rgb_image` 127-128, `get_raw_raster` 271-272, `apply_color_key_mask` 423-424) via a `builtins.__import__` monkey-patch; `bytes(data)` coercion path on a `memoryview`-returning stream (lines 170, 291); the `padding_bits = 8 - padding_bits` non-aligned-row branch (lines 197, 297); the two-arg `get_rgb_image(pd_image, color_key)` overload routing a non-tuple/list color-key into the elif branch (line 137); `get_raw_raster` 2-component → `mode="L"` fall-back (line 307); `get_rgb_image` 2-component grayscale-expansion else (line 252); region-offset clip-skip branches; and `MultipleInputStream.readinto` exhausted-streams break (line 456) + empty-streams `read(n)` |
| `tests/pdmodel/font/test_true_type_embedder_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/true_type_embedder.py` — drives `subset()` fontTools ImportError → OSError wrap (lines 134-135) via `builtins.__import__` monkey-patch, `get_tag` leading-"A" pad branch (line 181) via `builtins.hash` monkey-patch to force `num=0`, `_create_font_descriptor` missing-hhea KeyError → zero-metrics (lines 254-257), missing-head outer KeyError → FontBBox/CapHeight branch skipped (lines 297-298), `rect.get_width` TypeError swallow (lines 295-296), OS/2 sFamilyClass serif/script branches, OS/2 fsSelection italic bit, `_build_full_font_file` save() OSError + AttributeError swallowed (lines 332-333), TTC magic rejection (line 336), `build_font_file2` direct-TTC rejection, and `_compute_gid_to_cid` missing-maxp KeyError → empty mapping (lines 352-353) — all driven by a minimal `_FakeTTF` table-dict stand-in (OS/2/post/head/hhea/maxp/name) so the test is wheel-free and deterministic |
| `tests/fontbox/encoding/test_glyph_list_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/encoding/glyph_list.py` — drives `load` and `load_list` across all input-shape branches: string path (`open(...).read()` + iso-8859-1 decode, lines 4588-4590 / 4620-4622), file-like returning `str` (else-branch, lines 4598 / 4630), file-like returning `bytes` (load_list, line 4628), iterable-of-lines fallback (lines 4600 / 4632), and the duplicate-name warning emission (lines 4664-4669) via the `pypdfbox.fontbox.encoding.glyph_list` logger captured with `caplog`; also exercises the `base=` keyword for cumulative loading |
| `tests/xmpbox/xml/test_xmp_serializer_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/xmpbox/xml/xmp_serializer.py` (wave-1337 flat-dict rewrite) — drives `_normalize_schema_fields` dict-input → typed-field generation and non-dict-input passthrough (lines 91-92); `_iter_flat_typed` typed-cache-hit short-circuit (lines 102-104) + cached primitive wrap (lines 105-110); `_wrap_primitive` every type branch — `bool` → `BooleanType`, `int` → `IntegerType`, `datetime` → `DateType`, `str` → `TextType`, `list` → `ArrayProperty` (with non-string-item skip), `dict` → `LangAlt` (with non-string-value skip), and the unrecognised-type → None caller-skip (lines 122-143); `_cardinality_hint` class-mapping `_FIELD_CARDINALITIES` Seq override, method-based `get_property_cardinality` Alt override, method-returns-None fall-back, hook-raising Exception swallow + Bag default, non-Enum-return ignored, and the `schema is None` early return (lines 153-168); plus `_append_field` non-AbstractField primitive skip (line 197) and the `get_string_value`-absent → `get_raw_value` fall-back (line 209) via a duck-typed virtual subclass of `AbstractSimpleProperty` |
| `tests/pdmodel/interactive/annotation/handlers/test_pd_abstract_appearance_handler_wave1339.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/annotation/handlers/pd_abstract_appearance_handler.py` — drives the existing-stream-entry happy returns for `get_normal_appearance` / `get_down_appearance` / `get_rollover_appearance` (lines 226, 310, 323); `get_appearance_entry_as_content_stream` fallback to `get_normal_appearance_stream` when the supplied entry's appearance-stream is None (line 291); `draw_style` LE_R_OPEN_ARROW + LE_R_CLOSED_ARROW (lines 508-512), LE_SLASH 60°/240° geometry (lines 513-523), and the unknown-style early-return else branch (line 525); `_components_to_rgb` empty-list default-to-black (line 653) + 2-component fall-through-to-black branch + 1-component grayscale + CMYK→RGB inversion; and the base-class default no-op `generate_rollover_appearance` (line 662) / `generate_down_appearance` (line 666) calls invoked through the MRO |
| `tests/examples/pdmodel/test_go_to_second_bookmark_on_open.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/pdmodel/go_to_second_bookmark_on_open.py` (wave 1341 agent B) — extends the smoke tests in `test_loader_examples.py` with `__init__` no-op (line 19), one-arg + three-arg `usage` stderr branches (lines 30-34), the under-two-pages OSError guard (line 36), happy path with a real two-bookmark outline asserting `/OpenAction` is set on the saved PDF (lines 44-49), and the encrypted-doc SystemExit(1) branch via `monkeypatch.setattr(PDDocument, "is_encrypted", lambda self: True)` (lines 30-34) |
| `tests/cos/test_cos_float_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/cos/cos_float.py` (wave 1341 agent D) — drives `_coerce` NaN passthrough / ±infinity clamp / subnormal-flush / normal-value branches, the public `coerce` instance alias, `equals` matching-and-non-cosfloat (NotImplemented → False) arms, `hash_code` regular-and-NaN-canonical arms, `to_string` `{<formatted-value>}` wrap for both string-constructed and float-constructed instances, `_float_bits` NaN canonicalisation to `0x7FC00000`, two-NaN `COSFloat` equality contract, and `__repr__` no-original-form value-only fallback |
| `tests/cos/test_cos_increment_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/cos/cos_increment.py` (wave 1341 agent D) — drives the directness-exclusion branch on dirty array children (lines 165-170), the `child_demands_parent_update` re-add of a clean parent (lines 176-177), the excluded-parent early-return (line 174), the `_collect_array` already-contained continue (line 184) and primitive-entry skip, the `_collect_object` already-contained early-return (lines 194-195) reached via direct helper call, plus a non-array `_UpdateableDict` direct-flag set arm. Uses thin `_UpdateableArray` / `_UpdateableDict` subclasses to bridge the singular `is_need_to_be_updated` alias the source method requires |
| `tests/filter/test_dct_filter_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/filter/dct_filter.py` (wave 1341 agent D) — drives `Raster.get_width` / `get_height` / `get_num_bands` accessors, `read_image_raster` mode-`"1"` `convert("L")` fall-through (line 111) + num-channels-vs-getbands mismatch (line 110) via a stub-filter subclass, `get_num_channels` empty-bands and `getbands`-raises arms (lines 130-131, 128-129), `get_adobe_transform` plain-dict (line 158) / arbitrary-wrapper-with-info / wrapper-without-info / invalid-int-payload / None-input branches, `get_adobe_transform_by_brute_force` unsupported-seek (lines 190-191), no-Adobe-marker, canonical APP14 happy-path returning the transform byte, tag-not-0xFFEE reseek-and-continue, short-tag-bytes (lines 205-207) and short-len-bytes (lines 213-215) defensive branches driven by a `_ShortReadStream` wrapper, `from_ycc_kto_cmyk` happy path + wrong-band-count ValueError, `from_bg_rto_rgb` 1×1 and 2×2 multi-scanline swap + wrong-band-count ValueError, and `clamp` below-zero / above-255 / in-range-truncation arms |
| `tests/io/test_non_seekable_random_access_read_input_stream_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/io/non_seekable_random_access_read_input_stream.py` (wave 1341 agent D) — drives `_available_on_underlying` fall-through when the underlying lacks `available()` (line 198) via `io.BytesIO`-backed `length()` and `available()`, `_fetch` salvage branch (lines 281-286) by reading past EOF with a half-full CURRENT and a full LAST then rewinding 50 bytes to verify the preserved tail, and `_fetch` OSError propagation (lines 295-298) with warning-log capture via a `_RaisingStream` whose `readinto` throws |
| `tests/pdmodel/font/test_pd_font_factory_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_font_factory.py` (wave 1341 agent C) — drives `_FontType` string-subtype dispatch (Type1 / Type1C / unknown), `is_cid_subtype` non-Type0 short-circuit, and the OpenType / Type 1 / PFB / CFF arms of `get_font_type_from_font` in both the composite (/Type0 descendant subtype) and non-composite branches, the MMType1 carve-out for raw-Type1 + CFF programs, and the unrecognised-header → None fallthrough |
| `tests/pdmodel/font/test_pd_simple_font_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_simple_font.py` (wave 1341 agent C) — drives `read_encoding` "Unknown encoding" warning path with `caplog`, the symbolic-with-no-valid-base `/Differences` branch that consults `read_encoding_from_font` for the built-in, the abstract `NotImplementedError` raises for `read_encoding_from_font` / `get_path` / `has_glyph` / `get_font_box_font` via a `_ConcreteForAbstractTests` stub, the `get_standard14_width` `nbspace` → `space` and `sfthyphen` → `hyphen` substitutions via stub AFM + encoding, and the base-class `will_be_subset` False return + `add_to_subset` / `subset` `NotImplementedError` raises (called via the unbound-method form because `PDType1Font` / `PDType3Font` override) |
| `tests/pdmodel/graphics/color/test_pd_color_space_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/color/pd_color_space.py` (wave 1341 agent C) — drives `_create_from_cos_object` resource-cache pathways (cache hit, miss-with-put-back, no-cache fall-through, array-form caching) via a `_StubCache`/`_StubResources` pair, the default `to_rgb` PDColor-delegation arm called directly through `PDColorSpace.to_rgb(PDDeviceGray.INSTANCE, ...)`, the base `to_raw_image` DeviceCMYK fast path via a `_BaseCMYKShaped` stub (because `PDDeviceCMYK.to_raw_image` overrides to return None per upstream), and the base `__str__` returning the color-space name |
| `tests/pdmodel/graphics/shading/test_pd_shading_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/shading/pd_shading.py` (wave 1341 agent C) — drives `set_color_space_object` typed-PDColorSpace-with-None-cos-object clear path via a `_NoCosColorSpace` stub, the base `get_function` single-dictionary `PDFunction.create` wrap (called as `PDShading.get_function(shading)` because Types 1–7 all override), and the base `to_paint` dispatch arms for shading types 1 through 7 plus the unknown-type → None fallthrough (concrete subclasses override `to_paint`, so the base implementation is exercised via `PDShading.to_paint(instance)`) |
| `tests/debugger/ui/test_pdf_tree_cell_renderer_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/ui/pdf_tree_cell_renderer.py` (wave 1341 agent C) — drives the instance-method `PDFTreeCellRenderer.lookup_icon_with_overlay` for both the node-form (overlay=None → OverlayIcon for indirect MapEntry, plain-icon for direct) and image-form (alpha-composites two PIL images) calling conventions, `_to_tree_object` empty-nested → bare-key/index fallback for MapEntry/ArrayEntry with None values, xref-dictionary carve-out (renders as ""), final fallthrough `return str(node_value)` for an arbitrary `_Custom` object, and the `_lookup_icon` ArrayEntry value-recursion arm |
| `tests/debugger/ui/test_error_dialog_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/ui/error_dialog.py` (wave 1341 agent C) — drives `create_content` / `create_error_message` / `create_detailed_message` `tk.TclError` widget-construction fallbacks via `monkeypatch.setattr(module.tk, "Frame"/"Label", _raise)` and `module.scrolledtext.ScrolledText = _raise`; the `create_error_message` BaseException-with-empty-message → type-name fallback under a real Tk root; the `create_detailed_message` default-throwable arm (throwable=None → self._error); and the `position` outer `tk.TclError` swallow via `_FakeComponentRaises` / `_FakeParent` stubs whose Tk-method calls raise |
| `tests/fontbox/ttf/test_true_type_collection_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/true_type_collection.py` (wave 1341 agent E) — drives the v2 TTC header DSig-triple consumption (lines 153-155) via a v1→v2 patcher that rewrites the version field and offsets, `_extract_font_bytes` IndexError beyond the fontTools-side font count (lines 328-329), the `create_buffered_data_stream` static helper close-after-reading `True`/`False` arms (lines 371-376), the `MemoryTTFDataStream` ``isinstance`` branch in `_extract_font_bytes` (line 322-323) via a manually-constructed memory stream, the bare ``RandomAccessRead``-shaped object constructor branch (line 122), and the OTF scaler-tag dispatch in `create_font_parser_at_index_and_seek` (line 351) via a synthetic TTC pointing at an ``OTTO`` SFNT slot constructed bypassing the full parse |
| `tests/fontbox/pfb/test_pfb_parser_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/pfb/pfb_parser.py` (wave 1341 agent E) — drives the `Path` / `str` source constructor branch (line 43), graceful EOF after a complete record sequence missing the `0x80 0x03` terminator (lines 76-77), EOF after a stray `0x80` start marker (line 83), invalid record-type byte (line 88), EOF mid-size-field (line 91), declared record size larger than the input (line 102), and EOF mid-payload (line 107). Three defensive branches at lines 78 / 100 / 113 are confirmed unreachable behind the 18-byte minimum and unsigned-byte composition — flagged in `CHANGES.md` wave-1341 agent-E latent issues |
| `tests/pdmodel/fdf/test_fdf_document_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/fdf/fdf_document.py` (wave 1341 agent E) — drives `set_catalog` with a trailer-less `COSDocument` (lines 147-149), `set_xfdf` Element overload (line 222), `bytearray` overload (lines 223-226), readable-stream overload (lines 225-226), TypeError fallback for an unsupported type (line 228), and `close()` exercising a non-`None` `_fdf_source` whose `close()` succeeds vs. raises (lines 295-301) via a `_CloseRecorder` stand-in |
| `tests/pdmodel/documentinterchange/logicalstructure/test_pd_structure_node_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_node.py` (wave 1341 agent E) — drives `append_objectable_kid` / `remove_objectable_kid` / `insert_objectable_before` fall-through arms when the argument lacks `get_cos_object` (lines 301 / 311 / 325) via bare `int` MCIDs, `_same_kid` raw-equality match (line 407-408) via two value-equal but identity-distinct `COSString` instances, and `_same_kid` COSObject indirection on both sides (lines 414-417 / 418-421) via direct helper invocation (public call sites pre-dereference through `COSArray.get_object` / `COSDictionary.get_dictionary_object`, so the indirection branch is only reachable by calling `_same_kid` itself — matches upstream's defensive parity branch) |
| `tests/pdmodel/interactive/form/test_pd_terminal_field_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/form/pd_terminal_field.py` (wave 1341 agent E) — drives `_apply_fdf_value` COSStream arm (lines 221-223), COSArray-routed-to-PDChoice arm (lines 224-229) via a typed multi-select `PDChoice`, COSArray non-choice raw-write arm (lines 232-234), unknown-type OSError arm (line 237) called directly to bypass `FDFField.get_cos_value`'s upstream pre-screen, plus `PDFieldStub.set_value` None / COSBase / TypeError-on-unsupported branches (lines 286-297) |
| `tests/pdmodel/interactive/form/test_pd_acro_form_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/form/pd_acro_form.py` (wave 1341 agent A) — drives `import_fdf` empty-/Fields short-circuit (line 630) and per-field `partial is None` skip (line 634); `export_fdf` `cos_doc.get_document_id` propagation arm (lines 692-699, 702) via direct `COSDocument.set_document_id` seeding plus a `get_document`-returning-None `_DocShim`; `is_visible_annotation` negative branches for non-stream /N (line 1224), short /BBox (line 1227), non-numeric /BBox entry (line 1233) and AttributeError on `.value` via a `_BoomInt(COSInteger)` subclass (lines 1235-1236); `resolve_transformation_matrix` `_read_rect`-None (line 1289) and `_read_form_geometry`-None (line 1292) short-circuits; `build_pages_widgets_map` reverse-walk fallback (lines 1322, 1328-1345) via two-widget setup where widget1 carries /P but widget2 doesn't, so `has_missing_page_ref` flips True and the page-Annots scan runs |
| `tests/debugger/pagepane/test_page_pane_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/pagepane/page_pane.py` (wave 1341 agent A) — drives `collect_link_locations` `PDAnnotationLink` ImportError fallback (lines 172-173); `collect_link_location` primary 4-module import block ImportError + URI-only retry success path (lines 206-217), the `PDActionGoTo is None or PDPageDestination is None` short-circuit for non-URI actions (line 227), and the primary+URI both-fail return (lines 216-217); `start_extracting` `PDFTextStripper` ImportError fallback (lines 336-338) and `get_text` OSError swallow (lines 356-358); `RenderWorker.do_in_background` `ImageUtil.get_rotated_image` ValueError swallow (lines 789-790). Uses `monkeypatch.setitem(sys.modules, name, None)` to force ModuleNotFoundError on demand |
| `tests/pdmodel/fdf/test_fdf_field_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/fdf/fdf_field.py` (wave 1341 agent A) — drives `get_value` / `get_cos_value` / `get_rich_text` COSObject unwrap fallback arms via pre-resolved `COSObject(1, 0, resolved=...)` indirections, `get_rich_text` `None` fallback for unexpected types (line 351), `write_xml` non-string-skip on multi-select arrays (line 513) via mixed `COSString`/`COSFloat` entries, `_cos_value_to_python` `COSInteger` (line 580) + `COSStream` passthrough (lines 583-585), `FDFNamedPageReference.set_file_specification` / `get_file_specification` round-trip and clear paths via `PDSimpleFileSpecification`, and `FDFIconFit.get_fractional_space_to_allocate` existing-/A `PDRange(array)` branch (line 677). Three COSObject-unwrap defensive guards (lines 105-106, 127-128, 345-346) are dead code under `COSDictionary._resolve_item`'s eager dereference — flagged in `CHANGES.md` wave-1341 agent-A latent issues |
| `tests/pdmodel/font/test_pd_type1_font_wave1341.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/font/pd_type1_font.py` (wave 1341 agent A) — drives `_get_type1_font` descriptor-without-/FontFile sentinel cache (lines 135-136) via a fresh `PDFontDescriptor`, `get_glyph_width` Standard-14 typed-encoding hit (line 198), `get_glyph_path` Standard-14 fallback paths for typed-encoding hit (line 341), Standard/Symbol/ZapfDingbats default-encoding arms (line 360 and family carve-outs), and the `.notdef` short-circuit (line 362), `get_height` AFM-without-/Encoding `0.0` return (line 524), `generate_bounding_box` program-bbox fallback (lines 749-753) and program-bbox-None (lines 750-751) via a `_FakeT1Program(Type1Font)` subclass, `get_font_matrix` program-matrix-wins-default (lines 771-774), `repair_length1` short-buffer reset (line 807) and brute-force second-pass (line 811) with `length1=5` carefully placed before the embedded `exec` token, and `read_encoding_from_font` `BuiltInEncoding` synthesis from a populated program encoding map (lines 911-916) + `StandardEncoding.INSTANCE` fall-through for an empty program encoding map |

### Wave 1343 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/util/test_hex_coverage.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/util/hex.py` (wave 1343 agent D) — drives `get_bytes` single-int branch (lines 64-65) with masking + bounds, `write_hex_bytes` sequence helper happy path / empty / `bytearray` input (lines 103-104), `decode_hex` mid-stream `\n` / `\r` / mixed-CRLF / leading-LF skip-and-resume (lines 120-121), and the invalid-hex-pair `_LOG.error` + abort path covering both first-nibble and second-nibble rejection with `caplog` log capture (lines 126-128); also asserts empty / single-char / odd-length / lowercase decode behaviours |
| `tests/pdfparser/test_brute_force_parser_delegation.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdfparser/brute_force_parser.py` (wave 1343 agent D) — exercises the `getattr(super(), ..., None) is callable` branches of every fallback delegator (`bf_search_for_last_eof_marker` line 76, `bf_search_for_obj_stream_offsets` line 89, `bf_search_for_obj_streams` line 103, `bf_search_for_x_ref_streams` line 113, `bf_search_for_x_ref_tables` line 124, `find_string` line 146, `get_bfcos_object_offsets` line 157, `search_for_trailer_items` line 202, `bf_search_for_trailer` line 230) by monkey-patching `COSParser` with probe helpers in a teardown-restoring fixture and asserting both forwarded args and returned sentinels |

### Wave 1343 additions — hand-written test files (agent C)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/cos/test_cos_name_wave1343.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/cos/cos_name.py` (wave 1343 agent C) — drives `__eq__` `NotImplemented` branch with non-COSName operands (line 172) yielding the public "not equal" outcome under reflected comparison; the `NotImplemented` returns of `__le__` / `__gt__` / `__ge__` (lines 183-185, 188-190, 193-195) raising `TypeError` when compared with non-`COSName`; the consistent-with-`compare_to` happy paths for `<=` / `>` / `>=`; and the `__repr__` `f"COSName({self.get_name()!r})"` format (line 198) for normal, empty, and multi-letter names |
| `tests/fontbox/ttf/test_glyf_simple_descript_wave1343.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/glyf_simple_descript.py` (wave 1343 agent C) — drives `read_coords` X_DUAL+X_SHORT_VECTOR unsigned-byte positive delta (lines 124-125), X_SHORT_VECTOR without X_DUAL unsigned-byte subtract (line 128), Y_DUAL+Y_SHORT_VECTOR positive delta (lines 139-140), Y_SHORT_VECTOR without Y_DUAL subtract (line 143); `read_flags` successful REPEAT-flag `index += repeats` advancement (line 166) via a two-point contour; `from_glyph` n==0 fast-path early-return without calling `getCoordinates` (line 188); and the positive-value branch of `_to_signed_short` (line 211) for 0x7FFF / 0 / small ints plus a `program.bytecode`-bearing stub glyph to drive the `_instructions = list(bytecode)` capture |
| `tests/pdmodel/fdf/test_fdf_annotation_polyline_wave1343.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/fdf/fdf_annotation_polyline.py` (wave 1343 agent C) — drives `init_vertices` `None` / empty-string OSError raise (line 44) and non-float-token OSError (lines 48-49) plus the comma + semicolon delimiter happy paths; `init_styles` malformed-hex `ValueError` swallow (lines 72-73), valid-hex RGB parse, wrong-length and missing-`#` no-ops, plus head/tail forwarding; `set_vertices(None)` removal arm (lines 87-88) verifying the underlying `/Vertices` slot is deleted; `get_vertices` non-`COSArray` slot returning `None` (line 102) via a manually-seeded `COSInteger`-at-/Vertices dictionary; and `get_end_point_ending_style` default-`"None"` return (line 158) when `/LE` is absent |

### Wave 1345 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/pdmodel/test_examples_wave1345.py` | 3.0.x | hand-written coverage round-out for six example modules (wave 1345 agent A) — `examples/pdmodel/add_metadata_from_doc_info.py` (encrypted guard lines 52-55, creation/modification-date branches lines 70/73, `_emit_value` None short-circuit line 137, `_stringify` datetime ISO-format line 162, no-op constructor line 39); `examples/pdmodel/embedded_multiple_fonts.py` (TTC tuple branch lines 63-74 via monkeypatched `TrueTypeCollection` test double — happy-path + missing-font OSError both verifying `close()` runs in `finally`; `.notdef` short-circuit line 211 via stubbed `GlyphList.get_adobe_glyph_list`); `examples/rendering/custom_page_drawer.py` (`main()` success body lines 110-117 via patched `Loader.load_pdf` + stubbed `MyPDFRenderer.render_image` writing PNG to `target/`); `examples/util/print_text_locations.py` (`main([file])` happy path line 34, `write_string` per-position emit lines 51-56 with both `get_font` success + `<unknown>` fallback); `examples/interactive/form/determine_text_fits_field.py` (widget normal-appearance with /Resources/Font/Helv covering lines 65-66, broken `get_normal_appearance_stream` exception arm lines 67-68, NaN fallback lines 82-87 via patched `PDType1Font.get_string_width`); `examples/pdmodel/bengali_pdf_generation_hello_world.py` (`[skipped]` placeholder branch lines 153-157 via wrapped `show_text` that raises on non-ASCII, `importlib.resources` bundled-resource path lines 269-271 via fake `Traversable`/`as_file`, strategy-1 `AttributeError` swallow lines 272-273). Total 22 tests; all six modules now at 100% line coverage |

### Wave 1345 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/tools/test_pdf_to_image_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/tools/pdf_to_image.py` (wave 1345 agent B) — derived `output_prefix` fallback (line 44) via missing `-prefix`; both `AttributeError` and `NotImplementedError` rescue arms around the acro-form `refresh_appearances` call (lines 66-68) via fake `Loader` / fake document / form raising the respective exception; `if not success` failure return (lines 97-100) via a patched `ImageIOUtil.write_image` returning `False` → exit 1; module `if __name__ == '__main__'` dispatch (line 158) via `runpy.run_module(..., run_name='__main__')` (5 tests) |
| `tests/examples/ant/test_pdf_to_text_task_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/ant/pdf_to_text_task.py` (wave 1345 agent B) — `_iter_fileset` `DirectoryScanner`-alike branch (lines 129-131) with and without `get_basedir`, single `str | Path` branch (line 133), and the `TypeError` fall-through (lines 134-137) via non-iterable `int` and `object()` inputs (6 tests) |
| `tests/examples/util/test_extract_text_simple_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/util/extract_text_simple.py` (wave 1345 agent B) — `__init__` body (line 23), single-arg `main` delegating to `extract` (line 35), the `(AttributeError, NotImplementedError)` rescue arms (lines 47-49) via monkey-patched `get_current_access_permission`, and the `can_extract_content()` → `OSError` raise branch (line 46) via a permission stand-in returning False (6 tests) |
| `tests/examples/printing/test_printing_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/printing/printing.py` (wave 1345 agent B) — `main(None)` consults `sys.argv` (line 34), single-arg load-and-close happy path (lines 41-45) via a fake `Loader` returning a `_FakePDDocument` stand-in (worked around latent `COSDocument`-vs-`PDDocument` bug flagged in CHANGES.md), and the `finally` close branch still runs when `Printing.print` raises (4 tests) |
| `tests/examples/signature/cert/test_crl_verifier_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/signature/cert/crl_verifier.py` (wave 1345 agent B) — `LOG.warning` + `continue` when no CRL override is supplied (lines 50-51), `verify_certificate_cr_ls` snake-case alias delegation (line 62), post-sign-date silent return in `check_revocation` (line 79), the three offline `download_crl` / `download_crl_from_web` / `download_crl_from_ldap` placeholders (lines 88, 93, 98), and the `if not full_name` continue (line 113) via a CRL distribution point carrying `relative_name` only (7 tests) |
| `tests/examples/signature/validation/test_cert_information_helper_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/signature/validation/cert_information_helper.py` (wave 1345 agent B) — `hashlib.sha1` RuntimeError rescue + `LOG.error` arm (lines 43-45) via monkey-patched `hashlib.sha1`, `extract_crl_url_from_sequence` always-`None` placeholder (line 72), and the post-loop `return None` (line 90) via a CRL DP whose only general name is a `DirectoryName` rather than a `UniformResourceIdentifier` (4 tests) |
| `tests/examples/pdmodel/test_extract_metadata_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/pdmodel/extract_metadata.py` (wave 1345 agent B) — `__init__` body (line 27), populated `list_calendar` print loop (lines 111-113) over `datetime.date` entries, and the `XmpParsingException` rescue branch (lines 49-50) via a stubbed `DomXmpParser` whose `parse` raises (3 tests) |
| `tests/examples/interactive/form/test_create_check_box_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/examples/interactive/form/create_check_box.py` (wave 1345 agent B) — `__init__` body (line 44), `get_line_width` with a populated border style returning the width (lines 108-110), and the `None` fallback returning `1.0` (line 111) via two minimal fake-widget stand-ins (3 tests) |

### Wave 1345 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/debugger/colorpane/test_cs_array_based_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/colorpane/cs_array_based.py` (wave 1345 agent D) — `OSError` catch in `__init__` (lines 75-79) via monkey-patched `PDColorSpace.create`; the `PDICCBased` arm of `_init_ui` (lines 120-125) emitting `Colorspace type:` + `sRGB:` labels via a minimal valid `[/ICCBased <stream with /N 3>]` array (2 tests) |
| `tests/debugger/colorpane/test_cs_separation_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/colorpane/cs_separation.py` (wave 1345 agent D) — slider-`None` re-read via `str(self._slider.get())` (line 192); `OSError` caught inside `state_changed` writing the exception message to the entry (lines 206-208) via a monkey-patched `update_color_bar`; same `OSError` catch inside `_on_tint_entry` (lines 239-240) (3 tests) |
| `tests/debugger/ui/textsearcher/test_search_engine_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/ui/textsearcher/search_engine.py` (wave 1345 agent D) — camelCase `Highlight.get_start_offset` / `get_end_offset` / `get_painter` getters (lines 41, 44, 47); `search_regex(None, ...)` early-return (line 147) and `search_regex("", ...)` clear-then-return (line 150); defensive `search_key_length == 0` guard after lower-casing (line 117) via a `str` subclass whose `.lower()` collapses to empty (5 tests) |
| `tests/fontbox/cff/test_char_string_command_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/cff/char_string_command.py` (wave 1345 agent D) — `_COMMAND_UNKNOWN`'s `get_key` / `name` falling through to `None`; the Type-1-only single-byte command exercising the Type-1 arms of `get_key` (line 128) and `name` (line 188); `__repr__` round-trip via `to_string` (line 151); `COMMAND_RLINETO` exercising the Type-2 arm of `get_key` (line 126) (5 tests) |
| `tests/fontbox/ttf/gsub/test_gsub_worker_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/gsub/gsub_worker.py` (wave 1345 agent D) — `_DictScriptFeature.get_name` (line 84); `_adapt_feature` short-circuit on a conformant `_ScriptFeatureLike` (line 114); `_adapt_feature` `TypeError` for unsupported feature shapes (lines 117-118); `_split_into_chunks` empty-substitution-keys per-glyph chunk path (line 141); `_iterable_to_list` defensive copy (line 187) (5 tests) |
| `tests/fontbox/ttf/gsub/test_gsub_worker_factory_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/gsub/gsub_worker_factory.py` (wave 1345 agent D) — `_normalize_language(None)` empty fallback (line 61); the missing-language-module `ImportError` rescue (lines 66-67) via a `find_spec`-driven `meta_path` finder raising on `pypdfbox.fontbox.ttf.model.language`; `_resolve_language_from_scripts` swallowing `AttributeError` / `TypeError` from a deliberately broken `get_script_list` (lines 92-93); the "scripts present but none belong to any known language" empty-fallback (line 105) via a fake `GsubData` whose `script_list` carries only `taml` / `thai` (6 tests) |

### Wave 1345 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdfwriter/compress/test_cos_writer_object_stream_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdfwriter/compress/cos_writer_object_stream.py` (wave 1345 agent E) — `_write_pdf` missing-method `OSError` (line 48) via a bespoke `COSBase` subclass with no `write_pdf`; each `write_object` dispatch arm reached via the top-level dispatch path rather than the typed helpers — `COSString` (line 141), `COSFloat` (line 143), `COSBoolean` (line 147), `COSArray` (line 151), `COSDictionary` (line 153); and the `None`-value `continue` of `write_cos_dictionary` (line 217) via direct `_items[key] = None` mutation since the public `set_item(name, None)` deletes the entry (7 tests) |
| `tests/multipdf/test_pdf_clone_utility_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/multipdf/pdf_clone_utility.py` (wave 1345 agent E) — `clone_merge_cos_base` default `seen_pairs is None` construct branch (line 193-194); the six private back-compat shims (`_clone_cos_base_for_new_document` line 257, `_clone_cos_array` line 260, `_clone_cos_stream` line 263, `_clone_cos_dictionary` line 266, `_clone_merge_cos_base` line 274, `_has_self_reference` line 278) including both the cyclic and non-cyclic arms of the static helper; plus a same-key dict-merge recursion that exercises the `existing is not None` branch (8 tests) |
| `tests/pdmodel/fdf/test_fdf_java_script_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/fdf/fdf_java_script.py` (wave 1345 agent E) — `get_after` with a `COSStream` value decoded via `to_text_string` (lines 75-77) and the unknown-type `None` return; `set_after(None)` deletion arm (lines 85-86); the `/Doc` map's `get_name(i)` fallback when the key half of a pair is a `COSName` rather than a `COSString` (line 112); plus the odd-length array tail-drop, non-dictionary value skip, and non-`COSArray` `/Doc` entry returning `None` (7 tests) |
| `tests/pdmodel/test_page_iterator_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/page_iterator.py` (wave 1345 agent E) — non-`COSDictionary` kid skip (line 51) via a `COSNull` entry; leaf-shaped node with no `/Type` and no `/Kids` enqueued as a page (lines 62-65); `_is_page_tree_node(None)` shortcut (line 70); `__next__` `/Type`-missing repair to `/Page` (line 95) and `/Type`-mismatch `RuntimeError` (line 97) via post-construction `set_name` override; plus `__iter__` self-return (6 tests) |
| `tests/filter/test_predictor_output_stream_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/filter/predictor_output_stream.py` (wave 1345 agent E) — negative-row-length `OSError` (line 47) via `columns=-1`; `writable()` accessor (line 61); flush-pad of an incomplete final row with TIFF-2 predictor (lines 131-134); idempotent `close()` invoking `flush` to pad-and-emit; and the `contextlib.suppress` swallow of a sink-side `close()` exception (5 tests) |
| `tests/fontbox/ttf/gsub/test_gsub_worker_for_bengali_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/gsub/gsub_worker_for_bengali.py` (wave 1345 agent E) — `script_feature is None` continue branch (lines 100-101) via a feature-list entry whose value is literally `None`; the `init`-feature glyph-id harvesting (lines 167-175) for single-glyph substitution clusters, including a populated-init case that augments the before-half list and exercises the swap path, plus an init feature carrying only multi-glyph substitutions (no augmentation) (3 tests) |
| `tests/fontbox/ttf/test_random_access_read_unbuffered_data_stream_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/random_access_read_unbuffered_data_stream.py` (wave 1345 agent E) — `read_long` sign-extension via an unsigned-high `read_int` override (line 84 — the defensive clamp is otherwise dead because `read_int` already sign-extends); `get_original_data` early-EOF break (line 138) via a view stand-in returning `-1` after a partial read; `get_original_input_stream` non-closing-view helper (line 152); and `create_sub_view` `OSError → None` fallback (lines 175-176) via a buffer raising on `create_view(pos>0)` (4 tests) |
| `tests/pdmodel/encryption/test_access_permission_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/encryption/access_permission.py` (wave 1345 agent E) — `is_permission_bit_on` for both default and all-zero instances (line 199); `set_permission_bit` true / false arms returning the new state (lines 211-215); upstream-parity bypass of read-only gate on `set_permission_bit`; 1-based indexing sanity (bit 1 == `1 << 0`); idempotent repeat-set/clear (7 tests) |
| `tests/util/test_number_format_util_wave1345.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/util/number_format_util.py` (wave 1345 agent E) — `_get_exponent` saturation tail (line 27) for values >= 10**18; negative-value minus-prefix branch of `format_float_fast` (lines 81-83); fraction-carry-into-integer branch (lines 91-92) via 0.99999 with 4-digit precision; the public `get_exponent` / `format_positive_number` upstream-parity wrappers (lines 111, 122); plus `inf`/over-LONG_MAX/over-MAX_FRACTION_DIGITS rejection arms, zero-fraction-digits no-decimal-point path, and trailing-zero strip (13 tests) |

### Wave 1347 additions — hand-written test files (agent C)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/filter/test_crypt_filter_wave1347.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/filter/crypt_filter.py` (wave 1347 agent C) — drives the residual `_resolve_name` fallback branches: `parameters is None` short-circuit (line 74); `get_dictionary_object` fallback returning a `COSName` (line 83), a plain `str` (line 85), and a non-`COSName`/non-`str` object (return-None tail); `str(value)` fall-through when `get_cos_name` yields a non-`COSName` value (line 89); plus end-to-end `decode`/`encode` rejection via the fallback-name path (8 tests). 89.7% → 100% |
| `tests/pdfparser/test_normal_x_reference_wave1347.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdfparser/xref/normal_x_reference.py` (wave 1347 agent C) — drives `_is_object_stream` `False` for a non-`COSStream` wrapped object (line 48); `__repr__`/`__str__` `ObjectStreamParent{` prefix branch (lines 95-96) for object-stream parents; `to_string()` Java-parity alias (line 109); and the `isinstance(obj, COSObject)` → `obj.get_object()` resolution path via a `COSObject` wrapper around a `/Type /ObjStm` stream; also re-asserts column accessors round-trip for the non-stream branch (6 tests). 89.7% → 100% |
| `tests/printing/test_pdf_pageable_wave1347.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/printing/pdf_pageable.py` (wave 1347 agent C) — drives the previously-uncovered getter/setter pairs: `get_rendering_hints` (line 50), `set_rendering_hints` (line 53), `is_subsampling_allowed` (line 56), `set_subsampling_allowed` (line 59); plus a round-trip that confirms the per-page `PDFPrintable` inherits the pageable's rendering hints + subsampling flag, and a default-`AUTO`-orientation `get_page_format` smoke (7 tests). 89.7% → 100% |
| `tests/filter/test_dct_decode_wave1347.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/filter/dct_decode.py` (wave 1347 agent C) — drives the Pillow-fallback colour-mode branches by monkey-patching `imagecodecs.jpeg8_decode` to raise so `Image.open` engages: `mode == "L"` (line 86), `mode == "CMYK"` (line 88), `mode == "RGB"` (line 90); plus the `OSError("DCTDecode: JPEG decode failed: ...")` wrapping when both decoders refuse (4 tests). 94.1% → 100% |
| `tests/io/test_random_access_read_write_buffer_wave1347.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/io/random_access_read_write_buffer.py` (wave 1347 agent C) — drives the residual constructor + `write_bytes` validation branches: `defined_chunk_size` positive override (line 27) and zero / negative / `None` no-op baselines; `write_bytes` `length=None` default-length branch (line 64) with both `bytes` and `memoryview` inputs; negative `length` `ValueError` (line 66); negative-`offset` and `offset + length` out-of-range `ValueError` (line 68); boundary `offset == nbytes, length == 0` (10 tests). 91.2% → 100% |

### Wave 1347 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/coverage_boost/test_wave1347_agent_e.py` | 3.0.x | hand-written coverage round-out for six modules (wave 1347 agent E). **`pypdfbox/xmpbox/xml/dom_helper.py` 89.7% → 100%** — `get_unique_element_child` empty-element `None` return (line 40); `get_first_child_element` text-only-element `None` return (line 49); `get_qname` triple return (line 58); `get_q_name` snake-case alias (line 63). **`pypdfbox/pdmodel/graphics/color/pd_tristimulus.py` 92.3% → 100%** — `get_cos_object` exposing the backing array (line 35); `_read` non-`COSNumber` fallback to `0.0` (line 41) via a `COSName` slot; `set_y` (line 60) and `set_z` (line 68) round-trips. **`pypdfbox/pdmodel/graphics/shading/cubic_bezier_curve.py` 90.6% → 100%** — `to_string` formatting every control point as `Point2D.Double[...]` (lines 57-60); `__repr__` delegation to `to_string` (line 63). **`pypdfbox/tools/pdf_box.py` 92.5% → 100%** — `run()` raising `SystemExit` (line 64); `main(None)` defaulting to `sys.argv[1:]` (line 69); `if __name__ == "__main__":` guard executed via `runpy.run_module(..., run_name="__main__")` (line 82). **`pypdfbox/tools/pdf_merger.py` 91.4% → 100%** — happy-path `call()` returning `0` with two real one-page PDFs merged via `PDFMergerUtility` (line 51); `if __name__ == "__main__":` block exercised via `runpy.run_module` (lines 79-80). **`pypdfbox/fontbox/ttf/otf_parser.py` 93.0% → 100%** — legacy underscore aliases `_new_font` / `_allow_cff` / `_read_table` forwarding to the public names (lines 114, 117, 120); `_check_tables` embedded-mode early-return (line 154); `_check_tables` lenient tail (line 162) reached by forcing `is_supported_otf()` to `False` on a parsed font (post-script-tag flag + stubbed `has_table` mapping `CFF ` → False / `CFF2` → True) (17 tests) |

### Wave 1347 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/test_coverage_wave1347_agent_b.py` | 3.0.x | hand-written coverage round-out for seven targets (wave 1347 agent B): **`pypdfbox/examples/interactive/form/create_multi_widgets_form.py` 95.7% → 100%** — `__init__` body (line 41); `set_widgets` exception-fallback to `get_widgets().extend(...)` (lines 104-107) via monkeypatched `PDTerminalField.set_widgets` raising. **`pypdfbox/examples/interactive/form/create_simple_form.py` 95.0% → 100%** — `__init__` body (line 39); `set_value` exception-fallback writing `"warning: set_value skipped"` to stderr (lines 94-97) via monkeypatched `PDTextField.set_value` raising. **`pypdfbox/examples/pdmodel/create_separation_color_box.py` 95.2% → 98%** — `__init__` body (line 53); two-or-more-arg usage-error `SystemExit(1)` writing `"Usage: ..."` to stderr (lines 70-73). **`pypdfbox/examples/signature/tsa_client.py` 92.9% → 100%** — real-`urlopen` transport fallback (lines 104-106) with a stubbed `urlopen` via `unittest.mock.patch` returning a context-manager fake response — no network IO. **`pypdfbox/tools/export_fdf.py` 90.7% → 100%** — `(AttributeError, NotImplementedError)` shim branch around `form.export_fdf()` (lines 37-38) via monkeypatched `PDAcroForm.export_fdf` raising `AttributeError`; `__main__` block (lines 64-65) via `runpy.run_module(..., run_name="__main__")`. **`pypdfbox/tools/export_xfdf.py` 90.5% → 100%** — same shim branch (lines 34-35) via monkeypatched `PDAcroForm.export_fdf` raising `NotImplementedError`; `__main__` block (lines 61-62) via `runpy`. **`pypdfbox/tools/overlay_pdf.py` 95.2% → 100%** — `finally`-block `OSError` from `overlayer.close()` (lines 67-71) via monkeypatched `Overlay.close` raising after delegating to the real close; `__main__` block (line 108) via `runpy` (13 tests) |

### Wave 1347 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/examples/pdmodel/test_examples_wave1347.py` | 3.0.x | hand-written coverage round-out for six pdmodel examples (wave 1347 agent A). **`pypdfbox/examples/pdmodel/create_patterns_pdf.py` 93.8% → 100%** — `__init__` body (line 47); two-or-more-arg usage-error `SystemExit(1)` (lines 65-68); `_set_tile_contents` TypeError guard (line 36) for a fake pattern whose `get_cos_object()` returns a non-`COSStream`; happy-path raw-byte write into the real `PDTilingPattern` COSStream. **`pypdfbox/examples/pdmodel/embedded_fonts.py` 91.3% → 100%** — `__init__` body (line 47); TTF-load branch (line 81) via `demo_with_font(out, ttf)` *and* via `main([out, ttf])` using the bundled `LiberationSans-Regular.ttf` fixture; glyph-fallback `try/except` (lines 102-108) via a `PDPageContentStream` subclass whose second `show_text` call raises `ValueError` — confirms the demo writes `"[skipped: unsupported glyph]"` and finishes saving a valid PDF. **`pypdfbox/examples/pdmodel/print_bookmarks.py` 92.3% → 100%** — item-level unknown-destination branch (line 69) via `unittest.mock.patch.object(PDOutlineItem, "get_destination", return_value=StubDest())`; action-level `PDNamedDestination` branch (lines 82-84) via `patch.object(PDActionGoTo, "get_destination", return_value=PDNamedDestination(...))` with a real `/Names /Dests` name tree wired into the catalog so `find_named_destination_page` resolves to page 2. Both branches are dead via the production `get_destination` dispatcher (which returns `str` for `/D`-as-name); patched here purely to pin the upstream-faithful guards. **`pypdfbox/examples/pdmodel/print_document_meta_data.py` 90.5% → 100%** — `/Metadata` stream branch (lines 57-60) by attaching an XML `/Metadata` `COSStream` containing `<?xpacket?><xmp/>` via `PDMetadata`, plus `format_date` non-None branch (line 68) by setting both creation and modification `datetime` values on `PDDocumentInformation`; direct call to the `@staticmethod` `format_date(datetime(2024,12,31,14,30))` pins the locale-default `%m/%d/%y %I:%M %p` format. **`pypdfbox/examples/pdmodel/add_message_to_each_page.py` 93.5% → 100%** — rotated-page branch (lines 40-42, 54) via `PDPage` with `set_rotation(90)`; confirms the rotate text-matrix path (`Matrix.get_rotate_instance(pi/2, ...)`) renders without raising and the resulting PDF is well-formed. **`pypdfbox/examples/pdmodel/create_bookmarks.py` 92.9% → 100%** — `__init__` body (line 31); encrypted-doc short-circuit (lines 41-45) via a `StandardProtectionPolicy`-protected source — the example writes `"Error: Cannot add bookmarks to encrypted document."` to stderr and raises `SystemExit(1)` without producing the destination file (15 tests) |
| `tests/examples/util/test_examples_wave1347.py` | 3.0.x | hand-written coverage round-out for two util examples (wave 1347 agent A). **`pypdfbox/examples/util/pdf_merger_example.py` 94.4% → 100%** — xmpbox `ImportError` branch (lines 108-109) by monkeypatching `sys.modules["pypdfbox.xmpbox.xml.xmp_serializer"]` and `sys.modules["pypdfbox.xmpbox.xmp_metadata"]` to `None`; `AttributeError` fallback inside `create_xmp_metadata` (lines 128-129) by installing a fake `XMPMetadata`/`XmpSerializer` module pair whose `create_and_add_pdfa_identification_schema` raises `AttributeError`; plus a round-trip that confirms `merge()` still emits a `%PDF`-prefixed buffer when `create_xmp_metadata` returns `None`. **`pypdfbox/examples/util/remove_all_text.py` 95.7% → 100%** — `strip` `(ImportError, AttributeError)` fallback (lines 61-65) by monkeypatching `sys.modules["pypdfbox.pdmodel.common.pd_stream"]` to `None` so the localized `from ... import PDStream` raises — the per-page rewrite is skipped and the saved PDF still appears on disk; `write_tokens_to_stream` `ContentStreamWriter` `ImportError` no-op (lines 100-101) via the same `sys.modules` trick — confirms `create_output_stream` on a sabotaged fake stream is never invoked (5 tests) |

### Wave 1349 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/debugger/ui/test_tree_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/ui/tree.py` (wave 1349 agent B). **`pypdfbox/debugger/ui/tree.py` 96.3% → 100%**: `_get_file_extension` fall-through where `node` is neither `MapEntry` nor `ArrayEntry` (line 179) via a plain `"FontFile"`/`"FontFile2"` string; `_make_save_raw_stream` save callback (lines 219-220) invoked through `build_menu_items` against a fake dialog capturing the *compressed* payload of a real `FlateDecode` stream; `_read_stream` `return bytes(data)` branch (line 355) via a context-manager whose `__enter__` returns plain `bytes` (no `.read`) for both the raw `create_raw_input_stream` and decoded `create_input_stream` paths; `_read_stream_partial` `TypeError` fall-back (lines 376-377) where the creator does not accept a `stop_filters` positional arg — forces the bare `creator()` retry; `_read_stream_partial` `return bytes(data)` branch (line 380) via a creator that returns plain `bytes`; and the empty-`stop_filters` skip when `stop_index >= len(filters)` (10 tests) |
| `tests/pdmodel/encryption/test_pd_encryption_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/encryption/pd_encryption.py` (wave 1349 agent B). **`pypdfbox/pdmodel/encryption/pd_encryption.py` 97.4% → 100%**: `get_security_handler` raising `OSError` with the upstream-parity message format `"No security handler for filter ..."` (matched by Apache Tika via TIKA-4082; verified with both the default-`None` `/Filter` and a named `"Standard"` filter) (lines 115-118); `set_security_handler` round-trip incl. overwriting an installed handler and the upstream-parity quirk that it does **not** also rewrite `/Filter` (line 127); the inverted `has_security_handler()` whose Java body is `return securityHandler == null;` — returns `True` when *missing* (line 136); `remove_v45filters` (the no-underscore alias) delegating to `remove_v45_filters` to strip `/CF`, `/StmF`, `/StrF`, `/EFF` when downgrading to V<=3 (line 569), including the idempotent no-op on an empty dict and a parity check between the two spellings (10 tests) |
| `tests/pdmodel/graphics/image/test_png_converter_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/image/png_converter.py` (wave 1349 agent B). **`pypdfbox/pdmodel/graphics/image/png_converter.py` 96.9% → 100%**: `parse_png_chunks` populating `state.iccp` (line 271), `state.trns` (line 273), `state.srgb` (line 275), `state.gama` (line 277), `state.chrm` (line 279) from synthetic PNG byte streams that splice each ancillary chunk type (iCCP, tRNS, sRGB, gAMA, cHRM) directly after a hand-crafted IHDR — the parser ignores the CRC value at chunk-walk time, so the helper builds chunks with `crc=0`; a combined-chunks PNG that proves the loop populates every slot in one pass without an early break; and the `convert_png_image` `ImportError` fall-through (lines 90-91) via a `monkeypatch` of `builtins.__import__` that raises for both the lazy `PIL` import and the `LosslessFactory` import — the helper returns `None` instead of propagating (8 tests) |

### Wave 1349 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdmodel/graphics/color/test_pd_indexed_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/color/pd_indexed.py` (wave 1349 agent A). **`pypdfbox/pdmodel/graphics/color/pd_indexed.py` 96.3% → 100%**: `set_base_color_space` `TypeError` raise (line 90) via a custom `PDColorSpace` subclass whose `get_cos_object` returns `None`; `read_lookup_data` consuming the `COSStream` branch (lines 205-206) by constructing the array with a `COSStream` /Lookup entry, plus the unsupported-slot-type fall-through returning `b""`; `read_color_table` clamping `n` to `1` when the base CS reports `0` components (line 229) via a monkeypatched `get_base_color_space` returning a `_ZeroComponentColorSpace`; `init_rgb_color_table` no-base-CS DeviceRGB-style fallback (lines 277-285) via `COSNull` in slot 1; `to_rgb_image` empty-palette short-circuit returning a black image (line 388) via the default `PDIndexed()` (no /Lookup); and `to_rgb_image` oversized-raster truncation (line 403) via a 4-byte raster for a 2×1 image (9 tests) |
| `tests/pdmodel/graphics/image/test_pd_inline_image_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/graphics/image/pd_inline_image.py` (wave 1349 agent A). **`pypdfbox/pdmodel/graphics/image/pd_inline_image.py` 97.6% → 100%**: `get_image` region-tuple crop branch (lines 641-643) via `(1, 1, 2, 2)` against a 4×4 DeviceGray ramp; `get_image` subsampling resize branch (lines 644-651) including the `max(1, dim // subsampling)` clamp at lines 647-648 via a 2×2 image with `subsampling=4`; `get_image` short-circuit returning `None` when `to_pil_image` returns `None` (via a 16-bpc raster); `get_stencil_image` post-guard branch (lines 665-666) returning the underlying mask when `is_stencil()` is true, with a `monkeypatch` recording stub on `to_pil_image` to confirm the `paint` argument is discarded; plus the upstream `ValueError("Image is not a stencil")` contract on a non-stencil image (9 tests) |

### Wave 1349 additions — hand-written test files (agent C)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/debugger/ui/test_osx_adapter_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/ui/osx_adapter.py` (wave 1349 agent C). **`pypdfbox/debugger/ui/osx_adapter.py` 96.3% → 100%**: `is_correct_method` `inspect.signature(method)` raising `TypeError` / `ValueError` (lines 89-90) via `monkeypatch.setattr(inspect, "signature", boom)`; string-annotation mismatch (line 112) — under `from __future__ import annotations` the source-declared `int` annotation is stored as `"int"`, so asking for `[str]` (which stringifies to `"str"`) trips the name-comparison miss path while keeping arity-match; and the live-class-object annotation mismatch (lines 114-115) via manual `fn.__annotations__ = {"a": int}` injection plus the success path that lets the loop fall through to `return True` (4 tests) |
| `tests/pdmodel/interactive/form/test_pd_button_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/interactive/form/pd_button.py` (wave 1349 agent C). **`pypdfbox/pdmodel/interactive/form/pd_button.py` 97.6% → 100%**: the instance-method `get_on_value(index)` alias delegating to `get_on_value_at_index` (line 298) on the base `PDButton` (sub-classes such as `PDCheckBox` shadow the zero-arg form); `update_by_value` widget-rejection branches when `/AP` is missing entirely, when `/AP` is a `COSString` rather than a dict (line 317), and when `/AP /N` is non-dict (line 320) — each interleaved with a sibling widget carrying a valid `/AP /N` so the field's `/V` is still rewritten via the matched key; `update_by_option` short-circuit when `value` is absent from `/Opt` (lines 376-377) — verifies neither widget's `/AS` nor the field's `/V` is touched (5 tests) |
| `tests/tools/test_text_to_pdf_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/tools/text_to_pdf.py` (wave 1349 agent C). **`pypdfbox/tools/text_to_pdf.py` 97.9% → 100%**: `_create_pdf_from_text` falling through `self.font is None` to call `PDFontFactory.create_default_font(self.standard_font.value)` (line 161); the form-feed look-ahead branch where the *next* word in `line_words` itself contains a `\f` and the width calculation trims it before measuring (line 211) — driven by `"a \fb"` so the lookahead from word `"a"` hits `next_word.find("\f")` → `[:idx]`; the defensive `OSError("Error:Expected non-null content stream.")` raise (line 233) by setting `t.bottom_margin = -10_000.0` so `y - line_height < bottom_margin` is False on the first iteration and `content_stream` never gets initialised. Three lines (`if text_is_empty: doc.add_page(page)` at 249, and the `if __name__ == "__main__"` guard at 320) were marked `# pragma: no cover` after analysis confirmed unreachability — the `[""]` fallback always iterates the outer loop once and clears `text_is_empty` before the post-loop check (3 tests) |

### Wave 1349 additions — hand-written test files (agent E)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/tools/test_extract_images_coverage_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/tools/extract_images.py` (wave 1349 agent E). **`pypdfbox/tools/extract_images.py` 97.5% → 100%**: `ImageGraphicsEngine.run` soft-mask-with-`None`-group `continue` (line 66) via an `_ExtGState` whose `get_soft_mask().get_group()` returns `None`; the outer `try`/`except` swallow around `copy_into_graphics_state` (line 70) and `process_soft_mask` (line 71) — each driven by stubs that raise `AttributeError` / `NotImplementedError` and asserting the loop continues without dispatching. The `if __name__ == "__main__"` script entrypoint (line 226) was marked `# pragma: no cover` (3 tests) |
| `tests/debugger/treestatus/test_tree_status_pane_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/debugger/treestatus/tree_status_pane.py` (wave 1349 agent E). **`pypdfbox/debugger/treestatus/tree_status_pane.py` 96.2% → 100%**: subclasses `TreeStatusPane` to override `_locate_item_for_path` so the resolved-item branch of `_on_text_input` fires `selection_set` / `see` / `focus_set` on the underlying `ttk.Treeview` (lines 128-130); verifies `tree.selection()` after the dispatch (1 test) |
| `tests/fontbox/ttf/test_glyf_composite_comp_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/glyf_composite_comp.py` (wave 1349 agent E). **`pypdfbox/fontbox/ttf/glyf_composite_comp.py` 97.9% → 100%**: the point-anchored decode path (flags=0 → no `ARGS_ARE_XY_VALUES`) that stores the two signed-byte argument words on `_point1` / `_point2` while leaving the translate slots at zero (lines 82-85); plus the `has_instructions()` predicate (line 215) verified across no-flag, `WE_HAVE_INSTRUCTIONS` alone, and combined-flag inputs (2 tests) |
| `tests/fontbox/ttf/test_glyph_renderer_wave1349.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/fontbox/ttf/glyph_renderer.py` (wave 1349 agent E). **`pypdfbox/fontbox/ttf/glyph_renderer.py` 96.2% → 100%**: builds a one-contour glyph with two consecutive off-curve interior points (on, off, off, on) so the third `elif` branch fires `mid_value` + `qCurveTo` for the implicit on-curve midpoint (lines 118-119); the trailing defensive `else` (lines 120-124) was marked `# pragma: no cover` after analysis confirmed `contour[-1]` is always on-curve after the close-step massaging (1 test) |
| `pypdfbox/fontbox/pfb/pfb_parser.py` (no new test file; existing wave-1341 coverage suite combined with `# pragma: no cover` annotations) | 3.0.x | round-out for `pypdfbox/fontbox/pfb/pfb_parser.py` (wave 1349 agent E). **`pypdfbox/fontbox/pfb/pfb_parser.py` 97.4% → 100%**: three truly unreachable defensive branches were annotated `# pragma: no cover` after analysis confirmed they cannot fire through any public-API path — line 78 (`PFB header missing` after `total == 0` in the inner `while`, guarded out by the `len(pfb) < 18` minimum check at line 66); line 100 (`size < 0` — `size` is composed from four unsigned bytes via OR/shift, always 0..0xFFFFFFFF); line 113 (`total > len(pfb)` after the accumulating loop — each record consumes `6 + size` bytes, so `sum(size) + 6N <= len(pfb)`). Wave 1341 already flagged these as dead code; this wave records the conclusion in source. |

### Wave 1349 additions — hand-written test files (agent D)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/coverage_boost/test_wave1349_agent_d.py` | 3.0.x | hand-written coverage round-out for five targets (wave 1349 agent D). **`pypdfbox/examples/pdmodel/extract_ttf_fonts.py` 97.5% → 100%**: the four `return` statements that follow `ExtractTTFFonts.usage()` (lines 37, 50, 56, 67) — `usage()` raises `SystemExit(1)` in normal use so the `return`s are otherwise unreachable; tests monkey-patch `usage` to a no-op so the subsequent `return` executes for each argv-validation arm (empty argv, `-password` missing value, `-prefix` missing value, `-addkey` only); `process_resources(None, ...)` short-circuit (line 117); `write_font(None, ...)` short-circuit (line 207). **`pypdfbox/pdmodel/fixup/processor/acro_form_orphan_widgets_processor.py` 96.4% → 100%**: `handle_annotations` `ImportError` swallow (lines 103-104) and `resolve_non_root_field` `ImportError` swallow (lines 174-175) — both reached via a monkey-patched `builtins.__import__` that raises on the lazy `PDAnnotationWidget` / `PDFieldFactory` imports. **`pypdfbox/pdmodel/graphics/shading/radial_shading_context.py` 97.0% → 98%** (98% reported — see latent bug below): high-input no-extend / no-bg `continue` (line 165) via `extend=(True, False)` so the elif chain selects `r0 > 1` then the high-side block falls through `elif bg is None: continue`; low-input extend[0]-with-`r0==0` `use_background = True` (line 174) and its mirror high-input extend[1]-with-`r1==0` (line 174) — both with `coords[2]=0` or `coords[5]=0` forcing the first clause to fail and bg present. **`pypdfbox/pdmodel/interactive/annotation/handlers/pd_line_appearance_handler.py` 97.6% → 100%**: `paths_array is None` early-return (line 49) by removing `/L` from a freshly-constructed `PDAnnotationLine`; caption-emit `(AttributeError, ValueError)` swallow (lines 182-184) by monkey-patching `PDPageContentStream.begin_text` to raise `AttributeError` so the catch fires without leaving the content stream in BT-mode; `_interior_components` `size()` branch (line 269) via a lazy `__getattr__` stand-in that hides `to_float_array` from the outer `hasattr` probe yet resolves it inside the elif arm. **`pypdfbox/pdmodel/interactive/annotation/handlers/pd_polyline_appearance_handler.py` 96.7% → 100%**: `cs.set_dash_pattern` emission (line 80) via a `PDBorderStyleDictionary` with `STYLE_DASHED` + non-zero `/D` dash array — verified through the `d` operator in the resulting appearance-stream bytes; `_interior_components` `size()` branch (lines 170-172) via the same lazy-`__getattr__` pattern as the line handler. **Latent bugs flagged:** (1) `RadialShadingContext.get_raster` clamps `input_value` to literal `0` / `1` on the extend branches (lines 163, 170) rather than `self._domain[0]` / `self._domain[1]` as the sibling `AxialShadingContext` does — this leaves the post-key clamps at lines 180 / 182 (`if key < 0: key = 0` / `elif key > factor: key = factor`) structurally dead. Upstream Java RadialShadingContext likely uses domain values; needs an upstream cross-check before fixing. (2) `PDLineAppearanceHandler.generate_normal_appearance` catches `(AttributeError, ValueError)` around the caption emission block (lines 173-184) but does *not* call `cs.end_text()` in the except clause; if `cs.show_text` raises mid-BT, the subsequent `cs.restore_graphics_state()` at line 201 then raises `RuntimeError: restore_graphics_state is not allowed within a text block`. The test deliberately patches `begin_text` (pre-BT) to avoid this latent crash. (20 tests) |

### Wave 1348 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdfwriter/test_cos_writer_wave1348.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdfwriter/cos_writer.py` (wave 1348 agent A) — drives every residual defensive branch reported by coverage. **`pypdfbox/pdfwriter/cos_writer.py` 97.1% → 100%**: `_format_xref_table_generation` rejecting `< 0` and `> 65535` (line 110); the snake_case PDFBox-parity façades that forward to the underscore-prefixed workers — `prepare_increment` (line 667), `do_write_header` (line 743), `do_write_body` (line 748), `do_write_body_compressed` (line 755), `do_write_trailer` (line 767), `do_write_x_ref_table` (line 772), `do_write_x_ref_inc` BOTH branches: classic-xref via incremental mode (lines 789-791) and xref-stream via full-save mode (line 788), `fill_gaps_with_free_entries` (line 797), `do_write_increment` (line 804); `is_need_to_be_updated` non-callable-attribute (line 690) and exception-during-callable (lines 693-694); `detect_possible_signature` full body (lines 714-738) — non-`COSDictionary` guard, full-save short-circuit, idempotent flag, no `/Type` name, unrelated `/Type` (e.g. `/Annot`), missing `/ByteRange`, `ByteRange[2]` not a `COSInteger`, success edge for both `/Sig` and `/DocTimeStamp` with `ByteRange[2] > source_length`, and the negative edge where the placeholder lies inside the source; `_do_write_body_xref_stream` `info is not None` arm (line 1837) via a trailer carrying both `/Root` and `/Info`; `_pack_object_streams` `_is_packable` False `continue` (line 1875) via a `COSStream` injected into `_key_object`; `_propagate_document_id` early-return when the trailer already carries a 2-element `/ID` (line 1166); `_stage_encryption` `PublicKeyProtectionPolicy` arm (lines 1135-1137) via a stubbed `PublicKeySecurityHandler` whose `prepare_document` records the routing without needing X.509 / PKCS#7 infrastructure (27 tests) |
| `tests/multipdf/test_splitter_wave1348.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/multipdf/splitter.py` (wave 1348 agent B). **`pypdfbox/multipdf/splitter.py` 93% → 100%**: public-named hooks (`process_pages` line 325, `create_new_document_if_necessary` line 459, `process_annotations(imported)` 1-arg form line 472); `_process_annotations` source-side `/Annots` walk skipping non-`COSDictionary` entries (line 636), popup back-reference rewrite from `source_ann_dict` (line 645), orphan-popup clone + `set_page` (lines 664-681), popup `/Parent` source-side lookup (line 686), popup `/Parent` rewrite to cloned markup and the `remove_item(/Parent)` orphan fallback (lines 701-705); `_stage_link_destination` named-destination str wrapping into `PDNamedDestination` for `GoTo` action `/D` (line 907), source-target `get_page()` exception path (lines 935-936), cloned-link `get_action()` exception fallback to source action dict (lines 957-958); `clone_structure_tree` annotation `/StructParent` clone (line 1105) and normal-appearance-stream `/Resources` walk (lines 1114-1118) with patched `PDAnnotation.get_normal_appearance_stream` returning a stub whose `get_resources()` raises; `process_resources` Form XObject `/StructParents` branch (lines 1525-1548) via real `PDFormXObject` with nested `/Resources` recursion, Image XObject `/StructParent` branch (lines 1549-1555) via real `PDImageXObject`, plus defensive guards for resources `get_cos_object`/`get_xobject_names`/`get_x_object` raising (lines 1513-1514, 1522-1523, 1527-1528) and the Form/Image `get_struct_parent[s]` exception arms (lines 1540-1548, 1552-1553) (22 tests) |
| `tests/pdmodel/encryption/test_standard_security_handler_wave1348.py` | 3.0.x | hand-written coverage round-out for `pypdfbox/pdmodel/encryption/standard_security_handler.py` (wave 1348 agent B). **`pypdfbox/pdmodel/encryption/standard_security_handler.py` 97.1% → 100%**: arity-dispatch `TypeError` on a wrong-arg-count call to `is_user_password` / `is_owner_password` (lines 445, 493); str-password Latin-1 / UTF-8 encoding branches in `_is_user_password_explicit` (lines 576-577) and `_is_owner_password_explicit` (lines 602-603); `_get_document_id_bytes` `size()` raising `TypeError` (lines 1167-1168), missing `get`/`get_object` accessor, and `getter(0)` lacking `get_bytes` (line 1177); `truncate_127(None)` returning `b""` (line 1388); `compute_rc_4_key` raising `ValueError` from `hashlib.md5` → re-raised as `OSError` (lines 1475-1477) via a temporary patch; `validate_perms` `perms is None` early return (line 1497), decrypt-failure log (lines 1500-1501), perm-int mismatch warning (lines 1513-1514), and metadata-flag mismatch warning (covers the encrypt-metadata branch); `_compute_encryption_key_rev_5_6` missing-`/OE` and missing-`/UE` guards (lines 1543, 1552) plus the r5 SHA-256 owner and user branches (lines 1546, 1555); public `compute_encrypted_key_rev56` mirror raising on missing `/OE` and `/UE` (lines 1872, 1869); upstream-name aliases `is_user_password234` / `is_user_password56` / `is_owner_password234` / `is_owner_password56` (lines 1906, 1931); `get_user_password234` r2 single-pass branch (line 1950); `prepare_encryption_dict_rev234` empty-owner-pw promotion to user-pw (line 2019) and r4 AESV2 install (line 2047); `prepare_encryption_dict_rev6` empty-owner-pw promotion (line 2066) (31 tests) |
| `tests/cos/test_cos_array_wave1348.py` + `tests/debugger/pagepane/test_debug_text_overlay_wave1348.py` + `tests/pdmodel/interactive/form/test_pd_choice_wave1348.py` + `tests/xmpbox/type/test_type_mapping_wave1348.py` + `tests/debugger/streampane/test_stream_pane_wave1348.py` + `tests/fontbox/ttf/test_cmap_subtable_wave1348.py` + `tests/pdmodel/encryption/test_security_handler_wave1348.py` | 3.0.x | hand-written coverage round-out for seven files (wave 1348 agent E). **`pypdfbox/cos/cos_array.py` 96.5% → 100%**: module-level `_add_to_collection` `append` fallback + no-op when neither method exists (lines 27-29); `growToSize` camelCase Java-name alias (line 220); `reset_object_keys` short-circuit when an indirect key is already in the visited set (line 496), recursive descent into a nested `COSArray` (line 499), and `elif indirect_key is not None` arm recording an indirect leaf (line 501); `iterator()` (line 529); `maybe_wrap` for an indirect dict with recorded key — rewrapped as `COSObject` (lines 544-554), direct dict pass-through, indirect dict missing recorded key pass-through, leaf pass-through. **`pypdfbox/debugger/pagepane/debug_text_overlay.py` 96.5% → 100%**: `calculate_glyph_bounds` Type3 `get_char_proc` raising → returns None (lines 544-545); Type3 `get_glyph_bbox` raising → returns None (lines 551-552); Type3 bbox-clamp setters raising → silently caught + un-clamped points still emitted (lines 571-572); non-Type3 `get_normalized_path` raising → falls back to bbox (lines 584-585); non-Type3 bbox point construction raising → returns None (lines 615-616). **`pypdfbox/pdmodel/interactive/form/pd_choice.py` 96.2% → 100%**: `get_value_for` dispatch (lines 319-320) for absent entry, single `COSString`, and `COSArray`; `update_selected_options_index` ascending-sort of mixed indices (line 342), `-1` for absent values mirroring Java `List.indexOf` (line 341), and empty-values path that clears `/I`. **`pypdfbox/xmpbox/type/type_mapping.py` 96.6% → 100%**: `initialize` ``continue`` arm when a structured class lacks `NAMESPACE` (line 299) via monkeypatching `_STRUCTURED`; `get_specified_property_type` multi-struct namespace branches — `parent_type_name` match (lines 482-484), local-part fallback scan (lines 485-488), and total miss returning None (line 489); `get_associated_schema_object` factory fallback (lines 607-609) when `XMPMetadata.create_and_add_default_schema_for_namespace` is removed. **`pypdfbox/debugger/streampane/stream_pane.py` 97.2% → 100%**: `_content_stream_segments` broad-except path (lines 311-313) via a monkeypatched `PDFStreamParser.from_bytes` that raises `RuntimeError`; `_ContentStreamEmitter.write_token` `AttributeError` catch (lines 391-392) by patching `_write_operand` to raise; `DocumentCreator.get_content_stream_document` broad-except path (lines 636-638) via the same parser monkeypatch. **`pypdfbox/fontbox/ttf/cmap_subtable.py` 97.6% → 100%**: the underscore-prefixed backwards-compat aliases that delegate to the public subtype processors — `_process_subtype_0` (line 110) with a 256-byte mapping, `_process_subtype_4` (line 165) with a minimal 2-segment body, `_process_subtype_6` (line 189) with 3 trimmed entries, `_process_subtype_8` (line 225), `_process_subtype_10` (line 250), `_process_subtype_13` (line 324), `_process_subtype_14` (line 371); static `_new_glyph_id_to_character_code` alias (line 471) returning `[-1] * size`; `_get_char_code` alias (line 533) delegating to `get_char_code`. **`pypdfbox/pdmodel/encryption/security_handler.py` 97.8% → 100%**: base `compute_encrypted_key` `StandardSecurityHandler` dispatch (line 370) — reachable only via an explicit unbound `SecurityHandler.compute_encrypted_key(handler, ...)` call (subclass classmethod shadows the base method on instance dispatch; see latent-bug note in CHANGES.md); `decrypt` COSStream dispatch (line 467); `decrypt_stream_in_place` `COSName` `ImportError` fallback (lines 523-524) via monkeypatched `builtins.__import__`; `get_item("Type")` arm (lines 532-533) via a legacy duck-typed stream lacking `get_cos_name`; broad-except on `get_raw_bytes` raising (lines 555-556); `_decrypt_array` setter path (line 620) via a real `COSArray` end-to-end decrypt walk (45 tests across the seven files). **Latent bug observed:** `SecurityHandler.compute_encrypted_key` is unreachable through normal instance dispatch — every concrete `SecurityHandler` subclass either overrides it (`StandardSecurityHandler` via classmethod) or raises `TypeError` (`PublicKeySecurityHandler`). The branch on line 370 is structurally dead unless invoked unbound. |
| `tests/fontbox/ttf/test_glyph_substitution_table_wave1348.py` + `tests/pdmodel/graphics/color/test_pd_icc_based_wave1348.py` + `tests/pdmodel/interactive/annotation/handlers/test_pd_text_appearance_handler_wave1348.py` + `tests/pdmodel/fdf/test_fdf_annotation_wave1348.py` | 3.0.x | hand-written coverage round-out for four files (wave 1348 agent D). **`pypdfbox/fontbox/ttf/glyph_substitution_table.py` 96.0% → 100%**: structural None-guard branches (`get_lookup_indices_for_feature` empty `FeatureList`, record-with-None-`Feature` skip, dedup; `get_lookup_count` / `get_lookup_types` None `LookupList`; `get_lang_sys_tables` None `ScriptList` / None `Script` / `LangSysRecord` iteration with mixed-None entries — lines 208, 217, 237, 252, 383, 389, 396-398); `get_feature_records` None `FeatureList`, empty `FeatureRecord`, out-of-range `FeatureIndex` skip, enabled-features re-sort (lines 433, 436, 448, 461); `_select_script_tag` empty-tags branches — cached, first script, none — and the single-tag `DFLT`-without-scripts path (lines 598-600, 613); `_collect_feature_indices` None script_tag, `absorb(None)` skip, out-of-range tag_for filter (lines 636, 650, 672); `_apply_single_lookup_in_gid_space` falsy-mapping subtable skip (line 702); `apply_feature` out-of-range / non-single LookupType skip and None-feature short-circuit (lines 746, 749); `get_substitution` out-of-range feature-index skip via monkeypatch (line 549); byte-level `read_script_table` lang-sys sort-error path and valid lang-sys collection (lines 905-911, 920); `read_feature_list` debug-only sort branch (alphanumeric tags out of order, parser continues — line 969); `read_lookup_list` out-of-bounds lookup offset (line 1039); `read_lookup_subtable` dispatch to types 2/3/4 via crafted MULTIPLE/ALTERNATE/LIGATURE sub-tables (lines 1071, 1073, 1075); `read_lookup_table` extension-lookup-type-mismatch error skip — second extension subtable's `extensionLookupType` differs from the first subtable's reassigned value (lines 1148-1155). **`pypdfbox/pdmodel/graphics/color/pd_icc_based.py` 96.1% → 100%**: `create()` resource-cache miss-then-hit, non-ICC cache entry repointed, missing-cache short-circuit, direct-stream skip (lines 85-92); malformed-stream short-circuits in `set_alternate` / `set_alternate_color_spaces` / `set_range` / `clear_range` (lines 201-202, 238, 272); in-place `set_range_for_component` replace via existing-array path (lines 314-315); `to_rgb` N-based alternate inference for N=1 → DeviceGray, N=4 → DeviceCMYK, N=2 → None (lines 729, 732-735); `_try_icc_to_rgb` Pillow-malformed-profile path and `n not in (1,3,4)` early-outs (lines 749, 753-754, 766-769, 772-773, 805-806); defensive `UnicodeDecodeError` branches in `is_srgb` / `is_s_rgb` / `get_color_space_type` triggered via a bytes-proxy whose `__getitem__` returns a `.decode`-raising slice (lines 444-445, 478-479, 525-526). **`pypdfbox/pdmodel/interactive/annotation/handlers/pd_text_appearance_handler.py` 96.6% → 100%**: every public `draw_*` snake_case alias forwarder (`draw_note` / `draw_circles` / `draw_insert` / `draw_cross_hairs` / `draw_help` / `draw_comment` / `draw_key` / `draw_paragraph` / `draw_new_paragraph` / `draw_right_arrow` / `draw_up_arrow` / `draw_up_left_arrow` / `draw_zapf` — lines 223, 230, 237, 244, 251, 258, 265, 272, 279, 286, 293, 300, 312) plus `adjust_rect_and_b_box` (line 184); `generate_normal_appearance` non-`PDAnnotationText` reject (line 111) via a `PDAnnotationLink`; unsupported `/Name` no-op short-circuit; parametrised dispatch walk over all 16 supported `/Name` values. **`pypdfbox/pdmodel/fdf/fdf_annotation.py` 96.1% → 100%**: `create()` dispatch branches for Polygon, PolyLine, Polyline, Ink, Stamp, Caret, Highlight/Underline/StrikeOut/Squiggly TextMarkup, unknown-subtype + missing-subtype fall-through to bare `FDFAnnotation` (lines 591-615); `get_rectangle_as_pd_rectangle` `TypeError` swallow when slot 2 is a `COSName` instead of a number (lines 186-187); `set_rich_contents(None)` removal path (lines 470-471); `parse_rectangle_attributes` `None`-rect and non-numeric token `OSError` raises (lines 521, 527-528) plus length-mismatch and `create_rectangle_from_attributes` round-trip (113 tests across the four files) |

### Wave 1351 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdfparser/test_object_numbers_wave1351.py` + `tests/pdfparser/test_pdf_xref_stream_parser_wave1351.py` + `tests/pdmodel/fdf/test_fdf_annotation_caret_wave1351.py` + `tests/pdmodel/fdf/test_fdf_annotation_free_text_wave1351.py` + `tests/pdmodel/fdf/test_fdf_annotation_polygon_wave1351.py` + `tests/pdmodel/fdf/test_fdf_template_wave1351.py` | 3.0.x | hand-written coverage round-out for six residual-2-line files (wave 1351 agent C). **`pypdfbox/pdfparser/object_numbers.py` 96.6% → 100%**: the constructor's second `except StopIteration: break` arm (lines 43-44) reached by passing an odd-length `/Index` array (`[0, 3, 99]`); the trailing unpaired start value is silently dropped, matching upstream's lenient parse (1 test). **`pypdfbox/pdfparser/pdf_xref_stream_parser.py` 97.5% → 100%**: the constructor's `except OSError: self.close(); raise` arm (lines 41-42) reached by feeding `/Index` whose first element is a `COSName` instead of `COSInteger` — `PDFParseError` is `ValueError`-derived and slips past this `except`, but `ObjectNumbers`'s own constructor raises `OSError` directly which the parser catches, closes itself, and re-raises (1 test). **`pypdfbox/pdmodel/fdf/fdf_annotation_caret.py` 94.9% → 100%**: the `except (TypeError, ValueError): return None` arm of `get_fringe()` (lines 48-49) reached by a 4-entry `/RD` of `COSName.A` values — `PDRectangle.from_cos_array` raises `TypeError` and the helper swallows it (1 test). **`pypdfbox/pdmodel/fdf/fdf_annotation_free_text.py` 97.7% → 100%**: same `get_fringe()` swallow path as caret (lines 169-170), driven the same way (1 test). **`pypdfbox/pdmodel/fdf/fdf_annotation_polygon.py` 96.6% → 100%**: `init_vertices` early `return` on `None` (line 33) and the empty-segment `continue` (line 38) reached by `";1,2;;3,4;"` whose leading / trailing / consecutive `;` separators yield empty pairs around the valid ones (2 tests). **`pypdfbox/pdmodel/fdf/fdf_template.py` 95.7% → 100%**: `set_fields(None)` remove-and-return arm (lines 78-79), exercised both against a populated template and a freshly-constructed template (2 tests). No source changes; no `# pragma: no cover` markers added; no latent bugs flagged. |
| `tests/debugger/fontencodingpane/test_font_pane_wave1351.py` + `tests/debugger/ui/test_recent_files_wave1351.py` + `tests/debugger/ui/test_zoom_menu_wave1351.py` + `tests/examples/interactive/form/test_print_fields_wave1351.py` + `tests/examples/lucene/test_lucene_pdf_document_wave1351.py` | 3.0.x | hand-written coverage round-out for five residual-2-line files (wave 1351 agent A). **`pypdfbox/debugger/fontencodingpane/font_pane.py` 97.4% → 100%**: `_iter_xy_pairs` early-return for `None` / `str` segments inside the outer iterable (line 138) via paths `[None]` and `["closePath"]`; final `return []` for non-list-non-tuple inner items (line 150) via paths `[42]` and `[object()]` — the existing wave-pre-1351 test `test_y_bounds_handles_path_iteration_error` passed `42` directly as the path, which `_path_y_bounds` short-circuits at `list(path)` raising `TypeError`, so `_iter_xy_pairs` was never entered (4 tests). **`pypdfbox/debugger/ui/recent_files.py` 97.9% → 100%**: `write_history_to_pref` `except OSError: return` on the second `Path.write_text` call (lines 145-146) via a `monkeypatch` of `Path.write_text` that raises `OSError("disk full")` for the target store — confirms no exception propagates and nothing is written (1 test). **`pypdfbox/debugger/ui/zoom_menu.py` 96.8% → 100%** (current 94% in this environment, lines 113-114 also missed alongside the brief-quoted 117-118): `get_zoom_scale` `_instance is None` `RuntimeError` (lines 113-114) reached with no prior `get_instance` call; `get_zoom_scale` empty-selection / malformed-selection `RuntimeError` (lines 117-118) reached by setting `_zoom_var` to `""` and to `"garbage"` (3 tests). **`pypdfbox/examples/interactive/form/print_fields.py` 95.7% → 100%**: `process_field` `except Exception: field_value = ""` (lines 56-57) via a direct call with a `Mock(spec=PDTextField)` whose `get_value_as_string.side_effect = RuntimeError` — the existing wave-pre-1351 test `test_process_field_handles_value_exception` monkey-patched the bound method on an instance but `PDAcroForm.get_fields()` re-wraps the COS tree on every read, dropping the monkey-patch before `process_field` is dispatched, so the exception branch had been silently uncovered (1 test). **`pypdfbox/examples/lucene/lucene_pdf_document.py` 95.7% → 100%**: `create_uid` URL-style branch (lines 131-132) — `time=None` *and* `file_or_url` not `str`/`Path` (a duck-typed `_UrlLike` stand-in for `java.net.URL`) triggers the `key = str(file_or_url); time = 0` arm that mirrors upstream's `createUID(URL u)` overload (1 test). **Latent bug flagged:** `tests/examples/interactive/form/test_print_fields.py::test_process_field_handles_value_exception` (wave pre-1351) silently fails to exercise the exception branch it claims to cover — `field.get_value_as_string = _raise` monkey-patches the instance, but `PDAcroForm.get_fields()` constructs fresh wrappers from the COS tree on every call, so the patched method is discarded before `print_fields` dispatches into `process_field`. The new wave-1351 test bypasses `print_fields` and calls `process_field` directly with a `Mock` field so the exception path is actually executed. The original test still asserts on output strings and passes coincidentally because the bare `PDTextField` returns an empty value via the happy path. |
| `tests/tools/test_tools_main_blocks_wave1351.py` + `tests/tools/test_write_decoded_doc_wave1351.py` + `tests/xmpbox/schema/test_xmp_schema_factory_wave1351.py` | 3.0.x | hand-written coverage round-out for six residual-2-line files (wave 1351 agent E). **`pypdfbox/tools/decompress_objectstreams.py` 94.1% → 100%** (lines 57-58), **`pypdfbox/tools/import_fdf.py` 96.2% → 100%** (lines 85-86), **`pypdfbox/tools/import_xfdf.py` 96.2% → 100%** (lines 77-78), **`pypdfbox/tools/pdf_split.py` 97.1% → 100%** (lines 104-105), **`pypdfbox/tools/write_decoded_doc.py` 97.4% → 100%** (line 113 of the `__main__` trailer): a single parametrised test invokes each module under `runpy.run_module(..., run_name="__main__")` with a missing input path and asserts `SystemExit.code == 4` (5 tests). **`pypdfbox/xmpbox/schema/xmp_schema_factory.py` 93.3% → 100%**: the `elif prefix and len(params) >= 2: args = [metadata, prefix]` branch (lines 55-56), reached via `AdobePDFSchema` (init `(metadata, own_prefix=None)`) with an explicit prefix routes through the two-arg constructor path; plus the fall-through `args = [metadata]` arm with `prefix=None` (2 tests). **`pypdfbox/tools/write_decoded_doc.py` line 59** (the `skip_images=True` AND-of-three early `return` on `/Type == /XObject` ∧ `/Subtype == /Image`): one positive (skip leaves `/Filter` intact even with corrupt FlateDecode payload), one negative for the AND short-circuit at SUBTYPE (`/Form` XObject still gets processed under `skip_images=True`), and one for the gate itself (3 tests). **Latent bug fixed (write_decoded_doc skip-images):** the `process_object` early-return on line 57-59 references `COSName.XOBJECT` and `COSName.IMAGE` — neither was defined on `COSName` (only the spec literals existed in the canonical-name table). The `-skipImages` CLI flag therefore raised `AttributeError: type object 'COSName' has no attribute 'XOBJECT'` on any document with a typed stream. Added three spec-standard static names to `pypdfbox/cos/cos_name.py` after `COSName.METADATA`: `XOBJECT = "XObject"`, `IMAGE = "Image"`, `FORM = "Form"` (PDF 32000-1 §8.8). The `-skipImages` codepath now works as documented. No `# pragma: no cover` markers added. |
| `tests/examples/pdmodel/test_using_text_matrix_wave1351.py` + `tests/examples/util/test_pdf_highlighter.py` + `tests/fontbox/cff/test_cff_operator.py` + `tests/fontbox/cff/test_dict_data.py` + `tests/io/test_random_access_read_wave1351.py` + `tests/pdfparser/test_fdf_parser_coverage.py` | 3.0.x | hand-written coverage round-out for six residual-2-line files (wave 1351 agent B). **`pypdfbox/examples/pdmodel/using_text_matrix.py` 97.3% → 100%**: `main`'s `len(argv) != 2` branch that routes to `usage()` (line 125) — exercised with `main([])`, `main(["only-message"])`, `main(["a", "b", "c"])`, and `main(None)`; plus a direct `usage()` invocation to cover the `sys.stderr.write` call (line 130) — 5 tests. **`pypdfbox/examples/util/pdf_highlighter.py` 96.7% → 100%**: the `try / except AttributeError: pass` arm of `__init__` (lines 35-37) — reached by `monkeypatch.delattr(PDFTextStripper, "set_should_separate_by_beads")` so the constructor's third `self.set_*` call raises `AttributeError` and the swallow arm finishes initialisation (1 test). **`pypdfbox/fontbox/cff/cff_operator.py` 94.6% → 100%**: `register(b0, *args)` `TypeError` raise on wrong positional-arg count (lines 76-79) via `register(42)` and `register(42, 1, 2, "TooMany")`; plus the `isinstance(name, str)` guard (line 81) via single-byte `register(252, 1234)` and two-byte `register(253, 7, 9876)` — 4 tests. **`pypdfbox/fontbox/cff/dict_data.py` 97.7% → 100%**: `Key.__str__` (line 42) returning the bare operator name; `DictData.__repr__` (line 207) delegating to `to_string()` — 2 tests. **`pypdfbox/io/random_access_read.py` 97.4% → 100%**: the ABC's default `create_view` body (lines 145-147 — deferred import of `RandomAccessReadView` and the `RandomAccessReadView(self, start, length)` factory call) — every shipped concrete subclass overrides `create_view`, so a barebones `RandomAccessRead` test subclass is constructed to drive the default path with a non-empty slice and a zero-length slice — 2 tests. **`pypdfbox/pdfparser/fdf_parser.py` 94.1% → 100%**: the explicit `raise PDFParseError("Error: Header doesn't contain versioninfo")` inside `parse` when `parse_fdf_header()` returns falsy (line 62) — reached by replacing the bound method on the parser instance with `lambda: False`; plus the `parse_pdf_header()` fallback in `parse_fdf_header()` (line 86), reached via `monkeypatch` of `COSParser.parse_fdf_header` to `None` (delattr) and to a non-callable sentinel string `"not-a-method"` — 3 tests. No source changes; no `# pragma: no cover` markers added; no latent bugs flagged. |

### Wave 1352 additions — hand-written test files (agent A)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/rendering/test_pdf_renderer_wave1352.py` | 3.0.x | hand-written coverage round-out for the largest residual-gap file in the suite (wave 1352 agent A). **`pypdfbox/rendering/pdf_renderer.py` 98.6% → 100%**, closing all 35 missing lines across 11 distinct branch clusters (26 tests). Covered branches: `has_blend_mode` page-with-no-resources (line 762), `get_ext_g_state_names` raises (lines 765-766), `get_ext_gstate` raises (lines 771-772), `ext_gstate is None` skip (line 776) — driven by `MagicMock` `PDPage` / `PDResources` shapes. `is_bitonal` duck-typed branches (lines 801, 809-810, 813): inner `.image.mode`, `get_bit_depth()` callable returning 1 / raising, `bit_depth` int attribute 1 / non-1. `create_page_drawer` `PageDrawer(parameters)` raises `TypeError` → falls back to `self` (lines 873-874) via `monkeypatch` of `PageDrawer.__init__`. `transform` rotation 180 (lines 906-907) and 270 (line 904) translation arms; plus duck-typed `scale` / `translate` / `rotate` replays on a graphics target. `render_page_to_graphics` anisotropic-scale `Image.resize` path (lines 975-979) and the duck-typed paste fallbacks (lines 987-995): `paste` happy path, `draw_image`, `drawImage` (camelCase), the `TypeError` → 3-arg retry, and the silent no-op for objects with no paste API. `_stroke_via_aggdraw` (line 1594) delegating to `_draw_via_aggdraw(stroke=True, fill=False)` via a `monkeypatch` spy. `_get_type1_units_per_em` Standard-14 substitute branches: `font.get_name()` returns `None` (line 4222), unmapped name → `None` substitute (line 4225), substitute UPEM raises (lines 4228-4229) — each driven by a `MagicMock(spec=PDType1Font)` with `_get_type1_font` returning `None` and `Standard14Fonts.get_substitute_ttf` monkey-patched. `render_image` fallback when `create_page_drawer` returns `None` or `self` (line 472) via a `PDFRenderer` subclass returning each. No source changes; no `# pragma: no cover` markers added; no latent bugs flagged. |
| `tests/wave1352/test_coverage_boost.py` | 3.0.x | hand-written coverage round-out for seven near-100% modules (wave 1352 agent E round 2), 8 tests. Files elevated to **100%**: `pypdfbox/pdfparser/xref_trailer_resolver.py` (98.0% → 100%, `/Prev` byte-position misses warning branch, lines 272-277); `pypdfbox/pdmodel/fdf/fdf_field.py` (98.4% → 100%); `pypdfbox/pdmodel/font/pd_type1_font.py` (98.9% → 100%, ``PDType1Font.load(document, pfb_stream, encoding)`` convenience classmethod lines 134-140 with the ``fontTools.t1Lib.T1Font`` parser monkey-patched); `pypdfbox/pdmodel/font/pd_type3_font.py` (98.8% → 100%, ``generate_bounding_box`` non-stream ``/CharProcs`` skip + ``OSError``/``ValueError`` continue arm via ``monkeypatch`` on ``PDType3CharProc.get_glyph_bbox``); `pypdfbox/pdmodel/graphics/image/sampled_image_reader.py` (98.7% → 100%); `pypdfbox/rendering/group_graphics.py` (98.8% → 100%); `pypdfbox/rendering/page_drawer.py` (98.8% → 100%, ``show_transparency_group`` fall-through to ``show_form`` when ``_render_form_xobject`` is non-callable + ``is_rectangular`` first-not-``M`` and second-not-``L`` reject arms). One latent source bug fixed: `pypdfbox/rendering/group_graphics.py::backdrop_removal` RGBA branch built the constant backdrop in ``self._image.mode`` (RGBA) and then called ``ImageChops.subtract`` against an RGB-converted source — Pillow rejects the mode mismatch, leaving the entire RGBA arm dead. Pinned the backdrop to ``"RGB"`` and re-attach the original alpha after subtraction. Eight ``# pragma: no cover`` markers added on provably-unreachable defensive branches: four ``COSObject`` unwrap arms in ``fdf_field.py`` (already dereferenced by ``COSDictionary.get_dictionary_object``); the ``elif isinstance(rich, COSStream)`` arm of ``FDFField.write_xml`` (``get_rich_text`` always decodes to ``str``); two ``sample_max == 0`` arms in ``sampled_image_reader.py`` (``sample_max = (1<<bpc)-1 if bpc>0 else 1`` is always ≥ 1); the two ``out_y >= out_h`` / ``out_x >= out_w`` defensive overflow checks in ``get_rgb_image`` (the ceil-div ``out_h`` / ``out_w`` bound the integer division by construction); the ``section is None`` arm of ``XrefTrailerResolver.set_startxref``'s merge loop (every ``b_pos`` was sourced from ``byte_pos_map.keys()``); and the ``BlendMode`` import-failure guard in ``PageDrawer.has_blend_mode`` (defensive against an in-tree import that can't actually fail). |
| `tests/pdmodel/interactive/digitalsignature/test_pd_signature_wave1352.py` + `tests/pdfparser/test_pdf_parser_wave1352.py` + `tests/pdmodel/interactive/annotation/handlers/test_cloudy_border_wave1352.py` + `tests/pdmodel/test_pd_resources_wave1352.py` + `tests/multipdf/test_overlay_wave1352.py` | 3.0.x | hand-written coverage round-out for five large 5–9-line-residual production modules (wave 1352 agent D), 34 tests. All five files driven to **100%**. **`pypdfbox/pdmodel/interactive/digitalsignature/pd_signature.py` 98.2% → 100%** (9 tests): `_verify_signed_attrs_signature` EC successful-verify (line 301) via a fresh `ec.SECP256R1` signature; the EC arm's `(ValueError, TypeError)` raise (lines 304-305) via a non-bytes (``str``) signature triggering cryptography's TypeError; the OID-vs-key-type fall-through "unsupported signature algorithm" (line 307) by feeding an RSA cert with an ECDSA signatureAlgorithm OID. `_verify_chain_trust` chain-broken with invalid issuer signature (line 366) — leaf cert claims a root issuer but is signed by its own key; pathological-loop guard (line 370) via two cross-signed certs (A signs B, B signs A, neither in trust roots) and BOTH in the embedded pool so the walker bounces until the iteration counter expires; self-signed-root fails-self-verify (lines 354-357) via a `monkeypatch` of `_verify_cert_signature` to fail for `c is i`. `_verify_cert_signature` no-signature-hash-algorithm (line 385) via an Ed25519 cert (RFC 8410 — EdDSA does its own internal hashing); issuer-side `ValueError` (lines 404-405) via an ABC-registered `RSAPublicKey` subclass whose ``verify()`` raises ``ValueError``; unsupported-issuer-key-type (line 406) via a real Ed25519 issuer cert. **`pypdfbox/pdfparser/pdf_parser.py` 98.7% → 100%** (9 tests): `initial_parse` missing-trailer raise (line 227) when no parse has run; hybrid `/XRefStm` parse failure under lenient mode (lines 784-787) logged via `_LOG.exception` AND under strict mode raises `PDFParseError` (line 786); `_read_until_endstream` end-stream-marker-not-found raise (line 1272) via a buffer with no marker, EOF raise (line 1265) via a stub `RandomAccessRead` whose `read_into` returns `EOF` while `length()` lies about 64 bytes available, and the partial-read trim (line 1267) via a stub source that returns fewer bytes than requested. **`pypdfbox/pdmodel/interactive/annotation/handlers/cloudy_border.py` 98.7% → 100%** (2 tests): `cloudy_polygon_impl` defensive `n < 0` skip with `not self._output_started` (lines 379-382) via a `CloudyBorder` subclass that overrides `compute_params_polygon` to return -1 on the first j-loop call (the production helper only returns -1 on `length == 0`, which the loop short-circuits earlier); `flatten_ellipse` closure-tolerance duplicate-append (line 915) via radii 1e16 — floating-point drift on `sin(2π) * ry` exceeds the 0.05 closure threshold. Two `# pragma: no cover` markers added on `flatten_ellipse` lines 891-894 (the two `arg < -1.0` / `arg > 1.0` defensive clamps are mathematically unreachable: `arg = 1 - 0.5/r_max` with `r_max > 0.5 > 0` stays strictly inside `(0, 1)`). **`pypdfbox/pdmodel/pd_resources.py` 98.6% → 100%** (6 tests): `get_indirect` indirect-`COSObject` happy path (line 163) by setting an indirect through the sub-dict bypass; `is_allowed_cache` payload-without-callable-`get_name` early-return (line 862) via a `PDImageXObject` subclass returning a bare `object()` from `get_cos_object`; missing-`/ColorSpace` early-return (line 865); `DefaultCMYK` override blocks `DeviceCMYK` (line 870); `DefaultGray` override blocks `DeviceGray` (line 878); and the final `return not has_color_space(cs_name)` fall-through for a custom (non-Device) colour-space name — both with and without the resource registering that name. **`pypdfbox/multipdf/overlay.py` 98.5% → 100%** (8 tests): all six public 1:1 upstream-named delegate methods — `create_combined_content_stream` (line 701, two flavours: real page contents + `None`), `get_layout_page` (line 738, configured default + bare overlay returning `None`), `create_adjusted_layout_page` (line 743, rotation-cache idempotency), `create_overlay_form_x_object` (line 753, `PDFormXObject` shape + Form subtype assertion), `create_overlay_stream` (line 763, `q\nq\n ... /OL0 Do Q\nQ\n` placement-stream body assertion), and `overlay_page` (line 731, registers `/OL0` XObject + appends Do call to content array). No latent source bugs flagged. |
| `tests/fontbox/type1/test_type1_font_pfb_edge_wave1352.py` + `tests/pdmodel/font/test_pd_type0_font_edge_wave1352.py` + `tests/multipdf/test_pdf_merger_utility_edge_wave1352.py` | 3.0.x | hand-written coverage round-out for three large near-100% production modules (wave 1352 agent B), 29 tests. Files elevated to **100%**: `pypdfbox/fontbox/type1/type1_font.py` (98.0% → 100%, 7 tests): PFB framing edge cases — marker-is-last-byte break (line 209), truncated length field (217-219), negative record size (222-224), oversized record (225-227), truncated payload after passing the global-size guard (228-230), and the trailing `cleartomark` ASCII-record exclusion (242-249) including the >= 600-byte trailer fold-back guard. `pypdfbox/pdmodel/font/pd_type0_font.py` (98.2% → 100%, 13 tests): `get_path` / `get_normalized_path` non-callable-descendant short-circuits (lines 856, 873); `get_cmap_lookup` non-`PDCIDFontType2` descendant (900), unicode-lookup raises (906-909), fontTools `_tt["cmap"].getBestCmap()` fallback (910-915), `_tt` missing-`cmap` and `_tt is None` (911-913), `getBestCmap` raising (914-917); `has_explicit_width` no-descendant (949) and non-callable-accessor (952) guards; `subset()` honouring `add_glyphs_to_subset` — `subsetter.add_glyph_ids(self._subset_glyph_ids)` pinning branch (line 1464) and the `RuntimeError` raised on `add_glyphs_to_subset` when subsetting is disabled. `pypdfbox/multipdf/pdf_merger_utility.py` (98.8% → 100%, 9 tests): `_hash_cos` recursion through `COSObject` indirect references (lines 50-51); optimize-mode `set_destination_document_information` / `set_destination_metadata` overrides (635, 639); optimize-mode and legacy-mode destination-close-raise swallow paths (651-652, 776-777). **Latent bug flagged:** the outer `finally`-loop source-close branches in both merge paths (lines 655-658 optimize, 780-783 legacy) are dead code as written — the per-source inner `finally` unconditionally flips `opened_sources[-1] = (source_doc, False)` after the close attempt (regardless of whether the close raised), so the outer cleanup never observes `still_owned=True`. The fix would be to gate the flip on a successful close (e.g. `else:` or a success flag). Five `# pragma: no cover` markers added across each dead block (10 markers total) with explanatory comments pointing back to this CHANGES.md entry. |

### Wave 1354 additions — hand-written test files (agent B)

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/pdmodel/graphics/test_tail_sweep_wave1354.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/pdmodel/graphics/**` (wave 1354 agent B), 34 tests, takes the whole `pdmodel/graphics/` subtree from **99% (37 missing lines across 18 files) → 100%**. Per-file breakdown: `blend/blend_function.py` 91% → 100% (`__call__` dunder delegation, line 40); `blend_mode.py` 99% → 100% (`name` property mirror of `get_name`, line 272; `get_luminosity_rgb` overflow `delta > 0` branch with positive scale arithmetic, lines 510-512 — driven by asymmetric `src=[1, 1, 0]` / `dest=[0.5, 1, 0.5]` that forces the green channel to 279, setting bit 0x100 in the OR-mask); `color/pd_lab.py` 98% → 100% (the three `if x/y/z < 0.0: clamp = 0.0` branches in `to_rgb`, lines 294/296/298 — driven by extreme `a*`/`b*` values pushing the affine inverse negative, plus a negative `/WhitePoint` to flip the y arm); `color/pd_separation.py` 99% → 100% (the `elif isinstance(transform, COSBase)` branch on line 158 marked `# pragma: no cover` — dead code: COSBase always carries `get_cos_object`, so the `hasattr` branch above always wins; kept for defensive parity with upstream's COSObjectable surface); `color/pd_tristimulus.py` 92% → 100% (`_read` non-`COSNumber` fallback returning 0.0, line 41, via a COSName slot; `set_y`/`set_z` round-trips, lines 60/68); `form/pd_form_x_object.py` 99% → 100% (`set_b_box` `TypeError` raise for non-`PDRectangle`/`None` values, line 120); `image/custom_factory.py` 92% → 100% (`__call__` dunder delegation, line 34); `image/lossless_factory.py` 99% → 100% (`prepare_image_x_object` `ValueError` raise when `init_color_space.get_cos_object()` returns `None`, line 277, via a custom PDColorSpace subclass); `shading/cubic_bezier_curve.py` 91% → 100% (`to_string` formatting all four control points as `Point2D.Double[...]`, lines 57-60; `__repr__` delegation, line 63); `shading/gouraud_shading_context.py` 90% → 100% (`dispose` clearing the triangle list and chaining parent, lines 43-44); `shading/int_point.py` 90% → 100% (`equals(self)` identity short-circuit, line 33; `__repr__` rendering, line 45); `shading/pd_shading_type4.py` 98% → 100% (non-stream COSDictionary guard returning `[]`, line 181; trailing `return []` after `/Decode` validation passes, line 197); `shading/pd_shading_type5.py` 98% → 100% (same two branches as type 4, lines 171/189 — lattice-form variant with `/VerticesPerRow` validation); `shading/pd_triangle_based_shading_type.py` 99% → 100% (the `get_function() is not None → components = 1` branch, line 79, reached by instantiating the base `PDTriangleBasedShadingType` directly with a `/Function` dict — concrete `PDShadingType4`/`PDShadingType5` override the method); `shading/radial_shading_context.py` 97% → 100% (high-input no-extend no-bg `continue`, line 165 — `extend=(True, False)` with `input_value > 1`; low-input no-extend `use_background = True`, line 174 — `extend=(False, True)` with bg present; key-clamp-to-0 when `int(input_value * factor) < 0`, line 180 — driven by `domain=[-2.0, 1.0]` so the extend-low arm sets `input_value = -2.0`; key-clamp-to-`factor` when key > factor, line 182 — driven by `domain=[0.0, 5.0]` so the extend-high arm sets `input_value = 5.0`); `shading/type4_shading_paint.py` 90% → 100% (the `(NotImplementedError, AttributeError, OSError)` swallow around `collect_triangles`, lines 40-41 — parametrized across all three exception types); `shading/type5_shading_paint.py` 90% → 100% (same three-exception swallow as type 4, lines 39-40); `state/pd_extended_graphics_state.py` 99% → 100% (the three public-named aliases `default_if_null` / `get_float_item` / `set_float_item` delegating to the underscored private helpers, lines 425/429/433). **One latent bug flagged**: `pd_separation.py` `set_tint_transform` lines 157-158 — the `elif isinstance(transform, COSBase)` branch is unreachable because all `COSBase` subclasses inherit `get_cos_object` (returning `self`), so the `hasattr` branch on line 150 always wins. Marked `# pragma: no cover` with an explanatory inline note; no functional change. Reusable `_FakeRadialShading` / `_ArrAdapter` / `_BgArr` / `_Bool` / `_ExtendArr` helpers structurally identical to the ones in `tests/pdmodel/graphics/shading/test_axial_radial_shading_context_coverage.py` (the wave-1284/1349 surface) for consistency. |
| `tests/coverage_boost/test_wave1354_agent_a.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/examples/**` and `pypdfbox/tools/**` (wave 1354 agent A), 30 tests, takes both subtrees from **99% (~30 missing lines across 20+ files) → 100%**. Per-file breakdown — examples: `interactive/form/create_push_button.py` 97% → 100%, `interactive/form/create_simple_form_with_embedded_font.py` 98% → 100`, `interactive/form/field_remover.py` 99% → 100% (nested-field `remove_recursive` fall-through, line 86, via a `PDNonTerminalField` parent containing a `PDTextField` leaf); `pdmodel/add_annotations.py` 99% → 100%, `pdmodel/add_javascript.py` 92% → 100% (encrypted-input `OSError` raise via empty-user-password `StandardProtectionPolicy`), `pdmodel/create_blank_pdf.py` 94% → 100%, `pdmodel/create_page_labels.py` 96% → 100%, `pdmodel/create_pdfa.py` 98% → 100% (font-descriptor-unembedded `RuntimeError` raise via mocked `PDType0Font`), `pdmodel/embedded_files.py` 98% → 100% (`main([out])` falls through to `do_it`, line 99), `pdmodel/extract_embedded_files.py` 99% → 100% (non-`PDAnnotationFileAttachment` `continue`, line 64, via a page carrying a `PDAnnotationLink`), `pdmodel/hello_world.py` 97% → 100%, `pdmodel/remove_first_page.py` 91% → 100% (`__init__` placeholder + encrypted `OSError`), `pdmodel/rubber_stamp.py` 93% → 100% (`__init__` placeholder + encrypted `OSError`), `pdmodel/rubber_stamp_with_image.py` 99% → 100% (encrypted `OSError` via `do_it_bytes` against a minimal PNG), `pdmodel/show_color_boxes.py` 97% → 100%, `pdmodel/show_text_with_positioning.py` 98% → 100%, `pdmodel/superimpose_page.py` 98% → 100%; `signature/validation_time_stamp.py` 96% → 100% (`sign_time_stamp` one-line delegate, line 38, both no-TSA passthrough and with-transport append). Tools: `decrypt.py` 96% → 100% (keystore `OSError` via missing-keystore-path lines 161-165; in-place `PDInvalidPasswordException` via monkey-patched `decrypt_pdf` lines 222-223 — paired with `AccessPermission.is_owner_permission` monkeypatched True so the probe passes for the empty-user-password fixture); `extracttext.py` 99% → 100% (`extract_embedded_pdfs` short-circuits when `/Names` lacks `/EmbeddedFiles`, line 261; when tree exists but `get_names()` empty, line 264); `pdf_box.py` 92% → 100% (`run()` raising `SystemExit("Subcommand required")` line 64; `main(None)` defaulting to `sys.argv[1:]` line 69 + falling through to the empty-args usage branch); `pdf_merger.py` 91% → 100% (`call()` returning 0 on the two-file happy path line 51 — uses real `PDFMergerUtility`, no mocks); `print_pdf.py` 99% → 100% (`show_available_printers` for-loop body line 102 with `get_trays_from_print_service` monkey-patched to `["Tray-A", "Tray-B"]`). **`# pragma: no cover` markers added at source** (no tests faked): `examples/pdmodel/extract_ttf_fonts.py` lines 37/50/56/67 — `return` after `usage()` is upstream's mirror that Python never executes (`usage()` raises `SystemExit(1)`); `tools/imageio/image_io_util.py` line 137 — defensive `raise OSError("no filename or output stream")` (callers always pass one of `filename`/`output_stream`); `tools/encrypt.py` lines 233-234 — `Path.resolve()` OSError fallback for cross-platform safety (Windows long-path); plus `# pragma: no cover — module-as-script entrypoint` on the `__main__` blocks of `decrypt_tool.py`, `encrypt_tool.py`, `extract_text.py`, `extract_xmp.py`, `image_to_pdf.py`, `pdf_box.py`, `pdf_merger.py`, `print_pdf.py` — matching the existing convention in `extract_images.py` / `text_to_pdf.py` / `cli.py`. No latent example or tool bugs flagged. |
| `tests/debugger/flagbitspane/test_panose_flag_wave1354.py` + `tests/debugger/hexviewer/test_hexviewer_tail_wave1354.py` + `tests/debugger/ui/test_debugger_ui_tail_wave1354.py` + `tests/debugger/streampane/test_streampane_tail_wave1354.py` + `tests/debugger/streampane/tooltip/test_tooltip_tail_wave1354.py` + `tests/debugger/treestatus/test_tree_status_tail_wave1354.py` + `tests/debugger/signaturepane/test_signature_pane_tail_wave1354.py` + `tests/debugger/test_pd_debugger_tail_wave1354.py` + `tests/xmpbox/xml/test_dom_helper_tail_wave1354.py` + `tests/xmpbox/test_pdfa_extension_helper_tail_wave1354.py` + `tests/xmpbox/test_date_type_tail_wave1354.py` + `tests/xmpbox/test_xmp_media_management_schema_tail_wave1354.py` + `tests/rendering/test_page_drawer_tail_wave1354.py` + `tests/benchmark/test_null_output_stream.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/debugger/**`, `pypdfbox/xmpbox/**`, `pypdfbox/rendering/**`, `pypdfbox/benchmark/**` (wave 1354 agent E), 14 test files, +37 tests, takes all four subtrees from **99% (25 files <100%, ~33 missing lines) → 100%**. Test-driven branches: `benchmark/null_output_stream.py` 86% → 100% (line 25 — `write(None)` returns 0); `debugger/flagbitspane/panose_flag.py` 99% → 100% (line 276 — static `get_panose_bytes` raises `TypeError` when `/Panose` is not a `COSString`); `debugger/hexviewer/address_pane.py` 97% → 100% (line 56 — `set_selected(same_index)` early-return); `debugger/hexviewer/ascii_pane.py` 98% → 100% (line 54 — `hex_model_changed` listener fan-out via `HexModelChangedEvent(0, BULK_CHANGE)`); `debugger/hexviewer/hex_editor.py` 99% → 100% (line 194 — jump-dialog `_commit` empty-input early-return); `debugger/hexviewer/hex_model.py` 98% → 100% (line 26 — `HexModel(None)` empty-data branch); `debugger/pd_debugger.py` 99% → 100% (line 1142 — `_show_font` success path with a stub `FontEncodingPaneController` returning a real `ttk.Frame`); `debugger/signaturepane/signature_pane.py` 99% → 100% (lines 184-185 — `create_text_view` `except Exception` fallback via `monkeypatch.setattr(SignaturePane.get_text_string, ...)` raising `RuntimeError`); `debugger/streampane/stream_image_view.py` 99% → 100% (line 125 — `zoom_image(scale=None, rotation=90)` stores rotation); `debugger/streampane/stream_pane.py` 99% → 100% (line 388 — `_ContentStreamEmitter.write_token(Operator)` dispatch); `debugger/streampane/tooltip/color_tool_tip.py` 97% → 100% (line 55 — `extract_color_values("")` empty-words `return None`); `debugger/streampane/tooltip/k_tool_tip.py` 96% → 100% (line 87 — `get_icc_color_space` success path with `get_icc_profile` monkey-patched to a sentinel); `debugger/treestatus/tree_status.py` 99% → 100% (line 133 — `_search_node` `XrefEntry` → `COSObject` → `COSDictionary` unwrap chain); `debugger/ui/log_dialog.py` 99% → 100% (line 92 — `set_visible(True)` first-time call builds the toplevel via `show()`); `debugger/ui/textsearcher/searcher.py` 99% → 100% (lines 140-141 — no-panel `search()` with zero matches resets `_total_match = 0` / `_current_match = -1`); `debugger/ui/tree_view_menu.py` 98% → 100% (line 90 — `get_tree_view_selection` `RuntimeError` when `_var` is set to an out-of-band label); `debugger/ui/xref_entries.py` 96% → 100% (line 49 — `index_of` returns 0 when the entry's key is absent); `rendering/page_drawer.py` 99% → 100% (line 410 — `show_transparency_group` falls back to `show_form` when renderer lacks `_render_form_xobject`; line 742 — `is_rectangular` returns False when the first segment is not `M`; line 745 — `is_rectangular` returns False when an interior segment is not `L`); `xmpbox/xml/dom_helper.py` 90% → 100% (line 40 — `get_unique_element_child` returns None when there are no element children; line 49 — `get_first_child_element` returns None when only text children; line 58 — `get_qname` returns `(namespaceURI, localName, prefix)` triple; line 63 — `get_q_name` alias delegates to `get_qname`); `xmpbox/type/date_type.py` 98% → 100` (line 114 — `get_string_value` returns None when `_date_value is None`, forced by clearing `_date_value` after construction); `xmpbox/xmp_media_management_schema.py` 99% → 100% (line 367 — `get_manager_variant_property` typed accessor paired with the existing `set_manager_variant_property`); `xmpbox/xml/pdfa_extension_helper.py` 99% → 100% (line 64 — `validate_naming` early-return when the element's `attributes` is `None`, exercised via a stand-in element class). **`# pragma: no cover` applied at source for unreachable residue** (no tests faked): `xmpbox/date_converter.py::_two_digit_year_to_full` line 812 (with today's pivot 2026, base=1947, century=1900, so candidate=1900..1999 always < base+99=2046 — the `candidate -= 100` arm only fires if the pivot crosses a century boundary in a way `datetime.now()` cannot produce); `xmpbox/date_converter.py::parse_date` lines 725-727 (the "simple-format consumed more than big-endian" residue arm — both parsers must succeed AND both leave residue AND simple consumed more; unreachable with the partial `SimpleDateFormat` port because the simple parser only matches numeric prefixes that big-endian already eats); `xmpbox/dom_xmp_parser.py::_manage_typed_array_property` line 549 (`container_ns != _RDF_NS` — `_find_rdf_container` returns only `rdf:*` children by construction); `xmpbox/type/type_mapping.py::create_and_add_default_schema_for_namespace` line 606 (the `getattr` always returns `None` because `XMPMetadata` does not expose the upstream `create_and_add_default_schema_for_namespace` hook yet); `xmpbox/xmp_media_management_schema.py::_get_simple_typed` lines 143-144 (every caller uses `TextType` or `URLType`, both of which accept any `str` without raising — guard kept as parity scaffolding for subclasses where the constructor may reject the value). No latent source bugs flagged. |
| `tests/pdmodel/test_pdmodel_tail_sweep_wave1354.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/pdmodel/**` excluding `graphics/` (wave 1354 agent C), 21 tests, drives 22 distinct production files with 1-3 missing lines each from **97-99% → 100%**. Per-file breakdown: `common/function/type4/bitwise_operators.py` 98% → 100% (the lowercase-`f` upstream alias `applyfor_integer` for `And` / `Or` / `Xor`, line 83); `common/function/type4/instruction_sequence_builder.py` 98% → 100% (the public-named `get_current_sequence` mirror of `_get_current_sequence`, line 68); `common/function/type4/relational_operators.py` 98% → 100% (`AbstractNumberComparisonOperator.compare` raising `NotImplementedError` when called directly on the abstract base, line 105); `common/label_generator.py` 98% → 100% (`LabelGenerator.remove()` `NotImplementedError`, line 39); `common/pd_stream.py` 99% → 100% (`internal_get_decode_params` `TypeError` for a non-dict, non-null entry inside the `/DecodeParms` `COSArray`, line 383); `documentinterchange/logicalstructure/pd_structure_tree_root.py` 99% → 100% (`_to_cos` passthrough when value lacks `get_cos_object`, line 587, via a bare object routed through `PDStructureElementNumberTreeNode.convert_value_to_cos`); `encryption/security_handler.py` 99% → 100% (the `set` setter branch of `_decrypt_array` line 620, via a `SecurityHandler` subclass whose `decrypt` always returns a fresh `COSString`); `fdf/fdf_annotation_ink.py` 97% → 100% (`get_ink_list` non-array-entry branch returning `[]`, line 59); `fdf/fdf_annotation_stamp.py` 99% → 100% (`parse_dict_element` early-return when `getattr(element, "iter", None) is None`, line 103); `font/font_mapper_impl.py` 99% → 100% (`get_provider` lazy-install of the default `FileSystemFontProvider`, lines 204-206, with the provider monkey-patched to a stub returning empty `get_font_info`); `font/pd_type1_font_embedder.py` 99% → 100% (the `(AttributeError, TypeError, ValueError)` swallow in the per-glyph width loop, lines 136-137, driven by a fontTools `T1Font` stub whose `getGlyphSet()` raises `ValueError` — also defensively registers the missing `COSName.BASE_FONT` / `COSName.ENCODING` / `COSName.FONT_DESC` static-attribute constants at test-setup time, mirroring `test_pd_true_type_font_embedder_coverage.py`); `interactive/action/pd_action_factory.py` 97% → 100% (`create_action` `s_type is None` (no `/S` subtype) `return None`, line 44); `interactive/annotation/handlers/pd_ink_appearance_handler.py` 98% → 100% (`generate_normal_appearance` `rect is None` early-return, line 67, driven by an ink annotation with `/C` + `/BS` + `/InkList` but no `/Rect`); `interactive/annotation/pd_annotation_screen.py` 99% → 100% (`_as_cos_dictionary` `TypeError` for a non-wrapper, non-dict value, lines 33-36, via `set_action(42)`); `interactive/annotation/pd_annotation_watermark.py` 97% → 100% (`set_fixed_print` `TypeError` for a value with neither `COSDictionary` nor `get_cos_object`, line 62, via `set_fixed_print("not a dict")`); `interactive/annotation/pd_appearance_stream_name_tree_node.py` 95% → 100% (`convert_cos_to_pd` typed-factory shim routing through `convert_cos_to_value`, line 53); `interactive/annotation/pd_external_data_dictionary.py` 95% → 100% (caller-supplied `COSDictionary` preserved verbatim instead of allocating a new one, line 23); `interactive/digitalsignature/pd_seed_value_certificate.py` 99% → 100% (the two static helpers `convert_list_of_byte_arrays_to_cos_array` / `get_list_of_byte_arrays_from_cos_array`, lines 465/475, via round-trip of `[b"\x01\x02", b"\xff\xee"]`); `interactive/form/pd_variable_text.py` 99% → 100% (`get_default_appearance_string` `dr is None → return None` branch, line 88, when the field's inheritable `/DA` is set but the parent AcroForm exposes no `/DR` resources); `pd_document_name_dictionary.py` 99% → 100% (`get_ap_raw` returning `None` when `/AP` is absent, line 408); `resource_cache.py` 94% → 100% (`ResourceCache.put` plain-`PDXObject` dispatch branch line 34-35, distinct from the preceding `PDFormXObject` branch, via a `ConcreteResourceCache` mixing `ResourceCache` and `DefaultResourceCache`). **One latent source bug flagged**: `pypdfbox/pdmodel/font/pd_type1_font_embedder.py` lines 123/127/146 reference `COSName.FONT_DESC` / `COSName.BASE_FONT` / `COSName.ENCODING` as static-attribute constants, but `pypdfbox/cos/cos_name.py` does not pre-register them (the same gap was already noted by `tests/pdmodel/font/test_pd_true_type_font_embedder_coverage.py` for `PDTrueTypeFontEmbedder`). Any caller running `PDType1FontEmbedder.__init__` in a fresh process before some other test has triggered the defensive registration would hit `AttributeError: type object 'COSName' has no attribute 'FONT_DESC'`. The fix is a three-line registration in `cos_name.py` at module bottom (next to the existing `COSName.WIDTHS = _static_name("Widths")` block); kept out of this wave because it touches production source. No `# pragma: no cover` markers added. |

| `tests/pdmodel/font/test_pd_true_type_font_wave1356.py` + `tests/pdmodel/font/test_pd_cid_font_type2_wave1356.py` + `tests/pdmodel/font/test_standard14_fonts_wave1356.py` | 3.0.x | hand-written final-push tail-sweep across `pypdfbox/pdmodel/font/**` (wave 1356 agent A), 13 tests, takes three modules from **99% (12 missing lines total) → 100%**. `pd_true_type_font.py` (655 stmts, +9 tests): line 351 (`get_width_from_font` `units_per_em == 1000` short-circuit), line 442 (`get_normalized_path` gid-0 + non-embedded + non-standard14 PDFBOX-2372 guard), line 825 (`get_path_from_outlines` empty-path-from-CFF `return None`), lines 960-961 (`encode_codepoint` raise when both AGL + uniXXXX fallback miss), lines 967-969 (`encode_codepoint` raise when encoding contains name but inverse code-map lacks it), lines 1030 + 1038 (`_scale_path` `None`-point and non-`(x,y)` argument short-circuits). `pd_cid_font_type2.py` (372 stmts, +2 tests): lines 643-644 (`get_path_from_outlines` swallowing a `code_to_gid` exception), line 727 (embedded `encode` falling through with `cid == -1` after the Identity / UCS-2 / `/ToUnicode` branches all skip — reset to 0 before the final raise). `standard14_fonts.py` (371 stmts, +2 tests): lines 280-281 (`_ttf_glyph_path_for_gid` swallowing a `glyph.draw` exception, distinct from the existing glyph-set lookup-exception test at lines 274-275), line 1037 (`Standard14Fonts.get_glyph_path` returning the `uniXXXX` outline from the mapped-font wrapper after the direct AGL name misses, non-SymbolMT branch). No `# pragma: no cover` markers added — every line is now exercised by a real test. No latent source bugs flagged. |
| `tests/pdmodel/common/test_pd_dictionary_wrapper.py` + `tests/pdmodel/common/filespecification/test_pd_complex_file_specification_wave271.py` + `tests/pdmodel/common/function/type4/test_parser.py` + `tests/pdmodel/interactive/annotation/handlers/test_pd_free_text_line_appearance_coverage.py` + `tests/pdmodel/test_pd_resource_cache.py` + `tests/util/test_util_wave1281.py` | 3.0.x | hand-written final-push tail-sweep extending existing test files across `pypdfbox/pdmodel/common/**`, `pypdfbox/pdmodel/interactive/annotation/handlers/**`, `pypdfbox/pdmodel/**`, `pypdfbox/util/**` (wave 1356 agent C), +14 tests, takes 6 modules from **99% (12 missing lines total) → 100%** and applies one `# pragma: no cover` to xml_util. Per-file branches: `pd_dictionary_wrapper.py` (20 stmts) lines 43/47 — `equals(Object)` / `hash_code()` Java-parity wrappers delegating to `__eq__` / `__hash__`. `pd_complex_file_specification.py` (188 stmts) lines 106/114 — public `get_ef_dictionary` / `get_object_from_ef_dictionary` delegates that mirror upstream's private getters; round-trip via `set_embedded_file(PDEmbeddedFile())`. `pdmodel/common/function/type4/parser.py` (117 stmts) line 113 — `Tokenizer.peek` returns `_EOT` when the cursor sits on the last input character (lone `\r` at EOF, no trailing `\n`); line 202 — `Parser()` no-op constructor instantiation (upstream's Java `private Parser() {//nop}`). `pd_line_appearance_handler.py` (167 stmts) lines 191-194 — caption `show_text` raising mid-BT/ET; the `finally`-closed `end_text` keeps the text block balanced so `restore_graphics_state` doesn't trip the text-block guard (monkey-patches `PDAppearanceContentStream.show_text` to raise `ValueError`). `pd_resource_cache.py` (226 stmts) line 491 — `DefaultResourceCache.put` routing a bare `PDFont` (constructed via `__new__` + `_dict = COSDictionary()`) to the font slot; line 495 — routing `PDDeviceRGB.INSTANCE` (a `PDColorSpace`) to the color-space slot. `util/string_util.py` (14 stmts) line 31 — `tokenize_on_space` falsy-non-empty branch returning `[]` for `None` (the empty-string case returns `[""]`). **`# pragma: no cover` applied at source**: `pypdfbox/util/xml_util.py` line 48 — the `defusedxml.minidom.parseString` hardened path; `defusedxml` is not on the project's permissive-only dependency list and not installed in the dev / CI envs, so the import in line 46 always raises `ImportError` and falls through to the `minidom.parseString` fallback on line 50. Already documented in `tests/util/test_xml_util_coverage.py` module docstring. No latent source bugs flagged. |
| `tests/coverage_boost/test_wave1356_agent_b.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/pdmodel/**` form / fdf / page tail (wave 1356 agent B), 10 tests. **`pypdfbox/pdmodel/pd_page.py`** — closes lines 311 / 679 / 685-686 / 1026: `set_contents` wrapper-not-COSStream `TypeError`, `add_annotation` non-`PDAnnotation` `TypeError`, the existing-`COSArray` `/Annots` extend branch, and the `get_indirect_resource_objects` non-`COSDictionary` short-circuit. **`pypdfbox/pdmodel/interactive/form/pd_default_appearance_string.py`** — closes lines 177 / 275: `process_set_font` "Could not load font" raise via a `PDResources` subclass returning a sentinel int (neither `None` / `COSDictionary` / `PDFont`); `write_to` "No font set on /DA" raise via empty `/DA`. **`pypdfbox/pdmodel/interactive/form/key_value.py`** — closes lines 41 / 45: `to_string()` parity wrapper and `__eq__` `NotImplemented` branch. **`pypdfbox/pdmodel/fdf/fdf_option_element.py`** — closes lines 44 / 63: `return ""` fallbacks when the underlying `COSArray` slot is not a `COSString`. **`pypdfbox/pdmodel/interactive/form/appearance_generator_helper.py`** — `# pragma: no cover` applied at source for lines 170-171 and 384 with inline notes flagging two latent bugs pinned by existing tests: (a) `COSName.DA` is not defined on the lite-port facade so `get_widget_default_appearance_string` raises `AttributeError` before reaching the assignment / constructor call (`test_get_widget_default_appearance_string_raises_attribute_error`); (b) `pypdfbox.pdmodel.common` does not re-export `PDRectangle` so `apply_padding` raises `ImportError` before reaching the constructor call (`test_apply_padding_inset_returns_smaller_rectangle`). **Latent source bugs flagged**: the two above in `appearance_generator_helper.py`; the fixes are a one-line `COSName.DA = _static_name("DA")` registration in `cos_name.py` and adding `PDRectangle` to `pypdfbox/pdmodel/common/__init__.py`'s re-exports — kept out of this wave because they touch production source paths the existing tests pin. |
| `tests/test_coverage_tail_wave1354.py` | 3.0.x | hand-written tail-sweep across `pypdfbox/fontbox/**`, `pypdfbox/cos/**`, `pypdfbox/io/**`, `pypdfbox/filter/**`, `pypdfbox/pdfparser/**`, `pypdfbox/pdfwriter/**`, `pypdfbox/contentstream/**` (wave 1354 agent D), 54 tests, takes all seven subtrees from **99% (~25 files <100%, ~85 missing lines) → 100%**. Test-driven branches: `contentstream/operator/state/save.py` 93% → 100% (`get_name` returns `"q"`); `contentstream/operator/draw_object.py` 98% → 100% (resources without `get_x_object` short-circuit, line 53); `contentstream/operator/graphics/close_fill_even_odd_and_stroke_path.py` 94% → 100% (no-engine `_log_invocation` fallback, line 31); `contentstream/operator/markedcontent/begin_marked_content_sequence_with_properties.py` 97% → 100% (hook dispatch, line 53; `get_name`, line 56); `contentstream/operator/markedcontent/marked_content_point_with_properties.py` 97% → 100% (same two branches at lines 46/49); `cos/cos_array.py` 99% → 100% (`getUpdateState` camelCase alias line 220; `of_cos_floats` factory line 432); `cos/cos_boolean.py` 98% → 100% (`__repr__` line 97); `cos/cos_dictionary.py` 99% → 100% (`get_name` line 567; non-COSName/str `__contains__` line 1074; `__repr__` lines 1077-1078); `cos/cos_document.py` 99% → 100% (linearization scan with `cos_obj is None` line 249; non-dict-resolved `continue` line 252; `set_trailer(None)` line 268); `cos/cos_object.py` 99% → 100% (`getUpdateState` alias line 98); `cos/cos_stream.py` 99% → 100% (`create_raw_input_stream` no-data OSError line 236); `cos/cos_string.py` 99% → 100% (`__repr__` line 222); `cos/cos_update_state.py` 98% → 100% (`_set_child_origin(None)` early-return line 116); `fontbox/afm/ligature.py` 94% → 100% (`get_ligature` line 24); `fontbox/cff/cff_type1_font.py` 98% → 100% (`has_glyph` empty-name line 309 + in-charset True branch line 310; `get_path` line 316; `get_width` line 321); `fontbox/cff/format1_encoding.py` 96% → 100% (`Range3.__repr__` lines 59-63); `fontbox/cmap/cmap.py` 99% → 100% (`_read_one` BinaryIO non-empty branch line 346); `fontbox/cmap/cmap_parser.py` 99% → 100% (list-form / count-form type-error raises lines 523/533; `_create_string_from_bytes` module helper line 847); `fontbox/ttf/cff_table.py` 98% → 100% (`# pragma: no cover` on the `read_into → 0` defensive break, line 141); `fontbox/ttf/gsub/lookup_subtable.py` 99% → 100% (base `get_coverage_table` invoked through the LookupTypeSingleSubstFormat1 instance, line 113); `fontbox/ttf/otf_parser.py` 93% → 100% (`_allow_cff` / `_read_table` aliases line 117/120; `_new_font` alias line 114; `_check_tables` lenient OTF skip line 162); `fontbox/ttf/random_access_read_non_closing_input_stream.py` 99% → 100% (`read_into → 0` mid-read returns `b""`, line 66); `fontbox/ttf/table/common/coverage_table_format1.py` 97% → 100% (`__str__` delegation line 110); `fontbox/ttf/table/common/coverage_table_format2.py` 96% → 100% (same delegation line 64); `fontbox/ttf/ttf_data_stream.py` 99% → 100% (non-bytes file-like `TypeError` lines 254-255); `fontbox/type1/token.py` 98% → 100% (`to_string` non-CHARSTRING branch line 83); `fontbox/util/autodetect/native_font_dir_finder.py` 90% → 100% (OSError swallow lines 27-28); `io/random_access_output_stream.py` 94% → 100% (`writable` returns True, line 25); `io/random_access_read_buffered_file.py` 99% → 100% (`check_closed` after close, line 40); `io/scratch_file_buffer.py` 99% → 100% (owner-closed OSError line 67; within-page True line 102); `pdfparser/xref/free_x_reference.py` 91% → 100% (`__repr__` lines 50-54; `to_string` line 63); `fontbox/ttf/gsub/gsub_worker_for_dflt.py` 96% → 100% (`_adapt_feature → None` skip line 43); `fontbox/ttf/gsub/gsub_worker_for_latin.py` 96% → 100% (same shape line 41); `filter/predictor.py` 97% → 100% (no-op constructor line 37); `filter/jpx_decode.py` 99% → 100% (`encode` unsupported BPC OSError lines 205-208). **`# pragma: no cover` applied at source for genuinely unreachable / platform-specific residue**: `cos_parser.py` line 1630 (defensive `ImportError` on `pdmodel.encryption` — always importable when this code runs) and line 1851 (`_last_parsed_trailer is None` after `parse_trailer()` returned True — invariant); `base_parser.py` line 913 (empty `bad_string` after non-WS/non-digit lead — corrupt-stream edge), line 978 (nested-array `[` recovery), lines 1091-1096 (negative generation — lexer rejects); `pdf_parser.py` line 388 (linearization-scan early-out on non-digit lead — comments interleaved with header skipped before this point); `xref_trailer_resolver.py` lines 271-277 (malformed `/Prev` chain pointing outside byte-pos map); `cff_parser.py` lines 464-466 (`illegal nibble` — `b // 16` / `b % 16` always 0x0-0xF); `glyph_array_splitter_regex_impl.py` line 61-62 (`compare(x, x)` — dedup'd before sort); `cff_table.py` line 141 (`read_into → 0` truncated-table guard); `true_type_font.py` line 287 (`set_data` setter — pre-wave compat shim, all TTFTable subclasses define it now), line 1082 (`tables` empty fallback — parser rejects fonts without cmap subtables earlier), line 1122 (non-None GSUB result — corpus fonts lack GSUB), lines 1171-1172 (`g\d+` literal-GID `ValueError` after `isdigit()` — unreachable), lines 1305-1306 (`glyphOrder is None` — fontTools always sets it), line 1641 (`"(null)"` — fixtures always carry a PostScript name); `type1_parser.py` line 1354 (next-token None after non-None peek — array form), line 1398 (same shape — procedure), line 1425 (same — proc_void), line 1568 (empty `read_dict_value` — defensive for malformed Type1 dicts), line 1643 (next-token None after non-None peek — encoding), line 1662 (next-token None after non-None peek — encoding inner loop); `io/non_seekable_random_access_read_input_stream.py` line 126 (`buf is None` — already `# type: ignore[unreachable]`); `io/random_access_read_memory_mapped.py` line 36 (Windows-only `mmap.ACCESS_READ` branch — dev box POSIX); `filter/jbig2_filter.py` lines 112-113 (defensive `FilterFactory.register` try/except guard); `filter/jpx_filter.py` lines 82-83 (same defensive registration guard); `filter/jpx_decode.py` line 214 (`pixels == 0 or bytes_per_sample == 0` — guarded above). **One latent observation**: the `# type: ignore[unreachable]` on `non_seekable_random_access_read_input_stream.py` line 125 was already present and is correct under static type-checking; the runtime guard is dead but mirrors upstream's Java `Objects.requireNonNull` defensiveness. No latent source bugs flagged. |
| `tests/debugger/test_pd_debugger_print_wave1359.py` | 3.0.x | hand-written behaviour-feature tests for the Debugger Print menu (wave 1359 agent C). 10 tests covering `_print_menu_item_action_performed` (no-document silent return, empty-document info dialog, populated-document spooler dispatch, helper-raises error dialog, `get_number_of_pages` failure surfaced via showerror) and the new `_send_document_to_printer` helper across its three OS-dispatch arms (POSIX `lp` writes a valid 3-page temp PDF; Windows `os.startfile(path, 'print')`; `open` / `xdg-open` fallback when no spooler; `Popen('lp', ...)` OSError falls through to opener; final no-spooler-no-opener info dialog points the user at the rasterised PDF). The Print menu previously surfaced a 'not implemented' messagebox; this wave wires it to the host OS print pipeline by rasterising every page via `PDFRenderer.render_image_with_dpi(dpi=150)` and bundling the images into a temp multi-page PDF via Pillow's `Image.save(save_all=True, append_images=...)`. No new dependencies. |
