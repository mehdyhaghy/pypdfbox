from __future__ import annotations

from importlib import resources
from typing import Any

from pypdfbox.fontbox.afm import AFMParser, CharMetric, FontMetrics, KernPair, Ligature
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

# Canonical PostScript names of the 14 Standard fonts (PDF 32000-1 §9.6.2.2).
_STANDARD14: tuple[str, ...] = (
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
)


class AfmMetrics:
    """Typed wrapper over a parsed Adobe AFM file.

    Mirrors what ``org.apache.pdfbox.pdmodel.font.PDType1Font`` consumes
    from its bundled ``FontMetrics`` object: per-glyph advance widths,
    font-bbox, italic angle, ascender / descender / cap-height /
    x-height, and the average advance width across the encoded glyph set.

    Construction takes the canonical font name (one of the Standard 14)
    and the parsed :class:`pypdfbox.fontbox.afm.FontMetrics`. Instances
    are immutable; the module-level cache returns the same instance per
    font name.

    Beyond the original AFMBox-style accessors, this wrapper exposes the
    full upstream surface — kern pairs, ligatures, comments, vertical
    metrics, and the underlying :class:`FontMetrics` itself — through
    additional ``get_*`` methods so callers that need post-Type1
    formatting (e.g. text shaping with kerning) can reach the data
    without re-parsing the file.
    """

    __slots__ = ("_name", "_fm", "_widths_by_name", "_average_width")

    def __init__(self, name: str, font_metrics: FontMetrics) -> None:
        self._name: str = name
        self._fm: FontMetrics = font_metrics
        self._widths_by_name: dict[str, float] = {
            cm.get_name(): float(cm.get_wx())
            for cm in font_metrics.get_char_metrics()
            if cm.get_name()
        }
        non_zero = [w for w in self._widths_by_name.values() if w > 0.0]
        self._average_width: float = (
            sum(non_zero) / len(non_zero) if non_zero else 0.0
        )

    # ---------- identity ----------

    def get_font_name(self) -> str:
        """Canonical PostScript name (e.g. ``"Times-Roman"``)."""
        return self._name

    def get_font_metrics_object(self) -> FontMetrics:
        """The underlying typed :class:`FontMetrics`.

        Use this when you need to reach upstream-shaped data (kern pairs,
        ligatures, char-metric bbox, comments, etc.). The accessor is
        named ``..._object`` so it doesn't shadow the long-standing
        :meth:`get_font_metrics` (which still returns the
        font-descriptor dict).
        """
        return self._fm

    # ---------- per-glyph widths ----------

    def get_glyph_width(self, glyph_name: str) -> float:
        """Return the advance width for ``glyph_name`` in 1/1000 em.

        Returns ``0.0`` for unknown / ``.notdef`` slots — matches PDFBox's
        ``FontMetrics.getCharacterWidth`` fallback for missing glyphs.
        """
        return self._widths_by_name.get(glyph_name, 0.0)

    def has_glyph(self, glyph_name: str) -> bool:
        """``True`` when the AFM defines a real entry for ``glyph_name``."""
        return glyph_name in self._widths_by_name

    def get_average_width(self) -> float:
        """Mean of non-zero advance widths across the AFM's glyph set."""
        return self._average_width

    # ---------- font-descriptor metrics ----------

    def get_font_metrics(self) -> dict[str, Any]:
        """Return PDF font-descriptor entries derived from the AFM.

        Keys mirror the PDF font-descriptor entry names: ``FontName``,
        ``FontBBox`` (4-element tuple of ints), ``ItalicAngle`` (float),
        ``Ascent`` / ``Descent`` / ``CapHeight`` / ``XHeight`` /
        ``StemV`` (floats; ``0.0`` when the AFM omits the entry, e.g.
        Symbol / ZapfDingbats), and ``IsFixedPitch`` (bool).
        """
        bbox = self._fm.get_font_b_box()
        if bbox is None:
            bbox_tuple: tuple[int, int, int, int] = (0, 0, 0, 0)
        else:
            bbox_tuple = (
                int(bbox.get_lower_left_x()),
                int(bbox.get_lower_left_y()),
                int(bbox.get_upper_right_x()),
                int(bbox.get_upper_right_y()),
            )
        return {
            "FontName": self._fm.get_font_name() or self._name,
            "FontBBox": bbox_tuple,
            "ItalicAngle": float(self._fm.get_italic_angle()),
            "Ascent": float(self._fm.get_ascender()),
            "Descent": float(self._fm.get_descender()),
            "CapHeight": float(self._fm.get_cap_height()),
            "XHeight": float(self._fm.get_x_height()),
            # AFM ships StdVW (vertical stem); PDF descriptors call it StemV.
            "StemV": float(self._fm.get_standard_vertical_width()),
            "IsFixedPitch": self._fm.get_is_fixed_pitch(),
        }

    # ---------- enriched accessors (parity round-out) ----------

    def get_full_name(self) -> str | None:
        """``FullName`` AFM header (e.g. ``"Times Roman"``)."""
        return self._fm.get_full_name()

    def get_family_name(self) -> str | None:
        """``FamilyName`` AFM header."""
        return self._fm.get_family_name()

    def get_weight(self) -> str | None:
        """``Weight`` AFM header (e.g. ``"Medium"``, ``"Bold"``)."""
        return self._fm.get_weight()

    def get_font_version(self) -> str | None:
        """``Version`` AFM header (e.g. ``"002.000"``)."""
        return self._fm.get_font_version()

    def get_notice(self) -> str | None:
        """``Notice`` AFM header (Adobe copyright string)."""
        return self._fm.get_notice()

    def get_encoding_scheme(self) -> str | None:
        """``EncodingScheme`` AFM header (e.g. ``"AdobeStandardEncoding"``)."""
        return self._fm.get_encoding_scheme()

    def get_character_set(self) -> str | None:
        """``CharacterSet`` AFM header (e.g. ``"ExtendedRoman"``)."""
        return self._fm.get_character_set()

    def get_comments(self) -> list[str]:
        """All ``Comment`` lines from the AFM, in document order."""
        return self._fm.get_comments()

    def get_underline_position(self) -> float:
        """``UnderlinePosition`` AFM header."""
        return self._fm.get_underline_position()

    def get_underline_thickness(self) -> float:
        """``UnderlineThickness`` AFM header."""
        return self._fm.get_underline_thickness()

    def get_standard_horizontal_width(self) -> float:
        """``StdHW`` (dominant horizontal stem)."""
        return self._fm.get_standard_horizontal_width()

    def get_standard_vertical_width(self) -> float:
        """``StdVW`` (dominant vertical stem; PDF /StemV)."""
        return self._fm.get_standard_vertical_width()

    def get_char_metrics(self) -> list[CharMetric]:
        """All :class:`CharMetric` entries in the AFM."""
        return self._fm.get_char_metrics()

    def get_char_metric(self, glyph_name: str | None) -> CharMetric | None:
        """Look up the typed :class:`CharMetric` for ``glyph_name``.

        Mirrors upstream ``FontMetrics.getCharMetric`` (delegated through
        the AFM-shaped wrapper). Returns ``None`` when the glyph isn't
        defined or when ``glyph_name`` is ``None`` — matching upstream's
        null-tolerant lookup so callers can hand in
        ``Encoding.getName(...)`` results without pre-checking.
        """
        if glyph_name is None:
            return None
        return self._fm.get_char_metric(glyph_name)

    def has_char_metric(self, glyph_name: str | None) -> bool:
        """``True`` when the AFM has a :class:`CharMetric` for ``glyph_name``.

        ``has_glyph`` only knows about *named* entries with a non-empty
        name; this predicate goes through the underlying char-metric map
        and is symmetric with :meth:`get_char_metric`. Returns ``False``
        when ``glyph_name`` is ``None`` (parity with upstream
        ``FontMetrics.hasCharMetric``).
        """
        if glyph_name is None:
            return False
        return self._fm.has_char_metric(glyph_name)

    def get_character_width(self, glyph_name: str) -> float:
        """``WX`` of glyph ``glyph_name``; ``0.0`` if missing.

        Parity alias for upstream ``FontMetrics.getCharacterWidth``.
        Equivalent to :meth:`get_glyph_width` for normal Standard 14
        fonts but reaches through :class:`FontMetrics` rather than the
        cached widths dict, so any AFM with duplicate glyph names returns
        the *last* metric's width (upstream behaviour) rather than the
        first.
        """
        return self._fm.get_character_width(glyph_name)

    def get_character_height(self, glyph_name: str) -> float:
        """Glyph height: ``WY`` when non-zero, otherwise the bbox height.

        Parity alias for upstream ``FontMetrics.getCharacterHeight``.
        Returns ``0.0`` for unknown glyphs and for glyphs that have
        neither a ``WY`` nor a bounding box (Symbol / ZapfDingbats edge
        case).
        """
        return self._fm.get_character_height(glyph_name)

    def get_font_b_box(self) -> BoundingBox | None:
        """Typed :class:`BoundingBox` from the AFM ``FontBBox`` header.

        :meth:`get_font_metrics` already exposes the bbox as a 4-tuple in
        the descriptor dict; this accessor returns the upstream-shaped
        :class:`BoundingBox` directly so callers that want the typed
        object (e.g. for ``get_height()`` / ``get_width()``) don't have
        to round-trip through the dict.
        """
        return self._fm.get_font_b_box()

    def has_font_b_box(self) -> bool:
        """``True`` when the AFM declares a ``FontBBox`` header.

        Parity alias for upstream ``FontMetrics.hasFontBBox``.
        """
        return self._fm.has_font_b_box()

    def get_italic_angle(self) -> float:
        """``ItalicAngle`` AFM header (degrees clockwise from vertical).

        Parity alias — :meth:`get_font_metrics` exposes this through the
        descriptor dict; this accessor returns it directly so callers
        that only need the angle (e.g. shaping fallback code) skip the
        dict allocation.
        """
        return float(self._fm.get_italic_angle())

    def is_fixed_pitch(self) -> bool:
        """``True`` when the AFM marks the font as monospaced.

        Parity alias for upstream ``FontMetrics.getIsFixedPitch`` (the
        Java getter is named *get* but the value is a boolean — Python
        idiom prefers ``is_*``). The descriptor dict's ``IsFixedPitch``
        entry returns the same value.
        """
        return bool(self._fm.get_is_fixed_pitch())

    def get_afm_version(self) -> float:
        """``StartFontMetrics`` version line (e.g. ``4.1``).

        Parity alias for upstream ``FontMetrics.getAFMVersion``. The
        Standard 14 AFMs all ship as version 4.1 — useful when
        differentiating between a bundled Adobe AFM and a user-supplied
        one parsed at runtime.
        """
        return float(self._fm.get_afm_version())

    def get_kern_pairs(self) -> list[KernPair]:
        """``StartKernPairs`` entries (writing-direction-agnostic)."""
        return self._fm.get_kern_pairs()

    def get_ligatures(self, glyph_name: str) -> list[Ligature]:
        """Ligatures declared on the ``L`` entries of ``glyph_name``.

        Returns an empty list when the glyph has no ligatures or doesn't
        exist. ``Helvetica.afm`` declares ``f i fi`` and ``f l fl`` on
        the ``f`` glyph; that's where this is most useful.
        """
        for cm in self._fm.get_char_metrics():
            if cm.get_name() == glyph_name:
                return cm.get_ligatures()
        return []


