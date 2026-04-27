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

### `pypdfbox/pdfparser/`

PDF-specific parsing — port territory.

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdfparser/base_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/BaseParser.java` (tokenization subset only) |
| `pypdfbox/pdfparser/cos_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/COSParser.java` (direct-object / array / dict / indirect-ref subset; no xref / stream-body / object-stream paths yet) |
| `pypdfbox/pdfparser/xref_trailer_resolver.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/XrefTrailerResolver.java` |
| `pypdfbox/pdfparser/pdf_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFParser.java` (traditional xref + trailer + /Prev + stream body; xref-streams / object-streams / malformed recovery deferred) |
| `pypdfbox/pdfparser/pdf_stream_parser.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdfparser/PDFStreamParser.java` |
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
| `pypdfbox/contentstream/operator/text/show_text_adjusted.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextAdjusted.java` |
| `pypdfbox/contentstream/operator/text/show_text_line.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLine.java` |
| `pypdfbox/contentstream/operator/text/show_text_line_and_space.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/ShowTextLineAndSpace.java` |

### `pypdfbox/text/`
_(not started)_

### `pypdfbox/rendering/`

Clusters #1 + #2 ship **original Python work** built on Pillow + aggdraw + fontTools — not a line-by-line port of upstream `PDFRenderer.java` / `PageDrawer.java`. The upstream classes target Java2D's `Graphics2D` API; there is no Python equivalent to port verbatim. The PUBLIC API surface (`render_image(page_index, scale)`, `render_image_with_dpi(page_index, dpi)`) does mirror upstream, and operator dispatch reuses the ported `PDFStreamEngine` infrastructure. Cluster #2 added text/glyph rasterisation (TrueType glyph outlines through fontTools), Form XObject `Do`, `W`/`W*` clip paths, and inline images.

| pypdfbox path | upstream PDFBox version | upstream Java path | derivation scope |
|---|---|---|---|
| `pypdfbox/rendering/pdf_renderer.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/rendering/PDFRenderer.java` + `pdfbox/src/main/java/org/apache/pdfbox/rendering/PageDrawer.java` | API surface only (`renderImage` / `renderImageWithDPI` entry points + per-operator semantics from `PageDrawer`). Implementation is original Python over Pillow + aggdraw + fontTools — Java2D `Graphics2D` has no Python equivalent. |

Original work (no PROVENANCE entry needed; listed for clarity):
- `pypdfbox/rendering/__init__.py` — re-exports `PDFRenderer`

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
| `pypdfbox/pdmodel/graphics/pd_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDXObject.java` |
| `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/image/PDImageXObject.java` (metadata + stream access surface only; image decoding deferred) |
| `pypdfbox/pdmodel/graphics/form/pd_form_x_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/form/PDFormXObject.java` |

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
| `pypdfbox/pdmodel/interactive/action/pd_action_sound.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionSound.java` (lite — `/Sound` returns raw COS, typed PDSoundStream deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_action_movie.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionMovie.java` (lite — `/Annotation` returns raw COS, typed PDAnnotationMovie deferred) |
| `pypdfbox/pdmodel/interactive/action/pd_action_rendition.py` | 3.0.x | PDF 32000-1 §12.6.4.13 (no upstream source — modelled on spec; `/AN` and `/R` return raw COS) |
| `pypdfbox/pdmodel/interactive/action/pd_action_transition.py` | 3.0.x | PDF 32000-1 §12.6.4.14 (no upstream source; `/Trans` typed via PDTransition) |
| `pypdfbox/pdmodel/interactive/action/pd_action_embedded_go_to.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionEmbeddedGoTo.java` (`/T` typed via PDTargetDirectory) |
| `pypdfbox/pdmodel/interactive/action/pd_target_directory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDTargetDirectory.java` (lite — `/N` exposed as named-destination string, `/P` as page index int per task spec; deviates from upstream `/N`=embedded filename, `/P`=page-or-named-dest) |
| `pypdfbox/pdmodel/interactive/action/pd_document_catalog_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDDocumentCatalogAdditionalActions.java` |
| `pypdfbox/pdmodel/interactive/annotation/pd_border_style_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDBorderStyleDictionary.java` (lite — `/D` returns raw `COSArray`, `PDLineDashPattern` deferred) |
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
| `pypdfbox/pdmodel/graphics/color/pd_output_intent.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/color/PDOutputIntent.java` (lite — `setData(InputStream)` ICC embedding deferred; `/DestOutputProfile` returns raw COSStream) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_membership_dictionary.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentMembershipDictionary.java` (`/VE` raw COSArray — visibility-expression tree parsing deferred per upstream) |
| `pypdfbox/pdmodel/graphics/pd_property_list.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDPropertyList.java` (lite — `create()` returns `None` for unknown `/Type`) |
| `pypdfbox/pdmodel/graphics/pd_line_dash_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/PDLineDashPattern.java` (lite — phase accepts `float`) |
| `pypdfbox/pdmodel/graphics/state/pd_extended_graphics_state.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PDExtendedGraphicsState.java` (lite — `/SMask`/`/TR`/`/TR2`/`copy_into_graphics_state` deferred) |
| `pypdfbox/pdmodel/graphics/state/pd_font_setting.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/state/PDFontSetting.java` |
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
| `pypdfbox/pdmodel/font/pd_font_descriptor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontDescriptor.java` (scaffold) |
| `pypdfbox/pdmodel/font/pd_font_factory.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontFactory.java` (Type1/TrueType/Type0 only; PDCIDFont/PDType3Font deferred) |
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
| `pypdfbox/pdmodel/graphics/pattern/pd_tiling_pattern.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDTilingPattern.java` (lite — `PDContentStream` mixin deferred) |
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
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_layout_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDLayoutAttributeObject.java` (lite — accessor subset) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_list_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDListAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_print_field_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDPrintFieldAttributeObject.java` |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_table_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDTableAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_export_format_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/taggedpdf/PDExportFormatAttributeObject.java` (lite) |
| `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_user_attribute_object.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDUserAttributeObject.java` (lite — /P entries as plain dicts) |
| `pypdfbox/pdmodel/pd_page_content_stream.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageContentStream.java` (lite — text encoding, AppendMode, compression, BMC/BDC/EMC deferred) |
| `pypdfbox/contentstream/operator/operator_processor.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/OperatorProcessor.java` (lite — handlers are no-op stubs) |
| `pypdfbox/contentstream/operator/operator_registry.py` | 3.0.x | original (Python-side dispatch registry) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransition.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionStyle.java` (plain class with constants, not `enum.Enum`) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_motion.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionMotion.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_dimension.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDimension.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_direction.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDirection.java` |
| `pypdfbox/pdmodel/interactive/form/pd_acro_form.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/form/PDAcroForm.java` (scaffold + `flatten` — refresh_appearances/FDF/scripting/PDFieldTree/XFA deferred) |
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
| `pypdfbox/xmpbox/dom_xmp_parser.py` | 3.0.x | `xmpbox/src/main/java/org/apache/xmpbox/xml/DomXmpParser.java` (+ `XmpParsingException.java`; read path only, ElementTree-backed) |

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

Not yet ported (classes not implemented in pypdfbox): `EndstreamFilterStreamTest`, `PDFObjectStreamParserTest`, `TestPDFParser`.

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
| `pypdfbox/pdmodel/common/function/pd_function.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/function/PDFunction.java` (lite — eval deferred) |
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
