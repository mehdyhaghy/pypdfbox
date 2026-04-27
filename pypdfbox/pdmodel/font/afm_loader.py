from __future__ import annotations

from importlib import resources
from typing import Any

from pypdfbox.fontbox.afm import AFMParser, CharMetric, FontMetrics, KernPair, Ligature

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
