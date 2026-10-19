import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache

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


def _safe_font_name(font: Any) -> str | None:
    """``font.getName()`` that never raises."""
    try:
        return font.get_name()
    except Exception:
        return None


# (substitute name, base font) pairs already reported, so the fresh
# descendant wrapper PDType0Font builds per call doesn't log per glyph.
_WARNED_FALLBACKS: set[tuple[str | None, str | None]] = set()


def _warn_fallback(font: Any, base_font: str | None) -> None:
    key = (_safe_font_name(font), base_font)
    if key in _WARNED_FALLBACKS:
        return
    _WARNED_FALLBACKS.add(key)
    _LOG.warning("Using fallback %s for CID-keyed font %s", key[0], base_font)


def _font_box_font_path(font: Any, name: str) -> list[tuple]:
    """``t1Font.getPath(name)`` for a substitute FontBox font, in the shared
    path-command format and in font units. A TrueType (``glyf``) substitute
    is drawn by GID, so a name that resolves to ``.notdef`` draws the
    ``.notdef`` glyph as upstream ``TrueTypeFont.getPath(String)`` does."""
    if isinstance(font, TrueTypeFont):
        is_post_script = getattr(font, "is_post_script", None)
        if not (callable(is_post_script) and is_post_script()):
            from .pd_cid_font_type2 import PDCIDFontType2

            return PDCIDFontType2._draw_glyph(font, font.name_to_gid(name))
    try:
        path = font.get_path(name)
    except Exception:
        return []
    return list(path) if path else []


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
        resource_cache: PDResourceCache | None = None,
    ) -> None:
        # ``resource_cache`` (can be ``None``) mirrors upstream trunk's
        # ``PDCIDFontType0(COSDictionary, ResourceCache)`` (PDFBOX-6175);
        # the descendant no longer knows its parent Type 0 font.
        super().__init__(font_dict, resource_cache)
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
        # Substitute for a NON-embedded (or damaged) font, resolved lazily
        # through the FontMappers registry: ``None`` = not yet attempted,
        # else a ``(cid_font, t1_font, substitute_unicode_cmap)`` triple
        # mirroring upstream's ``cidFont`` / ``t1Font`` /
        # ``substituteUnicodeCmap`` fields of the non-embedded branch of
        # the constructor.
        self._substitute: tuple[CFFCIDFont | None, Any | None, Any | None] | None = None

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE

    # ---------- code -> CID ----------

    def code_to_cid(self, code: int, parent: PDType0Font | None) -> int:
        """Map a character ``code`` to a CID via the parent's encoding CMap.

        Mirrors upstream trunk ``PDCIDFontType0.codeToCID(int,
        PDType0Font)``: ``parent.getCMap().toCID(code)`` — the CMap's
        mapping is returned verbatim, including the ``0`` (`.notdef`) result
        for a code the CMap does not map. When there is no parent / the
        parent carries no encoding CMap (a bare wrapper, as in unit tests)
        the code passes through unchanged.
        """
        if parent is None:
            return int(code)
        cmap = parent.get_cmap()
        if cmap is None:
            return int(code)
        return cmap.to_cid(code)

    # ---------- code -> GID ----------

    def code_to_gid(self, code: int, parent: PDType0Font | None) -> int:
        """Return the GID for the character ``code``.

        Mirrors upstream trunk ``PDCIDFontType0.codeToGID(int, PDType0Font)``
        (including PDFBOX-6249):

        * A non-embedded font whose substitute is a CID-keyed font of a
          different character collection with an ``Identity`` ordering
          resolves the glyph via Unicode: code -> ``toUnicode`` -> the
          substitute's Unicode ``cmap`` (an unmapped code yields GID 0).
        * A CID-keyed CFF program (embedded, or the substitute) maps the
          CID through its charset (CID 40 may well be GID 10).
        * Otherwise the CID is used directly as the GID.
        """
        cid = self.code_to_cid(code, parent)
        if self._get_substitute_unicode_cmap() is not None:
            return max(self._code_to_substitute_gid(code, parent), 0)
        cid_font = self._get_cid_font()
        if cid_font is not None:
            # The CIDs shall be used to determine the GID value for the
            # glyph procedure using the charset table in the CFF program
            target = self._cff_glyph_name(cid)
            charset = cid_font.get_charset()
            if not charset:
                return 0
            try:
                return charset.index(target)
            except ValueError:
                return 0
        # The CIDs shall be used directly as GID values
        return int(cid)

    # ---------- substitute font (non-embedded branch) ----------

    def _get_substitute(
        self,
    ) -> tuple[CFFCIDFont | None, Any | None, Any | None]:
        """Resolve the substitute for a non-embedded (or damaged) font.

        Mirrors the ``else`` (not embedded) branch of upstream's
        constructor: ``FontMappers.instance().getCIDFont(baseFont,
        fontDescriptor, cidSystemInfo)`` and then

        * a CID mapping (an OpenType font with CFF outlines) supplies its
          CFF program: a CID-keyed one becomes ``cidFont``; a name-keyed
          one (PDFBOX-3515: OpenType fonts load as ``CFFType1Font``)
          becomes ``t1Font``;
        * otherwise the TrueType substitute becomes ``t1Font``.

        PDFBOX-6249 (3.0 branch): when the CID-keyed substitute belongs
        to another character collection and has an ``Identity`` ordering
        (modern CJK fonts are Adobe-Identity-0), this font's CIDs are
        meaningless in it, so the substitute's Unicode cmap is kept and
        glyphs are resolved via Unicode.

        The default pypdfbox mapper has no CID font scanner and answers
        ``None``; upstream's mapper always ends with a last-resort font,
        so the bundled last-resort font is used then (as for
        :class:`PDCIDFontType2`). Returns ``(cid_font, t1_font,
        unicode_cmap)`` with every slot ``None`` for an embedded font or
        when nothing could be found. Never raises.
        """
        if self._substitute is not None:
            return self._substitute
        cid_font: CFFCIDFont | None = None
        t1_font: Any | None = None
        unicode_cmap: Any | None = None
        if self.get_cff_font() is None:
            mapping = self._find_cid_font_mapping()
            font: Any | None = None
            if mapping is not None:
                if mapping.is_cid_font():
                    cff_font = self._mapping_cff(mapping)
                    if isinstance(cff_font, CFFCIDFont):
                        cid_font = cff_font
                        font = cid_font
                    elif cff_font is not None:
                        # PDFBOX-3515: OpenType fonts are loaded as
                        # CFFType1Font
                        t1_font = cff_font
                        font = t1_font
                else:
                    t1_font = mapping.get_true_type_font()
                    font = t1_font
                if font is not None and mapping.is_fallback():
                    _warn_fallback(font, self.get_base_font())
                if (
                    cid_font is not None
                    and not self._is_character_collection_match(cid_font)
                    and cid_font.get_ordering() == "Identity"
                ):
                    try:
                        unicode_cmap = mapping.get_font().get_unicode_cmap_lookup()
                    except Exception:
                        _LOG.warning(
                            "Could not read cmap of the substitute for font %s",
                            self.get_base_font(),
                            exc_info=True,
                        )
            if font is None:
                # pypdfbox: the mapper had nothing (upstream's always ends
                # with its last-resort font)
                from .pd_cid_font_type2 import _bundled_last_resort

                t1_font = _bundled_last_resort(self.get_font_descriptor())
                if t1_font is not None:
                    _warn_fallback(t1_font, self.get_base_font())
        self._substitute = (cid_font, t1_font, unicode_cmap)
        return self._substitute

    def _find_cid_font_mapping(self) -> Any | None:
        """``FontMappers.instance().getCIDFont(...)``; ``None`` on failure."""
        from pypdfbox.fontbox.font_mappers import FontMappers

        try:
            mapper = FontMappers.instance()
            get_cid_font = getattr(mapper, "get_cid_font", None)
            if not callable(get_cid_font):
                return None
            return get_cid_font(
                self.get_base_font() or "",
                self.get_font_descriptor(),
                self.get_cid_system_info(),
            )
        except Exception:
            _LOG.debug("CID font mapping failed", exc_info=True)
            return None

    @staticmethod
    def _mapping_cff(mapping: Any) -> CFFFont | None:
        """``mapping.getFont().getCFF().getFont()``; ``None`` when the
        mapped OpenType font carries no CFF program."""
        try:
            cff = mapping.get_font().get_cff()
        except Exception:
            return None
        # pypdfbox's ``OpenTypeFont.get_cff`` returns the CFF font itself;
        # tolerate an upstream-shaped wrapper exposing ``get_font``.
        if cff is not None and not isinstance(cff, CFFFont):
            get_font = getattr(cff, "get_font", None)
            cff = get_font() if callable(get_font) else None
        return cff if isinstance(cff, CFFFont) else None

    def _get_cid_font(self) -> CFFCIDFont | None:
        """Upstream's ``cidFont`` field: the CID-keyed CFF program, embedded
        or substitute."""
        program = self.get_cff_font()
        if program is not None:
            return program if isinstance(program, CFFCIDFont) else None
        return self._get_substitute()[0]

    def _get_t1_font(self) -> Any | None:
        """Upstream's ``t1Font`` field: an embedded name-keyed CFF program,
        or the non-CID substitute (``CFFType1Font`` or a TrueType font)."""
        program = self.get_cff_font()
        if program is not None:
            return None if isinstance(program, CFFCIDFont) else program
        return self._get_substitute()[1]

    def _get_substitute_unicode_cmap(self) -> Any | None:
        """Upstream's ``substituteUnicodeCmap`` field (PDFBOX-6249)."""
        if self.get_cff_font() is not None:
            return None
        return self._get_substitute()[2]

    def _is_character_collection_match(self, substitute: CFFCIDFont) -> bool:
        """Mirrors upstream private ``isCharacterCollectionMatch``
        (PDFBOX-6249): the substitute has this font's Registry and
        Ordering."""
        ros = self.get_cid_system_info()
        return (
            ros is not None
            and ros.get_registry() == substitute.get_registry()
            and ros.get_ordering() == substitute.get_ordering()
        )

    def _code_to_substitute_gid(self, code: int, parent: PDType0Font | None) -> int:
        """GID in the substitute for the given code, via Unicode; -1 if
        unmapped. The substitute's Identity charset makes GIDs address its
        charstrings directly. Mirrors upstream private
        ``codeToSubstituteGID`` (PDFBOX-6249)."""
        unicodes = parent.to_unicode(code) if parent is not None else None
        if not unicodes:
            return -1
        lookup = self._get_substitute_unicode_cmap()
        if lookup is None:
            return -1
        try:
            return int(lookup.get_glyph_id(ord(unicodes[0])))
        except Exception:
            return -1

    # ---------- /FontFile3 + /Subtype /CIDFontType0C wiring ----------

    def is_embedded(self) -> bool:  # type: ignore[override]
        """``True`` when the font carries a usable embedded CFF program.

        Mirrors upstream ``PDCIDFontType0.isEmbedded``: the font counts as
        embedded only when ``/FontFile3`` parses into a CFF font (or a
        program was injected through :meth:`set_cff_font`). A missing or
        damaged program, or a ``/FontFile`` / ``/FontFile2`` stream (not a
        valid program location for a CIDFontType0), is not embedded: the
        substitute font is used instead. :meth:`is_cff_embedded` keeps the
        descriptor-only ``/FontFile3`` subtype check.
        """
        return self.get_cff_font() is not None

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
        except Exception:
            _LOG.exception("failed to parse /FontFile3 for %s", self.get_base_font())
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
        Returns ``None`` when there is no program or it reports a zero
        advance. Width is normalized to 1/1000 em (the PDF width unit)
        regardless of the program's native units-per-em.

        Mirrors upstream ``PDCIDFontType0.getWidthFromFont`` /
        ``getGlyphWidth``, which take the width straight from the CID's
        Type 2 charstring (``cidFont.getType2CharString(cid).getWidth()``)
        with no ``hasGlyph`` gate: an unmapped CID (and CID 0, ``.notdef``)
        resolves to GID 0's charstring whose advance is the Private DICT
        ``defaultWidthX`` — so the embedded-program width for ``.notdef``
        is a real value (e.g. 250), not 0. A CID-keyed
        :class:`CFFCIDFont` resolves the CID→GID→charstring chain inside
        ``get_width`` directly; a name-keyed CFF (the rare simple-CFF
        descendant) keeps the glyph-name lookup.
        """
        program = self.get_cff_font()
        if program is None:
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        if getattr(program, "is_cid_font", lambda: False)():
            # CID-keyed: hand the CID straight to the program. Its
            # ``get_width`` does the CID→GID→charstring resolution, with an
            # unmapped CID (and CID 0, ``.notdef``) routed to GID 0 whose
            # advance is the Private DICT ``defaultWidthX`` — so the
            # embedded-program width for ``.notdef`` is a real value
            # (e.g. 250), not 0. Mirrors upstream
            # ``PDCIDFontType0.getWidthFromFont`` /
            # ``cidFont.getType2CharString(cid).getWidth()`` (no hasGlyph gate).
            advance = program.get_width(cid)
        else:
            # Name-keyed CFF descendant (rare): look the glyph up by name,
            # returning ``None`` when the program has no such glyph.
            name = self._cff_glyph_name(cid)
            if not program.has_glyph(name):
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

    def get_width_from_font(self, code: int, parent: PDType0Font | None) -> float:
        """Width of the glyph for the character ``code`` taken *only* from
        the font program (embedded, or the substitute for a non-embedded
        font), in 1/1000 em. Returns ``0.0`` when no program is available.

        Mirrors upstream trunk ``PDCIDFontType0.getWidthFromFont(int,
        PDType0Font)`` (including PDFBOX-6249):

        * Unicode-resolved Identity substitute: the advance of the
          substitute glyph found via ``toUnicode``;
        * CID-keyed CFF: the advance of the CID's Type 2 charstring;
        * embedded name-keyed CFF: the CID is used as the GID;
        * otherwise (a TrueType or name-keyed CFF substitute) the advance
          of the ``uniXXXX`` glyph named after the code's Unicode value.

        The advance is mapped through the font matrix (scaled by 1000).
        Distinct from :meth:`get_glyph_width`, which prefers ``/W``.
        """
        cid = self.code_to_cid(code, parent)
        try:
            cid_font = self._get_cid_font()
            if self._get_substitute_unicode_cmap() is not None and cid_font is not None:
                # the Identity charset makes the GID address the charstring
                gid = max(self._code_to_substitute_gid(code, parent), 0)
                width = float(cid_font.get_width(gid))
            elif cid_font is not None:
                # ``CFFCIDFont.get_width(cid)`` is the width of the CID's
                # Type 2 charstring (``getType2CharString(cid).getWidth()``)
                width = float(cid_font.get_width(cid))
            elif self.is_embedded():
                # embedded name-keyed CFF: the CID is the GID
                width = float(self.get_type2_char_string(cid).get_width())
            else:
                t1_font = self._get_t1_font()
                if t1_font is None:
                    return 0.0
                width = float(t1_font.get_width(self.get_glyph_name(code, parent)))
        except Exception:
            _LOG.debug("width lookup failed for code %d", code, exc_info=True)
            return 0.0
        matrix = self.get_font_matrix()
        # fontMatrixTransform = fontMatrix.createAffineTransform().scale(1000, 1000)
        return matrix[0] * width * 1000.0 + matrix[4]

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

    def _get_height_for_cid(self, cid: int) -> float:
        """Height of the glyph at ``cid`` in *font units*; backs
        :meth:`PDCIDFont.get_height` ``(code, parent)``.

        Mirrors upstream trunk ``PDCIDFontType0.getHeight(int code,
        PDType0Font parent)`` — derived
        from the CFF outline's bounding box (max-y minus min-y) when an
        embedded CFF program is available. Falls back to the parent
        :meth:`PDCIDFont.get_height` (which reads ``/W2``) when no
        program is present.

        A non-embedded font with a CFF substitute measures the substitute's
        Type 2 charstring for the CID, as upstream does; with no CFF program
        at all (no substitute, or a TrueType one, where upstream would fail
        on the missing charstring) the parent ``/W2`` answer is returned.

        Result is cached per-CID.
        """
        program = self.get_cff_font()
        if program is None:
            cs = self.get_type2_char_string(cid)
            if cs is None:
                return super()._get_height_for_cid(cid)
            cached = self._glyph_heights.get(cid)
            if cached is not None:
                return cached
            try:
                bounds = cs.get_bounds()
            except Exception:
                bounds = None
            height = float(bounds[3] - bounds[1]) if bounds else 0.0
            self._glyph_heights[cid] = height
            return height
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
        (CFF Top DICT, default ``[0.001 0 0 0.001 0 0]``); for a
        non-embedded font, the substitute's matrix; otherwise the CFF
        default. Returned as an immutable tuple to
        prevent accidental in-place mutation by callers.
        """
        try:
            program: Any = self.get_cff_font()
            if program is not None:
                matrix = program.font_matrix
            else:
                # non-embedded: the substitute's matrix (upstream
                # ``cidFont`` / ``t1Font.getFontMatrix()``), e.g.
                # 1/unitsPerEm for a TrueType substitute
                program = self._get_substitute_program()
                if program is None:
                    return _CFF_DEFAULT_FONT_MATRIX
                if isinstance(program, CFFFont):
                    matrix = program.font_matrix
                else:
                    matrix = program.get_font_matrix()
        except Exception:
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
           ``/FontBBox``, or the substitute's bounding box for a
           non-embedded font.

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
        else:
            # non-embedded: the substitute's bounding box
            substitute = self._get_substitute_program()
            if substitute is not None:
                try:
                    rect = self._coerce_bbox(substitute.get_font_b_box())
                except Exception:
                    rect = None
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

    # ---------- font-box accessors ----------

    def get_font_box_font(self) -> Any | None:
        """Return the embedded or substituted font, or ``None`` when there
        is neither.

        Mirrors upstream ``PDCIDFontType0.getFontBoxFont``: ``cidFont``
        when set, else ``t1Font``. For an embedded font that is the parsed
        ``/FontFile3`` program (:meth:`get_cff_font`); for a non-embedded
        one, the substitute located through :class:`FontMappers` (a
        :class:`CFFCIDFont`, a :class:`CFFType1Font` or a TrueType font).
        """
        cid_font = self._get_cid_font()
        if cid_font is not None:
            return cid_font
        return self._get_t1_font()

    def _get_substitute_program(self) -> Any | None:
        """The substitute program of a non-embedded font (``None`` when
        embedded or when there is none)."""
        if self.get_cff_font() is not None:
            return None
        return self.get_font_box_font()

    def get_type2_char_string(self, cid: int) -> object | None:
        """Return the Type 2 charstring for ``cid``, or ``None`` when the
        font (embedded or substituted) does not contain Type 2 charstrings.

        Mirrors upstream ``PDCIDFontType0.getType2CharString(int cid)``.
        A CID-keyed CFF resolves the CID through its charset; a name-keyed
        CFF (an embedded program under a CIDFontType0 wrapper, or a
        CFF-based OpenType substitute) treats the CID as the GID. A
        TrueType substitute has no charstrings.
        """
        program = self.get_cff_font()
        if program is not None and not isinstance(program, CFFCIDFont):
            # Embedded name-keyed CFF: CID is GID.
            return program.get_type2_char_string(int(cid))
        cid_font = self._get_cid_font()
        if cid_font is not None:
            # Pass the CID straight through: ``CFFCIDFont.get_type2_char_string``
            # does the CID→GID resolution itself (mirroring upstream
            # ``cidFont.getType2CharString(cid)``). Pre-resolving the GID here
            # and passing *that* would trigger a second CID→GID lookup inside
            # the CFFCIDFont accessor, corrupting the returned wrapper's GID.
            return cid_font.get_type2_char_string(int(cid))
        t1_font = self._get_t1_font()
        if isinstance(t1_font, CFFType1Font):
            # Name-keyed CFF: CID is GID.
            return t1_font.get_type2_char_string(int(cid))
        return None

    # ---------- glyph name / path / hasGlyph (upstream-named) ----------

    def get_glyph_name(self, code: int, parent: PDType0Font | None) -> str:
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
        if parent is None:
            return ".notdef"
        unicodes = parent.to_unicode(code)
        if not unicodes:
            return ".notdef"
        return _uni_name_of_code_point(ord(unicodes[0]))

    def get_path(self, code: int, parent: PDType0Font | None) -> list[tuple]:
        """Glyph outline for the character ``code`` in *font units*.

        Mirrors upstream trunk ``PDCIDFontType0.getPath(int, PDType0Font)``
        (including PDFBOX-6249). Resolution order:

        1. A non-embedded font with a Unicode-resolved Identity substitute
           draws the substitute glyph found via ``toUnicode`` (``.notdef``
           when unmapped).
        2. Resolve ``code -> CID``; an embedded font with a
           ``/CIDToGIDMap`` stream (PDFBOX-4093: a CIDFontType0 may carry
           one despite the spec) remaps the CID through it.
        3. The CID's Type 2 charstring from the CFF program (embedded or
           substitute).
        4. Otherwise (a TrueType substitute) the ``uniXXXX`` glyph named
           after the code's Unicode value.

        Returns ``[]`` when no program is available or the glyph cannot be
        drawn, matching upstream's ``new GeneralPath()`` empty fallback.
        """
        cid = self.code_to_cid(code, parent)
        try:
            if self._get_substitute_unicode_cmap() is not None:
                gid = max(self._code_to_substitute_gid(code, parent), 0)
                cs = self.get_type2_char_string(gid)
                return list(cs.get_path()) if cs is not None else []
            if self.is_embedded() and self.has_cid_to_gid_map_stream():
                # PDFBOX-4093: despite being a type 0 font, there is a
                # CIDToGIDMap
                cid_to_gid = self.read_cid_to_gid_map()
                if cid_to_gid is not None and 0 <= cid < len(cid_to_gid):
                    cid = cid_to_gid[cid]
            cs = self.get_type2_char_string(cid)
            if cs is not None:
                return list(cs.get_path())
            t1_font = self._get_t1_font()
            if t1_font is None:
                return []
            if self.is_embedded() and isinstance(t1_font, CFFType1Font):
                return list(t1_font.get_type2_char_string(cid).get_path())
            return _font_box_font_path(t1_font, self.get_glyph_name(code, parent))
        except Exception:
            _LOG.debug("glyph path failed for code %d", code, exc_info=True)
            return []

    def get_normalized_path(
        self, code: int, parent: PDType0Font | None
    ) -> list[tuple]:
        """Glyph outline for the character ``code``.

        Mirrors upstream ``PDCIDFontType0.getNormalizedPath``, which simply
        returns :meth:`get_path`: no coordinate transform is applied (a
        CFF program already uses a 1000-unit em by default). Distinct from
        the :class:`PDCIDFontType2` override, which scales TTF outlines.
        """
        return self.get_path(code, parent)

    def has_glyph(self, code: int, parent: PDType0Font | None) -> bool:
        """``True`` when the character ``code`` resolves to a
        non-``.notdef`` glyph.

        Mirrors upstream trunk ``PDCIDFontType0.hasGlyph(int, PDType0Font)``
        (including PDFBOX-6249): a Unicode-resolved Identity substitute
        must map the code's Unicode value to a GID above 0; a CFF program
        (embedded or substitute) must resolve the CID's Type 2 charstring
        to a GID other than 0; a TrueType substitute must have the
        ``uniXXXX`` glyph named after the code's Unicode value.

        With no font program at all (a bare descendant without an
        embedded program), the parent :meth:`PDCIDFont.has_glyph`
        ``/W``/``/DW`` heuristic answers instead.
        """
        cid = self.code_to_cid(code, parent)
        try:
            if self._get_substitute_unicode_cmap() is not None:
                return self._code_to_substitute_gid(code, parent) > 0
            cs = self.get_type2_char_string(cid)
            if cs is not None:
                return cs.get_gid() != 0
            t1_font = self._get_t1_font()
            if t1_font is None:
                return super().has_glyph(code, parent)
            if self.is_embedded() and isinstance(t1_font, CFFType1Font):
                return t1_font.get_type2_char_string(cid).get_gid() != 0
            return bool(t1_font.has_glyph(self.get_glyph_name(code, parent)))
        except Exception:
            return False

    def encode(self, unicode_codepoint: int, parent: PDType0Font | None) -> bytes:
        """Encoding by Unicode codepoint is unsupported for a CFF CIDFont.

        Mirrors upstream trunk ``PDCIDFont.encode(int, PDType0Font)``, which
        throws ``UnsupportedOperationException`` for a ``PDCIDFontType0``: the CIDFontType0 has
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
