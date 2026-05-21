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

## Wave 1379 — close DEFERRED items

- **Agent A — Typed `PDAttributeObject` owner subclasses (DEFERRED closed).** `pypdfbox/pdmodel/documentinterchange/taggedpdf/{pd_layout_attribute_object,pd_list_attribute_object,pd_print_field_attribute_object,pd_table_attribute_object,pd_export_format_attribute_object}.py` already cover every upstream-public typed accessor (Layout: Placement / WritingMode / BackgroundColor / BorderColor / BorderStyle / BorderThickness / Padding / Color / SpaceBefore / SpaceAfter / StartIndent / EndIndent / TextIndent / TextAlign / BBox / Width / Height / BlockAlign / InlineAlign / TBorderStyle / TPadding / BaselineShift / LineHeight / TextDecorationColor / TextDecorationThickness / TextDecorationType / RubyAlign / RubyPosition / GlyphOrientationVertical / ColumnCount / ColumnGap / ColumnWidths; List: ListNumbering; PrintField: Role / checked / Desc; Table: RowSpan / ColSpan / Headers / Scope / Summary; ExportFormat: full Layout surface + cross-cut List/Table accessors plus the seven §14.8.5.2 owner constants). The DEFERRED entry was "Needs verification" — closure anchored by `tests/pdmodel/documentinterchange/taggedpdf/test_owner_subclass_parity_wave1379.py` (28 verification tests: introspection-driven method-surface parity audit per upstream Java class, owner-constant checks, full set→get round trips, polymorphic scalar/array setters, upstream default values, and `toString` shape parity).
- **Agent D — GSUB lookup Types 2 / 3 / 4 audit closure.** Type 2 (multiple-substitution), Type 3 (alternate-substitution) and Type 4 (ligature-substitution) lookup subtables, sequence / alternate-set / ligature-set wrappers, and the `GlyphSubstitutionDataExtractor` dispatch for each were all already in place in `pypdfbox/fontbox/ttf/gsub/lookup_subtable.py` + `glyph_substitution_data_extractor.py` (ported across waves 290-786). Wave 1379 adds 24 fresh hand-written verification tests at `tests/fontbox/ttf/gsub/test_lookup_type{2,3,4}_wave1379.py` that pin: multi-Coverage subtables, spec-legal zero-length Sequence (Type-2 glyph deletion), all-alternates-equal-coverage degeneracy (Type-3 extractor empty-emit), extractor warn-and-skip on Coverage / sub-array size mismatch (Types 2 + 3), Type-4 greedy left-to-right walk with non-coverage interspersed glyphs, chained ligatures within a single run, empty-component candidate skip, and the upstream "later same-length candidate wins" extension contract. `DEFERRED.md` GSUB entry was already narrowed to Types 5/6/7/8 in an earlier audit; verified still accurate.
- **Agent C — Transparency-group `/K` (knockout) + `/I` (isolation) flag handling + full PDF 32000-1 §11.3.5 blend modes (DEFERRED closed).** `pypdfbox/rendering/pdf_renderer.py::_render_transparency_group` already implements all four combinations: `/I=true` paints onto a fresh transparent backdrop (`Image.new("RGBA", …, (0, 0, 0, 0))`), `/I=false` inherits the parent canvas (`parent_image.convert("RGBA")`); `/K=true` snapshots the group-entry canvas (`group_canvas.copy()`) and restores it before every top-level painting operator (`_KNOCKOUT_PAINT_OPS` covers `S s f F f* B B* b b* sh Do BI Tj TJ ' "`) via `process_operator` + `_restore_knockout_snapshot`, with a depth counter (`_knockout_form_depth`) bumped in `_process_form_bytes` so nested Form-XObject paints don't trigger the reset. All 16 PDF 32000-1 §11.3.5 separable + non-separable HSL blend modes are wired through `_blend` for §11.4.7.4 group compositing — separable Multiply/Screen/Darken/Lighten/Difference via `ImageChops`, Overlay/ColorDodge/ColorBurn/HardLight/SoftLight/Exclusion via per-pixel `_blend_scalar`, non-separable Hue/Saturation/Color/Luminosity via `_blend_hue` / `_blend_saturation` / `_blend_color` / `_blend_luminosity` using the §11.3.5.3 `Lum` / `Sat` / `SetLum` / `SetSat` / `ClipColor` helpers. The DEFERRED entry "Currently falls back to isolated non-knockout; only a subset of blend modes are implemented" was stale (knockout snapshot mechanism lands wave 31, soft-mask ExtGState wave 40, ColorDodge/ColorBurn §11.3.5.1 alignment wave 1363). Wave 1379 adds 9 structural verification tests at `tests/rendering/test_transparency_group_knockout_isolation_wave1379.py` pinning: three-overlapping-shapes knockout (isolated + non-isolated — only the last paint survives, earlier paints knocked back to the group-entry snapshot, exactly the synthetic test case from the wave 1379 brief), non-knockout layering contrast, parent-pixel preservation outside the group's painted region, isolated-group alpha channel, nested-form-XObject paints surviving the depth-counter guard, empty content-stream no-op, and `PDFRenderer.render_image` Pillow-image contract.
- **Agent E — `PDFAExtensionSchema` nested-struct typing + Splitter destination edge-case rewrites (two DEFERRED entries closed).** (1) `pypdfbox/xmpbox/pdfa_extension_schema.py`: typed nested-struct surface for the PDF/A Extension schema's `pdfaExtension:schemas` Bag — `add_schema_description(PDFASchemaType) -> "li"` writes through to both the typed mirror (`_typed_schemas`) and the existing lite `list[dict[str, str]]` so pre-1379 readers (`get_extension_schemas` / `get_count`) keep working; `get_schema_descriptions()` / `get_typed_schemas()` expose the typed Seq, `find_schema_by_namespace(uri)` / `find_schema_by_prefix(prefix)` provide O(n) lookup; `create_schema_type()` / `create_property_type()` / `create_value_type()` / `create_field_type()` are convenience constructors bound to the schema's owning metadata. The pre-existing `PDFASchemaType` / `PDFAPropertyType` / `PDFATypeType` / `PDFAFieldType` typed wrappers (already shipped in `pypdfbox/xmpbox/type/`) now have a first-class entry-point on the parent schema, closing the round-trip for nested `pdfaSchema:property` Seq + `pdfaSchema:valueType` Seq (with `pdfaType:field` sub-structures). (2) `pypdfbox/multipdf/splitter.py`: opt-in cross-chunk destination resolver via `set_cross_chunk_destination_resolver(callable)` — the callable receives the source target page COSDictionary and may return `None` (keep historical null-out), a plain `str` filename (`/D[0]` becomes integer 0), or a `(filename, page_index)` tuple. `fix_destinations` calls the resolver only for cross-chunk targets; when it opts in, the cloned destination's `[0]` page slot is replaced by the integer page index and the hosting link annotation's `/A` is rewritten to a fresh `PDActionRemoteGoTo` carrying the resolved filename + the original fit-type name + coordinate slots (XYZ / Fit / FitH / FitV / FitR / FitB / FitBH / FitBV all round-trip verbatim). The legacy `/Dest` is stripped after the rewrite so viewers don't pick the stale array. Resolver exceptions are caught and fall back to null-out; unsupported return types log a warning and null-out. Per-chunk state piggybacks on a new `_dest_to_link_map: dict[int(cloned_array_id), COSDictionary(link)]` populated by `_stage_link_destination` so the legacy 3-tuple `_dest_to_fix` shape (and the pre-wave-1294 2-tuple fallback) stay wire-compatible. Anchored by 14 hand-written tests at `tests/xmpbox/test_pdfa_extension_typed_wave1379.py` + 27 hand-written tests at `tests/multipdf/test_splitter_dest_edges_wave1379.py` (8 parametrised per-fit-mode in-chunk preservation tests + 6 parametrised cross-chunk fit-mode null-out tests + GoToR / GoToE pass-through + resolver setter contract + tuple / string / None / invalid-type / invalid-tuple-length / exception fallback paths + per-page-dict dispatch + in-chunk resolver short-circuit).
- **Agent B — Per-glyph PANOSE byte category accessors + per-subtype markup annotation accessors (two DEFERRED entries closed).** (1) `pypdfbox/pdmodel/font/pd_font_descriptor.py::PDPanoseClassification` already shipped the 10 per-byte read accessors (`get_family_kind` / `get_serif_style` / `get_weight` / `get_proportion` / `get_contrast` / `get_stroke_variation` / `get_arm_style` / `get_letterform` / `get_midline` / `get_x_height`, wave 41+). Wave 1379 closes the asymmetry by adding matched setters (`set_family_kind` … `set_x_height`), a generic `get_byte(index)` / `set_byte(index, value)` pair, the universal `ANY` / `NO_FIT` constants, plus the full set of named sub-classification constants for every category — `SERIF_STYLE_COVE` … `SERIF_STYLE_ROUNDED` (bytes 2-15), `WEIGHT_VERY_LIGHT` … `WEIGHT_NORD`, `PROPORTION_OLD_STYLE` … `PROPORTION_MONOSPACED`, `CONTRAST_NONE` … `CONTRAST_VERY_HIGH`, `STROKE_VARIATION_*` (9 buckets), `ARM_STYLE_*` (10 buckets), `LETTERFORM_*` (14 buckets), `MIDLINE_*` (12 buckets), `X_HEIGHT_*` (6 buckets), matching the OS/2 PANOSE 2.0 specification. Setter range check accepts signed `-128..127` and unsigned `128..255` (Java byte parity), pads short buffers up to the required index, mutates the wrapper in place. Anchored by 48 hand-written tests at `tests/pdmodel/font/test_pd_panose_wave1379.py`. (2) `pypdfbox/pdmodel/interactive/annotation/pd_annotation_markup.py` already shipped `/Popup`, `/RC`, `/BS`, `/ExData`; wave 1379 adds the missing `/IC` (interior color, 1/3/4-component float list — DeviceGray / DeviceRGB / DeviceCMYK) and `/Measure` (typed `PDMeasureDictionary`) accessors at the markup base so read-only callers traversing mixed annotation trees no longer have to downcast, plus explicit `remove_*` helpers for `/Popup` / `/RC` / `/BS` / `/IC` / `/Measure` and `has_border_style` / `has_interior_color` / `has_measure` presence predicates. Concrete subtypes (Line / Polyline / Polygon / SquareCircle / FreeText) retain their typed overrides — base accessors don't shadow them. Anchored by 20 hand-written tests at `tests/pdmodel/interactive/annotation/test_pd_annotation_markup_wave1379.py`. Net: 68 new tests, zero failures, both DEFERRED entries closed.

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