# ---------------------------------------------------------------------------
# Cached loader
# ---------------------------------------------------------------------------

_CACHE: dict[str, AfmMetrics] = {}


def _afm_path_for(name: str) -> str:
    """Return the on-disk path of the bundled ``<name>.afm`` resource."""
    pkg = resources.files("pypdfbox.pdmodel.font.afm")
    res = pkg.joinpath(f"{name}.afm")
    return str(res)


def load_standard14(name: str) -> AfmMetrics:
    """Return the parsed :class:`AfmMetrics` for one of the Standard 14 fonts.

    Calling this twice for the same canonical name returns the same
    instance (PDFBox parity — upstream caches its parsed
    ``FontMetrics`` on first access via ``Standard14Fonts.getAFM``).

    Raises ``ValueError`` when ``name`` is not one of the 14 canonical
    PostScript names; alias resolution (e.g. ``"Arial"`` ->
    ``"Helvetica"``) happens upstream in :class:`Standard14Fonts`.
    """
    if name not in _CACHE:
        if name not in _STANDARD14:
            raise ValueError(f"{name!r} is not one of the 14 Standard fonts")
        with open(_afm_path_for(name), "rb") as fp:
            font_metrics = AFMParser(fp).parse()
        _CACHE[name] = AfmMetrics(name, font_metrics)
    return _CACHE[name]


def standard14_names() -> tuple[str, ...]:
    """The 14 canonical PostScript names, in PDF 32000-1 §9.6.2.2 order."""
    return _STANDARD14


__all__ = ["AfmMetrics", "load_standard14", "standard14_names"]
