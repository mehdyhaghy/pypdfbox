from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)

_CID_FONT_TYPE0C: str = "CIDFontType0C"
_OPEN_TYPE: str = "OpenType"

# CFF defaults to a 1000-unit em (font matrix [0.001 0 0 0.001 0 0]).
_CFF_DEFAULT_UNITS_PER_EM: int = 1000
_CFF_DEFAULT_FONT_MATRIX: tuple[float, float, float, float, float, float] = (
    0.001,
    0.0,
    0.0,
    0.001,
    0.0,
    0.0,
)


def _uni_name_of_code_point(code_point: int) -> str:
    """Synthesise the ``uniXXXX`` glyph name for ``code_point``.

    Mirrors upstream ``UniUtil.getUniNameOfCodePoint`` — uppercase hex,
    minimum width four. Inlined here (rather than imported from the
    sibling ``pd_true_type_font`` module) to keep the dependency graph
    flat between ``PDCIDFontType0`` and ``PDTrueTypeFont``.
    """
    hex_str = format(code_point, "X")
    if len(hex_str) < 4:
        hex_str = hex_str.rjust(4, "0")
    return "uni" + hex_str


class PDCIDFontType0(PDCIDFont):
    """CIDFontType0 — CFF-based CIDFont. Mirrors PDFBox ``PDCIDFontType0``.

    The descendant of a composite ``PDType0Font`` whose embedded font
    program is a Compact Font Format (CFF) stream marked
    ``/Subtype /CIDFontType0C`` (or, less commonly, ``/OpenType`` with a
    CFF table) on the descriptor's ``/FontFile3``.

    Glyph metric / outline access goes through the same
    :class:`CFFFont` primitive as :class:`PDType1CFont`, but indexed by
    CID rather than by glyph name. CID-keyed CFF fonts use a charset
    that maps CIDs directly into the CharStrings INDEX — fontTools
    surfaces CharString entries keyed by ``"cid12345"`` zero-padded
    names. We reuse :class:`CFFFont` for parsing and width extraction
    and translate ``cid -> "cidNNNNN"`` ourselves.
    """

    SUB_TYPE = "CIDFontType0"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)
        # Lazily-loaded embedded CFF program. ``None`` = not yet
        # attempted; ``False`` = tried, no /FontFile3 or parse failed.
        self._cff: CFFFont | None | bool = None
        # Per-CID glyph-height cache (computed from CFF outlines on
        # demand, mirroring PDFBox's ``glyphHeights`` map).
        self._glyph_heights: dict[int, float] = {}
        # Lazily-computed font bounding box (mirrors upstream's
        # ``fontBBox`` instance field; resolved by
        # :meth:`generate_bounding_box`).
        self._font_bbox: PDRectangle | None = None

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE

    # ---------- code -> CID ----------

    def code_to_cid(self, code: int) -> int:  # type: ignore[override]
        """For CID-keyed CFF fonts the "code" arriving at this layer is
        already the CID (the parent :class:`PDType0Font`'s ``/Encoding``
        CMap performed ``code -> CID`` upstream). Identity mapping here
        mirrors upstream ``PDCIDFontType0.codeToCID``.
        """
        return int(code)

    # ---------- code -> GID ----------

    def code_to_gid(self, code: int) -> int:
        """Resolve a character code (already CMap-decoded into a CID by
        the parent :class:`PDType0Font`) to a CFF glyph index (GID).

        Mirrors upstream ``PDCIDFontType0.codeToGID``:

        * For a CIDKeyed CFF program we look up ``cidNNNNN`` in the
          charset (which lists glyph names in CharStrings order, so
          index = GID).
        * For a name-keyed (Type 1-flavoured) CFF embedded under a
          CIDFontType0 wrapper, the CID is treated as a GID directly.
        * When the font has no embedded program, the CID is the GID —
          matches the renderer-fallback path PDFBox follows.
        """
        program = self.get_cff_font()
        if program is None:
            return int(code)
        cid = self.code_to_cid(code)
        if isinstance(program, CFFCIDFont):
            target = self._cff_glyph_name(cid)
            charset = program.get_charset()
            if not charset:
                return 0
            try:
                return charset.index(target)
            except ValueError:
                return 0
        # Name-keyed CFF: CID is GID.
        return int(cid)

    # ---------- /FontFile3 + /Subtype /CIDFontType0C wiring ----------

    def is_embedded(self) -> bool:  # type: ignore[override]
        """``True`` when the descriptor carries an embedded font program.

        Returns ``True`` when any of ``/FontFile``, ``/FontFile2``, or
        ``/FontFile3`` is present — matching :meth:`PDCIDFont.is_embedded`
        for descriptor-level liveness — *or* when a ``/FontFile3`` with
        ``/Subtype /CIDFontType0C`` (or ``/OpenType``) is present, which
        is the canonical embedded form for a CIDFontType0 per
        PDF 32000-1 §9.6.2.2 and §9.7.4.2. The combined check keeps
        legacy descriptor inputs working while still surfacing the
        CID-keyed CFF case explicitly through :meth:`is_cff_embedded`.
        """
        if super().is_embedded():
            return True
        return self.is_cff_embedded()

    def is_cff_embedded(self) -> bool:
        """``True`` when the descriptor carries a ``/FontFile3`` whose
        own ``/Subtype`` is ``/CIDFontType0C`` (or ``/OpenType``).

        This is the strict upstream ``PDCIDFontType0.isEmbedded`` form —
        a CFF-program-backed CIDFontType0 program lives only in
        ``/FontFile3`` with the correct subtype. Exposed separately so
        callers that need the strict check (renderer / metrics paths)
        can ask for it without losing the legacy descriptor liveness
        signal carried by :meth:`is_embedded`.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            return False
        subtype = font_file3.get_cos_object().get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        return subtype in (_CID_FONT_TYPE0C, _OPEN_TYPE)

    def is_damaged(self) -> bool:
        """``True`` when the embedded ``/FontFile3`` stream failed to
        parse. Mirrors upstream ``PDCIDFontType0.isDamaged``. Returns
        ``False`` when the font is not embedded (nothing to parse) or
        when parsing succeeded.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None or descriptor.get_font_file3() is None:
            return False
        # Force the lazy parse.
        self.get_cff_font()
        return self._cff is False

    def get_cff_font(self) -> CFFFont | None:
        """Return the parsed CFF program for this font's
        ``/FontFile3`` stream, or ``None`` if the font is not embedded
        or the stream cannot be parsed. Result is cached on the
        instance.

        Mirrors upstream ``PDCIDFontType0.getCFFFont`` whose return type
        is the polymorphic ``CFFFont`` — the concrete instance will be
        a :class:`CFFCIDFont` (the spec-blessed CIDFontType0C form) or
        a :class:`CFFType1Font` (a name-keyed CFF embedded under a
        CIDFontType0 wrapper, which PDFBox tolerates for malformed
        producers). Callers that need to distinguish should ``isinstance``
        check.
        """
        if self._cff is not None:
            return self._cff if isinstance(self._cff, CFFFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._cff = False
            return None
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            self._cff = False
            return None
        try:
            raw = font_file3.to_byte_array()
            base = CFFFont.from_bytes(raw)
            # Specialise into CFFCIDFont / CFFType1Font so callers can
            # rely on isinstance checks matching upstream's polymorphic
            # return.
            if base.is_cid_font():
                self._cff = CFFCIDFont.from_cff_font(base)
            else:
                self._cff = CFFType1Font.from_cff_font(base)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile3 for %s", self.get_name())
            self._cff = False
            return None
        return self._cff

    def set_cff_font(self, font: CFFFont | None) -> None:
        """Inject a pre-parsed :class:`CFFFont`. Mirrors the equivalent
        injector on :class:`PDType1CFont` — lets callers that already
        have the font program in hand bypass ``/FontFile3`` parsing,
        and lets tests skip the byte-level fixture round-trip.
        """
        self._cff = font if font is not None else False
        # Reset derived caches.
        self._glyph_heights.clear()
        self._font_bbox = None

    # ---------- glyph widths ----------

    def _cff_glyph_name(self, cid: int) -> str:
        """fontTools surfaces CID-keyed CFF charstrings under the name
        ``"cidNNNNN"`` (5-digit zero-padded). The ``.notdef`` glyph is
        always CID 0.
        """
        if cid == 0:
            return ".notdef"
        return f"cid{cid:05d}"

    def _cff_program_width(self, cid: int) -> float | None:
        """Width contributed by the embedded CFF program for ``cid``.
        Returns ``None`` when there is no program, the CID is unmapped,
        or the program reports a zero advance. Width is normalized to
        1/1000 em (the PDF width unit) regardless of the program's
        native units-per-em.
        """
        program = self.get_cff_font()
        if program is None:
            return None
        name = self._cff_glyph_name(cid)
        if not program.has_glyph(name):
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        advance = program.get_width(name)
        if advance <= 0.0:
            return None
        return advance * 1000.0 / units_per_em

    def get_glyph_width(self, cid: int) -> float:  # type: ignore[override]
        """Width of ``cid`` in 1/1000 em.

        Resolution order, mirroring upstream ``PDCIDFontType0``:

        1. ``/W`` (per-CID widths, parsed by :class:`PDCIDFont`).
        2. Embedded CFF program width when available.
        3. ``/DW`` default (defaults to 1000 per spec).
        """
        widths = self.get_widths()
        explicit = widths.get(cid)
        if explicit is not None:
            return explicit
        program_width = self._cff_program_width(cid)
        if program_width is not None:
            return program_width
        return self.get_default_width()

    def get_width_from_font(self, cid: int) -> float:
        """Width of ``cid`` taken *only* from the embedded font program
        (in 1/1000 em). Returns ``0.0`` when the font has no embedded
        CFF program or the CID is unmapped.

        Mirrors upstream ``PDCIDFontType0.getWidthFromFont`` — the
        renderer uses this for scale-correction when ``/W`` is missing
        but a font program is embedded. Distinct from
        :meth:`get_glyph_width` which prefers ``/W`` first.
        """
        program_width = self._cff_program_width(cid)
        return program_width if program_width is not None else 0.0

    def get_average_font_width(self) -> float:  # type: ignore[override]
        """Mean glyph advance for this CID font in 1/1000 em.

        Mirrors upstream ``PDCIDFontType0.getAverageFontWidth`` — routes
        resolution through :meth:`get_average_character_width`. Upstream
        caches the result once, but the Python port honours subsequent
        ``/DW`` setter calls (the underlying cache is reset by the
        :meth:`set_cff_font` injector and otherwise recomputed cheaply).
        """
        return self.get_average_character_width()

    def get_average_character_width(self) -> float:
        """Resolve the mean character advance from the available metadata.

        Mirrors upstream private
        ``PDCIDFontType0.getAverageCharacterWidth``. Resolution order:

        1. Mean of positive entries in ``/W``.
        2. CFF Private DICT ``defaultWidthX`` when an embedded CFF
           program is present (CFF spec §10).
        3. ``/DW`` default (1000 per spec) — falls through to the
           hardcoded ``500`` upstream sentinel only when ``/DW`` is the
           explicit zero a damaged font sometimes reports.

        Exposed under the upstream name (without an underscore prefix)
        because PDFBox treats it as a protected method; keeping the same
        surface helps ports of upstream callers find what they expect.
        We deliberately diverge from upstream's ``PDCIDFontType0`` (which
        plumbs through to ``PDCIDFont.getAverageFontWidth``) by promoting
        the CFF default width: it is information actually present in the
        embedded program and yields a far better answer than the spec's
        1000-unit default for non-Western non-Latin fonts.
        """
        widths = self.get_widths()
        positive = [w for w in widths.values() if w > 0.0]
        if positive:
            return sum(positive) / len(positive)
        program = self.get_cff_font()
        if program is not None:
            default = program.get_default_width_x()
            if default > 0.0:
                upem = program.units_per_em
                if upem > 0:
                    return default * 1000.0 / upem
        dw = float(self.get_default_width())
        # Upstream's ``getAverageCharacterWidth`` hardcodes ``500`` as
        # the last-resort sentinel ("highly suspect" per the upstream
        # comment). Surface that only when /DW is itself a useless zero.
        return dw if dw > 0.0 else 500.0

    def get_height(self, cid: int) -> float:  # type: ignore[override]
        """Height of the glyph at ``cid`` in *font units*.

        Mirrors upstream ``PDCIDFontType0.getHeight(int code)`` — derived
        from the CFF outline's bounding box (max-y minus min-y) when an
        embedded CFF program is available. Falls back to the parent
        :meth:`PDCIDFont.get_height` (which reads ``/W2``) when no
        program is present.

        Result is cached per-CID.
        """
        program = self.get_cff_font()
        if program is None:
            return super().get_height(cid)
        cached = self._glyph_heights.get(cid)
        if cached is not None:
            return cached
        name = self._cff_glyph_name(cid)
        if not program.has_glyph(name):
            self._glyph_heights[cid] = 0.0
            return 0.0
        path = program.get_path(name)
        if not path:
            self._glyph_heights[cid] = 0.0
            return 0.0
        ys: list[float] = []
        for cmd in path:
            # Commands look like ("moveto", x, y), ("lineto", x, y),
            # ("curveto", x1, y1, x2, y2, x, y), ("closepath",). Skip
            # the closepath singleton; for everything else extract the
            # y coordinates (every odd-indexed numeric arg).
            if len(cmd) <= 1:
                continue
            for i in range(2, len(cmd), 2):
                ys.append(float(cmd[i]))
        height = (max(ys) - min(ys)) if ys else 0.0
        self._glyph_heights[cid] = height
        return height

    # ---------- font-level metrics ----------

    def get_font_matrix(self) -> tuple[float, float, float, float, float, float]:
        """Six-element font matrix.

        Mirrors upstream ``PDCIDFontType0.getFontMatrix``: when an
        embedded CFF program is present, return its ``FontMatrix``
        (CFF Top DICT, default ``[0.001 0 0 0.001 0 0]``); otherwise
        fall back to the CFF default. Returned as an immutable tuple to
        prevent accidental in-place mutation by callers.
        """
        program = self.get_cff_font()
        if program is None:
            return _CFF_DEFAULT_FONT_MATRIX
        try:
            matrix = program.font_matrix
        except Exception:  # noqa: BLE001
            return _CFF_DEFAULT_FONT_MATRIX
        if not matrix or len(matrix) < 6:
            return _CFF_DEFAULT_FONT_MATRIX
        return (
            float(matrix[0]),
            float(matrix[1]),
            float(matrix[2]),
            float(matrix[3]),
            float(matrix[4]),
            float(matrix[5]),
        )

    def get_bounding_box(self) -> PDRectangle | None:  # type: ignore[override]
        """Return the font's bounding box as a :class:`PDRectangle`.

        Mirrors upstream ``PDCIDFontType0.getBoundingBox`` — caches the
        result of :meth:`generate_bounding_box` on first call so repeated
        renderer queries hit a single resolution path. The cache is keyed
        only on the program's identity; callers that mutate the embedded
        CFF program via :meth:`set_cff_font` reset it implicitly.
        """
        if self._font_bbox is None:
            self._font_bbox = self.generate_bounding_box()
        return self._font_bbox

    def generate_bounding_box(self) -> PDRectangle | None:
        """Resolve the font's bounding box from the available metadata.

        Mirrors upstream private ``PDCIDFontType0.generateBoundingBox``:

        1. Prefer the descriptor's ``/FontBBox`` when at least one of its
           four corners is non-zero (an all-zero box is the spec-default
           sentinel and means "ask the font program instead").
        2. Otherwise read the embedded CFF program's Top DICT
           ``/FontBBox``.

        Exposed under the upstream name (without an underscore prefix)
        because PDFBox treats it as a protected method that subclasses
        and tooling can override; keeping the same surface here keeps
        ports of upstream callers honest. Returns ``None`` when neither
        source provides a usable box.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is not None:
            bbox = descriptor.get_font_b_box()
            if bbox is not None and bbox.size() >= 4:
                rect = super().get_bounding_box()
                if rect is not None and (
                    rect.get_lower_left_x() != 0.0
                    or rect.get_lower_left_y() != 0.0
                    or rect.get_upper_right_x() != 0.0
                    or rect.get_upper_right_y() != 0.0
                ):
                    return rect
        program = self.get_cff_font()
        if program is not None:
            cff_bbox = program.get_property("FontBBox")
            if cff_bbox is not None:
                rect = self._coerce_bbox(cff_bbox)
                if rect is not None:
                    return rect
        return super().get_bounding_box()

    @staticmethod
    def _coerce_bbox(value: object) -> PDRectangle | None:
        """Coerce a CFF Top DICT ``FontBBox`` value (a 4-element list of
        numbers as fontTools surfaces it) into a :class:`PDRectangle`.
        Returns ``None`` for malformed input rather than raising —
        matches the lenient upstream behaviour for damaged CFF programs.
        """
        if not isinstance(value, (list, tuple)) or len(value) < 4:
            return None
        try:
            llx, lly, urx, ury = (float(v) for v in value[:4])
        except (TypeError, ValueError):
            return None
        rect = PDRectangle()
        rect.set_lower_left_x(llx)
        rect.set_lower_left_y(lly)
        rect.set_upper_right_x(urx)
        rect.set_upper_right_y(ury)
        return rect

    # ---------- glyph paths ----------

    def get_glyph_path(self, cid: int) -> list[tuple]:
        """CFF outline for ``cid``, in font units. Returns ``[]`` when
        the font has no embedded CFF program or the CID is unmapped.

        For CID-keyed CFF the charset maps CIDs directly into the
        CharStrings INDEX; fontTools exposes those entries under
        ``"cidNNNNN"`` keys so we translate the CID accordingly. If
        the running ``CFFFont`` build doesn't expose CID-keyed glyph
        names this path returns ``[]`` and rendering is expected to
        fall back to the .notdef box, matching upstream behaviour for
        unembedded CIDFontType0 instances.
        """
        program = self.get_cff_font()
        if program is None:
            return []
        name = self._cff_glyph_name(cid)
        if not program.has_glyph(name):
            return []
        return program.get_path(name)

    def get_normalized_path(self, cid: int) -> list[tuple]:
        """Normalized glyph outline for ``cid`` in 1/1000 em.

        Mirrors upstream ``PDCIDFontType0.getNormalizedPath`` which on
        the CFF-backed CIDFontType0 path is a thin alias of
        :meth:`get_glyph_path`: the embedded CFF program already
        expresses outlines in its own font units (1000 upem by default
        for a CFF font matrix of ``[0.001 0 0 0.001 0 0]``), so no
        coordinate transform is applied here. Distinct from the
        :class:`PDCIDFontType2` override, which has to scale TTF
        outlines from a non-1000 upem.
        """
        return self.get_glyph_path(cid)

    # ---------- font-box accessors ----------

    def get_font_box_font(self) -> CFFFont | None:
        """Return the underlying embedded CFF font program, or ``None``
        when the font is not embedded / cannot be parsed.

        Mirrors upstream ``PDCIDFontType0.getFontBoxFont``. Upstream
        keeps two private slots — ``cidFont`` (a :class:`CFFCIDFont`)
        and ``t1Font`` (a name-keyed :class:`CFFType1Font` or a
        substitute :class:`TrueTypeFont`) — and surfaces whichever is
        non-null. For our CFF-only embedding path the two slots collapse
        into one return value, which matches the Java getter when the
        font *is* embedded. Substitute / fallback fonts are out of scope
        — the renderer never reaches this path without a real
        ``/FontFile3`` stream.
        """
        return self.get_cff_font()

    def get_type2_char_string(self, cid: int) -> object | None:
        """Return the Type 2 charstring wrapper for ``cid``, or ``None``
        when the font has no embedded CFF program.

        Mirrors upstream ``PDCIDFontType0.getType2CharString(int cid)``.
        For a CID-keyed CFF the charset maps CIDs into the CharStrings
        INDEX directly, so the wrapper indexes by GID == charset index
        of ``cidNNNNN``. For a name-keyed (Type 1 -flavoured) CFF
        embedded under a CIDFontType0 wrapper the CID is treated as
        the GID, which mirrors upstream's
        ``CFFType1Font.getType2CharString`` fall-through.
        """
        program = self.get_cff_font()
        if program is None:
            return None
        if isinstance(program, CFFCIDFont):
            target = self._cff_glyph_name(cid)
            charset = program.get_charset()
            if not charset:
                gid = 0
            else:
                try:
                    gid = charset.index(target)
                except ValueError:
                    gid = 0
            return program.get_type2_char_string(gid)
        # Name-keyed CFF: CID is GID.
        return program.get_type2_char_string(int(cid))

    # ---------- glyph name / path / hasGlyph (upstream-named) ----------

    def get_glyph_name(self, code: int) -> str:
        """Synthesise a glyph name for ``code`` via the parent's ToUnicode
        mapping.

        Mirrors upstream private ``PDCIDFontType0.getGlyphName``: looks up
        the parent :class:`PDType0Font`'s ``toUnicode`` for the code,
        then formats the resulting codepoint as ``uniXXXX`` via
        ``UniUtil.getUniNameOfCodePoint``. Returns ``".notdef"`` when the
        lookup fails — matches upstream behaviour for codes outside the
        font's ToUnicode coverage. Used by name-keyed (Type 1-flavoured)
        CFF fallbacks where the embedded program addresses glyphs by
        PostScript name rather than by CID.

        Exposed under the upstream name (without an underscore prefix)
        despite being marked private upstream because the rendering /
        text-extraction layer needs the same hook.
        """
        parent = self.get_parent()
        if parent is None:
            return ".notdef"
        unicodes = parent.to_unicode(code)
        if not unicodes:
            return ".notdef"
        return _uni_name_of_code_point(ord(unicodes[0]))

    def get_path(self, code: int) -> list[tuple]:
        """Glyph outline for ``code`` in *font units*.

        Mirrors upstream ``PDCIDFontType0.getPath(int)``. Resolution
        order:

        1. Resolve ``code -> CID`` via :meth:`code_to_cid`.
        2. If the descendant carries a ``/CIDToGIDMap`` stream and the
           font is embedded (PDFBOX-4093: a CIDFontType0 may carry an
           explicit CID→GID map despite the spec saying otherwise),
           remap ``cid`` through it.
        3. Ask the embedded CFF program for the Type 2 charstring's
           outline (CIDFontType0C) or fall back to the CFFType1Font
           branch when the embedded program is name-keyed.
        4. Final fallback: ``.notdef`` empty path — matches upstream's
           ``new GeneralPath()`` empty fallback.
        """
        cid = self.code_to_cid(code)
        if self.is_embedded() and self.has_cid_to_gid_map_stream():
            cid_to_gid = self.read_cid_to_gid_map()
            if cid_to_gid is not None and 0 <= cid < len(cid_to_gid):
                cid = cid_to_gid[cid]
        program = self.get_cff_font()
        if program is None:
            return []
        cs = self.get_type2_char_string(cid)
        if cs is not None:
            try:
                return cs.get_path()
            except Exception:  # noqa: BLE001
                return []
        return []

    def has_glyph(self, code: int) -> bool:  # type: ignore[override]
        """``True`` when ``code`` resolves to a non-``.notdef`` glyph.

        Mirrors upstream ``PDCIDFontType0.hasGlyph(int)`` — when an
        embedded CFF program is available we check that the CID's
        Type 2 charstring resolves to a non-zero GID (upstream's
        ``charstring.getGID() != 0``). For a name-keyed CFF embedded
        under a CIDFontType0 wrapper the upstream implementation goes
        through ``CFFType1Font`` directly; we collapse that branch into
        the same charstring lookup since :meth:`get_type2_char_string`
        already routes both polymorphic cases.

        When no embedded program is present we fall back to the parent
        :meth:`PDCIDFont.has_glyph` ``/W``/``/DW`` heuristic — upstream
        always reaches a substitute font program in that branch
        (``t1Font.hasGlyph(getGlyphName(code))``) but the Python port
        deliberately stops at the metric-table answer rather than
        synthesising a substitute.
        """
        program = self.get_cff_font()
        if program is None:
            return super().has_glyph(self.code_to_cid(code))
        cid = self.code_to_cid(code)
        cs = self.get_type2_char_string(cid)
        if cs is None:
            return False
        try:
            return cs.get_gid() != 0
        except Exception:  # noqa: BLE001
            return False

    def encode(self, unicode_codepoint: int) -> bytes:  # type: ignore[override]
        """Encoding by Unicode codepoint is unsupported for a CFF CIDFont.

        Mirrors upstream ``PDCIDFontType0.encode(int unicode)`` which
        throws ``UnsupportedOperationException``: the CIDFontType0 has
        no ``/Encoding`` of its own and cannot synthesise a CID for a
        unicode codepoint without going through the parent
        :class:`PDType0Font`'s CMap. Callers that need encoding should
        go through :meth:`PDType0Font.encode` instead.
        """
        raise NotImplementedError(
            "PDCIDFontType0.encode is unsupported — encode through the "
            "parent PDType0Font's CMap-driven encoder instead."
        )

    # ---------- glyph-ID encoding ----------

    def encode_glyph_id(self, glyph_id: int) -> bytes:
        """Encoding by glyph index is unsupported for a CFF CIDFont.

        Mirrors upstream ``PDCIDFontType0.encodeGlyphId(int)`` which
        throws ``UnsupportedOperationException``: CFF-backed CIDFonts
        encode by CID (a separate identity from GID for CID-keyed
        programs), so a glyph-ID-only encoder cannot generate
        round-trippable bytes. Callers that need encoding should go
        through the parent :class:`PDType0Font.encode` / ``encodeGlyphId``
        which routes via ``/Encoding`` and the descendant's CMap.
        """
        raise NotImplementedError(
            "PDCIDFontType0.encode_glyph_id is unsupported — encode through "
            "the parent PDType0Font's CMap-driven encoder instead."
        )


__all__ = ["PDCIDFontType0"]
