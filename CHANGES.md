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

- **No `preflight` module.** Apache PDFBox 4.0 removes Preflight; we follow that decision. PDF/A and PDF/UA validation is out of scope — users can plug in any external validator they choose. The pypdfbox repo intentionally has no dependency on, nor scaffolding for, any specific validator (GPL-licensed tools in particular are not used, per PRD §4 forbidden-license list).
- **No commons-logging / log4j.** Python `logging` (stdlib) is used throughout.
- **Method naming.** Java camelCase → Python snake_case across the entire API surface. Semantics unchanged.

## Project status (as of Wave 1377, 2026-05-21)

- **Upstream baseline**: Apache PDFBox 3.0 HEAD (last sync wave 1377).
- **Tests**: 42,688 passing (full pytest, wave 1377).
- **Line coverage**: 100.000% global.
- **Class parity / method parity**: TBD — last published snapshot at wave 1301 was 100.0% class parity (excl. preflight) / 97.3% method parity; recompute pending after the 1238-1377 wave run.
- **Local TODOs**: 0 in production source (all deferrals tracked in `DEFERRED.md`).
- **Out of scope (permanent)**: `org.apache.pdfbox.preflight.*` (PDFBox 4.0 removed it; PDF/A and PDF/UA validation delegated to whichever external validator the user chooses, per PRD §13).
- **Phase**: Phase 3 closeout. Wave history lives in `HISTORY.md`; open follow-ups live in `DEFERRED.md`.

## Active divergences vs upstream

Divergences that remain live (will affect observable behaviour vs Java PDFBox):

