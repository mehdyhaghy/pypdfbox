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
| `pypdfbox/io/scratch_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/io/ScratchFile.java` | API surface (`create_buffer()`, lifecycle); storage is `tempfile.SpooledTemporaryFile`, not page-based |

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
| `pypdfbox/cos/pd_linearization_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocument.java` (linearization-hint parsing extracted from upstream `PDDocument` into a standalone typed wrapper) |

### `pypdfbox/pdfparser/`

PDF-specific parsing — port territory.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfparser/base_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/BaseParser.java` (tokenization subset only) |
| `pypdfbox/pdfparser/cos_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/COSParser.java` (direct-object / array / dict / indirect-ref + brute-force recovery + parsePDFHeader + parseXrefTable + parseXrefObjStream + parseObjectStream + direct-/Length stream body; indirect-/Length deferred to PDFParser) |
| `pypdfbox/pdfparser/xref_trailer_resolver.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/XrefTrailerResolver.java` |
| `pypdfbox/pdfparser/pdf_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFParser.java` (traditional xref + trailer + /Prev + stream body; xref-streams / object-streams / malformed recovery deferred) |
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
| `pypdfbox/filter/ccitt_fax_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/CCITTFaxFilter.java` | API surface; T.4 / T.6 decoding delegated to libtiff via Pillow (synthetic TIFF wrapper around the encoded strip). Decode-only (no encoder use case yet). |
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
| `pypdfbox/pdmodel/pd_document_catalog.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentCatalog.java` (cluster #1 surface — pages / version / language / page layout / page mode; struct tree, AcroForm, outlines, metadata stubbed) |
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
| `pypdfbox/pdmodel/graphics/pd_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDXObject.java` |
| `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObject.java` (metadata + stream access surface only; image decoding deferred) |
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
| `pypdfbox/pdmodel/interactive/documentnavigation/destination/pd_destination_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/destination/PDDestinationNameTreeNode.java` (lite flat `/Names` array wrapper only) |
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
| `pypdfbox/pdmodel/pd_document_name_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentNameDictionary.java` (lite — `/AP /Pages /Templates /IDS /URLS /AlternatePresentations /Renditions` accessors deferred) |
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

Cluster #1 — XMP packet read path. Wraps `xml.etree.ElementTree` (stdlib).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/xmpbox/xmp_metadata.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/XMPMetadata.java` (+ `XmpConstants.java` folded in; `TypeMapping` omitted — deferred to write-path cluster) |
| `pypdfbox/xmpbox/xmp_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPSchema.java` (read-path accessors only; AbstractField/ArrayProperty hierarchy deferred) |
| `pypdfbox/xmpbox/dublin_core_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/DublinCoreSchema.java` (constants + value getters) |
| `pypdfbox/xmpbox/xmp_basic_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPBasicSchema.java` (constants + value getters; dates kept as ISO strings) |
| `pypdfbox/xmpbox/pdfa_identification_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/PDFAIdentificationSchema.java` (typed `part` / `conformance` / `amd` / `rev` accessors with upstream `setPartValueWithInt` / `setPartValueWithString` / `setRevValueWithInt` / `setRevValueWithString` aliases; conformance validates against `{A, B, U, e, f}` per PDFBOX-6088 and raises `BadFieldValueException`; pypdfbox-only `corr` correction-year passthrough) |
| `pypdfbox/xmpbox/pdfa_extension_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/PDFAExtensionSchema.java` (lite surface — `pdfaExtension:schemas` Bag dict accessors + raw element passthrough; nested `pdfaProperty` / `pdfaType` struct hierarchy deferred) |
| `pypdfbox/xmpbox/xmp_rights_management_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPRightsManagementSchema.java` (typed `Certificate` / `Marked` / `Owner` / `UsageTerms` / `WebStatement` accessors) |
| `pypdfbox/xmpbox/xmp_media_management_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/XMPMediaManagementSchema.java` (typed `DocumentID` / `InstanceID` / `OriginalDocumentID` / `VersionID` / `RenditionClass` / `RenditionParams` / `ManageTo` / `ManageUI` / `Manager` / `ManagerVariant` accessors; `DerivedFrom` / `Ingredients` deferred) |
| `pypdfbox/xmpbox/dom_xmp_parser.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/DomXmpParser.java` (+ `XmpParsingException.java`; read path only, ElementTree-backed) |
| `pypdfbox/xmpbox/date_converter.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/DateConverter.java` (returns `datetime.datetime` instead of `Calendar`; naive ISO 8601 strings are anchored to UTC matching upstream's `fromISO8601` fallback; year-0 input rejected — Python `datetime` does not support year 0, deviates from upstream `0000-01-01` → `0001-01-01`) |

### `pypdfbox/tools/`

Tools cluster #1 — command-line dispatcher and basic commands.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/tools/cli.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFBox.java` |
| `pypdfbox/tools/merge.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFMerger.java` |
| `pypdfbox/tools/split.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/PDFSplit.java` |
| `pypdfbox/tools/decrypt.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/Decrypt.java` |
| `pypdfbox/tools/version.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/Version.java` |

Original work (no PROVENANCE entry needed; listed here for clarity):
- `pypdfbox/tools/info.py` — small pypdfbox-specific document summary command.

---

## Ported upstream tests

Per PRD §12.1, every cluster's tests come in two layers: hand-written tests (under `tests/<module>/`) and ported upstream JUnit 5 tests (under `tests/<module>/upstream/`). Only the **ported** tests are listed below — hand-written tests are original work.

Upstream baseline branch: `apache/pdfbox` `3.0` (most files at `pdfbox/src/test/java/org/apache/pdfbox/<module>/...`; the io subproject lives at `io/src/test/java/org/apache/pdfbox/io/...`).

### `tests/io/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/io/upstream/test_random_access_read_buffer.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferTest.java` |
| `tests/io/upstream/test_random_access_read_buffered_file.py` | `io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferedFileTest.java` |
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
| `tests/cos/upstream/test_cos_integer.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSInteger.java` (folds in `TestCOSNumber.java`) |
| `tests/cos/upstream/test_cos_name.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSName.java` (all skipped — needs pdmodel) |
| `tests/cos/upstream/test_cos_object_key.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/COSObjectKeyTest.java` |
| `tests/cos/upstream/test_cos_stream.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSStream.java` |
| `tests/cos/upstream/test_cos_string.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSString.java` |
| `tests/cos/upstream/test_cos_update_info.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSUpdateInfo.java` (skipped — needs pdfwriter) |
| `tests/cos/upstream/test_pdf_doc_encoding.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java` (skipped — needs fontbox) |
| `tests/cos/upstream/test_unmodifiable_cos_dictionary.py` | `pdfbox/src/test/java/org/apache/pdfbox/cos/UnmodifiableCOSDictionaryTest.java` (all skipped — `as_unmodifiable_dictionary` not yet ported) |

`TestCOSBase.java` and `TestCOSNumber.java` are abstract upstream — folded into the relevant subclass tests rather than ported separately.

### `tests/pdfparser/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdfparser/upstream/test_base_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/TestBaseParser.java` |
| `tests/pdfparser/upstream/test_pdf_stream_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/PDFStreamParserTest.java` |
| `tests/pdfparser/upstream/test_cos_parser.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/COSParserTest.java` (parse-header / brute-force / rebuild-trailer / parse-xref-stream / parse-xref-table subset; fixture-corpus-driven cases skipped) |
| `tests/pdfparser/upstream/test_endstream_filter_stream.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfparser/EndstreamFilterStreamTest.java` (the byte-sequence test is a direct port; the `embedded_zip.pdf` round-trip case is skipped — fixture not in pypdfbox corpus and it really tests `readUntilEndStream` plumbing rather than the filter helper) |

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
| `tests/pdfwriter/upstream/test_content_stream_writer.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/ContentStreamWriterTest.java` (single test `testPDFBox4750` skipped — depends on PDFRenderer + TestPDFToImage + PDStream.createOutputStream; round-trip semantics covered by hand-written tests) |

### `tests/xmpbox/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/xmpbox/upstream/test_dom_xmp_parser.py` | `xmpbox/src/test/java/org/apache/xmpbox/xml/DomXmpParserTest.java` (`testPDFBox5976` + `testPDFBox5649` ported; rest skipped — need rich type system / strict mode / additional schemas) |

### `tests/pdmodel/upstream/` (cluster #2 additions)

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/upstream/test_pd_document_information.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentInformation.java` (2 cases skipped — need fixtures) |

`PDPageLabelsTest` / `PDViewerPreferencesTest` do not exist upstream in PDFBox 3.0.

### `tests/pdmodel/upstream/` (cluster #3 additions)

PDFBox 3.0 has no focused upstream JUnit classes for `PDStream`, `PDXObject`, or `PDFormXObject`. `PDImageXObjectTest` exists upstream but its useful cases depend on image codecs, `PDImageXObject.createFromFile*`, `LosslessFactory`, and rendering/color-space classes outside pdmodel cluster #3. Cluster #3 is covered by hand-written tests under `tests/pdmodel/common/` and `tests/pdmodel/graphics/`; upstream image decoding tests are deferred to the rendering / image factory clusters.

### `tests/pdmodel/interactive/annotation/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/interactive/annotation/upstream/test_pd_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTest.java` |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_square_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDSquareAnnotationTest.java` |
| `tests/pdmodel/interactive/annotation/upstream/test_pd_circle_annotation.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDCircleAnnotationTest.java` |

### `tests/fontbox/cmap/`

PDFBox does not ship a focused `CMapParserTest` in the same shape as this cluster; CMap behavior is covered here with hand-written parser and mapping tests until broader font/text parity fixtures are ported.

### `tests/pdmodel/interactive/action/` and `tests/pdmodel/interactive/documentnavigation/`

PDFBox 3.0 does not provide focused unit-test classes for each lightweight action and destination wrapper. Cluster #7 wrappers are covered with hand-written tests for factory dispatch, COS round-trip, and outline/catalog/link integration. Broader upstream tests that depend on fixture PDFs remain skipped in `tests/pdmodel/upstream/` until those fixtures and page-index lookup support land.

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

Not yet ported (need `TTFParser` / `TrueTypeCollection` / `TTFSubsetter` — fontbox clusters #2+): `TestTTFParser`, `TestCMapSubtable`, `GlyfCompositeDescriptTest`, `TrueTypeFontCollectionTest`, `TTFSubsetterTest`, `GlyphSubstitutionTable*`.

### Test fixtures

| pypdfbox fixture path | upstream resource path | upstream PDFBox version |
|---|---|---|
| `tests/fixtures/fontbox/ttf/LiberationSans-Regular.ttf` | `fontbox/src/test/resources/ttf/LiberationSans-Regular.ttf` | 3.0.x |

### `tests/pdmodel/upstream/`

| pypdfbox test path | upstream Java test path |
|---|---|
| `tests/pdmodel/upstream/test_pd_document.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocument.java` (`testVersions` partial — auto-bump-on-save deferred to font / encryption clusters; `testSaveArabicLocale` skipped — Java-locale-specific) |
| `tests/pdmodel/upstream/test_pd_document_catalog.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDDocumentCatalogTest.java` (page-labels / output-intents / open-action / threads cases skipped — depend on later clusters) |
| `tests/pdmodel/upstream/test_pd_page.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageTest.java` (acroform / annotation / thread-bead cases skipped — depend on later clusters) |
| `tests/pdmodel/upstream/test_pd_page_tree.py` | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageTreeTest.java` (cases requiring `with_outline.pdf` / `page_tree_multiple_levels.pdf` / `PDFBOX-6040-nodeloop.pdf` fixtures skipped) |

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
| `pypdfbox/xmpbox/exif_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/ExifSchema.java` (simple-typed properties only — Rational / GPSCoordinate / typed-struct properties deferred until `RationalType` / `OECF` / `CFAPattern` / `Flash` / `DeviceSettings` types land) |
| `pypdfbox/xmpbox/tiff_schema.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/schema/TiffSchema.java` (substitute for non-existent `CameraRawSchema` — TIFF tags cover camera-pipeline metadata) |
| `pypdfbox/tools/extracttext.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/ExtractText.java` (round-out: `-html`/`-md` minimal-wrapper output, `-ignoreBeads`, `-debug` stderr summary — see CHANGES.md) |
| `tests/tools/upstream/test_extracttext.py` | 3.0.x | `pdfbox-tools/src/test/java/org/apache/pdfbox/tools/TestExtractText.java` |
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
| `pypdfbox/tools/pdfdebugger.py` | 3.0.x | original (upstream `PDFDebugger` is a Swing GUI — pypdfbox provides a CLI-only lite version per CLAUDE.md "no GUI subsystems") |
| `pypdfbox/tools/imagetopdf.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/tools/ImageToPDF.java` (image embedding inline via Pillow + zlib since `JPEGFactory` / `LosslessFactory` are not yet ported) |
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
| `pypdfbox/xmpbox/type/type_mapping.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/type/TypeMapping.java` (subset: simple-property registry + create_* factories; structured-type plumbing deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_windows_launch_params.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDWindowsLaunchParams.java` |
| `pypdfbox/pdmodel/interactive/form/pd_appearance_generator.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/AppearanceGeneratorHelper.java` (text-field flat-text path only — button/choice/signature appearances deferred) |
| `pypdfbox/tools/texttopdf.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/TextToPDF.java` |
| `pypdfbox/tools/writedecodedstream.py` | 3.0.x | `pdfbox-tools/src/main/java/org/apache/pdfbox/tools/WriteDecodedDoc.java` |
| `pypdfbox/pdmodel/pdfa_flavour.py` | 3.0.x | original (no upstream PDFBox class — closest analogue is `org.verapdf.pdfa.flavours.PDFAFlavour` from veraPDF; pypdfbox provides a passive *detector* per CLAUDE.md "no preflight, no veraPDF reimplementation") |
| `tests/xmpbox/type/upstream/test_attribute.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/AttributeTest.java` |
| `tests/xmpbox/type/upstream/test_simple_metadata_properties.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/type/TestSimpleMetadataProperties.java` |
| `tests/pdmodel/graphics/image/upstream/test_jpeg_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/JPEGFactoryTest.java` |
| `tests/pdmodel/graphics/image/upstream/test_lossless_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/LosslessFactoryTest.java` (rendering-comparison parts skipped) |
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
| `tests/xmpbox/upstream/test_xmp_basic_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/XMPBasicTest.java` |
| `tests/xmpbox/upstream/test_dublin_core_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/DublinCoreTest.java` |
| `tests/fontbox/afm/upstream/test_afm_parser.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/AFMParserTest.java` |
| `tests/fontbox/afm/upstream/test_font_metrics.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/FontMetricsTest.java` |
| `tests/fontbox/afm/upstream/test_char_metric.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/CharMetricTest.java` |
| `tests/fontbox/afm/upstream/test_composite.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/CompositeTest.java` |
| `tests/fontbox/afm/upstream/test_kern_pair.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/afm/KernPairTest.java` |
| `pypdfbox/pdmodel/pdfua_flavour.py` | 3.0.x | pypdfbox addition (no upstream Java class — modeled on veraPDF PDF/UA flavour metadata) |
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
| `tests/pdmodel/upstream/test_pd_page_content_stream.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageContentStreamTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_color.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDColorTest.java` |
| `tests/pdmodel/graphics/color/upstream/test_pd_color_space_factory.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDColorSpaceTest.java` |
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
| `tests/fontbox/cmap/upstream/test_cmap_parser.py` | 3.0.x | `fontbox/src/test/java/org/apache/fontbox/cmap/CMapParserTest.java` |
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
| `tests/text/upstream/test_pdf_text_stripper_deeper.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/text/TestTextStripper.java` (subset — synthetic content streams stand in for the upstream PDF fixtures the lite stripper does not yet round-trip; pins `setShouldFlipAxes`, `setShouldSeparateByBeads` bead-bucket ordering, `shouldSkipGlyph`, `isParagraphSeparation` drop+indent prongs, and `writeStringWithPositions` invariants) |
| `tests/pdmodel/font/upstream/test_pd_font_descriptor.py` | 3.0.x | derived line-by-line from `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontDescriptor.java`, `PDPanose.java`, `PDPanoseClassification.java` — upstream has no dedicated `PDFontDescriptorTest.java`; tests pin Javadoc-documented contracts (defaults, flag masks, /Type entry, /CharSet COSString storage, /CIDSet stream wrapping, 12-byte Panose layout) |

### Wave 41 additions

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `tests/multipdf/test_splitter_signatures.py` | 3.0.x | hand-written; signature widget detection + AcroForm /SigFlags scrub for `pdfbox/src/main/java/org/apache/pdfbox/multipdf/Splitter.java` (upstream has no dedicated `SplitterSignatureTest.java`) |
| `tests/multipdf/test_splitter_cid_fonts.py` | 3.0.x | hand-written; CID `/FontFile2` round-trip across `Splitter` chunks (upstream has no dedicated `SplitterCIDFontTest.java` — exercised via `PDFMergerUtilityTest` fixtures we don't carry) |
| `tests/multipdf/upstream/test_splitter_signatures.py` | 3.0.x | placeholder pointing at hand-written coverage — upstream has no `SplitterSignatureTest.java` |
| `tests/multipdf/upstream/test_splitter_cid_fonts.py` | 3.0.x | placeholder pointing at hand-written coverage — upstream has no `SplitterCIDFontTest.java` |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_configuration.py` | 3.0.x | original (no standalone upstream class — Apache PDFBox 3.0 inlines /D accessors on `PDOptionalContentProperties.java`; pypdfbox extracts a typed wrapper so the same surface services /Configs entries) |
| `tests/pdmodel/graphics/optionalcontent/upstream/test_optional_content_groups.py` | 3.0.x | `pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/TestOptionalContentGroups.java` (state-assertion subset — content-stream writing + image-diff render phases skipped per per-test comment) |
| `tests/multipdf/test_merger_struct_tree.py` | 3.0.x | hand-written; structure-tree edge-case coverage for `pdfbox/src/main/java/org/apache/pdfbox/multipdf/PDFMergerUtility.java` — RoleMap conflict, MCID-indexed parent-tree leaves, /Pg rewriting, destination /Info / /Metadata override, AcroFormMergeMode dispatch, IDTree collision (synthetic equivalents to upstream `PDFMergerUtilityTest.testStructureTreeMerge*` cases that depend on `input/PDFA-1b.pdf` fixture) |
| `tests/xmpbox/upstream/test_pdfa_identification_schema.py` | 3.0.x | `xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationOthersTest.java` + `PDFAIdentificationTest.java` (parameterised value channel — typed-field round-trip via `getPartProperty().getStringValue()` deferred until the AbstractField hierarchy lands; XmpSerializer round-trip uses a hand-rolled XMP packet because pypdfbox does not yet ship an upstream-shaped serializer) |
| `tests/pdmodel/graphics/color/upstream/test_pd_output_intent.py` | 3.0.x | parity-shaped tests for `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDOutputIntent.java` — upstream PDFBox 3.0 ships no dedicated `PDOutputIntentTest.java`, so coverage targets the documented Java API contract (subtype + flate-compressed `/DestOutputProfile` + `/N` + string accessors) |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_pd_signature.py` | 3.0.x | placeholder — upstream has no `PDSignatureTest.java` (verified 2026-04-27 against `apache/pdfbox` `3.0` branch); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_pd_signature.py` |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_pd_prop_build.py` | 3.0.x | placeholder — upstream has no `PDPropBuild*Test.java` (verified 2026-04-27); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_pd_prop_build.py` |
| `tests/pdmodel/interactive/digitalsignature/upstream/test_signature_verification.py` | 3.0.x | placeholder — upstream has no JUnit class for the verify pipeline (exercised via `pdfbox-examples`'s `ShowSignatureTest.java`); coverage in hand-written `tests/pdmodel/interactive/digitalsignature/test_signature_verification.py` |
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
| `tests/pdmodel/documentinterchange/logicalstructure/upstream/test_pd_object_reference.py` | 3.0.x | parity-shaped coverage for `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDObjectReference.java` |
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
