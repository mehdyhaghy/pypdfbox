from __future__ import annotations

import logging

from pypdfbox.cos import COSDictionary
from pypdfbox.fontbox.cff.cff_font import CFFFont

from .pd_type1_font import PDType1Font

_LOG = logging.getLogger(__name__)

# CFF defaults to a 1000-unit em (font matrix [0.001 0 0 0.001 0 0]).
_CFF_DEFAULT_UNITS_PER_EM: int = 1000
type GlyphPath = list[tuple[object, ...]]


class PDType1CFont(PDType1Font):
    """Type 1 font whose glyph program is a CFF (Compact Font Format) stream.

    Mirrors PDFBox ``PDType1CFont``. The font dictionary itself still
    declares ``/Subtype /Type1`` — Type1C-ness is signalled by a
    ``/FontFile3`` stream on the ``/FontDescriptor`` whose own
    ``/Subtype`` is ``Type1C``. ``PDFontFactory`` therefore selects this
    wrapper by inspecting both the font dictionary subtype (``Type1`` or
    ``MMType1``) and the descriptor's ``/FontFile3 /Subtype`` marker.

    The embedded CFF program is parsed lazily on first metric access
    via :class:`CFFFont` — itself a thin wrapper around
    ``fontTools.cffLib``. Glyph widths and outlines are exposed through
    :meth:`get_glyph_width` / :meth:`get_glyph_path`, inherited from
    :class:`PDType1Font` but routed through the CFF program rather than
    the Type 1 PFB-style program.
    """

    SUB_TYPE = "Type1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazily-loaded embedded CFF program. ``None`` means
        # "not yet attempted", ``False`` means "tried, no /FontFile3 or
        # parse failed".
        self._cff: CFFFont | None | bool = None
        # Per-glyph height cache. CFF glyph-bbox computation walks the
        # entire outline; cache the result the way upstream does
        # (``glyphHeights`` map in ``PDType1CFont``).
        self._glyph_heights: dict[str, float] = {}

    # ---------- CFF program access ----------

    def _get_cff_font(self) -> CFFFont | None:
        """Return the parsed CFF program for this font's
        ``/FontFile3`` stream (``/Subtype /Type1C``), or ``None`` if the
        font is not embedded or the stream cannot be parsed. Result is
        cached."""
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
            self._cff = CFFFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile3 for %s", self.get_name())
            self._cff = False
            return None
        return self._cff

    def get_cff_font(self) -> CFFFont | None:
        """Return the parsed embedded CFF program, or ``None`` when the
        font is not embedded or the program failed to parse. Mirrors
        upstream ``PDType1CFont.getCFFType1Font`` (the upstream method
        is named after the concrete CFFType1Font subtype; we surface the
        broader ``CFFFont`` because our fontbox wrapper does not split
        the CFFType1Font / CFFCIDFont hierarchy)."""
        return self._get_cff_font()

    # Upstream alias: ``getCFFType1Font`` returns the embedded CFFType1Font
    # instance. We expose the same name so PDFBox-side callers find it.
    def get_cff_type1_font(self) -> CFFFont | None:
        """Alias of :meth:`get_cff_font` matching the upstream name
        ``PDType1CFont.getCFFType1Font``."""
        return self._get_cff_font()

    def set_font_program(self, font: CFFFont | None) -> None:  # type: ignore[override]
        """Inject a pre-parsed :class:`CFFFont`. Mirrors the equivalent
        injector on :class:`PDType1Font` / :class:`PDTrueTypeFont` —
        lets callers that already have the font program in hand bypass
        ``/FontFile3`` parsing, and lets tests skip the byte-level
        fixture round-trip."""
        self._cff = font if font is not None else False
        # Reset the glyph-height cache: heights are derived from the
        # injected program's outlines.
        self._glyph_heights.clear()

    def get_font_program(self) -> CFFFont | None:  # type: ignore[override]
        """Return the parsed embedded CFF program, or ``None`` when the
        font is not embedded or the program failed to parse.

        Overrides :class:`PDType1Font`'s ``/FontFile``-backed accessor so
        the getter is symmetric with :meth:`set_font_program` and reads
        the Type 1C program from ``/FontDescriptor /FontFile3``.
        """
        return self._get_cff_font()

    # ---------- glyph widths / paths via CFF program ----------

    def _program_width(self, code: int) -> float | None:
        """CFF-backed override of :meth:`PDType1Font._program_width`."""
        program = self._get_cff_font()
        if program is None:
            return None
        name = self._code_to_glyph_name(code)
        if name is None or not program.has_glyph(name):
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        advance = program.get_width(name)
        if advance <= 0.0:
            return None
        return advance * 1000.0 / units_per_em

    def get_glyph_path(self, code: int) -> GlyphPath:
        """CFF-backed glyph outline for ``code``, in font units. Returns
        ``[]`` when the font has no embedded CFF program or the code is
        unmapped."""
        program = self._get_cff_font()
        if program is None:
            return []
        name = self._code_to_glyph_name(code)
        if name is None:
            return []
        return program.get_path(name)

    # ---------- upstream-parity overrides ----------

    def is_embedded(self) -> bool:
        """``True`` iff the font dictionary carries an embedded CFF
        program — ``/FontFile3`` on the ``/FontDescriptor``. Mirrors
        upstream ``PDType1CFont.isEmbedded``: PDType1C only honours
        ``/FontFile3`` (the Type 1 ``/FontFile`` slot is a Type1Font
        concern handled by the PDType1Font base)."""
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        return descriptor.get_font_file3() is not None

    def is_damaged(self) -> bool:
        """``True`` iff the embedded CFF program failed to parse.
        Mirrors upstream ``PDType1CFont.isDamaged``. Returns ``False``
        when the font is not embedded (nothing to parse, nothing to be
        damaged) or when parsing succeeded."""
        descriptor = self.get_font_descriptor()
        if descriptor is None or descriptor.get_font_file3() is None:
            return False
        # Force the lazy parse and check whether it surfaced a real CFF font.
        self._get_cff_font()
        return self._cff is False

    def get_path(self, name: str) -> GlyphPath:
        """Return the glyph outline for the named glyph, in font units.

        Mirrors upstream ``PDType1CFont.getPath(String name)`` —
        operates on a glyph *name* (not a character code; see
        :meth:`get_glyph_path` for the code-keyed variant). Returns
        ``[]`` when the font has no embedded program or the glyph is
        missing."""
        program = self._get_cff_font()
        if program is None:
            return []
        return program.get_path(name)

    def has_glyph(self, name: str) -> bool:
        """``True`` iff the embedded CFF program contains a glyph with
        this PostScript name. Mirrors upstream
        ``PDType1CFont.hasGlyph(String name)``. Returns ``False`` when
        the font has no embedded CFF program."""
        program = self._get_cff_font()
        if program is None:
            return False
        return program.has_glyph(name)

    # ---------- code → glyph name / GID ----------

    def code_to_name(self, code: int) -> str | None:  # type: ignore[override]
        """Resolve a 1-byte character code to its PostScript glyph name
        via the font's ``/Encoding`` (with ``/Differences`` overlay).

        Mirrors upstream ``PDType1CFont.codeToName(int code)``. Returns
        ``None`` when the code maps to ``.notdef`` or when the font has
        no ``/Encoding`` at all (callers treat that as "no glyph")."""
        return self._code_to_glyph_name(code)

    def code_to_gid(self, code: int) -> int:
        """Resolve a 1-byte character code to a CFF glyph index (GID).

        Lookup chain: code → glyph name (via ``/Encoding``) → GID via
        the CFF charset (which lists glyph names in CharStrings order,
        index = GID). Returns ``0`` (the ``.notdef`` GID per CFF spec
        §9) when the font has no embedded CFF program, the code does
        not resolve to a glyph name, or the name is absent from the
        charset."""
        program = self._get_cff_font()
        if program is None:
            return 0
        name = self._code_to_glyph_name(code)
        if name is None:
            return 0
        charset = program.get_charset()
        if not charset:
            return 0
        try:
            return charset.index(name)
        except ValueError:
            return 0

    # ---------- font-level metrics ----------

    def get_units_per_em(self) -> int:
        """Return the units-per-em of the embedded CFF font program.

        Mirrors upstream ``PDType1CFont``'s reliance on the CFF font
        matrix (``getFontMatrix()`` derives units-per-em from
        ``matrix[0]``). CFF defaults to a 1000-unit em (matrix
        ``[0.001 0 0 0.001 0 0]``) — when the font is not embedded or
        the program failed to parse, returns the CFF default of 1000
        rather than 0 so callers downstream of glyph metrics never
        divide by zero."""
        program = self._get_cff_font()
        if program is None:
            return _CFF_DEFAULT_UNITS_PER_EM
        upem = program.units_per_em
        return upem if upem > 0 else _CFF_DEFAULT_UNITS_PER_EM

    def get_height(self, code: int) -> float:
        """Height of the glyph at ``code`` in *font units*.

        Computed from the glyph outline's bounding box (max-y minus
        min-y) when an embedded CFF program is available; otherwise
        ``0.0``. Result is cached per-glyph-name. Mirrors upstream
        ``PDType1CFont.getHeight(int code)`` which caches in a
        ``glyphHeights`` map for the same reason."""
        program = self._get_cff_font()
        if program is None:
            return 0.0
        name = self._code_to_glyph_name(code)
        if name is None:
            return 0.0
        cached = self._glyph_heights.get(name)
        if cached is not None:
            return cached
        path = program.get_path(name)
        if not path:
            self._glyph_heights[name] = 0.0
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
        self._glyph_heights[name] = height
        return height

    def get_average_font_width(self) -> float:
        """Mean glyph advance for this font in 1/1000 em.

        Lookup order:

        1. Mean of positive entries in ``/Widths`` (matches
           :meth:`PDSimpleFont.get_average_font_width`).
        2. CFF Private DICT ``defaultWidthX`` (the advance assigned to
           glyphs whose charstring omits the leading width operand —
           CFF spec §10) when an embedded CFF program is present.
        3. Standard 14 AFM mean for the matching font.
        4. ``0.0``.

        Upstream ``PDType1CFont.getAverageFontWidth`` famously
        hard-codes ``500`` (see the ``// todo: not implemented, highly
        suspect`` comment). We deviate intentionally: the CFF default
        width is information actually present in the embedded program
        and is a far better answer for non-Standard-14 embedded fonts.
        """
        widths = self.get_widths()
        non_zero = [w for w in widths if w > 0.0]
        if non_zero:
            return sum(non_zero) / len(non_zero)
        program = self._get_cff_font()
        if program is not None:
            default = program.get_default_width_x()
            if default > 0.0:
                upem = program.units_per_em
                if upem > 0:
                    return default * 1000.0 / upem
        afm = self.get_standard_14_font_metrics()
        if afm is not None:
            return afm.get_average_width()
        return 0.0


__all__ = ["PDType1CFont"]