- **Symbol + ZapfDingbats Standard 14 substitution still deferred**. The remaining 12 Standard 14 faces (Times / Helvetica / Courier × Regular / Bold / Italic / BoldItalic) substitute through bundled Liberation TTFs (closed wave 1376). Symbol and ZapfDingbats stay as `.notdef` placeholders — no Liberation or DejaVu equivalent is bundled. `pypdfbox/pdmodel/font/standard14_fonts.py`.
- **ICU bidi reordering not ported.** `pypdfbox/text/pdf_text_stripper.py::handle_direction` uses Python stdlib `unicodedata.bidirectional` for RTL detection / reordering instead of upstream's `com.ibm.icu.text.Bidi.reorderVisually`. Whole-paragraph reversal works for pure-RTL and pure-LTR runs; mixed-LTR+RTL Unicode bidi paragraph reordering is the documented lite divergence (no parity vs the full ICU Bidi algorithm).
- **`SimpleDateFormat` locale-sensitive parsing not ported.** `pypdfbox/xmpbox/date_converter.py::parse_simple_date` is regex-driven for digit-start patterns; alpha-start patterns (locale month/weekday dictionaries: `"Friday, January 11, 2115"`, `"Sun, Jul 6, 1980 at 4:23pm"`, etc.) fall through. Production callers exercise the digit-start shapes only.
- **`split_on_space` / `tokenize_on_space` Python regex semantics.** `pypdfbox/util/string_util.py`: `split_on_space("   ")` returns `["", "", "", ""]` (Python's `re.split`); Java's `String.split("\\s")` strips trailing empties and returns `[]`. `tokenize_on_space("   ")` returns `["", " ", " ", " ", ""]`; Java's `Pattern.split` of zero-width lookarounds collapses adjacent matches and returns `[" ", " ", " "]`. Both shapes communicate the same tokens; we record the Python shape.
- **`PDFRenderer` pixel-exact parity not portable.** Upstream JUnit comparisons against stored TIFF/PNG references are *not* ported. Pypdfbox uses Pillow + a skia-backed `_aggdraw_compat` rasteriser; byte-equivalent raster output across the Java AWT and the Python pipeline is unachievable. Affected paths use structural parity (page count, MediaBox, Rotation, Contents shape, Resources keys, save-reload round-trip) anchored to the bundled reference PDFs. `pypdfbox/rendering/pdf_renderer.py`.
- **Skia anti-aliasing vs upstream Java2D AA.** The `_aggdraw_compat` skia path may render edge pixels differently from upstream Java2D in low-resolution rasters. Recorded as a known limitation; full pixel parity is not in scope (see preceding bullet).

## Per-file deviations

- `pypdfbox/pdmodel/interactive/form/pd_field_factory.py`: malformed or unknown field dictionaries are skipped by factory/tree traversal.
- `pypdfbox/xmpbox/dom_xmp_parser.py`: unknown namespaces preserve their declared XML prefixes.
- `pypdfbox/contentstream/pdf_graphics_stream_engine.py`: registers the `sh` shading operator.
- `pypdfbox/pdmodel/pd_resource_cache.py`: repeated removals mark shared resources stable at `MAX_REMOVALS`.
- `pypdfbox/tools/texttopdf.py`: non-positive font sizes fail early as usage errors.
- `pypdfbox/pdmodel/interactive/form/pd_default_appearance_string.py`: missing-font /DA fallback to Standard-14 Helvetica (PDFBOX-2661 "special mapping"); upstream raises IOException. Also tracks `cs` / `CS` / `gs` named-resource references and carries them across in `copy_needed_resources_to` (upstream "todo: other kinds of resource…" placeholder filled in).
- `pypdfbox/pdmodel/interactive/annotation/pd_appearance_stream.py`: appearance streams expose the content-stream byte-access surface.
- `pypdfbox/pdmodel/interactive/documentnavigation/destination/`: `/XYZ` and `/FitR` coordinate setters grow short arrays before writing.
- `pypdfbox/pdfparser/endstream_filter_stream.py`: mid-stream CRLF bytes are preserved until final endstream length is proven.
- `pypdfbox/fontbox/ttf/true_type_font.py`: unicode cmap selection follows PDFBox priority order including Windows Symbol fallback.
- `pypdfbox/rendering/pdf_renderer.py`: image rendering uses `PDImageXObject.to_pil_image()` before legacy RGB/gray fallback.
- `pypdfbox/contentstream/operator/text/set_text_rendering_mode_op.py`: out-of-range text rendering modes no-op before notifying the engine.
- `pypdfbox/pdfparser/pdf_parser.py`: xref stream decoding rejects negative `/W` field widths.
- `pypdfbox/pdmodel/common/filespecification/pd_embedded_file.py`: embedded-file subtype lookup accepts COS string-backed names.
- `pypdfbox/pdmodel/font/pd_type1c_font.py`: `get_average_character_width()` is implemented (mean of `/Widths` -> mean of embedded CFF charstring widths -> `defaultWidthX` -> Standard 14 AFM -> `500` floor). Upstream's `PDType1CFont.getAverageCharacterWidth` returns a hard-coded `500` with a `// todo: not implemented, highly suspect` annotation — we close that TODO using `fontTools.cffLib`'s `T2WidthExtractor` per glyph via `CFFFont.get_width`. `500` is retained only as the absolute fallback when no real signal is available, preserving observable behaviour for the empty-font case.
- `pypdfbox/pdmodel/pd_document_catalog.py`: dictionary-only catalog setters reject non-dictionary values.
- `pypdfbox/fontbox/type1/type1_parser.py`: ASCII-hex eexec segments are normalized before Type1 decryption.
- `pypdfbox/pdmodel/fdf/fdf_annotation_file_attachment.py`: FDF file attachment annotations are implemented and factory-dispatched.
- `pypdfbox/pdmodel/font/pd_cid_font_type2.py`: embedded Type2 CID font programs are probed in PDFBox order: `/FontFile2`, `/FontFile3`, then `/FontFile`.
- `pypdfbox/pdmodel/encryption/protection_policy.py`: exposes Java-style key-length and AES preference aliases.
- `pypdfbox/pdfwriter/cos_writer.py`: xref table serialization rejects offsets and generations that cannot fit fixed-width rows.
- `pypdfbox/filter/filter.py`: decode-params arrays dereference indirect entries.
- `pypdfbox/pdmodel/interactive/form/pd_check_box.py`: checkbox on-value lookup resolves widgets and skips malformed `/Kids` entries.
- `pypdfbox/pdmodel/font/pd_true_type_font.py`: replacing or subsetting a TrueType font clears cmap and GID caches.
- `pypdfbox/cos/cos_dictionary.py`: numeric and boolean typed getters support fallback-key overloads.
- `pypdfbox/pdmodel/common/pd_name_tree_node.py`: name-tree lookup continues past matching child ranges that do not contain the requested name.
- `pypdfbox/rendering/pdf_renderer.py`: page rendering rejects negative page indexes.
- `pypdfbox/pdmodel/interactive/form/pd_text_field.py`, `pypdfbox/pdmodel/interactive/form/pd_variable_text.py`: text setters reject non-string values before mutating COS state.
- `pypdfbox/pdfparser/base_parser.py`: malformed literal-string recovery mirrors PDFBox end-of-string handling around dictionary-key boundaries.
- `pypdfbox/pdmodel/graphics/color/pd_device_n_process.py`: re-exports the canonical `PDDeviceNProcess` used by DeviceN attributes.
- `pypdfbox/pdmodel/font/pd_font_descriptor.py`: PANOSE classification follows Java signed-byte widening and range behavior.
- `pypdfbox/io/random_access_read_view.py`: zero-length `read_into()` returns `0` without disturbing the parent cursor.
- `pypdfbox/pdmodel/interactive/annotation/pd_annotation_widget.py`: widget dictionaries preserve an existing non-`/Annot` `/Type` while stamping `/Subtype /Widget`.
- `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py`: image suffix and predicate helpers recognize standard short filter aliases.
- `pypdfbox/cos/cos_document.py`: exposes `get_key()` / `getKey()` lookup for object-pool keys by resolved object identity.
- `pypdfbox/pdfwriter/cos_writer.py`: unsupported object-stream output combinations fail early instead of being silently ignored.
- `pypdfbox/pdmodel/common/function/pd_function_type2.py`: Type 2 functions clip outputs according to explicit `/Range` pairs.
- `pypdfbox/pdmodel/fdf/fdf_dictionary.py`: `get_file()` returns a typed file specification and string helpers remain available.
- `pypdfbox/fontbox/ttf/horizontal_metrics_table.py`: horizontal metric lookups guard negative and out-of-range glyph ids.
- `pypdfbox/pdmodel/common/pd_matrix.py`: matrix row/column access rejects coordinates outside `0..2`.
- `pypdfbox/pdmodel/encryption/standard_security_handler.py`: AES-256 owner-password decryption grants owner permissions.
- `pypdfbox/pdmodel/pd_page_labels.py`: computed page-label ranges are clamped to the actual document page count.
- `pypdfbox/pdmodel/interactive/action/pd_additional_actions.py`: generic additional-actions wrapper supports `/F` trigger round-tripping.
- `pypdfbox/pdmodel/common/pd_stream.py`: decode-parameter replacement clears stale `/DP`, and committed zero-byte streams report empty.
- `pypdfbox/fontbox/cff/cff_font.py`: format-1 CFF encoding ranges stop at code `255` instead of wrapping.
- `pypdfbox/pdfparser/xref_trailer_resolver.py`: `reset()` clears visited xref offsets for recovery/reparse passes.
- `pypdfbox/pdmodel/pd_resources.py`: pattern and shading resource helpers accept plain string names.
- `pypdfbox/pdmodel/font/pd_type3_font.py`: Type 3 fonts expose bounding-box and position-vector methods from the `PDFontLike` surface.
- `pypdfbox/cos/cos_integer.py`: `COSInteger.get(True/False)` rejects booleans instead of returning cached `1`/`0` integers.
- `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_item.py`: named destination page lookup prefers `/Names /Dests` over legacy catalog `/Dests`.
- `pypdfbox/filter/lzw_decode.py`: LZW encode/decode flushes caller-provided output streams.
- `pypdfbox/pdmodel/graphics/optionalcontent/pd_optional_content_properties.py`: visibility writes remove stale duplicate `/ON` and `/OFF` references before storing the new state.
- `pypdfbox/pdmodel/interactive/annotation/pd_appearance_content_stream.py`: dashed borders without explicit `/D` materialize the default `[3]` dash pattern.
- `pypdfbox/loader.py`: exposes Java-style `loadPDF`, `loadFDF`, and `loadXFDF` aliases.
- `pypdfbox/pdmodel/font/afm_loader.py`: bundled AFM resources load through `importlib.resources` handles instead of filesystem paths.
- `pypdfbox/io/scratch_file.py`: exposes main-memory-only ScratchFile factory aliases.
- `pypdfbox/pdmodel/documentinterchange/taggedpdf/pd_print_field_attribute_object.py`: print-field role and checked-state getters accept COS string-backed names.
- `pypdfbox/pdmodel/interactive/form/pd_acro_form.py`: form flattening guards against cyclic `/Kids` graphs.
- `pypdfbox/pdmodel/graphics/image/`: image factories expose Java-style PDFBox creation aliases.
- `pypdfbox/fontbox/ttf/ttf_data_stream.py`: `read_unsigned_int()` treats any negative byte as EOF.
- `pypdfbox/pdmodel/encryption/pd_encryption.py`, `pypdfbox/pdmodel/encryption/pd_crypt_filter_dictionary.py`: dictionary wrappers expose `get_cos_dictionary()`.
- `pypdfbox/pdmodel/common/pd_metadata.py`: filtered metadata size reports decoded XMP byte length.
- `pypdfbox/pdmodel/interactive/annotation/pd_annotation_file_attachment.py`: exposes PDFBox attachment-name aliases, including the legacy misspelled setter.
- `pypdfbox/pdmodel/graphics/color/pd_icc_based.py`: malformed ICCBased `/Range` arrays default component ranges to `(0.0, 1.0)`.
- `pypdfbox/pdmodel/font/pd_font_factory.py`: embedded font-program headers are read from decoded stream bytes.
- `pypdfbox/pdfparser/pdf_parser.py`: lenient parsing attempts shifted-offset recovery before rejecting out-of-bounds `startxref`.
- `pypdfbox/pdmodel/common/filespecification/pd_embedded_file.py`: malformed PDF date timezone offsets return `None`.
- `pypdfbox/pdmodel/pd_viewer_preferences.py`: includes the long-form deprecated `UseOC` non-full-screen page mode constant.
- `pypdfbox/cos/cos_stream.py`: `stop_filters` canonicalizes standard filter aliases before comparison.
- `pypdfbox/pdmodel/font/pd_cid_system_info.py`: string rendering uses Java-style `null` for missing registry or ordering.
- `pypdfbox/pdmodel/common/pd_number_tree_node.py`: switching a number tree node to kids clears stale `/Nums` and refreshes ancestor limits.
- `pypdfbox/pdfwriter/cos_writer.py`: incremental saves track absolute output offsets after copied source bytes.
- `pypdfbox/pdmodel/interactive/action/pd_action_java_script.py`: stream-form `/JS` actions decode through `COSStream.to_text_string()`.
- `pypdfbox/pdmodel/interactive/documentnavigation/destination/`: default coordinate-based destination constructors include optional coordinate slots as `COSNull`.
- `pypdfbox/pdmodel/pd_page_content_stream.py`: `move_text_position_and_set_leading()` requires an active text block.
- `pypdfbox/cos/cos_dictionary.py`: raw `get_item` supports the PDFBox alternate-key overload shape.
- `pypdfbox/filter/flate_decode.py`: Flate encode/decode flushes output sinks after writing.
- `pypdfbox/pdmodel/interactive/annotation/pd_border_effect_dictionary.py`: `set_style(None)` clears optional `/S`.
- `pypdfbox/pdmodel/graphics/color/pd_cal_rgb.py`: missing or cleared `/Matrix` returns the identity matrix.
- `pypdfbox/pdmodel/font/encoding/dictionary_encoding.py`: symbolic reader-mode encodings without a valid base or built-in encoding fail explicitly.
- `pypdfbox/pdfparser/pdf_stream_parser.py`: inline-image parsing only treats exact `ID` as image data, leaving `I` and longer operator names as normal operators.
- `pypdfbox/pdmodel/common/function/pd_function_type4.py`: Type 4 function parsing rejects missing and stray closing braces.
- `pypdfbox/pdmodel/interactive/form/pd_choice.py`: one-element nested `/Opt` entries are preserved in display values so tolerated malformed option arrays keep export/display alignment.
- `pypdfbox/fontbox/ttf/true_type_font.py`: synthesized header metadata preserves `head.created` and `head.modified` as UTC `datetime` values.
- `pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_node.py`: direct structure-element kid append/remove operations maintain the child's `/P` parent pointer.
- `pypdfbox/pdmodel/graphics/form/pd_transparency_group_attributes.py`: cached `/CS` color spaces are invalidated when the raw COS source is externally replaced or removed.
- `pypdfbox/pdmodel/encryption/security_provider.py`: `/Adobe.PubSec` resolves through the public-key security handler factory.
- `pypdfbox/pdmodel/graphics/image/pd_image_x_object.py`: stencil image XObjects now treat missing `/ColorSpace` as implicit `DeviceGray`.
- `pypdfbox/pdmodel/interactive/measurement/pd_media_clip.py`, `pypdfbox/pdmodel/interactive/measurement/pd_rendition.py`: media clip and rendition factories dereference indirect objects and treat unresolved or null references as absent.
- `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_item.py`, `pypdfbox/pdmodel/interactive/documentnavigation/outline/pd_outline_node.py`: sibling insertion rewrites inserted item parents consistently.
- `pypdfbox/fontbox/cff/cff_font.py`: empty or unparsed CFF fonts return safe width/path fallbacks.
- `pypdfbox/pdmodel/fdf/fdf_annotation_line.py`: FDF line annotations expose `/L` accessors and malformed coordinate arrays read as absent.
- `pypdfbox/io/random_access_read_buffer.py`: wraps `io.BytesIO` instead of reimplementing PDFBox's chunked-list storage. Observable behavior is identical; implementation is C-backed and ~25 lines instead of ~120. Justification: PRD §3.7 (stdlib-first for generic infrastructure).
- `pypdfbox/io/random_access_read_buffered_file.py`: wraps `io.BufferedReader` over a raw file fd. Stdlib provides the read-ahead buffering that upstream's `RandomAccessReadBufferedFile` implements manually. Justification: PRD §3.7.
- `pypdfbox/io/random_access_read_memory_mapped.py`: net-new optional implementation backed by `mmap.mmap`. No upstream counterpart; offered as opt-in for very large files where kernel paging beats userspace buffering. Justification: PRD §3.7 — use stdlib affordances when they fit.
- `pypdfbox/io/random_access_read_view.py`: original slice-view implementation. Mirrors the upstream `RandomAccessReadView` API; storage strategy is direct seek-on-parent rather than upstream's bounded-stream wrapper.
- `pypdfbox/io/scratch_file.py`: backed by `tempfile.SpooledTemporaryFile` (mixed mode), `tempfile.TemporaryFile` (temp-file-only), or `io.BytesIO` (memory-only). Upstream uses page-based scratch storage; we delegate spill-to-disk policy to stdlib. Behavior visible to callers (read/write/seek/clear) is identical. Justification: PRD §3.7. Default spill threshold in MIXED mode without an explicit cap is 16 MiB.
- `pypdfbox/pdmodel/font/pd_font_like.py`, `pypdfbox/pdmodel/font/pd_vector_font.py`: upstream Java `interface`s modelled as `typing.Protocol` (runtime-checkable) so existing duck-typed font classes satisfy `isinstance(...)` without inheritance — Python idiom, no observable behaviour change. AWT-typed returns (`Matrix`, `BoundingBox`, `Vector`, `GeneralPath`) are widened to `Any` since pypdfbox is AWT-free.

## See also

- [`HISTORY.md`](HISTORY.md) — chronological wave log (Wave 7 → Wave 1377).
- [`DEFERRED.md`](DEFERRED.md) — open follow-up items still tracked.
- [`PROVENANCE.md`](PROVENANCE.md) — per-file upstream porting provenance (Apache 2.0 §4(b)).
