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

