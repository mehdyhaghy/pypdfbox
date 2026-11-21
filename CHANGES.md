# CHANGES

How pypdfbox behaves differently from upstream Apache PDFBox, and what changed
in each release since 1.0.0. Routine camelCase to snake_case renames are not
listed.

## Format

- A behavior change goes under **Unreleased** in the release log as one
  bullet. If it leaves pypdfbox behaving differently from PDFBox 3.0.8, also
  add or update a one-line entry in **Active divergences**.
- Per-file porting attribution is in [`PROVENANCE.md`](PROVENANCE.md).

## Project-wide deviations vs upstream

- **No `preflight` module.** Apache PDFBox 4.0 removes Preflight; we follow that decision. PDF/A and PDF/UA validation is out of scope; users can plug in any external validator they choose. The pypdfbox repo intentionally has no dependency on, nor scaffolding for, any specific validator (GPL-licensed tools in particular are not used, per the project's forbidden-license list).
- **No commons-logging / log4j.** Python `logging` (stdlib) is used throughout.
- **Method naming.** Java camelCase → Python snake_case across the entire API surface. Semantics unchanged.
- **Upstream baseline.** Apache PDFBox 3.0.8, the latest release, plus settled fixes from the unreleased 3.0.9.

## Active divergences vs upstream

The baseline is Apache PDFBox 3.0.8 (also the oracle jar). This section lists only behavior that differs from it today. Fixes that brought pypdfbox to parity are in the release log below.

### Forward-ports from the unreleased PDFBox 3.0.9

These match the upstream 3.0 branch, so they differ from the 3.0.8 baseline and oracle jar.

- **Filters and functions.** PDFBOX-6330 (ASCII85 and ASCIIHex skip all PDF whitespace, including inside a hex pair), 6317 (`ASCII85InputStream` uses the filter's decoder; a missing `~>` ends the last group), 6304 (predictor rejects a non-positive row length), 6331 (type 4 integer `not`, `roll` modulo n, Java-style `eq`/`ne`), 6320 (malformed type 4 programs raise `OSError`), 6332, 6333 (type 0 and type 3 bounds checks).
- **Parsing and COS.** PDFBOX-6167 (an escaped `\)` in a literal string is always a literal `)`), 6200 (`COSUpdateState` links substructures iteratively), 6286 (`PDPageTree.get()` clears its visited set on every error path).
- **Fonts.** PDFBOX-3293 (TrueType hinting, off by default: `PDFRenderer.set_hinting_enabled`, `-hinting`), 6287 and follow-ups (shared encode and string-width caches on `PDFont`, per-code `PDCIDFont` width cache, one-byte default `read_code`), 6249 (CID substitution accepts Identity-ordered fonts such as Noto Sans CJK, prefers regular weight, masks bad Noto code page bits), 6251, 5953, 6292, 6293 (non-embedded CIDFontType2 substitute handling, `is_encoded_via_substitute`), 5960 (TrueType with both Symbolic and NonSymbolic flags maps by glyph name first), 6319 (malformed `/W` and `/W2` arrays warn and skip like upstream), 6288 and 5384 (non-embedded Identity CIDFontType2 uses CID as GID when the substitute is the same font), 6322 (underscore ligature glyph names such as `f_f_i` map to their parts), 6308 (charstring subroutine limits: 106 nesting levels for Type 1, 150 calls per glyph for Type 2), 6297 (cmap formats 8, 12, 13 skip unsorted groups and cap the group count), 6324 (`CFFParser.concatenate_matrix` uses `b1*d2`).
- **Rendering and color.** PDFBOX-6315 (cyclic optional-content `/VE` expressions are detected and evaluated as upstream), PDFBOX-5250 (patterns in a transparency group anchored to the group's space), 6077 (pattern-filled stencil masks paint the pattern and keep gaps transparent), 5074 (DeviceN falls back to the tint transform when a colorant is not white at zero tint), 5079 (CalRGB skips calibration only near D65), 6260 (Bradford adaptation of CIE whitepoints; CalGray always calibrates), 6258, 6264 (`PDColorSpace.clamp()`, cached Lab ranges, shadings clamp through their color space).
- **Encryption and XMP.** PDFBOX-6329 (missing `/U` or `/O` raises `OSError`), 6316 (key length below 40 bits rejected; V=1 always 40 bits), 6313 (`PDEncryption.has_security_handler` no longer inverted), 6314 (SaslPrep accepts astral-plane characters), 6334 (malformed `<?xpacket end ...?>` rejected).
- **Document model and signing.** PDFBOX-6307 (`PDVisibleSignDesigner.use_user_space_coordinates`), PDFBOX-6318 (page-tree `/Count` updates reach every ancestor and stop on cycles), 6170 (`PDDocument.add_font_for_subsetting`), 6270, 6271 (wrapping a parsed widget or XObject no longer marks it dirty), 6274, 6275 (`get_tree_as_map()` on name and number trees), 6221 (visible-signature AcroForm `/DA` is `/Helv 0 Tf 0 g`), 6289 (`CreateSignature.sign_detached` takes a password), 6291 (hardened `SigUtils.open_url`).
- **Text extraction.** PDFBOX-6281 (`/ActualText` replacement is kept as written, not bidi-reordered or normalized; `TextPosition.is_from_actual_text()`), 6310, 6311 (only the outermost `/ActualText` applies; nested marked content does not end it), 6338 (marked content left open is reset at each page), 6303 (`PDMarkedContent.get_struct_parent()`, set from the page or form `/StructParents`).
- **Merging.** PDFBOX-6301 (structure-tree merge offsets `/StructParent(s)` on image and form XObjects and maps `/ParentTree` references to the copies), 6276 (`merge_mark_info` OR-folds the flags), 6277, 6296, 6300 (page labels merged through `PDPageLabels`, seeded decimal page-0 range, flat `/Nums`), 6299 (merger review fixes: destination check first, highest source version in optimized mode, `/Lang` and `/ViewerPreferences` always merged).
- **Splitting.** PDFBOX-6283 and follow-ups (named destinations kept, `/Dests` rebuilt per document, per-chunk `/IDTree` and `/RoleMap`, end page validated in `split()`, documents closed on failure).

### PDFBox 4.0 (trunk) alignment on this branch

- **Stateless `PDCIDFont` (PDFBOX-6175, trunk).** `PDCIDFont` no longer subclasses `PDFont` or keeps a parent; per-glyph descendant methods take the parent `PDType0Font` as a final argument, and the resource cache shares CIDFonts and font descriptors. Deviations from trunk: no per-code width memo on the shared descendant, the descriptor wrapper is built per call without a cache, the descendant is created lazily (malformed `/DescendantFonts` gives `None`), and its width setters do not clear a parent's string-width cache.
- **Compact `/W2` ranges (trunk `bcf78963`).** Range entries are kept as range records; individual entries win over ranges. New `PDCIDFont.get_vertical_displacement_ranges()`.

### Parsing and I/O

- **Loading without a password.** The empty password is tried, as upstream does; when it is rejected, pypdfbox 2.x returns the still-encrypted document with a `DeprecationWarning` instead of raising `InvalidPasswordException` (3.0 will raise).
- **No eager `initialParse`.** Objects load lazily, so a `/Root` or `/Pages` object missing from the xref is added to `get_xref_table()` on first resolve, not at load. A missing or dangling `/Root` opens with an empty synthesized catalog (0 pages) where upstream throws, and a trailer without `/Root` keeps pypdfbox's located-entries repair instead of a full rebuild.
- **Malformed xref stream is not rebuilt.** A located but malformed xref stream raises its structural error; upstream falls back to a brute-force rebuild. Unlocatable xrefs are still rebuilt.
- **Object-stream edge cases.** A `/First` smaller than the real header parses the member at the literal offset (upstream skips forward), and a truncated member resolves to null instead of a partial dictionary.
- **Malformed numbers and containers.** About eight malformed multi-dot or sign-only numbers and partial container or string framings recover to different values than upstream. Integer literals longer than `sys.get_int_max_str_digits()` raise `PDFParseError` (CPython DoS guard, no Java analogue).
- **UTF-8 BOM text strings.** `COSString.get_string` decodes a `EF BB BF` prefix as UTF-8 (PDF 2.0 and PDFBox 4.0 behavior); 3.0.8 decodes those bytes as PDFDocEncoding.
- **Predefined CMap lookup is exact-case and confined to the resources folder.** Matches the case-sensitive jar classpath on case-insensitive macOS and Windows file systems and rejects path traversal in `usecmap`.
- **Random-access buffers use one cursor.** Upstream's relative-put after absolute-get quirk in `RandomAccessReadWriteBuffer` is not reproduced; no real writer uses that interleave.
- **Filter library gaps.** DCT goes through imagecodecs/libjpeg-turbo, which pads a forged oversize SOF where Java ImageIO throws; CCITT goes through libtiff, which differs past end of data and for negative `/Columns`; an empty CCITT inline image zero-fills where upstream throws.

### COS and writing

- **`COSObject` equality is by `(object number, generation)`.** Upstream uses Java identity; pypdfbox pools one `COSObject` per key, so resolution results are unchanged.
- **Deep nesting on save.** Past 64 levels `COSWriter` switches to an explicit-stack walk with identical bytes, because Python's recursion limit is far below the Java stack.
- **Re-save object numbering.** A full save of a loaded document can compact and reuse object keys where upstream mints new numbers from the loaded `/Size`, so the trailer `/Size` can differ; the saved objects are the same.
- **Extra container accessors.** `COSArray.get_float` and `get_boolean(index)` are pypdfbox additions.

### Encryption and signing

- **Malformed `/Encrypt` fails closed.** A bad `/Perms` gives a clean `InvalidPasswordException` (or warns and opens after a valid password for an absent or short `/Perms`), and a `/UE`, `/OE` or `/Perms` that is not a multiple of 16 bytes is tolerated, where upstream throws. `/Length 0` falls back to the default key length with a `DeprecationWarning` (upstream rejects it; 3.0 will raise). An unknown `/V` is rejected up front. R6 with a too-short `/O` or `/U` is sliced leniently, and `PDEncryption.get_recipients_length` returns 0 where upstream throws.
- **No `/Filter` handler on load.** `PDEncryption(dict)` does not install a handler through `SecurityHandlerFactory`, so `has_security_handler()` is False on a loaded document where upstream 3.0.9 returns True.
- **`OcspHelper` is stricter.** It enforces RFC 6960 responder authorization (issued by the CA, `id-kp-OCSPSigning` EKU) and CertID matching, which upstream only logs or skips; it rejects non-http(s) URLs and RSASSA-PSS responses, treats a `None` sign date as now, and `perform_request` returns raw DER.
- **Redirects in signature examples.** `SigUtils.open_url` and `OcspHelper` follow only the upstream http to https same-URL redirect; other 3xx responses fail, since urllib has no safe equivalent of Java's same-protocol redirect policy. One timeout covers connect and read.

### Fonts

- **Unencodable text is substituted, not rejected (permanent, user decision).** `PDFont.encode` writes `?` (simple fonts) or CID 0 (`.notdef`, Type 0) and `get_string_width` returns a number where upstream throws `IllegalArgumentException`; the Type 0 GSUB path logs a warning instead of `IllegalStateException`. These lenient `.notdef` results are not cached. `TextToPDF` inherits the substitution.
- **`show_text` input superset.** `show_text` and `show_text_with_positioning` also accept pre-encoded `bytes` (written as-is, no subset tracking), and positioning arrays accept `int` adjustments.
- **Bundled substitutes are Arimo, Tinos and Cousine (Apache 2.0) instead of Liberation (OFL 1.1).** Same metrics and ASCII widths, but PostScript names differ (`Arimo-Regular`) and about 30 non-ASCII code points Liberation covered render as `.notdef`.
- **No system CID font scanner.** The default `FontMapper` has no on-disk CID scanner, so a non-embedded CID font falls back to the bundled last-resort font instead of a host font. `get_true_type_font()` and `get_cff_font()` still return only the embedded program, a bare descendant without a parent Type 0 font gets no substitute, and `PDCIDFontType0.get_height` takes a CID.
- **`PDType1Font.get_width_from_font` uses the bundled AFM for non-embedded fonts.** Upstream reads the host substitute program (for example 666.99 for `A`); pypdfbox returns the AFM integer (667), or 0 when the AFM lacks the glyph. Host-dependent substitute loading stays in the renderer.
- **`Standard14Fonts` name lookup is a case-insensitive superset.** It accepts 21 extra aliases (`TimesNewRomanPS*`, `Arial-Bold`, `-MT` forms); every name upstream knows maps to the same font.
- **fontTools-backed parsing (library-first).** GSUB is decoded by fontTools (single-substitution formats folded, no byte-offset sanity checks); glyph names come from fontTools instead of `GID+N`; `glyf`, Type 1 and Type 2 charstrings are decoded strictly where FontBox zero-pads or tolerates (minor flex and endchar geometry differences); a DSIG-shifted TTC header is tolerated where FontBox throws; an over-long `name` string is skipped. `TTFSubsetter` drops out-of-range glyph ids instead of throwing.
- **Lenient font construction.** A Type 0 font with a missing or malformed `/DescendantFonts`, descendant `/Subtype` or `/Encoding` constructs with a null descendant or no CMap; malformed `/W2` or one-element `/DW2` contributes no vertical metrics; a garbage Type 3 char proc has width 0.0; `PDFontSetting.get_font_size` returns 0.0 for a short `/Font` array; CFF Format 0 FDSelect returns 0 for a negative GID; CID-keyed CFF synthesizes a name in `getNameForGID`; an AFM ligature without a trailing semicolon parses. Upstream throws in each case.
- **TrueType hinting adaptations.** 64-bit intermediates are exact Python ints (32-bit results still wrap); `HintingException` subclasses `RuntimeError` and is also raised where upstream hits `ArrayIndexOutOfBoundsException`; composite nesting is capped at 64 levels; glyph data fontTools cannot decode falls back to the raw outline.
- **Width cache reset.** The `PDCIDFont` width cache, and the parent Type 0 string-width cache, are cleared by pypdfbox's `set_w`, `set_dw`, `read_widths` and `clear_widths_cache` setters.

### Text extraction

- **`TextPosition.font_size` is the rendered (Y-scaled) size.** Upstream's `getFontSize()` is the raw `Tf` operand; pypdfbox keeps that in `tf_font_size`, and `get_font_size_in_pt()` matches upstream's X-scaled size.
- **`set_should_flip_axes` mode.** A pypdfbox-only stripper mode that regroups glyphs into runs with the old formatter; there is no upstream counterpart.
- **`PDFTextStripperByArea` leniency.** `get_text_for_region` of an unknown region returns `""` (upstream NPE), and a negative-size region rectangle is normalized.
- **Python string splitting.** `split_on_space("   ")` and `tokenize_on_space("   ")` return Python `re.split` shapes (`["", "", "", ""]`) rather than Java's trimmed results.

### Content streams and rendering

- **Unknown `/Usage` state names.** An unknown `/ViewState`, `/PrintState` or `/ExportState` name counts as not OFF, so the content stays visible; upstream throws.
- **No pixel-exact rendering parity.** Pillow plus a skia-backed rasterizer replaces Java2D, so anti-aliased edges differ and upstream TIFF/PNG reference comparisons are not ported; parity is checked structurally.
- **Explicit D65 color math instead of the JVM CMM.** CIE (CalGray, CalRGB, Lab) XYZ to sRGB uses the IEC 61966-2-1 D65 matrix and adapts whitepoints to D65 (upstream adapts to the D50 PCS of `java.awt`); DeviceCMYK, Separation and DeviceN also use deterministic math. Results can differ by tens of 8-bit levels.
- **Small compositing and resampling differences.** Multiply and ColorBurn over an opaque backdrop can differ by 1/255; stencil masks scale with nearest or bicubic resampling instead of Java's area averaging.
- **Permissive color-space factory.** `PDColorSpace.create` and `PDResources.get_color_space` return `None` (or construct lazily and fail on use) for malformed, unknown or null specs where upstream throws `IOException` or `MissingResourceException`; short names `G`, `RGB`, `CMYK` resolve in the bare factory; Separation and DeviceN validate the alternate and tint lazily; Lab and Cal spaces default short or non-numeric `/WhitePoint`, `/BlackPoint`, `/Gamma`, `/Range` instead of throwing; `PDPattern` reports 0 components instead of `UnsupportedOperationException`. DeviceN's PDFBOX-5074 check also accepts non-Separation colorant spaces.
- **Images tolerate a bad color space.** `PDImageXObject.get_color_space()` returns `None` for an absent or unknown `/ColorSpace` and accepts inline abbreviations on XObjects, so decoding degrades to a best-effort raster.
- **Lenient functions.** `PDFunction.create(None)` returns `None`; Type 4 parses its PostScript lazily at eval; Type 0 reads samples lazily (a huge `/Size` evaluates to 0.0 instead of exhausting memory) and rejects `/BitsPerSample` above 32; non-numeric arrays coerce to 0.0 through `to_float_array`; a missing `/Domain` counts as 0 inputs.
- **Shading and pattern accessors.** `PDShading.get_function()` returns the raw `COSArray` for an array `/Function` (upstream throws; use `get_functions_array()`); a tiling pattern with a short `/BBox` returns `None`, and `set_matrix(None)` clears the entry.
- **Engine defaults.** `PDFStreamEngine` processes color operators by default (upstream `false` outside a stream run), and `TD` sets the leading directly when no `TL` processor is registered.

### Document model and forms

- **Upstream bugs not reproduced.** `PDMarkInfo.set_suspect` writes the given value (upstream always writes false), and `PDWindowsLaunchParams.set_operation` writes `/O` (upstream writes `/D`, so its getter never sees the value).
- **`PDEmbeddedFile` checksum is `bytes`.** `get_check_sum` / `set_check_sum` use the binary MD5; the upstream string form is `get_check_sum_string` / `set_check_sum_string`. The `*_mac_resource_fork` stream helpers are additions.
- **Typed wrappers instead of raw maps.** `PDStructureTreeRoot.get_class_map()` returns a `PDStructureClassMap` or `None` (upstream: a never-null `Map`); `PDJavascriptNameTreeNode` values are the `/JS` source `str` rather than `PDActionJavaScript`; six extra name-tree subclasses (URLS, IDS, Pages, Templates, Renditions, AlternatePresentations) have no upstream class.
- **Annotation and field superset.** `create_annotation` returns typed classes for Movie, Screen, PrinterMark, Redact, Watermark, 3D and TrapNet (upstream `PDAnnotationUnknown`); a field with `/T` but no `/FT` becomes a `PDFieldStub` (upstream `null`); a name-valued choice `/V` is accepted; `get_field_flags` returns 0 for a non-integer `/Ff`, and `/Ff` is not narrowed to 32 bits.
- **Appearance generation.** A zero or negative `/DA` font size auto-sizes, colors are written as `g`/`rg`/`k` instead of `cs ... sc`, and Highlight appearances are inlined (`gs rg ... f`) rather than wrapped in a transparency-group XObject.
- **`PDAcroForm.flatten()` of all fields removes `/AcroForm` from the catalog.** Upstream keeps the (now empty) form dictionary and only drops `/XFA` and, without signatures, `/SigFlags`.
- **Tree leniency.** `PDNumberTreeNode.get_numbers` recurses through `/Kids` (upstream returns null on an intermediate node); kids missing `/Limits` and malformed `/Limits` fall through or return `None` where upstream stops or throws.
- **Page tree negative indexes.** `PDPageTree[-1]` and `PDDocument.get_page(-1)` count from the end; upstream throws.
- **Graceful `None` instead of exceptions.** Short destination arrays return `None` coordinates; `get_base_state()` tolerates an unknown `/BaseState` (`get_base_state_enum()` is the strict form); `get_output_intents` skips non-dictionary entries; FDF `/V` arrays containing names are coerced; attribute `get_headers` decodes the strings `set_headers` writes (upstream throws `ClassCastException`); `get_dests` on a catalog-less wrapper returns `None`; thread beads with null `/N` or `/V` return `None`, and `append_bead` repairs a missing `/N`; `PDSoftMask.get_group` accepts caller-built bare streams and dictionaries.
- **Enrichment getters with no upstream counterpart.** Viewer preferences `get_num_copies`, `get_print_page_range`, `get_enforce`, `PickTrayByPDFSize`; `/MK` `get_text_position`, `get_icon_fit` and `PDIconFit`; widget `get_parent()`; `PDOutputIntent.get_subtype` and the strict `get_dest_output_profile`.

### XMP

- **Subset parser without `TypeMapping`.** Unknown schemas and unknown properties are kept instead of raising `NoSchema` or `InvalidType`; values are not type-checked; duplicate properties are last-write-wins; the `<?xpacket?>` envelope (start and end) is optional; cardinality mismatches report different error types; a whitespace-only simple value reads back as `""`.

### Merging and splitting

- **Merge helpers kept.** `get_id_tree_as_map` and `get_number_tree_as_map` are kept although upstream removed them.
- **`Splitter` cross-chunk destinations.** `set_cross_chunk_destination_resolver` is an opt-in extension (off by default).

### Tools and examples

- **`PrintPDF` spooler path.** `-hinting` and `-subsampling` do not affect printing through the OS spooler, which sends the original file bytes.

### Platform and packaging

- **Python exceptions and messages.** Java exceptions map to Python ones (`IOException` to `OSError` or `PDFParseError`, `IllegalArgumentException` to `ValueError`, unsupported operations to `NotImplementedError`), and messages that embed a class name use the short Python name (`COSDictionary`, not `org.apache.pdfbox.cos.COSDictionary`).

## Release log

Changes since 1.0.0, the first release after the initial port. Newest first.
Full notes for each release are on
[GitHub Releases](https://github.com/mehdyhaghy/pypdfbox/releases); the
porting history before 1.0.0 is in git history.

### Unreleased (pypdfbox 3.0.0, on the `pdfbox-4.0` branch)

- **Breaking, PDFBox 4.0 alignment (PDFBOX-6175):** `PDCIDFont` is a stateless, shareable descendant. Removed `PDCIDFont.get_parent()`, `get_name()` (use `get_base_font()`) and the inherited `PDFont` methods; per-glyph methods (`code_to_cid`, `code_to_gid`, `get_width`, `get_path`, `has_glyph`, `encode`, ...) take the parent font as a final argument; constructors take `resource_cache` instead of a parent; `PDResourceCache` gains CIDFont and font-descriptor caching.
- **Breaking, upstream parity:** optimized-mode `PDFMergerUtility` copies only pages (crop box, media box, rotation and resources set on each page, highest source version) and no longer merges document information, metadata or the AcroForm, nor rejects dynamic XFA sources.
- **Breaking, upstream parity:** `Splitter.split()` raises when a chunk's structure-tree clone, destination fix-up or named-destination fix-up fails, after closing the documents it created; a malformed `/Names /Dests` tree aborts the split.
- `/W2` CID ranges are stored compactly (trunk `bcf78963`).
- `PDFTextStripper`: marked content nested inside an `/ActualText` span no longer ends the replacement, and a nested `/ActualText` is ignored (PDFBOX-6311).
- `PDFTextStripper` / `PDFTextStripperByArea`: marked content left unclosed on one page no longer replaces text on later pages or in the next document (PDFBOX-6338).
- `PDMarkedContent`: new `get_struct_parent()` / `set_struct_parent()` (default -1); `to_string()` appends `structParent`. `PDFMarkedContentExtractor` sets it from the page or form `/StructParents` (PDFBOX-6303).
- `PDCIDFont`: malformed `/W` and `/W2` width arrays no longer raise; a bad `/W2` triple stops the read and a bad `/W` range skips three entries, as upstream does (PDFBOX-6319).
- `PDCIDFontType2`: a non-embedded font with an Identity-ordered CMap and no `/CIDToGIDMap` stream uses the code as the GID when the substitute is the same font; names match when one is a prefix of the other, ignoring `,` and `-`. Both warnings are logged once (PDFBOX-6288, PDFBOX-5384).
- `GlyphList`: underscore ligature names such as `f_f_i` map to the Unicode of their parts, which improves text extraction (PDFBOX-6322).
- Type 1 and Type 2 charstring parsers raise `OSError` when subroutines nest more than 106 levels (Type 1) or a glyph makes more than 150 subroutine calls (Type 2), instead of recursing without end (PDFBOX-6308).
- cmap subtables in formats 8, 12 and 13 skip mapping groups not sorted by end code; formats 12 and 13 reject more than 0x10FFFF groups, and format 13 stops at a glyph id equal to the glyph count (PDFBOX-6297).
- `CFFParser.concatenate_matrix` computes the second matrix entry as `a1*b2 + b1*d2`, fixing skewed font matrices (PDFBOX-6324).
- `PDFMergerUtility`: merging with the structure tree offsets `/StructParent` on image XObjects and `/StructParents` on form XObjects (nested forms included) and maps `/ParentTree` object references to the merged copies; shared XObjects are offset once and self-referencing forms no longer recurse. Adds `COSName.STM` (PDFBOX-6301).
- `PDPageTree`: `add`, `remove` and inserts update every ancestor `/Count` and stop with a warning on a `/Parent` cycle (PDFBOX-6318). **Breaking, upstream parity:** removing an orphan page, or one whose parent has no `/Kids`, raises `ValueError` (upstream `IllegalArgumentException`).
- New `PDDocument.add_font_for_subsetting(font)`, which raises `ValueError` for a font that is not subset; content streams use it, and `get_fonts_to_subset` is deprecated as upstream (PDFBOX-6170).
- ASCII85 decoding (`ASCII85Decode` and `ASCII85InputStream`) skips all PDF whitespace (NUL, TAB, LF, FF, CR, SPACE); `ASCII85InputStream` now uses the filter's decoder instead of `base64.a85decode`, so a missing `~>` ends the last group (PDFBOX-6330, PDFBOX-6317).
- ASCIIHexDecode skips whitespace between the two hex digits of a byte (PDFBOX-6330).
- Predictor decoding rejects a zero or negative row length (for example `/Columns 0`) with `OSError` instead of hanging or returning empty output (PDFBOX-6304).
- Type 4 functions: integer `not` is a bitwise complement, `roll` reduces j modulo n, and `eq`/`ne` compare like Java `Double.compare` (PDFBOX-6331). Malformed programs always raise `OSError`, and NaN or infinite stack counts follow Java `intValue()` (PDFBOX-6320).
- Type 3 functions with at least as many `/Bounds` as `/Functions` raise `ValueError` up front instead of `IndexError` (PDFBOX-6332); type 0 functions with an odd-length `/Encode` or `/Decode` no longer raise `IndexError` (PDFBOX-6333).
- Rendering: a self-referencing optional content visibility expression (`/VE`) no longer recurses until `RecursionError`; the cycle is logged and evaluated as upstream. `/VE` evaluation now follows upstream `PageDrawer`: an empty `/VE` falls back to `/P` and `/OCGs`, unknown operators count as not hidden, and non-array, non-dictionary operands are skipped (PDFBOX-6315).
- `PDVisibleSignDesigner.use_user_space_coordinates(True)` treats `x_axis`/`y_axis` as the lower-left corner of the signature rectangle in page user space, without applying `/Rotate`. Off by default (PDFBOX-6307).
- Text extraction keeps `/ActualText` replacement text as written: it is no longer reordered as right-to-left text or decomposed from presentation forms, so Arabic text with digits no longer comes out as "7441" for "1447" (PDFBOX-6281).
- `TextPosition` gains `is_from_actual_text()` / `set_from_actual_text()`, true only for the glyph that carries an `/ActualText` replacement (PDFBOX-6281). The span-membership flag previously named `from_actual_text` is now `in_actual_text_span`.
- Encryption: a missing `/U` or `/O` raises `OSError` ("/Encrypt/U entry is missing") instead of `InvalidPasswordException` (PDFBOX-6329).
- Encryption: a key length from 1 to 39 bits raises `OSError("Invalid encryption dictionary length: N")` instead of a low-level `ValueError`, and V=1 always uses a 40-bit key whatever `/Length` says, so such files open with the right password (PDFBOX-6316). `/Length 0` still falls back to the default with a `DeprecationWarning`.
- `PDEncryption.has_security_handler()` returns True when a handler is installed; it was inverted (PDFBOX-6313).
- SaslPrep no longer rejects astral-plane password characters whose low 16 bits match a space or control character, such as U+12000 (PDFBOX-6314).
- XMP: a malformed `<?xpacket end ...?>` such as `<?xpacket end=?>` raises `XmpParsingException` (XpacketBadEnd) instead of being accepted; the "value 'r' or 'w'" message no longer ends with a space (PDFBOX-6334).
- Rendering: optional content groups honor their `/Usage` render state for the render destination (`/View /ViewState`, `/Print /PrintState`, falling back to `/Export /ExportState`); `OFF` hides and `ON` shows regardless of `/OCProperties`, which decides only when no usage state applies. This covers marked content, XObjects, annotations and OCMD members. As upstream, `get_default_destination()` is `None` until set (was `"View"`), `render_image` then uses EXPORT, and `render_page_to_graphics` uses VIEW and passes its destination through.
- Glyph outlines and widths built through fontTools enforce the same subroutine limits (Type 1: 106 nesting levels; Type 2: 150 calls per glyph): an over-limit glyph raises `OSError` from `get_path` / `get_width` / `get_width_from_font` as upstream does, and the renderer draws it empty. A composite (seac) Type 1 glyph skips an over-limit part with a warning (PDFBOX-6308).
- `PDFMarkedContentExtractor`: `Do` reports the XObject to `xobject()` and walks form XObjects and transparency groups, as upstream does.

### 2.5.0 (2026-10-31)

- **Merging:** page labels merge through `PDPageLabels` (`/Kids` trees kept,
  a label-less file gets default numbering); `/Lang` and
  `/ViewerPreferences` are merged for untagged files; destination checks
  and optimized-mode version follow upstream (PDFBOX-6296, 6300, 6299).
- **Splitting:** `split()` checks the page range (setters in any order),
  keeps ids and roles per output file, and closes created documents on
  failure (PDFBOX-6283).
- **Fonts:** non-embedded CIDFontType2 under Identity-H/V writes the
  substitute's glyph ids; substitute space width and Unicode glyph lookup
  for Identity-ordered substitutes (PDFBOX-6292, 6293); per-codepoint width
  cache (PDFBOX-6287).
- **Signing examples:** `SigUtils.open_url` is a hardened real port
  (PDFBOX-6291); invalid example signatures and the DocMDP crash are fixed;
  encrypted files can be signed (PDFBOX-6289).
- **Robustness:** the parser applies upstream's `MAX_RECURSION_DEPTH` (500)
  instead of leaking `RecursionError`; the writer handles deep direct
  nesting iteratively; an unreachable unclosed `COSDocument` is no longer
  closed by its finalizer; `PDFCloneUtility` keeps sources alive so ids are
  not reused.
- **Performance:** image sample decode 15 to 20 times faster, JBIG2 about
  5 times faster, CMap parsing 3.4 times faster, faster loads and
  object-stream saves; output byte-identical.
- fontTools 4.68.0 in the lock file.

### 2.4.0 (2026-10-24)

- **Python 3.15** supported alongside 3.14 (`skia-python>=144.1`).
- **Text extraction** works glyph by glyph with PDFBox's line, word,
  paragraph, duplicate and diacritic logic; output matches PDFBox 3.0.8.
- **`import_page`** makes a shallow copy like upstream; `Splitter` output
  matches PDFBox object for object.
- **Loading** an encrypted PDF without a password tries the empty password
  (`DeprecationWarning` when that fails; 3.0 will raise like PDFBox);
  owner-password-only files decrypt on load; RC4 keys of 48 to 120 bits
  work; damaged xref tables are repaired like upstream `checkXrefOffsets`.
- **Fixes:** `PDType1Font(Standard14Fonts.FontName...)`, UCS2 decoding for
  composite fonts without `/ToUnicode`, Helvetica fallback for missing
  fonts, blend modes over transparent backdrops, SASLprep on 3.15, lazy
  TrueType collection scanning.
- **Performance:** large files several times faster (for example text
  extraction of the ISO 32000 spec 29.4 s to 9.8 s).

### 2.3.1 (2026-10-19)

- Pages of a loaded document share the document's resource cache, as
  upstream does.
- Only final `vMAJOR.MINOR.PATCH` tags publish to PyPI.

### 2.3.0 (2026-10-19)

- **`show_text` encodes through the font** (fixes embedded Type 0 and
  TrueType text), fonts are subset on save, and GSUB substitutions work.
- **Rendering:** embedded Type 0 fonts about 65 times faster; opt-in
  TrueType hinting (PDFBOX-3293).
- **3.0.9 forward-ports:** PDFBOX-6283 (named destinations in split
  output), 6286, 6200, 6287.
- Locked Pillow 13.0.0, fontTools 4.67.0, numpy 2.5.4.

### 2.2.0 (2026-10-10)

- **3.0.9 forward-ports:** parsing and saving (PDFBOX-6167, 6270, 6271),
  merging and document model (6274, 6275, 6276, 6277, 6221), color (5074,
  5079, 6260 adapted to D65, 6258, 6264), fonts (5953, 6251, 5960, 6249
  unified CJK substitution), rendering (5250, 6077).
- Non-embedded `PDCIDFontType2` / `PDCIDFontType0` use font-mapper
  substitutes, as upstream always has.

### 2.1.0 (2026-10-09)

- Every shipped file is permissively licensed: bundled substitute fonts
  moved from Liberation (OFL) to Arimo, Tinos and Cousine (Apache-2.0);
  `License-Expression` covers APAFML and Bitstream-Vera / Arev.
- `OcspHelper` is a complete port (responder signature, lookup, nonce,
  freshness and chain checks; key-hash lookup fixed).

### 2.0.0 (2026-09-20)

- **Breaking:** Python 3.14 is the floor; first PDFBox 4.0 API removals
  (`PDIndexed` no-arg constructor and setters,
  `PDVisibleSigBuilder.append_raw_commands`); the PDFBOX-6175
  CIDFont/FontDescriptor caching that upstream reverted is backed out.
- **Behavior:** `Overlay` centring (PDFBOX-6048), `usecmap` parent lookup,
  Type 1 `rmoveto` operands, positional `/Headers` arrays,
  `show_text_with_positioning` checks.
- **Security floors:** `cryptography>=50`, `Pillow>=12.3.0`.
- Pluggable glyph layout (PDFBOX-4951); 3.0.8 and 3.0.9 forward-ports
  (PDFBOX-6145, 6227 to 6229, 6231, 6236, 6242, 6243, 6251, 6255, 6257,
  6261, 6265 to 6267); subsampled JBIG2 rasters keep their last row and
  column; the oracle runs against PDFBox 3.0.8.

### 1.0.0 (2026-07-20)

- First stable release: full method-surface parity with PDFBox 3.0.x,
  oracle-verified; 3.0.8 forward-ports (PDFBOX-6150, 6173, 6176, 6185,
  6189, 6203, 6206, 6207, 6210, 6216); rendering about 5.4 times faster.

## See also

- [`PROVENANCE.md`](PROVENANCE.md): per-file upstream porting provenance (Apache 2.0 §4(b)).
- [GitHub Releases](https://github.com/mehdyhaghy/pypdfbox/releases): full notes for each release.
