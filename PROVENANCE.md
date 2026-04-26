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
| `pypdfbox/filter/flate_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/FlateFilter.java` | API surface; underlying compress/decompress is `zlib`. Predictor (PNG/TIFF) is original |
| `pypdfbox/filter/ascii_hex_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCIIHexFilter.java` | API surface; underlying hex codec is `binascii` |
| `pypdfbox/filter/ascii85_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/ASCII85Filter.java` | API surface; base-85 numerics delegated to `base64.a85encode`/`a85decode` |
| `pypdfbox/filter/run_length_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/RunLengthFilter.java` | full port — encoder ported line-for-line so output bytes match PDFBox |
| `pypdfbox/filter/lzw_decode.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/filter/LZWFilter.java` | full port — PDF-flavored LZW (9-12 bit, MSB-first, EarlyChange handling) |

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
_(not started)_

### `pypdfbox/pdmodel/`

Cluster #1 (PDDocument / PDPage / PDPageTree / PDDocumentCatalog / PDResources / PDRectangle).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/pd_document.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocument.java` (cluster #1 surface — load / save / save_incremental / pages / version / encryption flags; signing, FDF, overlay, font subsetting deferred) |
| `pypdfbox/pdmodel/pd_document_catalog.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDDocumentCatalog.java` (cluster #1 surface — pages / version / language / page layout / page mode; struct tree, AcroForm, outlines, metadata stubbed) |
| `pypdfbox/pdmodel/pd_page.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPage.java` |
| `pypdfbox/pdmodel/pd_page_tree.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDPageTree.java` |
| `pypdfbox/pdmodel/pd_resources.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDResources.java` (cluster #1 surface — resource-dict accessors; XObject / font / colorspace lookups stubbed for later clusters) |
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
| `pypdfbox/pdmodel/interactive/action/pd_action_unknown.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDAction.java` (unknown-action fallback pattern) |
| `pypdfbox/pdmodel/interactive/action/pd_page_additional_actions.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/action/PDPageAdditionalActions.java` |

Cluster #7 foundations (file specifications, generic name tree, optional content, page transitions, AcroForm scaffold).

| pypdfbox path | upstream PDFBox version | upstream Java path |
|---|---|---|
| `pypdfbox/pdmodel/common/pd_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDNameTreeNode.java` |
| `pypdfbox/pdmodel/common/pd_string_name_tree_node.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/PDJavascriptNameTreeNode.java` (modelled after; concrete string-keyed subclass — additive value→COS direction) |
| `pypdfbox/pdmodel/common/filespecification/pd_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_simple_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDSimpleFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_complex_file_specification.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDComplexFileSpecification.java` |
| `pypdfbox/pdmodel/common/filespecification/pd_embedded_file.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/filespecification/PDEmbeddedFile.java` (lite — date accessors return raw COSString; constructor variants collapsed) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_group.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentGroup.java` (does not extend `PDPropertyList` — parent not yet ported) |
| `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_properties.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentProperties.java` (BaseState/RenderState enums collapsed to plain strings) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransition.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_style.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionStyle.java` (plain class with constants, not `enum.Enum`) |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_motion.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionMotion.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_dimension.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDimension.java` |
| `pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_direction.py` | 3.0.x | `pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/pagenavigation/PDTransitionDirection.java` |

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
